"""Tests for the shared CalendarProvider (design_notes.md §3.5).

Two suites with a deliberate split:

* **Pure calendar math** (union, ``is_valid_day``, ``next_valid_day``,
  ``"all"``) runs against a hand-written **stub backend** holding hard-coded
  holiday sets.  The math is decoupled from CSV parsing, so a pandas or
  fixture-format change cannot make a calendar-math test fail.
* **Integration** (file discovery, parsing, caching, warnings, missing files)
  runs against a **real** ``CsvBackend`` over the committed fixtures in
  ``tests/test_data/holidays/``.

The provider is constructed with a ``DataFeed`` in both suites -- the real
collaborator.  Only the backend is swapped, which is exactly the seam the
refactor introduced.
"""

import datetime
import inspect
import warnings
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest

from backtester.calendar_provider import _MAX_LOOKAHEAD_DAYS, CalendarProvider
from backtester.data.csv_backend import CsvBackend
from backtester.data.data_feed import DataFeed

TEST_DATA_DIR = Path(__file__).parent / "test_data"

# Mirrors the committed fixtures:
#   US.csv         -> 2024-01-04, 2024-02-02
#   UK.csv         -> 2024-01-05, 2024-01-06 (the latter is a Saturday)
#   EXTRA_COLS.csv -> 2024-01-04 (+ 2024-01-06, ignored) with name/note columns
US_HOLIDAYS = frozenset({"2024-01-04", "2024-02-02"})
UK_HOLIDAYS = frozenset({"2024-01-05", "2024-01-06"})


class StubBackend:
    """In-memory stand-in for ``CsvBackend`` implementing the storage contract.

    Holiday sets are supplied directly, so the pure calendar-math tests never
    touch the filesystem or CSV parsing.  An unknown code raises
    ``FileNotFoundError`` exactly like the real backend, so the fail-loud
    ordering is testable without a disk fixture.
    """

    def __init__(self, holidays: dict[str, frozenset[str]] | None = None):
        self._holidays = dict(holidays or {})
        self.holiday_calls: list[str] = []

    def get_value(self, dataset, date, ticker=None, **params):
        return None

    def get_series(self, dataset, start, end, ticker=None, **params):
        return pd.Series(dtype=float)

    def get_holiday_dates(self, code: str) -> frozenset[str]:
        self.holiday_calls.append(code)
        if code not in self._holidays:
            raise FileNotFoundError(
                f"No holiday calendar file for code {code!r}: expected "
                f"'holidays/{code}.csv'. Check the code for typos or add the file."
            )
        return self._holidays[code]


DEFAULT_STUB = {
    "US": US_HOLIDAYS,
    "UK": UK_HOLIDAYS,
    "NY": frozenset({"2025-01-01"}),
}


def _stub_provider(holidays=None) -> tuple[CalendarProvider, StubBackend]:
    """A provider over a stub backend.  Returns both, for call assertions."""
    stub = StubBackend(DEFAULT_STUB if holidays is None else holidays)
    return CalendarProvider(DataFeed(stub)), stub


def _csv_provider(base_dir=None) -> CalendarProvider:
    """A provider over a **real** ``CsvBackend`` (integration tests)."""
    return CalendarProvider(DataFeed(CsvBackend(str(base_dir or TEST_DATA_DIR))))


def _strict_feed() -> MagicMock:
    """A feed whose backend must never be reached (strict-by-assertion)."""
    return MagicMock(spec=DataFeed)


def _business_days(start: str, end: str) -> list[str]:
    return [d.strftime("%Y-%m-%d") for d in pd.bdate_range(start, end)]


def _calendar_days(start: str, end: str) -> list[str]:
    return [d.strftime("%Y-%m-%d") for d in pd.date_range(start, end)]


