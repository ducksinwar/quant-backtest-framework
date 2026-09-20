"""Tests for the shared CalendarProvider (design_notes.md §3.5)."""

import warnings
from pathlib import Path

import pandas as pd
import pytest

from backtester.calendar_provider import CalendarProvider

HOLIDAY_DIR = Path(__file__).parent / "test_data" / "holidays"
EMPTY_DIR = HOLIDAY_DIR / "empty"

# US.csv holds 2024-01-04 and 2024-02-02.
# UK.csv holds 2024-01-05 and 2024-01-06 (the latter is a Saturday).


def _provider(**kwargs) -> CalendarProvider:
    return CalendarProvider(**kwargs)


def _business_days(start: str, end: str) -> list[str]:
    return [d.strftime("%Y-%m-%d") for d in pd.bdate_range(start, end)]


class TestTradingDaysBusinessDaysMode:
    """holiday_dir=None -> business-days-only."""

    def test_no_holiday_dir_returns_business_days(self):
        prov = _provider()
        assert prov.trading_days(["US"], "2024-01-01", "2024-01-07") == _business_days(
            "2024-01-01", "2024-01-07"
        )

    def test_no_holiday_dir_unknown_code_is_business_days(self):
        prov = _provider()
        assert prov.trading_days([], "2024-01-01", "2024-01-07") == _business_days(
            "2024-01-01", "2024-01-07"
        )

    def test_no_holiday_dir_no_subtraction_of_any_code(self):
        prov = _provider()
        days = prov.trading_days(["US"], "2024-01-01", "2024-01-07")
        assert "2024-01-04" in days

    def test_is_valid_day_no_holiday_dir(self):
        prov = _provider()
        assert prov.is_valid_day("ANY", "2024-01-04") is True
        assert prov.is_valid_day("ANY", "2024-01-06") is False


class TestTradingDaysNoCodes:
    def test_none_codes_returns_business_days(self):
        prov = _provider(holiday_dir=HOLIDAY_DIR)
        with pytest.warns(UserWarning, match="loaded but unused"):
            days = prov.trading_days(None, "2024-01-01", "2024-01-07")
        assert days == _business_days("2024-01-01", "2024-01-07")

    def test_empty_codes_returns_business_days(self):
        prov = _provider(holiday_dir=HOLIDAY_DIR)
        with pytest.warns(UserWarning, match="loaded but unused"):
            days = prov.trading_days([], "2024-01-01", "2024-01-07")
        assert days == _business_days("2024-01-01", "2024-01-07")

    def test_none_codes_with_holiday_dir_warns_once(self):
        prov = _provider(holiday_dir=HOLIDAY_DIR)
        with pytest.warns(UserWarning, match="loaded but unused"):
            prov.trading_days(None, "2024-01-01", "2024-01-07")
        assert prov._warned_no_codes is True

        # Second call: no new warning (instance-level flag).
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            prov.trading_days(None, "2024-01-01", "2024-01-07")
        assert caught == []

    def test_empty_codes_with_holiday_dir_warns(self):
        prov = _provider(holiday_dir=HOLIDAY_DIR)
        with pytest.warns(UserWarning, match="loaded but unused"):
            prov.trading_days([], "2024-01-01", "2024-01-07")

    def test_no_warning_without_holiday_dir(self):
        prov = _provider()
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            prov.trading_days(None, "2024-01-01", "2024-01-07")
        assert caught == []
        assert prov._warned_no_codes is False

    def test_no_warning_when_codes_supplied(self):
        prov = _provider(holiday_dir=HOLIDAY_DIR)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            prov.trading_days(["US"], "2024-01-01", "2024-01-07")
        assert caught == []
        assert prov._warned_no_codes is False


