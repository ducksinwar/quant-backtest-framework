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
    }

    def _build_contract(self, resolved: dict) -> Contract:
        params = {
            k: v for k, v in resolved.items() if k not in self._INFRA_KEYS
        }
        return Contract(
            ticker=resolved.get("ticker", ""),
            asset_class=resolved.get("asset_class", "equity"),
            multiplier=resolved.get("multiplier", 1.0),
            currency=resolved.get("currency", "USD"),
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
