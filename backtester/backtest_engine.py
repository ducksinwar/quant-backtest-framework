import uuid
import warnings
from dataclasses import dataclass, field
from typing import Tuple

from backtester.instruments.instrument import Instrument
from backtester.snapshots import (
    LegSnapshot,
    PortfolioState,
    StructureSnapshot,
    TradeRecord,
    TradeSnapshot,
)
from backtester.structures.strategy_structure import StrategyStructure
from backtester.trades.trade import Trade


_INFRA_KEYS = {
    "ticker",
    "size",
    "multiplier",
    "currency",
    "asset_class",
    "tags",
    "structure_id",
    "leg_id",
    "cost_leg",
}


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
                for leg in structure.legs:
                    asset_class = leg.asset_class
                    if asset_class not in self._config.asset_class_configs:
                        raise ValueError(
                            f"Unknown asset class: {asset_class}"
                        )
                    cfg = self._config.asset_class_configs[asset_class]
                    pricer = cfg.pricer

                    price_today = pricer.price(leg, date)
                    if price_today is None:
                        leg.daily_total_pnl.append(float("nan"))
                        if cfg.record_pricing_inputs:
                            self._record_pricing_inputs_nan(leg, pricer, date, cfg)
                        continue

                    daily_pnl = (
                        (price_today - leg.current_price)
                        * leg.multiplier
                        * leg.current_size
                    )
                    leg.daily_total_pnl.append(daily_pnl)

                    leg.current_price = price_today

                    if cfg.record_pricing_inputs:
                        pi = pricer.pricing_inputs(leg, date)
                        if pi is not None:
                            keys = getattr(leg, "_pricing_input_keys", None)
                            if keys is None:
                                keys = set()
                                leg._pricing_input_keys = keys
                            keys.update(pi.keys())
                            for key, val in pi.items():
                                series = leg.pricing_inputs.setdefault(key, [])
                                series.append(val)

    def _record_pricing_inputs_nan(self, leg, pricer, date, cfg):
        keys = getattr(leg, "_pricing_input_keys", None)
        if not keys:
            return
        for key in keys:
            series = leg.pricing_inputs.setdefault(key, [])
            series.append(float("nan"))

    def _compute_risk_for_date(self, date: str):
        for trade in self.active_trades:
            for structure in trade.active_structures:
                for leg in structure.legs:
                    asset_class = leg.asset_class
                    cfg = self._config.asset_class_configs.get(asset_class)
                    if cfg is None:
                        continue
                    pricer = cfg.pricer
                    risk_measures = cfg.risk_measures

                    if risk_measures:
                        vd = pricer.valuation_data(leg, date, risk_measures)
                        if vd is not None:
                            for key, val in vd.items():
                                attr = f"{key}_ts"
                                series = getattr(leg, attr, None)
                                if series is None:
                                    series = []
                                    setattr(leg, attr, series)
                                series.append(val)

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
                    resolved = pricer.resolve_instrument(leg_dict, date)
                    if resolved is None:
                        return False
                    ticker = resolved.get("ticker", "")
                    params = {
                        k: v
                        for k, v in resolved.items()
                        if k not in _INFRA_KEYS
                    }
                    temp = Instrument(
                        ticker=ticker,
                        asset_class=resolved.get("asset_class", asset_class),
                        multiplier=resolved.get("multiplier", 1.0),
                        currency=resolved.get("currency", "USD"),
                        params=params,
                    )
                    if pricer.price(temp, date) is None:
                        return False
            return True

        if action == "UNWIND":
            trade_id = order.get("trade_id")
            if trade_id is None:
                for trade in self.active_trades:
                    for structure in trade.active_structures:
                        for leg in structure.legs:
                            asset_class = leg.asset_class
                            if asset_class not in self._config.asset_class_configs:
                                raise ValueError(
                                    f"Unknown asset class: {asset_class}"
                                )
                            cfg = self._config.asset_class_configs[asset_class]
                            if cfg.pricer.price(leg, date) is None:
                                return False
                return True
            trade = self._find_active_trade(trade_id)
            if trade is None:
                return True
            for structure in trade.active_structures:
                for leg in structure.legs:
                    asset_class = leg.asset_class
                    cfg = self._config.asset_class_configs.get(asset_class)
                    if cfg is None:
                        return False
                    pricer = cfg.pricer
                    if pricer.price(leg, date) is None:
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
                for leg in structure.legs:
                    leg_snap = LegSnapshot(
                        ticker=leg.ticker,
                        instrument_type=leg.asset_class,
                        size=leg.current_size,
                        entry_price=leg.entry_price,
                        current_price=leg.current_price,
                        leg_id=leg.leg_id,
                        daily_total_pnl=tuple(leg.daily_total_pnl),
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

    # ─── cost‑exposure helper ──────────────────────────────────────

    def _compute_cost_exposures(
        self, structure: StrategyStructure, date: str
    ) -> dict[str, dict]:
        result: dict[str, dict] = {}
        if not structure.cost_leg_ids or not structure.legs:
            return result

        asset_class = structure.legs[0].asset_class
        cfg = self._config.asset_class_configs.get(asset_class)
        if cfg is None:
            return result
        pricer = cfg.pricer

        leg_by_id = {leg.leg_id: leg for leg in structure.legs}

        for leg_id in structure.cost_leg_ids:
            leg = leg_by_id.get(leg_id)
            if leg is None:
                continue
            exposure = pricer.compute_cost_exposure(leg, date)
            if exposure is None:
                warnings.warn(
                    f"compute_cost_exposure returned None for leg {leg_id}"
                    f" on {date}; treating as cost‑free for this event."
                )
                continue
            result[leg_id] = exposure

        return result

    # ─── order dispatch ────────────────────────────────────────────

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

    # ─── structure / leg construction ──────────────────────────────

    def _build_structure_from_info(
        self, info: dict, date: str
    ) -> StrategyStructure | None:
        leg_dicts = info.get("legs", [])
        structure_id = info.get("structure_id") or str(uuid.uuid4())

        legs = []
        resolved_dicts = []
        for leg_dict in leg_dicts:
            instrument, resolved = self._resolve_and_price_leg(leg_dict, date)
            if instrument is None:
                return None
            legs.append(instrument)
            resolved_dicts.append(resolved)

        if not legs:
            return None

        cost_leg_ids = self._collect_cost_leg_ids(resolved_dicts, legs)

        return StrategyStructure(
            structure_id=structure_id,
            legs=legs,
            tags=info.get("tags"),
            cost_leg_ids=cost_leg_ids,
        )

    @staticmethod
    def _collect_cost_leg_ids(
        resolved_dicts: list[dict], legs: list[Instrument],
    ) -> list[str]:
        ids = []
        for resolved, leg in zip(resolved_dicts, legs):
            if resolved.get("cost_leg"):
                ids.append(leg.leg_id)
        if not ids and len(legs) == 1:
            ids.append(legs[0].leg_id)
        return ids

    def _resolve_and_price_leg(
        self, leg_dict: dict, date: str
    ) -> tuple[Instrument | None, dict | None]:
        ticker = leg_dict.get("ticker")
        asset_class = leg_dict.get("asset_class", "equity")
        if asset_class not in self._config.asset_class_configs:
            raise ValueError(f"Unknown asset class: {asset_class}")

        cfg = self._config.asset_class_configs[asset_class]
        pricer = cfg.pricer

        resolved = pricer.resolve_instrument(leg_dict, date)
        if resolved is None:
            return None, None

        leg_id = str(uuid.uuid4())
        params = {k: v for k, v in resolved.items() if k not in _INFRA_KEYS}

        size = resolved.get("size", 0)

        instrument = Instrument(
            ticker=resolved.get("ticker", ticker),
            asset_class=resolved.get("asset_class", asset_class),
            multiplier=resolved.get("multiplier", 1.0),
            currency=resolved.get("currency", "USD"),
            tags=resolved.get("tags"),
            leg_id=leg_id,
            params=params,
        )
        instrument.current_size = size

        entry_price = pricer.price(instrument, date)
        if entry_price is None:
            return None, None

        instrument.entry_price = entry_price
        instrument.current_price = entry_price

        return instrument, resolved

    # ─── lookups ───────────────────────────────────────────────────

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
