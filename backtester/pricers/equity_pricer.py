from backtester.pricers.base_pricer import BasePricer


class EquityPricer(BasePricer):
    def __init__(self, provider):
        self.provider = provider

    def price(self, instrument, date: str) -> float | None:
        return self.provider.get_price(instrument.ticker, date)

    def valuation_data(
        self, instrument, date: str, measures: list[str]
    ) -> dict[str, float] | None:
        return {}

    def resolve_instrument(self, leg_dict: dict, date: str) -> dict | None:
        return leg_dict

    def pricing_inputs(self, instrument, date: str) -> dict[str, float] | None:
        return {}