class TestTradingDaysAllCode:
    def test_all_returns_every_calendar_day(self):
        prov = _provider(holiday_dir=HOLIDAY_DIR)
        days = prov.trading_days(["all"], "2024-01-01", "2024-01-07")
        assert days == [
            "2024-01-01",
            "2024-01-02",
            "2024-01-03",
            "2024-01-04",
            "2024-01-05",
            "2024-01-06",
            "2024-01-07",
        ]

    def test_all_includes_weekends(self):
        prov = _provider(holiday_dir=HOLIDAY_DIR)
        days = prov.trading_days(["all"], "2024-01-06", "2024-01-07")
        assert days == ["2024-01-06", "2024-01-07"]

    def test_all_short_circuits_before_loading(self, monkeypatch):
        calls = []

        def _counting_read_csv(*args, **kwargs):
            calls.append(args)
            raise AssertionError("holiday loading must not happen for 'all'")

        monkeypatch.setattr(pd, "read_csv", _counting_read_csv)
        prov = _provider(holiday_dir=HOLIDAY_DIR)
        days = prov.trading_days(["all"], "2024-01-01", "2024-01-07")
        assert len(days) == 7
        assert calls == []

    def test_all_with_another_code_still_all_days(self):
        prov = _provider(holiday_dir=HOLIDAY_DIR)
        assert prov.trading_days(["all", "US"], "2024-01-01", "2024-01-07") == [
            d.strftime("%Y-%m-%d") for d in pd.date_range("2024-01-01", "2024-01-07")
        ]

    def test_all_with_unknown_code_does_not_raise(self):
        prov = _provider(holiday_dir=HOLIDAY_DIR)
        assert len(prov.trading_days(["all", "NOPE"], "2024-01-01", "2024-01-07")) == 7


class TestTradingDaysSingleCode:
    def test_holiday_subtracted(self):
        prov = _provider(holiday_dir=HOLIDAY_DIR)
        days = prov.trading_days(["US"], "2024-01-01", "2024-01-07")
        assert days == ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-05"]

    def test_holiday_outside_range_has_no_effect(self):
        prov = _provider(holiday_dir=HOLIDAY_DIR)
        days = prov.trading_days(["US"], "2024-01-08", "2024-01-12")
        assert days == _business_days("2024-01-08", "2024-01-12")

    def test_second_holiday_in_file_is_applied(self):
        prov = _provider(holiday_dir=HOLIDAY_DIR)
        days = prov.trading_days(["US"], "2024-01-29", "2024-02-05")
        assert "2024-02-02" not in days
        assert days == _business_days("2024-01-29", "2024-02-05")[:4] + _business_days(
            "2024-02-05", "2024-02-05"
        )


class TestTradingDaysUnion:
    def test_day_closed_in_one_code_only_is_kept(self):
        prov = _provider(holiday_dir=HOLIDAY_DIR)
        days = prov.trading_days(["US", "UK"], "2024-01-01", "2024-01-07")
        # US is closed 01-04, UK is closed 01-05 -- neither is common.
        assert days == [
            "2024-01-01",
            "2024-01-02",
            "2024-01-03",
            "2024-01-04",
            "2024-01-05",
        ]

    def test_day_closed_in_every_code_is_dropped(self):
        prov = _provider(holiday_dir=HOLIDAY_DIR)
        single = set(prov.trading_days(["US"], "2024-01-01", "2024-01-07"))
        union = set(prov.trading_days(["US", "US"], "2024-01-01", "2024-01-07"))
        assert union == single
        assert "2024-01-04" not in union

    def test_union_is_superset_of_each_individual_calendar(self):
        prov = _provider(holiday_dir=HOLIDAY_DIR)
        union = set(prov.trading_days(["US", "UK"], "2024-01-01", "2024-01-07"))
        assert set(prov.trading_days(["US"], "2024-01-01", "2024-01-07")) <= union
        assert set(prov.trading_days(["UK"], "2024-01-01", "2024-01-07")) <= union

    def test_holiday_on_weekend_is_ignored(self):
        # UK marks both 2024-01-05 (Fri, a real holiday) and 2024-01-06 (Sat,
        # a weekend). Removing the weekend row from the file must not change
        # anything, so compare against a synthetic calendar holding only the
        # Friday holiday: the Saturday row contributes nothing either way.
        prov = _provider(holiday_dir=HOLIDAY_DIR)
        days = prov.trading_days(["UK"], "2024-01-01", "2024-01-07")
        assert days == [
            "2024-01-01",
            "2024-01-02",
            "2024-01-03",
            "2024-01-04",
        ]

        prov_weekday_only = _provider()
        prov_weekday_only._cache["UK"] = {"2024-01-05"}
        assert (
            prov_weekday_only.trading_days(["UK"], "2024-01-01", "2024-01-07")
            == days
        )

    def test_no_valid_days_returns_empty_list(self):
        prov = _provider(holiday_dir=HOLIDAY_DIR)
        # 2024-01-06 and 2024-01-07 are Sat/Sun.
        assert prov.trading_days(["US"], "2024-01-06", "2024-01-07") == []


