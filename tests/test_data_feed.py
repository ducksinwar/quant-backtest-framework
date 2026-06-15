import pandas as pd
import pytest
from backtester.data.csv_backend import CsvBackend
from backtester.data.data_feed import DataFeed


@pytest.fixture
def data_feed():
    backend = CsvBackend(base_dir="market_data")
    return DataFeed(backend)


class TestDataFeed:
    def test_get_value_delegates_to_backend(self, data_feed):
        val = data_feed.get_value("eod_prices", "2024-01-02", "SPY")
        assert isinstance(val, float)
        assert val > 0

    def test_get_value_returns_none_for_missing(self, data_feed):
        val = data_feed.get_value("eod_prices", "1980-01-01", "SPY")
        assert val is None

    def test_get_series_delegates_to_backend(self, data_feed):
        series = data_feed.get_series("eod_prices", "2024-01-02", "2024-01-10", "SPY")
        assert isinstance(series, pd.Series)
        assert len(series) > 0
        assert series.index[0] == "2024-01-02"

    def test_get_series_unknown_dataset(self, data_feed):
        series = data_feed.get_series("unknown", "2024-01-02", "2024-01-10", "SPY")
        assert isinstance(series, pd.Series)
        assert len(series) == 0

    def test_get_value_unknown_dataset(self, data_feed):
        val = data_feed.get_value("unknown_dataset", "2024-01-02", "SPY")
        assert val is None

    def test_get_value_ticker_none(self, data_feed):
        val = data_feed.get_value("eod_prices", "2024-01-02", None)
        assert val is None
