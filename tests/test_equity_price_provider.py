import pytest
from backtester.data.csv_backend import CsvBackend
from backtester.data.data_feed import DataFeed
from backtester.data.typed_providers.equity_price_provider import EquityPriceProvider


@pytest.fixture
def provider():
    backend = CsvBackend(base_dir="market_data")
    feed = DataFeed(backend)
    return EquityPriceProvider(feed)


class TestEquityPriceProvider:
    def test_get_price_returns_float(self, provider):
        price = provider.get_price("SPY", "2024-01-02")
        assert isinstance(price, float)
        assert price > 0

    def test_get_price_missing_date_returns_none(self, provider):
        price = provider.get_price("SPY", "1980-01-01")
        assert price is None

    def test_get_price_missing_ticker_returns_none(self, provider):
        price = provider.get_price("NONEXISTENT", "2024-01-02")
        assert price is None

    def test_get_price_known_value(self, provider):
        price = provider.get_price("SPY", "1993-01-29")
        assert price == pytest.approx(24.175395965576172)

    def test_get_price_hk_ticker(self, provider):
        price = provider.get_price("0005.HK", "2024-01-02")
        assert isinstance(price, float)
        assert price > 0