class TestTradingDaysRangeBoundaries:
    def test_start_and_end_are_inclusive(self):
        prov = _provider()
        assert prov.trading_days(None, "2024-01-01", "2024-01-05") == _business_days(
            "2024-01-01", "2024-01-05"
        )

    def test_single_day_range(self):
        prov = _provider()
        assert prov.trading_days(None, "2024-01-03", "2024-01-03") == ["2024-01-03"]

    def test_single_day_range_on_holiday_is_empty(self):
        prov = _provider(holiday_dir=HOLIDAY_DIR)
        assert prov.trading_days(["US"], "2024-01-04", "2024-01-04") == []

    def test_start_after_end_returns_empty(self):
        prov = _provider()
        assert prov.trading_days(None, "2024-02-01", "2024-01-01") == []

    def test_start_after_end_with_all_returns_empty(self):
        prov = _provider()
        assert prov.trading_days(["all"], "2024-02-01", "2024-01-01") == []

    def test_result_is_sorted_and_string_typed(self):
        prov = _provider(holiday_dir=HOLIDAY_DIR)
        days = prov.trading_days(["US"], "2024-01-01", "2024-02-05")
        assert days == sorted(days)
        assert all(isinstance(d, str) for d in days)
        assert all(len(d) == 10 and d[4] == "-" and d[7] == "-" for d in days)


class TestMissingFile:
    def test_missing_file_raises_file_not_found(self):
        prov = _provider(holiday_dir=HOLIDAY_DIR)
        with pytest.raises(FileNotFoundError) as excinfo:
            prov.trading_days(["NOPE"], "2024-01-01", "2024-01-07")
        message = str(excinfo.value)
        assert "NOPE" in message
        assert "NOPE.csv" in message

    def test_missing_file_raises_for_empty_string_code(self):
        prov = _provider(holiday_dir=HOLIDAY_DIR)
        with pytest.raises(FileNotFoundError):
            prov.trading_days([""], "2024-01-01", "2024-01-07")

    def test_empty_holiday_dir_raises_for_any_code(self):
        prov = _provider(holiday_dir=EMPTY_DIR)
        with pytest.raises(FileNotFoundError):
            prov.trading_days(["US"], "2024-01-01", "2024-01-07")

    def test_missing_file_raises_from_is_valid_day(self):
        prov = _provider(holiday_dir=HOLIDAY_DIR)
        with pytest.raises(FileNotFoundError):
            prov.is_valid_day("NOPE", "2024-01-04")

    def test_missing_file_raises_from_next_valid_day(self):
        prov = _provider(holiday_dir=HOLIDAY_DIR)
        with pytest.raises(FileNotFoundError):
            prov.next_valid_day("NOPE", "2024-01-04")

    def test_no_holiday_dir_does_not_raise(self):
        prov = _provider()
        assert prov.trading_days(["NOPE"], "2024-01-01", "2024-01-07") == _business_days(
            "2024-01-01", "2024-01-07"
        )

    def test_missing_file_warning_is_not_emitted_instead(self):
        prov = _provider(holiday_dir=HOLIDAY_DIR)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            with pytest.raises(FileNotFoundError):
                prov.trading_days(["NOPE"], "2024-01-01", "2024-01-07")
        assert caught == []


