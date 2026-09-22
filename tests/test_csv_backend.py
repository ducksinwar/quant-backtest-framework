import os

import pandas as pd
import pytest
from backtester.data.csv_backend import CsvBackend


@pytest.fixture
def backend():
    return CsvBackend(base_dir="market_data")


@pytest.fixture
def test_backend():
    return CsvBackend(base_dir="tests/test_data")


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

    def test_known_spy_price(self, test_backend):
        val = test_backend.get_value("eod_prices", "1993-01-29", "SPY")
        assert val == pytest.approx(24.113256454467773)


class TestCsvBackendHolidays:
    """``get_holiday_dates``: the ``holidays/{CODE}.csv`` half of the contract.

    Fixtures live in ``tests/test_data/holidays/`` (mirroring ``market_data``):
    US.csv holds 2024-01-04 and 2024-02-02; UK.csv holds 2024-01-05 and
    2024-01-06 (the latter a Saturday); EXTRA_COLS.csv adds ``name``/``note``
    columns.
    """

    def test_returns_normalized_holiday_set(self, test_backend):
        holidays = test_backend.get_holiday_dates("US")
        assert isinstance(holidays, frozenset)
        assert holidays == frozenset({"2024-01-04", "2024-02-02"})

    def test_weekend_row_is_returned_verbatim(self, test_backend):
        # The backend does not editorialize: the provider's business-day base
        # is what makes a Saturday holiday inert.
        assert "2024-01-06" in test_backend.get_holiday_dates("UK")

    def test_missing_code_raises_file_not_found(self, test_backend):
        with pytest.raises(FileNotFoundError) as excinfo:
            test_backend.get_holiday_dates("NOPE")
        message = str(excinfo.value)
        assert "NOPE" in message
        assert "NOPE.csv" in message
        assert "holidays" in message

    def test_missing_code_raises_every_time(self, test_backend):
        # Failures are not cached as a "no holidays" result.
        for _ in range(2):
            with pytest.raises(FileNotFoundError):
                test_backend.get_holiday_dates("NOPE")

    def test_empty_string_code_raises(self, test_backend):
        with pytest.raises(FileNotFoundError):
            test_backend.get_holiday_dates("")

    def test_returns_cached_identical_object(self, test_backend):
        assert test_backend.get_holiday_dates("US") is test_backend.get_holiday_dates("US")

    def test_holiday_file_is_read_once(self, test_backend, monkeypatch):
        calls = []
        real_read_csv = pd.read_csv

        def _counting_read_csv(*args, **kwargs):
            calls.append(args[0])
            return real_read_csv(*args, **kwargs)

        monkeypatch.setattr(pd, "read_csv", _counting_read_csv)
        test_backend.get_holiday_dates("US")
        test_backend.get_holiday_dates("US")
        test_backend.get_holiday_dates("UK")
        assert len(calls) == 2

    def test_extra_columns_are_warned_once_per_instance(self, test_backend):
        with pytest.warns(UserWarning, match="not consumed in Phase 2"):
            holidays = test_backend.get_holiday_dates("EXTRA_COLS")
        assert holidays == frozenset({"2024-01-04", "2024-01-06"})
        # Cached: a second call neither re-reads nor re-warns.
        assert test_backend.get_holiday_dates("EXTRA_COLS") is holidays

    def test_cache_is_not_shared_between_instances(self):
        first = CsvBackend(base_dir="tests/test_data")
        second = CsvBackend(base_dir="tests/test_data")
        assert first.get_holiday_dates("US") == second.get_holiday_dates("US")
        assert first.get_holiday_dates("US") is not second.get_holiday_dates("US")

    def test_price_and_holiday_caches_are_separate_namespaces(self, tmp_path):
        """A ticker and a calendar code may share a name (``DE``: Deere vs Germany).

        Regression test for a shared-cache collision: the two datasets must
        return independent, correct results for the same key.
        """
        (tmp_path / "US_eod.csv").write_text("date,close\n2024-01-02,100.0\n")
        holidays_dir = tmp_path / "holidays"
        holidays_dir.mkdir()
        (holidays_dir / "US.csv").write_text("date\n2024-07-04\n")
        backend = CsvBackend(base_dir=str(tmp_path))

        assert backend.get_value("eod_prices", "2024-01-02", "US") == 100.0
        assert backend.get_holiday_dates("US") == frozenset({"2024-07-04"})

        # Order-independence: neither lookup evicts or corrupts the other.
        assert backend.get_value("eod_prices", "2024-01-02", "US") == 100.0
        assert backend.get_holiday_dates("US") == frozenset({"2024-07-04"})

    def test_null_date_cell_raises_value_error(self, tmp_path):
        """An empty date cell must never become an inert ``nan`` in the set."""
        holidays_dir = tmp_path / "holidays"
        holidays_dir.mkdir()
        # "NA" is in pandas' default na_values, so this row yields a null cell;
        # a blank line would be skipped by read_csv and never reach the check.
        (holidays_dir / "NULL.csv").write_text("date\n2024-01-04\nNA\n")
        backend = CsvBackend(base_dir=str(tmp_path))

        with pytest.raises(ValueError) as excinfo:
            backend.get_holiday_dates("NULL")
        message = str(excinfo.value)
        assert "NULL.csv" in message
        assert "empty date cell" in message
