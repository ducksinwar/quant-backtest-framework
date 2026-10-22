import datetime
import uuid
from dataclasses import dataclass, field
from typing import Tuple

from backtester.actions import (
    ActionType,
    AggregationContext,
    StructureSpec,
    TradeSpec,
)
from backtester.calendar_provider import CalendarProvider
from backtester.data_view import DataView
from backtester.execution import (
    ExecutionContext,
    ExecutionOutcome,
    SimulatedExecution,
    leg_dict_from_order_leg,
    write_cost_exposures,
)
from backtester.execution_log import ExecutionLog
from backtester.instruments import LegState
from backtester.action_group_log import ActionGroupLog
from backtester.order_synthesis import OrderSynthesis
from backtester.orders import OrderOutcome
from backtester.position_books import PositionBooks
from backtester.snapshots import (
    LegSnapshot,
    PortfolioState,
    StructureSnapshot,
    TradeRecord,
    TradeSnapshot,
)
from backtester.strategy_structure import StrategyStructure
from backtester.trade import Trade


@dataclass
class AssetClassConfig:
    pricer: object
    risk_measures: list[str] = field(default_factory=list)
    pnl_calculator: object | None = None
    record_pricing_inputs: bool = False


@dataclass
class BacktestConfig:
    signal: object
    start_date: str
    end_date: str
    asset_class_configs: dict[str, AssetClassConfig]
    #: Required: no default, so a missing provider fails loudly at construction
    #: instead of silently falling back to a no-holiday calendar.
    calendar_provider: CalendarProvider
    #: The union of markets to simulate.  Passed straight to
    #: ``CalendarProvider.trading_days``.  ``None`` means business days only.
    simulation_calendar_codes: list[str] | None = None
    #: Market-data feed the daily ``DataView`` is built from.  ``None`` leaves
    #: the view with no data to hand out, which fails loudly instead of
    #: exposing the loop day's own close.
    data_feed: object | None = None
    #: Ticker -> holiday calendar code, used by ``DataView`` for per-instrument
    #: ``as_of`` / last-valid-day resolution only.  An unmapped ticker gets no
    #: calendar scoping (data presence only), so the default ``None`` changes
    #: nothing for existing configs.
    ticker_to_calendar_code: dict[str, str] | None = None
    #: ActionGroup -> order synthesis.  ``None`` uses an ``OrderSynthesis``
    #: with no plugins, i.e. a pure pass-through; a configured instance
    #: supplies the synthesis rule chain.
    order_synthesis: object | None = None
    #: Execution backend: the backtest/live parity boundary.  ``None`` uses the
    #: default :class:`~backtester.execution.SimulatedExecution`.  Unlike the
    #: required ``calendar_provider``, a ``None`` default is honest here: a
    #: backtest cannot meaningfully run without simulated execution, so the
    #: default is the only sensible backend rather than a silent fallback.
    execution_backend: object | None = None


@dataclass(frozen=True)
class BacktestResult:
    trade_history: Tuple[Trade, ...]
    trading_days: Tuple[str, ...]
    active_trades: Tuple[Trade, ...]
    last_processed_date: str