class TestHolidayCaching:
    def test_file_read_once_across_repeated_calls(self, monkeypatch):
        calls = []
        real_read_csv = pd.read_csv

        def _counting_read_csv(*args, **kwargs):
            calls.append(args[0])
            return real_read_csv(*args, **kwargs)

        monkeypatch.setattr(pd, "read_csv", _counting_read_csv)
        prov = _provider(holiday_dir=HOLIDAY_DIR)

        first = prov.trading_days(["US"], "2024-01-01", "2024-01-07")
        second = prov.trading_days(["US"], "2024-01-01", "2024-02-05")
        third = prov.trading_days(["US"], "2024-01-01", "2024-12-31")

        assert first == second[: len(first)]
        assert third
        assert len(calls) == 1

    def test_read_once_across_different_methods(self, monkeypatch):
        calls = []
        real_read_csv = pd.read_csv

        def _counting_read_csv(*args, **kwargs):
            calls.append(args[0])
            return real_read_csv(*args, **kwargs)

        monkeypatch.setattr(pd, "read_csv", _counting_read_csv)
        prov = _provider(holiday_dir=HOLIDAY_DIR)

        prov.trading_days(["US"], "2024-01-01", "2024-01-07")
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
        prov = _provider(holiday_dir=HOLIDAY_DIR)

        prov.trading_days(["US", "UK"], "2024-01-01", "2024-01-07")
        prov.trading_days(["UK", "US"], "2024-01-01", "2024-01-07")

        assert sorted(calls) == ["UK.csv", "US.csv"]

    def test_separate_instances_do_not_share_cache(self, monkeypatch):
        calls = []
        real_read_csv = pd.read_csv

        def _counting_read_csv(*args, **kwargs):
            calls.append(args[0])
            return real_read_csv(*args, **kwargs)

        monkeypatch.setattr(pd, "read_csv", _counting_read_csv)
        _provider(holiday_dir=HOLIDAY_DIR).trading_days(["US"], "2024-01-01", "2024-01-07")
        _provider(holiday_dir=HOLIDAY_DIR).trading_days(["US"], "2024-01-01", "2024-01-07")

        assert len(calls) == 2


