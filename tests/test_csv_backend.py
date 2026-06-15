import os

import pandas as pd
import pytest
from backtester.data.csv_backend import CsvBackend


@pytest.fixture
def backend():
    return CsvBackend(base_dir="market_data")


class TestCsvBackend:
    def test_get_value_returns_close(self, backend):
        val = backend.get_value("eod_prices", "2024-01-02", "SPY")
        assert isinstance(val, float)
        assert val > 0

    def test_get_value_date_not_found_returns_none(self, backend):
        val = backend.get_value("eod_prices", "1980-01-01", "SPY")
        assert val is None

    def test_get_value_ticker_not_found(self, backend):
        val = backend.get_value("eod_prices", "2024-01-02", "NONEXISTENT")
        assert val is None

    def test_get_value_unknown_dataset_returns_none(self, backend):
        val = backend.get_value("unknown_dataset", "2024-01-02", "SPY")
        assert val is None

    def test_get_value_ticker_none_returns_none(self, backend):
        val = backend.get_value("eod_prices", "2024-01-02", None)
        assert val is None

    def test_get_series_returns_series(self, backend):
        series = backend.get_series("eod_prices", "2024-01-02", "2024-01-10", "SPY")
        assert isinstance(series, pd.Series)
        assert len(series) > 0
        assert series.index[0] == "2024-01-02"

    def test_get_series_unknown_dataset_returns_empty(self, backend):
        series = backend.get_series("unknown", "2024-01-02", "2024-01-10", "SPY")
        assert isinstance(series, pd.Series)
        assert len(series) == 0

    def test_get_series_ticker_none_returns_empty(self, backend):
        series = backend.get_series("eod_prices", "2024-01-02", "2024-01-10", None)
        assert isinstance(series, pd.Series)
        assert len(series) == 0

    def test_csv_caching(self, backend):
        val1 = backend.get_value("eod_prices", "2024-06-15", "SPY")
        val2 = backend.get_value("eod_prices", "2024-06-15", "SPY")
        assert val1 == val2

    def test_known_spy_price(self, backend):
        val = backend.get_value("eod_prices", "1993-01-29", "SPY")
        assert val == pytest.approx(24.175395965576172)
