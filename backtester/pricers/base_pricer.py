from abc import ABC, abstractmethod


class BasePricer(ABC):
    @abstractmethod
    def price(self, instrument, date: str) -> float | None:
        ...

    @abstractmethod
    def valuation_data(
        self, instrument, date: str, measures: list[str]
    ) -> dict[str, float] | None:
        ...

    @abstractmethod
    def resolve_instrument(self, leg_dict: dict, date: str) -> dict | None:
        ...

    @abstractmethod
    def pricing_inputs(self, instrument, date: str) -> dict[str, float] | None:
        ...