class TestTradingDaysBusinessDayBase:
    """``codes=None`` is an explicit "no holiday calendars" declaration."""

    def test_none_codes_returns_business_days(self):
        prov, _ = _stub_provider()
        assert prov.trading_days(None, "2024-01-01", "2024-01-07") == _business_days(
            "2024-01-01", "2024-01-07"
        )

    def test_empty_codes_returns_business_days(self):
        prov, _ = _stub_provider()
        assert prov.trading_days([], "2024-01-01", "2024-01-07") == _business_days(
            "2024-01-01", "2024-01-07"
        )

    def test_empty_codes_does_not_request_any_code(self):
        prov, stub = _stub_provider()
        prov.trading_days([], "2024-01-01", "2024-01-07")
        assert stub.holiday_calls == []

    def test_empty_codes_emits_no_warning(self):
        # A retracted Task 4 refinement: this is a legitimate declaration, not
        # a misconfiguration, so no warning is emitted any more.
        prov, _ = _stub_provider()
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            prov.trading_days(None, "2024-01-01", "2024-01-07")
        assert caught == []

    def test_business_day_base_is_mon_to_fri_even_with_a_month_of_data(self):
        prov, _ = _stub_provider()
        days = prov.trading_days(None, "2024-01-01", "2024-01-31")
        assert days == _business_days("2024-01-01", "2024-01-31")
        assert all(datetime.date.fromisoformat(d).weekday() < 5 for d in days)

    def test_holidays_are_not_subtracted_without_codes(self):
        prov, _ = _stub_provider()
        assert "2024-01-04" in prov.trading_days(None, "2024-01-01", "2024-01-07")


class TestTradingDaysAllCode:
    def test_all_returns_every_calendar_day(self):
        prov, _ = _stub_provider()
        assert prov.trading_days(["all"], "2024-01-01", "2024-01-07") == [
            "2024-01-01",
            "2024-01-02",
            "2024-01-03",
            "2024-01-04",
            "2024-01-05",
            "2024-01-06",
            "2024-01-07",
        ]

    def test_all_includes_weekends(self):
        prov, _ = _stub_provider()
        assert prov.trading_days(["all"], "2024-01-06", "2024-01-07") == [
            "2024-01-06",
            "2024-01-07",
        ]

    def test_all_short_circuits_before_any_backend_call(self):
        prov = CalendarProvider(_strict_feed())
        days = prov.trading_days(["all"], "2024-01-01", "2024-01-07")
        assert len(days) == 7
        prov._feed.get_holiday_dates.assert_not_called()

    def test_all_with_another_code_still_all_days(self):
        prov, stub = _stub_provider()
        assert prov.trading_days(["all", "US"], "2024-01-01", "2024-01-07") == (
            _calendar_days("2024-01-01", "2024-01-07")
        )
        assert stub.holiday_calls == []

    def test_all_with_unknown_code_does_not_raise(self):
        prov, _ = _stub_provider()
        assert len(prov.trading_days(["all", "NOPE"], "2024-01-01", "2024-01-07")) == 7


class TestTradingDaysSingleCode:
    def test_holiday_subtracted(self):
        prov, _ = _stub_provider()
        assert prov.trading_days(["US"], "2024-01-01", "2024-01-07") == [
            "2024-01-01",
            "2024-01-02",
            "2024-01-03",
            "2024-01-05",
        ]

    def test_holiday_outside_range_has_no_effect(self):
        prov, _ = _stub_provider()
        assert prov.trading_days(["US"], "2024-01-08", "2024-01-12") == _business_days(
            "2024-01-08", "2024-01-12"
        )

    def test_second_holiday_in_file_is_applied(self):
        prov, _ = _stub_provider()
        days = prov.trading_days(["US"], "2024-01-29", "2024-02-05")
        assert "2024-02-02" not in days
        assert days == _business_days("2024-01-29", "2024-02-05")[:4] + _business_days(
            "2024-02-05", "2024-02-05"
        )


class TestTradingDaysUnion:
    def test_day_closed_in_one_code_only_is_kept(self):
        prov, _ = _stub_provider()
        # US is closed 01-04, UK is closed 01-05 -- neither is common.
        assert prov.trading_days(["US", "UK"], "2024-01-01", "2024-01-07") == [
            "2024-01-01",
            "2024-01-02",
            "2024-01-03",
            "2024-01-04",
            "2024-01-05",
        ]

    def test_day_closed_in_every_code_is_dropped(self):
        prov, _ = _stub_provider()
        single = set(prov.trading_days(["US"], "2024-01-01", "2024-01-07"))
        union = set(prov.trading_days(["US", "US"], "2024-01-01", "2024-01-07"))
        assert union == single
        assert "2024-01-04" not in union

    def test_union_is_superset_of_each_individual_calendar(self):
        prov, _ = _stub_provider()
        union = set(prov.trading_days(["US", "UK"], "2024-01-01", "2024-01-07"))
        assert set(prov.trading_days(["US"], "2024-01-01", "2024-01-07")) <= union
        assert set(prov.trading_days(["UK"], "2024-01-01", "2024-01-07")) <= union

    def test_holiday_on_weekend_is_ignored(self):
        # UK marks both 2024-01-05 (Fri, a real holiday) and 2024-01-06 (Sat,
        # a weekend).  Dropping the weekend row from the stub must not change
        # anything: the Saturday row contributes nothing either way.
        prov, _ = _stub_provider()
        days = prov.trading_days(["UK"], "2024-01-01", "2024-01-07")
        assert days == [
            "2024-01-01",
            "2024-01-02",
            "2024-01-03",
            "2024-01-04",
        ]

        weekday_only, _ = _stub_provider({"UK": frozenset({"2024-01-05"})})
        assert weekday_only.trading_days(["UK"], "2024-01-01", "2024-01-07") == days

    def test_no_valid_days_returns_empty_list(self):
        prov, _ = _stub_provider()
        # 2024-01-06 and 2024-01-07 are Sat/Sun.
        assert prov.trading_days(["US"], "2024-01-06", "2024-01-07") == []


