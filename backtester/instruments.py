from dataclasses import dataclass, field


@dataclass(frozen=True)
class Contract:
    """Immutable contract definition for a financial instrument.

    The ``params`` dict is shallow-frozen -- callers must not mutate it
    after construction.  Use ``Contract`` for instrument identity only;
    mutable position-level state belongs on :class:`LegState`.
    """
    ticker: str
    asset_class: str
    multiplier: float = 1.0
    currency: str = "USD"
    params: dict = field(default_factory=dict)


@dataclass
class LegState:
    """Mutable position state for a single leg of a strategy structure.

    Holds a reference to the immutable :class:`Contract` plus mutable
    fields that change daily (price, size, P&L, valuation data, etc.).

    ``tags`` is an optional list of operational string labels assigned by
    the strategy (e.g. strategy name, asset sub‑class, alpha source), not
    part of instrument identity.  Tags are used by the summary/reporting
    layer for filtering and grouping.
    """
    contract: Contract
    leg_id: str = ""
    current_price: float = 0.0
    current_size: float = 0.0
    entry_price: float = 0.0
    daily_total_pnl: list[float] = field(default_factory=list)
    valuation_data: dict[str, list[float]] = field(default_factory=dict)
    pricing_inputs: dict[str, list[float]] = field(default_factory=dict)
    cost_leg: bool = False
    tags: list[str] | None = None

    def __repr__(self) -> str:
        return (
            f"LegState(ticker={self.contract.ticker!r}, "
            f"leg_id={self.leg_id!r}, size={self.current_size})"
        )