class Backtester:
    def __init__(self, config: BacktestConfig):
        self._config = config
        self.active_trades: list[Trade] = []
        self.trade_history: list[Trade] = []
        self.trading_days: list[str] = []
        #: Append-only action-group log for the most recent run (see
        #: ``backtester.action_group_log``); reset at the start of every run.
        self.action_group_log = ActionGroupLog()
        #: Write-once execution log for the most recent run (see
        #: ``backtester.execution_log``); reset at the start of every run.
        self.execution_log = ExecutionLog()

    def run(self) -> BacktestResult:
        self.trading_days = self._config.calendar_provider.trading_days(
            self._config.simulation_calendar_codes,
            self._config.start_date,
            self._config.end_date,
        )

        if not self.trading_days:
            return BacktestResult(
                trade_history=(),
                trading_days=(),
                active_trades=(),
                last_processed_date="",
            )

        portfolio_state = None
        trade_history_snapshot: tuple[TradeRecord, ...] = ()
        self.action_group_log = ActionGroupLog()
        self.execution_log = ExecutionLog()
        synthesis = self._config.order_synthesis or OrderSynthesis()
        execution_backend = (
            self._config.execution_backend or SimulatedExecution()
        )

        for T in self.trading_days:
            # 1. Mark to market T-1 -> T first: the signal below sees the
            #    T-1 position book, never today's prices.
            self._compute_pnl_for_date(T)

            # 2. Signal -> action groups -> log -> synthesis -> orders.
            position_books = PositionBooks(
                portfolio_state, trade_history_snapshot
            )
            ctx = AggregationContext(
                date=T,
                action_group_log=self.action_group_log,
                execution_log=self.execution_log,
                position_books=position_books,
                calendar=self._config.calendar_provider,
                config=self._config,
            )
            data_view = self._build_data_view(T)
            strategy_id = self._config.signal.strategy_id

            action_groups = self._config.signal.generate_action_groups(
                data_view,
                self.action_group_log.for_strategy(strategy_id),
                position_books.for_strategy(strategy_id),
            )

            # The log owns action_group_id and emission_date; the loop stamps
            # the context's date and asserts it is this loop day.
            emission_date = ctx.date
            assert emission_date == T, "emission_date must be the loop day"
            records = self.action_group_log.append_many(
                action_groups, emission_date
            )

            order_groups = synthesis.synthesize(
                [record.action_group for record in records],
                ctx,
                [record.action_ids for record in records],
            )
            for record, order_group in zip(records, order_groups):
                self._dispatch_synthesized_order(
                    record, order_group, T, execution_backend
                )

            # 3. Risk for T, then the snapshots tomorrow's signal will read.
            self._compute_risk_for_date(T)

            portfolio_state = self._build_portfolio_state(T)
            trade_history_snapshot = self._build_trade_history_snapshot()

        return BacktestResult(
            trade_history=tuple(self.trade_history),
            trading_days=tuple(self.trading_days),
            active_trades=tuple(self.active_trades),
            last_processed_date=self.trading_days[-1],
        )

    def _compute_pnl_for_date(self, date: str):
        for trade in self.active_trades:
            for structure in trade.active_structures:
                for leg_state in structure.legs:
                    asset_class = leg_state.contract.asset_class
                    if asset_class not in self._config.asset_class_configs:
                        raise ValueError(
                            f"Unknown asset class: {asset_class}"
                        )
                    cfg = self._config.asset_class_configs[asset_class]
                    pricer = cfg.pricer

                    price_today = pricer.price(leg_state.contract, date)
                    if price_today is None:
                        leg_state.daily_total_pnl.append(float("nan"))
                    else:
                        daily_pnl = (
                            (price_today - leg_state.current_price)
                            * leg_state.contract.multiplier
                            * leg_state.current_size
                        )
                        leg_state.daily_total_pnl.append(daily_pnl)
                        leg_state.current_price = price_today

                    if cfg.record_pricing_inputs:
                        today = (
                            pricer.pricing_inputs(leg_state.contract, date) or {}
                        )
                        for key, val in today.items():
                            if key not in leg_state.pricing_inputs:
                                prior_len = max(0, len(leg_state.daily_total_pnl) - 1)
                                leg_state.pricing_inputs[key] = (
                                    [float("nan")] * prior_len
                                )
                            leg_state.pricing_inputs[key].append(val)
                        for key in leg_state.pricing_inputs:
                            if key not in today:
                                leg_state.pricing_inputs[key].append(
                                    float("nan")
                                )

    def _compute_risk_for_date(self, date: str):
        for trade in self.active_trades:
            for structure in trade.active_structures:
                for leg_state in structure.legs:
                    asset_class = leg_state.contract.asset_class
                    cfg = self._config.asset_class_configs.get(asset_class)
                    if cfg is None:
                        continue
                    pricer = cfg.pricer
                    risk_measures = cfg.risk_measures

                    if risk_measures:
                        vd = pricer.valuation_data(leg_state.contract, date, risk_measures) or {}
                        for key, val in vd.items():
                            if key not in leg_state.valuation_data:
                                prior_len = max(0, len(leg_state.daily_total_pnl) - 1)
                                leg_state.valuation_data[key] = (
                                    [float("nan")] * prior_len
                                )
                            leg_state.valuation_data[key].append(val)
                        for key in leg_state.valuation_data:
                            if key not in vd:
                                leg_state.valuation_data[key].append(float("nan"))

    # --- action-group pipeline -------------------------------------------

    def _build_data_view(self, date: str) -> DataView:
        """The T-1-clamped view the signal may read on loop day *date*."""
        cutoff = (
            datetime.date.fromisoformat(date) - datetime.timedelta(days=1)
        ).isoformat()
        return DataView(
            self._config.data_feed,
            date=date,
            cutoff=cutoff,
            calendar=self._config.calendar_provider,
            ticker_to_calendar_code=self._config.ticker_to_calendar_code,
        )

    def _dispatch_synthesized_order(
        self, record, order_group, date: str, execution_backend
    ) -> None:
        """Execute the group atomically, then commit.

        There is no rejection path: a signal emits only what it is willing to
        dispatch, and the engine has no check stage.  Ordering guarantee,
        visible in one function: **execute -> finalize -> commit**.

        **Flow A.**  The backend decides the outcome; this method writes the
        action group's facts and one execution-log record per order, and
        commits to the book **only** when every order in the group is
        ``FILLED``.  A built-but-blocked structure is therefore never added to
        a trade and never appears in ``trade_history`` -- nothing is added then
        removed.  A block is an *order outcome* (``OrderOutcome.BLOCKED``) and
        an order-layer fact in the execution log.
        """
        # Single-action subset: the multi-action gate upstream ensures one
        # action per group here.
        if len(record.action_group.actions) != 1:
            raise ValueError(
                "dispatch requires exactly one action per group; "
                "multi-action groups are gated"
            )
        action = record.action_group.actions[0]

        ctx = ExecutionContext(
            active_trades=tuple(self.active_trades),
            asset_class_configs=self._config.asset_class_configs,
            date=date,
            action_group_id=record.action_group.action_group_id,
            strategy_id=record.action_group.strategy_id,
        )
        reports = execution_backend.execute_group(order_group, ctx)
        execution_records = tuple(
            self.execution_log.append(report) for report in reports
        )
        order_ids = tuple(order.order_id for order in order_group.orders)
        order_outcomes = tuple(
            OrderOutcome.FILLED
            if report.outcome is ExecutionOutcome.FILLED
            else OrderOutcome.BLOCKED
            for report in reports
        )
        record.finalize(order_ids, order_outcomes)

        if all(
            outcome is OrderOutcome.FILLED for outcome in order_outcomes
        ):
            self._commit_order_group(
                order_group, record, date, execution_records
            )

    def _build_portfolio_state(self, date: str) -> PortfolioState | None:
        """Position snapshot at *date*; always built (nothing gates it now)."""
        trade_snapshots = []
        for trade in self.active_trades:
            structure_snapshots = []
            for structure in trade.active_structures:
                leg_snapshots = []
                for leg_state in structure.legs:
                    leg_snap = LegSnapshot(
                        ticker=leg_state.contract.ticker,
                        asset_class=leg_state.contract.asset_class,
                        size=leg_state.current_size,
                        entry_price=leg_state.entry_price,
                        current_price=leg_state.current_price,
                        leg_id=leg_state.leg_id,
                        daily_total_pnl=tuple(leg_state.daily_total_pnl),
                        component_pnls={},
                        risk_measures={},
                    )
                    leg_snapshots.append(leg_snap)
                structure_snapshots.append(
                    StructureSnapshot(
                        legs=tuple(leg_snapshots),
                        structure_id=structure.structure_id,
                    )
                )
            trade_snapshots.append(
                TradeSnapshot(
                    trade_id=trade.trade_id,
                    structures=tuple(structure_snapshots),
                )
            )

        return PortfolioState(date=date, trades=tuple(trade_snapshots))

    def _build_trade_history_snapshot(self) -> tuple[TradeRecord, ...]:
        """Trade records as of *date*; always built, never ``None``."""
        records = []
        for trade in self.trade_history:
            records.append(
                TradeRecord(
                    trade_id=trade.trade_id,
                    entry_date=trade.entry_date or "",
                    exit_date=trade.exit_date,
                    tags=tuple(trade.tags) if trade.tags else (),
                    is_open=trade.exit_date is None,
                )
            )
        return tuple(records)

    # --- order commit (fill application) --------------------------------

    def _commit_order_group(
        self, order_group, record, date: str, execution_records
    ):
        """Apply a **fully filled** group to the book (the commit phase).

        Commit-only: availability was decided by the execution backend and only
        an all-``FILLED`` group reaches here, so there is no pre-check and no
        warning.  Filled orders are grouped by ``action_id`` -- with one action
        per group (the gate) this is the old one-order-per-ActionGroup commit
        exactly.  The opening execution (``order_id`` / ``fill_id``) is recorded
        on a newly created trade.

        A single action's filled orders may create a trade, extend one trade
        with new structures, or target existing structures -- never a mix.
        """
        action_by_id = dict(
            zip(record.action_ids, record.action_group.actions)
        )
        grouped: dict[str, list] = {}
        for order in order_group.orders:
            grouped.setdefault(order.action_id, []).append(order)

        for action_id, items in grouped.items():
            action = action_by_id[action_id]
            opens = any(
                order.structure_id is None and order.trade_id is None
                for order in items
            )
            targets = any(order.structure_id is not None for order in items)
            if opens and targets:
                raise ValueError(
                    "one action's filled orders mix trade creation with a "
                    "structure target"
                )
            if opens:
                self._commit_open(items, action, date, execution_records)
            elif items[0].structure_id is None:
                self._commit_extend(items, action, date)
            else:
                self._commit_structure(items, action, date)

        self.active_trades = [
            trade for trade in self.active_trades if trade.active_structures
        ]

    def _commit_open(self, items, action, date, execution_records):
        structures = []
        for content_index, order in enumerate(items):
            structures.append(
                self._build_structure_from_order(
                    order, date, self._structure_tags(action, content_index)
                )
            )
        linkage = execution_records[0] if execution_records else None
        trade = Trade(
            trade_id=str(uuid.uuid4()),
            tags=self._trade_tags(action),
            order_id=linkage.order_id if linkage is not None else None,
            fill_id=linkage.fill_id if linkage is not None else None,
            execution_marker="external",
        )
        for structure in structures:
            cost_exposures = write_cost_exposures(
                structure, date, self._config.asset_class_configs
            )
            trade.add_structure(structure, date, cost_exposures)
        self.active_trades.append(trade)
        self.trade_history.append(trade)

    def _commit_extend(self, items, action, date):
        trade = self._find_active_trade(items[0].trade_id)
        if trade is None:
            raise ValueError(
                f"cannot extend trade {items[0].trade_id!r}: it is not in the "
                f"live book"
            )
        for content_index, order in enumerate(items):
            structure = self._build_structure_from_order(
                order, date, self._structure_tags(action, content_index)
            )
            cost_exposures = write_cost_exposures(
                structure, date, self._config.asset_class_configs
            )
            trade.add_structure(structure, date, cost_exposures)

    def _commit_structure(self, items, action, date):
        for order in items:
            trade = self._find_active_trade(order.trade_id)
            if trade is None:
                raise ValueError(
                    f"cannot apply order {order.order_id!r}: trade "
                    f"{order.trade_id!r} is not in the live book"
                )
            structure = self._find_structure_in_trade(
                trade, order.structure_id
            )
            if structure is None:
                raise ValueError(
                    f"cannot apply order {order.order_id!r}: structure "
                    f"{order.structure_id!r} is not active"
                )
            cost_exposures = write_cost_exposures(
                structure, date, self._config.asset_class_configs
            )
            if action.type is ActionType.NEW:
                trade.add_to_structure(
                    structure, date, float(action.size), cost_exposures
                )
            elif action.size is None:
                trade.unwind_structure(
                    structure, date, fraction=1.0,
                    cost_exposures=cost_exposures,
                )
            else:
                # The anchor-delta/size ratio equals the old share-of-total
                # fraction for a single-leg structure (the only modifiable
                # shape); multi-leg modification is gated upstream.
                anchor = abs(structure.legs[0].current_size)
                fraction = float(action.size) / anchor if anchor else 0.0
                trade.unwind_structure(
                    structure, date, fraction=fraction,
                    cost_exposures=cost_exposures,
                )

    @staticmethod
    def _trade_tags(action):
        if isinstance(action.spec, TradeSpec) and action.spec.tags:
            return list(action.spec.tags)
        return None

    @staticmethod
    def _structure_tags(action, content_index):
        if isinstance(action.spec, TradeSpec):
            tags = action.spec.structures[content_index].tags
        elif isinstance(action.spec, StructureSpec):
            tags = action.spec.tags
        else:
            tags = ()
        return list(tags) if tags else None

    # --- structure / leg construction -----------------------------------

    def _build_structure_from_order(self, order, date: str, tags):
        leg_states = []
        for leg in order.legs:
            leg_state = self._resolve_and_price_leg(
                leg_dict_from_order_leg(leg), date
            )
            if leg_state is None:
                raise ValueError(
                    f"filled order {order.order_id!r} failed to resolve a leg "
                    f"at commit time"
                )
            leg_states.append(leg_state)

        return StrategyStructure(
            structure_id=str(uuid.uuid4()),
            legs=leg_states,
            tags=tags,
        )

    def _resolve_and_price_leg(
        self, leg_dict: dict, date: str
    ) -> LegState | None:
        asset_class = leg_dict.get("asset_class", "equity")
        if asset_class not in self._config.asset_class_configs:
            raise ValueError(f"Unknown asset class: {asset_class}")

        cfg = self._config.asset_class_configs[asset_class]
        pricer = cfg.pricer

        contract = pricer.resolve_instrument(leg_dict, date)
        if contract is None:
            return None

        leg_id = str(uuid.uuid4())
        size = float(leg_dict.get("size", 0))

        entry_price = pricer.price(contract, date)
        if entry_price is None:
            return None

        leg_state = LegState(
            contract=contract,
            leg_id=leg_id,
            current_size=size,
            entry_price=entry_price,
            current_price=entry_price,
            cost_leg=leg_dict.get("cost_leg", False),
            tags=leg_dict.get("tags"),
        )

        leg_state.daily_total_pnl.append(0.0)

        if cfg.record_pricing_inputs:
            inputs = pricer.pricing_inputs(contract, date) or {}
            for key, value in inputs.items():
                leg_state.pricing_inputs.setdefault(key, []).append(value)

        return leg_state

    # --- lookups --------------------------------------------------------

    def _find_active_trade(self, trade_id: str) -> Trade | None:
        for trade in self.active_trades:
            if trade.trade_id == trade_id:
                return trade
        return None

    def _find_structure_in_trade(
        self, trade: Trade, structure_id: str
    ) -> StrategyStructure | None:
        for structure in trade.active_structures:
            if structure.structure_id == structure_id:
                return structure
        return None