class TestTradingDaysRangeBoundaries:
    def test_start_and_end_are_inclusive(self):
        prov, _ = _stub_provider()
        assert prov.trading_days(None, "2024-01-01", "2024-01-05") == _business_days(
            "2024-01-01", "2024-01-05"
        )

    def test_single_day_range(self):
        prov, _ = _stub_provider()
        assert prov.trading_days(None, "2024-01-03", "2024-01-03") == ["2024-01-03"]

    def test_single_day_range_on_holiday_is_empty(self):
        prov, _ = _stub_provider()
        assert prov.trading_days(["US"], "2024-01-04", "2024-01-04") == []

    def test_start_after_end_returns_empty(self):
        prov, _ = _stub_provider()
        assert prov.trading_days(None, "2024-02-01", "2024-01-01") == []

    def test_start_after_end_with_all_returns_empty(self):
        prov, _ = _stub_provider()
        assert prov.trading_days(["all"], "2024-02-01", "2024-01-01") == []

    def test_result_is_sorted_and_string_typed(self):
        prov, _ = _stub_provider()
        days = prov.trading_days(["US"], "2024-01-01", "2024-02-05")
        assert days == sorted(days)
        assert all(isinstance(d, str) for d in days)
        assert all(len(d) == 10 and d[4] == "-" and d[7] == "-" for d in days)


class TestFailLoudUnknownCode:
    """Unknown/empty codes raise from every entry point, on every weekday."""

    @pytest.mark.parametrize("date_str", ["2024-01-04", "2024-01-06"])
    def test_is_valid_day_raises_on_weekday_and_weekend(self, date_str):
        prov, _ = _stub_provider()
        with pytest.raises(FileNotFoundError):
            prov.is_valid_day("NOPE", date_str)

    @pytest.mark.parametrize("date_str", ["2024-01-04", "2024-01-06"])
    def test_next_valid_day_raises_on_weekday_and_weekend(self, date_str):
        prov, _ = _stub_provider()
        with pytest.raises(FileNotFoundError):
            prov.next_valid_day("NOPE", date_str)

    @pytest.mark.parametrize("date_str", ["2024-01-04", "2024-01-06"])
    def test_empty_string_code_raises_from_is_valid_day(self, date_str):
        prov, _ = _stub_provider()
        with pytest.raises(FileNotFoundError):
            prov.is_valid_day("", date_str)

    @pytest.mark.parametrize("date_str", ["2024-01-04", "2024-01-06"])
    def test_empty_string_code_raises_from_next_valid_day(self, date_str):
        prov, _ = _stub_provider()
        with pytest.raises(FileNotFoundError):
            prov.next_valid_day("", date_str)

    def test_holiday_resolution_precedes_the_weekend_short_circuit(self):
        # The deliberate reversal of the old pin: a Saturday used to return
        # False *without* resolving the code, masking a configuration typo.
        prov, stub = _stub_provider()
        with pytest.raises(FileNotFoundError):
            prov.is_valid_day("TYPO", "2024-01-06")
        assert stub.holiday_calls == ["TYPO"]

    def test_no_business_days_fallback_remains(self):
        prov, _ = _stub_provider()
        with pytest.raises(FileNotFoundError):
            prov.trading_days(["NOPE"], "2024-01-01", "2024-01-07")


