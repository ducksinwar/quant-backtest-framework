from abc import ABC, abstractmethod
from backtester.instruments import Contract


class BasePricer(ABC):
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
        "trading_calendar_code",
        "settlement_calendar_codes",
    }

    def __init__(self, ticker_to_calendar_code=None):
        #: Ticker -> holiday calendar code, injected by the caller (Task 5b-2).
        #: The pricer only stamps it onto the ``Contract``; it performs no
        #: calendar math and holds no feed for it.  A defensively copied dict,
        #: so later mutation by the caller cannot retroactively change a
        #: stamped Contract.
        self._ticker_to_calendar_code = dict(ticker_to_calendar_code or {})

    def _build_contract(self, resolved: dict) -> Contract:
        params = {
            k: v for k, v in resolved.items() if k not in self._INFRA_KEYS
        }
        ticker = resolved.get("ticker", "")
        return Contract(
            ticker=ticker,
            asset_class=resolved.get("asset_class", "equity"),
            multiplier=resolved.get("multiplier", 1.0),
            currency=resolved.get("currency", "USD"),
            trading_calendar_code=self._ticker_to_calendar_code.get(ticker),
            settlement_calendar_codes=(),
            params=params,
        )

    @abstractmethod
    def price(self, contract: Contract, date: str) -> float | None:
        ...

    @abstractmethod
    def valuation_data(
        self, contract: Contract, date: str, measures: list[str]
    ) -> dict[str, float] | None:
        ...

    @abstractmethod
    def resolve_instrument(
        self, leg_dict: dict, date: str
    ) -> Contract | None:
        ...

    @abstractmethod
    def pricing_inputs(
        self, contract: Contract, date: str
    ) -> dict[str, float] | None:
        ...

    @abstractmethod
    def compute_cost_exposure(
        self, contract: Contract, date: str
    ) -> dict[str, float] | None:
        ...
