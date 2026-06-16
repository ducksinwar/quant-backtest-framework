from dataclasses import dataclass, field


@dataclass
class Instrument:
    ticker: str
    asset_class: str
    multiplier: float = 1.0
    currency: str = "USD"
    tags: list[str] | None = None
    leg_id: str = ""
    params: dict = field(default_factory=dict)

    daily_total_pnl: list[float] = field(default_factory=list)
    current_price: float = 0.0
    current_size: float = 0.0
    entry_price: float = 0.0

    pricing_inputs: dict[str, list[float]] = field(default_factory=dict)

    def __init__(
        self,
        ticker: str,
        asset_class: str,
        multiplier: float = 1.0,
        currency: str = "USD",
        tags: list[str] | None = None,
        leg_id: str = "",
        params: dict | None = None,
    ):
        self.ticker = ticker
        self.asset_class = asset_class
        self.multiplier = multiplier
        self.currency = currency
        self.tags = tags
        self.leg_id = leg_id
        self.params = params if params is not None else {}

        self.daily_total_pnl: list[float] = []
        self.current_price: float = 0.0
        self.current_size: float = 0.0
        self.entry_price: float = 0.0

        self.pricing_inputs: dict[str, list[float]] = {}