class TestMissingFileIntegration:
    """The real ``CsvBackend`` owns the path convention and the error."""

    def test_missing_file_raises_file_not_found(self):
        prov = _csv_provider()
        with pytest.raises(FileNotFoundError) as excinfo:
            prov.trading_days(["NOPE"], "2024-01-01", "2024-01-07")
        message = str(excinfo.value)
        assert "NOPE" in message
        assert "NOPE.csv" in message

    def test_missing_file_message_names_the_expected_path(self):
        prov = _csv_provider()
        with pytest.raises(FileNotFoundError) as excinfo:
            prov.trading_days(["NOPE"], "2024-01-01", "2024-01-07")
        message = str(excinfo.value)
        assert "holidays" in message
        assert "NOPE.csv" in message

    def test_missing_file_raises_for_empty_string_code(self):
        prov = _csv_provider()
        with pytest.raises(FileNotFoundError):
            prov.trading_days([""], "2024-01-01", "2024-01-07")

    def test_missing_file_raises_from_is_valid_day(self):
        prov = _csv_provider()
        with pytest.raises(FileNotFoundError):
            prov.is_valid_day("NOPE", "2024-01-04")

    def test_missing_file_raises_from_next_valid_day(self):
        prov = _csv_provider()
        with pytest.raises(FileNotFoundError):
            prov.next_valid_day("NOPE", "2024-01-04")

    def test_missing_file_warning_is_not_emitted_instead(self):
        prov = _csv_provider()
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            with pytest.raises(FileNotFoundError):
                prov.trading_days(["NOPE"], "2024-01-01", "2024-01-07")
        assert caught == []


class TestCsvParsingIntegration:
    """Parsing, normalization and caching of ``holidays/{CODE}.csv``."""

    def test_holiday_file_is_parsed_and_applied(self):
        prov = _csv_provider()
        assert prov.trading_days(["US"], "2024-01-01", "2024-01-07") == [
            "2024-01-01",
            "2024-01-02",
            "2024-01-03",
            "2024-01-05",
        ]

    def test_extra_columns_file_parsed_by_column_name(self):
        prov = _csv_provider()
        with pytest.warns(UserWarning, match="not consumed in Phase 2"):
            days = prov.trading_days(["EXTRA_COLS"], "2024-01-01", "2024-01-07")
        assert days == [
            "2024-01-01",
            "2024-01-02",
            "2024-01-03",
            "2024-01-05",
        ]

    def test_extra_columns_cause_no_failure(self):
        prov = _csv_provider()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            assert prov.is_valid_day("EXTRA_COLS", "2024-01-04") is False
            assert prov.is_valid_day("EXTRA_COLS", "2024-01-03") is True

    def test_weekend_row_in_extra_file_is_ignored(self):
        prov = _csv_provider()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            days = prov.trading_days(["EXTRA_COLS"], "2024-01-06", "2024-01-07")
        assert days == []

    def test_holiday_file_read_once_per_backend(self, monkeypatch):
        calls = []
        real_read_csv = pd.read_csv

        def _counting_read_csv(*args, **kwargs):
            calls.append(args[0])
            return real_read_csv(*args, **kwargs)

        monkeypatch.setattr(pd, "read_csv", _counting_read_csv)
        feed = DataFeed(CsvBackend(str(TEST_DATA_DIR)))
        prov = CalendarProvider(feed)

        prov.trading_days(["US"], "2024-01-01", "2024-01-07")
        prov.trading_days(["US"], "2024-01-01", "2024-02-05")
        prov.is_valid_day("US", "2024-01-04")
        prov.next_valid_day("US", "2024-01-04")

        assert len(calls) == 1

    def test_each_code_read_once(self, monkeypatch):
        calls = []
        real_read_csv = pd.read_csv

        def _counting_read_csv(*args, **kwargs):
            calls.append(Path(args[0]).name)
            return real_read_csv(*args, **kwargs)

        monkeypatch.setattr(pd, "read_csv", _counting_read_csv)
        prov = _csv_provider()

        prov.trading_days(["US", "UK"], "2024-01-01", "2024-01-07")
        prov.trading_days(["UK", "US"], "2024-01-01", "2024-01-07")

        assert sorted(calls) == ["UK.csv", "US.csv"]

    def test_two_providers_on_one_backend_share_the_cache(self, monkeypatch):
        calls = []
        real_read_csv = pd.read_csv

        def _counting_read_csv(*args, **kwargs):
            calls.append(args[0])
            return real_read_csv(*args, **kwargs)

        monkeypatch.setattr(pd, "read_csv", _counting_read_csv)
        feed = DataFeed(CsvBackend(str(TEST_DATA_DIR)))

        CalendarProvider(feed).trading_days(["US"], "2024-01-01", "2024-01-07")
        CalendarProvider(feed).trading_days(["US"], "2024-01-01", "2024-01-07")

        assert len(calls) == 1

    def test_separate_backends_do_not_share_the_cache(self, monkeypatch):
        calls = []
        real_read_csv = pd.read_csv

        def _counting_read_csv(*args, **kwargs):
            calls.append(args[0])
            return real_read_csv(*args, **kwargs)

        monkeypatch.setattr(pd, "read_csv", _counting_read_csv)
        _csv_provider().trading_days(["US"], "2024-01-01", "2024-01-07")
        _csv_provider().trading_days(["US"], "2024-01-01", "2024-01-07")

        assert len(calls) == 2


