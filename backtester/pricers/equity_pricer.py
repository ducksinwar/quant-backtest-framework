from backtester.pricers.base_pricer import BasePricer


class EquityPricer(BasePricer):
    def __init__(self, provider):
        self.provider = provider

    def price(self, contract, date: str) -> float | None:
        return self.provider.get_price(contract.ticker, date)

    def valuation_data(
        self, contract, date: str, measures: list[str]
    ) -> dict[str, float] | None:
        return {}

    def resolve_instrument(self, leg_dict: dict, date: str):
        return self._build_contract(leg_dict)

    def pricing_inputs(self, contract, date: str) -> dict[str, float] | None:
        return {}

    def compute_cost_exposure(
        self, contract, date: str
    ) -> dict[str, float] | None:
        price = self.provider.get_price(contract.ticker, date)
        if price is None:
            return None
        return {"notional_per_unit": price}
