import uuid
import warnings
from dataclasses import dataclass, field
from typing import Tuple

from backtester.instruments import LegState
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
    calendar_ticker: str = "SPY"


@dataclass(frozen=True)
class BacktestResult:
    trade_history: Tuple[Trade, ...]
    trading_days: Tuple[str, ...]
    active_trades: Tuple[Trade, ...]
    last_processed_date: str


class Backtester:
    def __init__(self, config: BacktestConfig, data_feed):
        self._config = config
        self._data_feed = data_feed
        self.active_trades: list[Trade] = []
        self.trade_history: list[Trade] = []
        self.trading_days: list[str] = []

    def run(self) -> BacktestResult:
        self.trading_days = self._data_feed.trading_days(
            self._config.calendar_ticker,
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
        trade_history_snapshot = None

        for T in self.trading_days:
            self._compute_pnl_for_date(T)

            orders = self._config.signal.generate_signals(
                current_date=T,
                portfolio_state=portfolio_state,
                trade_history_snapshot=trade_history_snapshot,
            )

            for order in orders:
                self._execute_order(order, T)

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

    def _check_data_available(self, order: dict, date: str) -> bool:
        action = order.get("Action")
        infos = order.get("info", [])

        if action == "NEW":
            for info in infos:
                leg_dicts = info.get("legs", [])
                for leg_dict in leg_dicts:
                    asset_class = leg_dict.get("asset_class")
                    if asset_class is None:
                        raise ValueError(
                            "Leg dict is missing required 'asset_class' field."
                        )
                    cfg = self._config.asset_class_configs.get(asset_class)
                    if cfg is None:
                        raise ValueError(
                            f"Unknown asset class: {asset_class}"
                        )
                    pricer = cfg.pricer
                    contract = pricer.resolve_instrument(leg_dict, date)
                    if contract is None:
                        return False
                    if pricer.price(contract, date) is None:
                        return False
            return True

        if action == "UNWIND":
            trade_id = order.get("trade_id")
            if trade_id is None:
                for trade in self.active_trades:
                    for structure in trade.active_structures:
                        for leg_state in structure.legs:
                            asset_class = leg_state.contract.asset_class
                            if asset_class not in self._config.asset_class_configs:
                                raise ValueError(
                                    f"Unknown asset class: {asset_class}"
                                )
                            cfg = self._config.asset_class_configs[asset_class]
                            if cfg.pricer.price(leg_state.contract, date) is None:
                                return False
                return True
            trade = self._find_active_trade(trade_id)
            if trade is None:
                return True
            for structure in trade.active_structures:
                for leg_state in structure.legs:
                    asset_class = leg_state.contract.asset_class
                    cfg = self._config.asset_class_configs.get(asset_class)
                    if cfg is None:
                        return False
                    pricer = cfg.pricer
                    if pricer.price(leg_state.contract, date) is None:
                        return False
            return True

        return True

    def _build_portfolio_state(self, date: str) -> PortfolioState | None:
        if not self._config.signal.requires_portfolio_state:
            return None

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

    def _build_trade_history_snapshot(self) -> tuple[TradeRecord, ...] | None:
        if not self._config.signal.requires_trade_history:
            return None

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

    # --- cost-exposure helper ------------------------------------------

    def _compute_cost_exposures(
        self, structure: StrategyStructure, date: str
    ) -> dict[str, dict]:
        result: dict[str, dict] = {}
        if not structure.legs:
            return result

        asset_class = structure.legs[0].contract.asset_class
        cfg = self._config.asset_class_configs.get(asset_class)
        if cfg is None:
            return result
        pricer = cfg.pricer

        for leg_state in structure.legs:
            if not leg_state.cost_leg:
                continue
            exposure = pricer.compute_cost_exposure(leg_state.contract, date)
            if exposure is None:
                warnings.warn(
                    f"compute_cost_exposure returned None for leg {leg_state.leg_id}"
                    f" on {date}; treating as cost-free for this event."
                )
                continue
            result[leg_state.leg_id] = exposure

        # Preserve existing behavior: for single-leg structures where
        # cost_leg was not explicitly marked, treat the sole leg as the
        # cost-bearing leg by default.
        if not result and len(structure.legs) == 1:
            sole = structure.legs[0]
            exposure = pricer.compute_cost_exposure(sole.contract, date)
            if exposure is not None:
                result[sole.leg_id] = exposure

        return result

    # --- order dispatch -------------------------------------------------

    def _execute_order(self, order: dict, date: str):
        if not self._check_data_available(order, date):
            warnings.warn(
                f"Order rejected on {date}: data not available for all instruments."
            )
            return

        action = order.get("Action")

        if action == "NEW":
            self._execute_new(order, date)
        elif action == "UNWIND":
            self._execute_unwind(order, date)
        elif action == "ROLL":
            raise NotImplementedError("ROLL not implemented in Phase 1")

    def _execute_new(self, order: dict, date: str):
        trade_id = order.get("trade_id")
        infos = order.get("info", [])

        if trade_id is None:
            self._execute_new_trade(infos, date, order.get("tags"))
        else:
            self._execute_add_to_existing(trade_id, infos, date)

    def _execute_new_trade(self, infos: list, date: str, tags=None):
        structures = []
        for info in infos:
            structure = self._build_structure_from_info(info, date)
            if structure is None:
                return
            structures.append(structure)

        if not structures:
            return

        trade = Trade(trade_id=str(uuid.uuid4()), tags=tags)
        for structure in structures:
            cost_exposures = self._compute_cost_exposures(structure, date)
            trade.add_structure(structure, date, cost_exposures)

        self.active_trades.append(trade)
        self.trade_history.append(trade)

    def _execute_add_to_existing(self, trade_id: str, infos: list, date: str):
        trade = self._find_active_trade(trade_id)
        if trade is None:
            return

        for info in infos:
            structure_id = info.get("structure_id")
            size_key = info.get("size")

            if structure_id is not None and size_key is not None:
                structure = self._find_structure_in_trade(trade, structure_id)
                if structure is not None:
                    cost_exposures = self._compute_cost_exposures(
                        structure, date,
                    )
                    trade.add_to_structure(
                        structure, date, size_key, cost_exposures,
                    )
            else:
                structure = self._build_structure_from_info(info, date)
                if structure is not None:
                    cost_exposures = self._compute_cost_exposures(
                        structure, date,
                    )
                    trade.add_structure(structure, date, cost_exposures)

    def _execute_unwind(self, order: dict, date: str):
        trade_id = order.get("trade_id")
        infos = order.get("info", [])

        if trade_id is None:
            if not infos:
                for trade in list(self.active_trades):
                    trade.exit_date = date
                    for structure in list(trade.active_structures):
                        cost_exposures = self._compute_cost_exposures(
                            structure, date,
                        )
                        trade.unwind_structure(
                            structure, date, fraction=1.0,
                            cost_exposures=cost_exposures,
                        )
                    self.active_trades = [
                        t for t in self.active_trades if t is not trade
                    ]
            return

        trade = self._find_active_trade(trade_id)
        if trade is None:
            return

        if not infos:
            trade.exit_date = date
            for structure in list(trade.active_structures):
                cost_exposures = self._compute_cost_exposures(
                    structure, date,
                )
                trade.unwind_structure(
                    structure, date, fraction=1.0,
                    cost_exposures=cost_exposures,
                )
            if not trade.active_structures:
                self.active_trades = [
                    t for t in self.active_trades if t is not trade
                ]
        else:
            for info in infos:
                structure_id = info.get("structure_id")
                size_key = info.get("size")

                if structure_id is None:
                    continue

                structure = self._find_structure_in_trade(trade, structure_id)
                if structure is None:
                    continue

                if size_key is not None:
                    total_size = sum(
                        leg.current_size for leg in structure.legs
                    )
                    fraction = (
                        size_key / total_size if total_size > 0 else 0.0
                    )
                    cost_exposures = self._compute_cost_exposures(
                        structure, date,
                    )
                    trade.unwind_structure(
                        structure, date, fraction=fraction,
                        cost_exposures=cost_exposures,
                    )
                else:
                    cost_exposures = self._compute_cost_exposures(
                        structure, date,
                    )
                    trade.unwind_structure(
                        structure, date, fraction=1.0,
                        cost_exposures=cost_exposures,
                    )

            if not trade.active_structures:
                trade.exit_date = date
                self.active_trades = [
                    t for t in self.active_trades if t is not trade
                ]

    # --- structure / leg construction -----------------------------------

    def _build_structure_from_info(
        self, info: dict, date: str
    ) -> StrategyStructure | None:
        leg_dicts = info.get("legs", [])
        structure_id = info.get("structure_id") or str(uuid.uuid4())

        leg_states = []
        for leg_dict in leg_dicts:
            leg_state = self._resolve_and_price_leg(leg_dict, date)
            if leg_state is None:
                return None
            leg_states.append(leg_state)

        if not leg_states:
            return None

        return StrategyStructure(
            structure_id=structure_id,
            legs=leg_states,
            tags=info.get("tags"),
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