class TestExtraColumns:
    def test_parsed_by_column_name_and_holiday_applied(self):
        prov = _provider(holiday_dir=HOLIDAY_DIR)
        with pytest.warns(UserWarning, match="not consumed in Phase 2"):
            days = prov.trading_days(["EXTRA_COLS"], "2024-01-01", "2024-01-07")
        assert days == [
            "2024-01-01",
            "2024-01-02",
            "2024-01-03",
            "2024-01-05",
        ]

    def test_extra_column_warning_fires_once_per_instance(self):
        prov = _provider(holiday_dir=HOLIDAY_DIR)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            prov.trading_days(["EXTRA_COLS"], "2024-01-01", "2024-01-07")
            prov.trading_days(["EXTRA_COLS"], "2024-02-01", "2024-02-05")
        matching = [w for w in caught if "not consumed in Phase 2" in str(w.message)]
        assert len(matching) == 1
        assert prov._warned_files == {str(HOLIDAY_DIR / "EXTRA_COLS.csv")}

    def test_second_instance_warns_again(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            _provider(holiday_dir=HOLIDAY_DIR).trading_days(["EXTRA_COLS"], "2024-01-01", "2024-01-07")
            _provider(holiday_dir=HOLIDAY_DIR).trading_days(["EXTRA_COLS"], "2024-01-01", "2024-01-07")
        matching = [w for w in caught if "not consumed in Phase 2" in str(w.message)]
        assert len(matching) == 2

    def test_extra_columns_cause_no_failure(self):
        prov = _provider(holiday_dir=HOLIDAY_DIR)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            assert prov.is_valid_day("EXTRA_COLS", "2024-01-04") is False
            assert prov.is_valid_day("EXTRA_COLS", "2024-01-03") is True

    def test_weekend_row_in_extra_file_is_ignored(self):
        prov = _provider(holiday_dir=HOLIDAY_DIR)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            days = prov.trading_days(["EXTRA_COLS"], "2024-01-06", "2024-01-07")
        assert days == []


class TestIsValidDay:
    def test_business_day_is_valid(self):
        prov = _provider(holiday_dir=HOLIDAY_DIR)
        assert prov.is_valid_day("US", "2024-01-03") is True

    def test_weekend_is_invalid(self):
        prov = _provider(holiday_dir=HOLIDAY_DIR)
        assert prov.is_valid_day("US", "2024-01-06") is False
        assert prov.is_valid_day("US", "2024-01-07") is False

    def test_holiday_is_invalid(self):
        prov = _provider(holiday_dir=HOLIDAY_DIR)
        assert prov.is_valid_day("US", "2024-01-04") is False

    def test_holiday_of_other_code_is_valid(self):
        prov = _provider(holiday_dir=HOLIDAY_DIR)
        assert prov.is_valid_day("US", "2024-01-05") is True
        assert prov.is_valid_day("UK", "2024-01-04") is True

    def test_all_code_is_always_valid(self):
        prov = _provider(holiday_dir=HOLIDAY_DIR)
        assert prov.is_valid_day("all", "2024-01-06") is True
        assert prov.is_valid_day("all", "2024-01-04") is True

    def test_all_code_valid_without_holiday_dir(self):
        prov = _provider()
        assert prov.is_valid_day("all", "2024-01-06") is True

    def test_empty_string_code_with_holiday_dir_raises(self):
        prov = _provider(holiday_dir=HOLIDAY_DIR)
        with pytest.raises(FileNotFoundError):
            prov.is_valid_day("", "2024-01-04")

    def test_empty_string_code_without_holiday_dir_is_business_day(self):
        prov = _provider()
        assert prov.is_valid_day("", "2024-01-04") is True
        assert prov.is_valid_day("", "2024-01-06") is False

    def test_unknown_code_without_holiday_dir_is_business_day(self):
        prov = _provider()
        assert prov.is_valid_day("TOTALLY_UNKNOWN", "2024-01-04") is True


class TestNextValidDay:
    def test_next_day_after_a_business_day(self):
        prov = _provider(holiday_dir=HOLIDAY_DIR)
        assert prov.next_valid_day("US", "2024-01-02") == "2024-01-03"

    def test_skips_over_weekend(self):
        prov = _provider(holiday_dir=HOLIDAY_DIR)
        assert prov.next_valid_day("US", "2024-01-05") == "2024-01-08"

    def test_skips_over_holiday(self):
        prov = _provider(holiday_dir=HOLIDAY_DIR)
        assert prov.next_valid_day("US", "2024-01-03") == "2024-01-05"

    def test_skips_over_consecutive_holiday_and_weekend(self):
        # 2024-02-02 (Fri) is a US holiday and 02-03/02-04 is a weekend.
        prov = _provider(holiday_dir=HOLIDAY_DIR)
        assert prov.next_valid_day("US", "2024-02-01") == "2024-02-05"

    def test_across_year_boundary(self):
        # 2024-12-31 is a Tuesday and 2025-01-01 the next day (a Wednesday).
        prov = _provider()
        assert prov.next_valid_day("ANY", "2024-12-31") == "2025-01-01"

    def test_across_year_boundary_over_new_year_holiday(self):
        # A calendar closed on 2025-01-01 must roll to Thursday 2025-01-02.
        prov = _provider()
        prov._cache["NY"] = {"2025-01-01"}
        assert prov.next_valid_day("NY", "2024-12-31") == "2025-01-02"

    def test_across_year_boundary_with_holiday(self):
        prov = _provider(holiday_dir=HOLIDAY_DIR)
        # US has no year-end holidays, so 2025-01-01 (Wed) is valid.
        assert prov.next_valid_day("US", "2024-12-31") == "2025-01-01"

    def test_strictly_after_not_inclusive(self):
        prov = _provider()
        assert prov.next_valid_day("ANY", "2024-01-03") != "2024-01-03"

    def test_all_code_returns_next_calendar_day(self):
        prov = _provider(holiday_dir=HOLIDAY_DIR)
        assert prov.next_valid_day("all", "2024-01-05") == "2024-01-06"

    def test_all_code_across_weekend(self):
        prov = _provider()
        assert prov.next_valid_day("all", "2024-01-06") == "2024-01-07"

    def test_all_code_across_year_boundary(self):
        prov = _provider()
        assert prov.next_valid_day("all", "2024-12-31") == "2025-01-01"

    def test_all_code_without_holiday_dir(self):
        prov = _provider()
        assert prov.next_valid_day("all", "2024-01-05") == "2024-01-06"

    def test_iteration_guard_raises_runtime_error(self):
        prov = _provider(holiday_dir=HOLIDAY_DIR)
        # Pre-seed the per-code cache with a pathological (all-days) calendar
        # rather than hand-writing a ~1000-row fixture.
        prov._cache["DENSE"] = set(
            pd.date_range("2020-01-01", "2030-12-31").strftime("%Y-%m-%d")
        )
        with pytest.raises(RuntimeError) as excinfo:
            prov.next_valid_day("DENSE", "2024-01-01")
        message = str(excinfo.value)
        assert "DENSE" in message
        assert "1000" in message
        assert "2024-01-01" in message

    def test_iteration_guard_not_triggered_for_sparse_calendar(self):
        prov = _provider(holiday_dir=HOLIDAY_DIR)
        assert prov.next_valid_day("US", "2024-01-02") == "2024-01-03"
