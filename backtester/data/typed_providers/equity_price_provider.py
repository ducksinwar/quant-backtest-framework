class EquityPriceProvider:
    def __init__(self, data_feed):
        self._data_feed = data_feed

    def get_price(self, ticker: str, date: str) -> float | None:
        return self._data_feed.get_value("eod_prices", date, ticker)