class TestBackendExtraColumnWarning:
    """The warn-once bookkeeping now lives in ``CsvBackend``."""

    def test_warning_fires_once_per_backend_instance(self):
        backend = CsvBackend(str(TEST_DATA_DIR))
        prov = CalendarProvider(DataFeed(backend))
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            prov.trading_days(["EXTRA_COLS"], "2024-01-01", "2024-01-07")
            prov.trading_days(["EXTRA_COLS"], "2024-02-01", "2024-02-05")
        matching = [w for w in caught if "not consumed in Phase 2" in str(w.message)]
        assert len(matching) == 1
        # The stored key includes the ``holidays/`` path segment.
        assert backend._warned_holiday_files == {
            str(TEST_DATA_DIR / "holidays" / "EXTRA_COLS.csv")
        }

    def test_second_backend_warns_again(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            _csv_provider().trading_days(["EXTRA_COLS"], "2024-01-01", "2024-01-07")
            _csv_provider().trading_days(["EXTRA_COLS"], "2024-01-01", "2024-01-07")
        matching = [w for w in caught if "not consumed in Phase 2" in str(w.message)]
        assert len(matching) == 2

    def test_warning_is_not_repeated_on_a_cache_hit(self):
        prov = _csv_provider()
        with pytest.warns(UserWarning, match="not consumed in Phase 2"):
            prov.trading_days(["EXTRA_COLS"], "2024-01-01", "2024-01-07")
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            prov.trading_days(["EXTRA_COLS"], "2024-01-01", "2024-01-07")
        assert [w for w in caught if "not consumed" in str(w.message)] == []

    def test_warning_is_attributed_to_the_provider_frame(self):
        # stacklevel=4 lands on the provider method: the frame a consumer of
        # CalendarProvider would recognise.  Anything deeper varies by consumer
        # and would blame the backend instead.  The line bound is a real range
        # check against the provider method's own source lines.
        prov = _csv_provider()
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            prov.trading_days(["EXTRA_COLS"], "2024-01-01", "2024-01-07")
        matching = [w for w in caught if "not consumed in Phase 2" in str(w.message)]
        assert len(matching) == 1
        assert Path(matching[0].filename).name == "calendar_provider.py"
        source_lines, first_line = inspect.getsourcelines(CalendarProvider.trading_days)
        assert first_line <= matching[0].lineno <= first_line + len(source_lines)


class TestIsValidDay:
    def test_business_day_is_valid(self):
        prov, _ = _stub_provider()
        assert prov.is_valid_day("US", "2024-01-03") is True

    def test_weekend_is_invalid(self):
        prov, _ = _stub_provider()
        assert prov.is_valid_day("US", "2024-01-06") is False
        assert prov.is_valid_day("US", "2024-01-07") is False

    def test_holiday_is_invalid(self):
        prov, _ = _stub_provider()
        assert prov.is_valid_day("US", "2024-01-04") is False

    def test_holiday_of_other_code_is_valid(self):
        prov, _ = _stub_provider()
        assert prov.is_valid_day("US", "2024-01-05") is True
        assert prov.is_valid_day("UK", "2024-01-04") is True

    def test_all_code_is_always_valid(self):
        prov, stub = _stub_provider()
        assert prov.is_valid_day("all", "2024-01-06") is True
        assert prov.is_valid_day("all", "2024-01-04") is True
        assert stub.holiday_calls == []

    def test_all_code_is_valid_on_a_strict_feed(self):
        prov = CalendarProvider(_strict_feed())
        assert prov.is_valid_day("all", "2024-01-06") is True
        prov._feed.get_holiday_dates.assert_not_called()

    def test_timestamp_string_is_truncated_to_its_date_part(self):
        prov, stub = _stub_provider()
        assert prov.is_valid_day("US", "2024-01-04 23:00:00") is False
        assert prov.is_valid_day("US", "2024-01-03 15:30:45") is True
        assert stub.holiday_calls == ["US", "US"]


class TestNextValidDay:
    def test_next_day_after_a_business_day(self):
        prov, _ = _stub_provider()
        assert prov.next_valid_day("US", "2024-01-02") == "2024-01-03"

    def test_skips_over_weekend(self):
        prov, _ = _stub_provider()
        assert prov.next_valid_day("US", "2024-01-05") == "2024-01-08"

    def test_skips_over_holiday(self):
        prov, _ = _stub_provider()
        assert prov.next_valid_day("US", "2024-01-03") == "2024-01-05"

    def test_skips_over_consecutive_holiday_and_weekend(self):
        # 2024-02-02 (Fri) is a US holiday and 02-03/02-04 is a weekend.
        prov, _ = _stub_provider()
        assert prov.next_valid_day("US", "2024-02-01") == "2024-02-05"

    def test_across_year_boundary(self):
        # 2024-12-31 is a Tuesday and 2025-01-01 the next day (a Wednesday).
        prov, _ = _stub_provider()
        assert prov.next_valid_day("US", "2024-12-31") == "2025-01-01"

    def test_across_year_boundary_over_new_year_holiday(self):
        # A calendar closed on 2025-01-01 must roll to Thursday 2025-01-02.
        prov, _ = _stub_provider()
        assert prov.next_valid_day("NY", "2024-12-31") == "2025-01-02"

    def test_strictly_after_not_inclusive(self):
        prov, _ = _stub_provider()
        assert prov.next_valid_day("US", "2024-01-03") != "2024-01-03"

    def test_all_code_returns_next_calendar_day(self):
        prov, _ = _stub_provider()
        assert prov.next_valid_day("all", "2024-01-05") == "2024-01-06"

    def test_all_code_across_weekend(self):
        prov, _ = _stub_provider()
        assert prov.next_valid_day("all", "2024-01-06") == "2024-01-07"

    def test_all_code_across_year_boundary(self):
        prov, _ = _stub_provider()
        assert prov.next_valid_day("all", "2024-12-31") == "2025-01-01"

    def test_all_code_short_circuits_before_any_backend_call(self):
        prov = CalendarProvider(_strict_feed())
        assert prov.next_valid_day("all", "2024-01-05") == "2024-01-06"
        prov._feed.get_holiday_dates.assert_not_called()

    def test_timestamp_string_is_truncated_to_its_date_part(self):
        prov, _ = _stub_provider()
        # 2024-01-04 is a US holiday; the time component must not leak into
        # the offset arithmetic or into the returned value.
        assert prov.next_valid_day("US", "2024-01-04 23:00:00") == "2024-01-05"
        assert prov.next_valid_day("US", "2024-01-03 15:30:45") == "2024-01-05"

    def test_iteration_guard_raises_runtime_error(self):
        # A pathological (all-days) calendar, no ~1000-row fixture needed.
        dense = frozenset(
            (datetime.date(2020, 1, 1) + datetime.timedelta(days=i)).isoformat()
            for i in range(
                (datetime.date(2030, 12, 31) - datetime.date(2020, 1, 1)).days + 1
            )
        )
        prov, _ = _stub_provider({"DENSE": dense})
        with pytest.raises(RuntimeError) as excinfo:
            prov.next_valid_day("DENSE", "2024-01-01")
        message = str(excinfo.value)
        assert "DENSE" in message
        # Assert against the constant, not a copied literal: the message and the
        # loop bound must not be able to drift apart.
        assert str(_MAX_LOOKAHEAD_DAYS) in message
        assert "2024-01-01" in message

    def test_iteration_guard_not_triggered_for_sparse_calendar(self):
        prov, _ = _stub_provider()
        assert prov.next_valid_day("US", "2024-01-02") == "2024-01-03"

    def test_saturday_rolls_to_monday(self):
        prov, _ = _stub_provider()
        assert prov.next_valid_day("US", "2024-01-06") == "2024-01-08"
