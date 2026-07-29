from dataclasses import dataclass, field


@dataclass(frozen=True)
class LegSnapshot:
    ticker: str
    asset_class: str
    size: float
    entry_price: float
    current_price: float
    leg_id: str = ""
    daily_total_pnl: tuple[float, ...] = ()
    component_pnls: dict = field(default_factory=dict)
    risk_measures: dict = field(default_factory=dict)


@dataclass(frozen=True)
class StructureSnapshot:
    legs: tuple[LegSnapshot, ...]
    structure_id: str = ""


@dataclass(frozen=True)
class TradeSnapshot:
    trade_id: str
    structures: tuple[StructureSnapshot, ...]


@dataclass(frozen=True)
class PortfolioState:
    date: str
    trades: tuple[TradeSnapshot, ...]


@dataclass(frozen=True)
class TradeRecord:
    trade_id: str
    entry_date: str
    exit_date: str | None
    tags: tuple[str, ...]
    is_open: bool
