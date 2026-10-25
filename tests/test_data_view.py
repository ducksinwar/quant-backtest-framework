"""DataView: the T-1 window, cutoff enforcement and calendar scoping (Task 5a).

The calendar-scoping tests are pivoted on a **real** anomalous day found in the
committed fixtures.  Sweeping all 6,716 union-calendar loop days (2000-2025) for
the four example tickers turned up 12 days where a price CSV holds a row on a
day the holiday file calls a holiday -- 2800.HK 2013-08-14 (+ 2016-08-02,
2016-10-21, 2017-08-23, 2017-12-27, 2018-09-17, 2023-12-27) and SXRT.DE
2015-12-25 (+ 2017-06-05, 2017-10-03).  Clamping a series end to
``prev_valid_day`` therefore *dropped* rows the Phase 1 path kept and shifted
the moving averages, which is exactly why ``get_series`` end-clamps to the
cutoff and never consults the calendar.  ``TestRealAnomalousDay`` pins that on
the real files; the synthetic fixture below mirrors the same day.
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from backtester.calendar_provider import CalendarProvider
from backtester.data.csv_backend import CsvBackend
from backtester.data.data_feed import DataFeed
from backtester.data_view import DataView, DataViewCutoffError

#: The real anomalous day: the HK calendar closes 2013-08-14 while the price
#: series has a row for it.
ANOMALY_DAY = "2013-08-14"
ANOMALY_PREV = "2013-08-13"
#: A loop day right after it (2013-08-15 is a Thursday).
ANOMALY_LOOP_DAY = "2013-08-15"

MARKET_DATA_DIR = Path(__file__).resolve().parents[1] / "market_data"


@pytest.fixture
def env(tmp_path):
    """A tiny market that mirrors the real anomaly on the same dates.

    ``2013-08-14`` is listed as an HK holiday *and* has a price row, exactly as
    ``market_data/holidays/HK.csv`` + ``market_data/2800.HK_eod.csv`` do.
    """
    (tmp_path / "holidays").mkdir()
    (tmp_path / "holidays" / "HK.csv").write_text(f"date\n{ANOMALY_DAY}\n")
    (tmp_path / "TEST_eod.csv").write_text(
        "date,close\n"
        "2013-08-09,100.0\n"
        "2013-08-12,101.0\n"
        f"{ANOMALY_PREV},102.0\n"
        f"{ANOMALY_DAY},103.0\n"
        f"{ANOMALY_LOOP_DAY},104.0\n"
    )
    feed = DataFeed(CsvBackend(base_dir=str(tmp_path)))
    return feed, CalendarProvider(feed)


HK_MAP = {"TEST": "HK"}


def _view(
    feed,
    calendar,
    date=ANOMALY_LOOP_DAY,
    cutoff=ANOMALY_DAY,
    mapping=None,
    max_staleness_days=7,
):
    return DataView(
        feed,
        date=date,
        cutoff=cutoff,
        calendar=calendar,
        ticker_to_calendar_code=mapping,
        max_staleness_days=max_staleness_days,
    )


class TestConstruction:
    def test_exposes_date_and_cutoff(self):
        view = _view(None, None)
        assert view.date == ANOMALY_LOOP_DAY
        assert view.cutoff == ANOMALY_DAY
        assert view.dataset == "eod_prices"

    def test_cutoff_on_or_after_the_loop_day_is_rejected(self):
        with pytest.raises(ValueError, match="not before the loop day"):
            _view(None, None, date=ANOMALY_DAY, cutoff=ANOMALY_DAY)
        with pytest.raises(ValueError, match="not before the loop day"):
            _view(None, None, date="2013-08-15", cutoff="2013-08-16")

    @pytest.mark.parametrize("field", ["date", "cutoff"])
    def test_empty_dates_are_rejected(self, field):
        kwargs = {"date": ANOMALY_LOOP_DAY, "cutoff": ANOMALY_DAY, field: ""}
        with pytest.raises(ValueError):
            DataView(None, **kwargs)

    def test_mapping_is_copied(self):
        mapping = dict(HK_MAP)
        view = _view(None, None, mapping=mapping)
        mapping["TEST"] = "US"
        assert view.calendar_code_for("TEST") == "HK"
        assert view.calendar_code_for("OTHER") is None


class TestCutoffEnforcement:
    def test_get_price_raises_beyond_the_cutoff(self):
        feed = MagicMock()
        view = _view(feed, None)
        with pytest.raises(DataViewCutoffError) as excinfo:
            view.get_price("TEST", ANOMALY_LOOP_DAY)
        assert isinstance(excinfo.value, ValueError)
        assert ANOMALY_DAY in str(excinfo.value)
        feed.get_value.assert_not_called()

    def test_get_price_raises_for_a_date_after_the_loop_day_too(self):
        view = _view(MagicMock(), None)
        with pytest.raises(DataViewCutoffError):
            view.get_price("TEST", "2014-01-01")

    def test_get_price_at_the_cutoff_is_allowed(self, env):
        feed, calendar = env
        view = _view(feed, calendar)
        assert view.get_price("TEST", ANOMALY_DAY) == 103.0

    def test_get_series_clamps_end_to_the_cutoff(self, env):
        feed, calendar = env
        view = _view(feed, calendar)
        for end in (None, "2014-01-01"):
            series = view.get_series("TEST", "2013-01-01", end)
            assert list(series.index) == [
                "2013-08-09",
                "2013-08-12",
                ANOMALY_PREV,
                ANOMALY_DAY,
            ]
            assert series.index[-1] == view.cutoff

    def test_get_series_beyond_the_cutoff_is_empty_not_an_error(self, env):
        feed, calendar = env
        view = _view(feed, calendar)
        assert view.get_series("TEST", "2013-09-01", "2013-10-01").empty


class TestSeriesWindow:
    def test_start_is_never_clamped_and_a_short_series_is_returned(self, env):
        """A pre-backtest lookback keeps working and simply starts later."""
        feed, calendar = env
        view = _view(feed, calendar)
        series = view.get_series("TEST", "1990-01-01", ANOMALY_PREV)
        assert list(series.index) == ["2013-08-09", "2013-08-12", ANOMALY_PREV]

    def test_rows_are_never_filtered_by_calendar(self, env):
        """The anomaly day is an HK holiday and its row still comes back."""
        feed, calendar = env
        scoped = _view(feed, calendar, mapping=HK_MAP)
        unscoped = _view(feed, calendar)

        scoped_series = scoped.get_series("TEST", "2013-08-01", None)
        assert ANOMALY_DAY in scoped_series.index
        assert scoped_series.index[-1] == ANOMALY_DAY
        assert scoped_series.equals(
            unscoped.get_series("TEST", "2013-08-01", None)
        )

    def test_series_start_after_end_is_empty(self, env):
        feed, calendar = env
        view = _view(feed, calendar)
        assert view.get_series("TEST", ANOMALY_DAY, ANOMALY_PREV).empty

    def test_unknown_ticker_is_empty(self, env):
        feed, calendar = env
        view = _view(feed, calendar)
        assert view.get_series("NOPE", None, None).empty


class TestReferencePrice:
    """``reference_price`` is the T-1 sizing read; there is no look-ahead."""

    def test_returns_the_t_minus_1_close_when_t_is_present(self, env):
        """Test A: T's row exists (104.0) but only the cutoff row (103.0) is used."""
        feed, calendar = env
        view = _view(feed, calendar)
        # The loop day's own row is in the feed...
        assert feed.get_value("eod_prices", ANOMALY_LOOP_DAY, "TEST") == 104.0
        # ...yet the loop day is structurally unreadable through the view...
        with pytest.raises(DataViewCutoffError):
            view.get_price("TEST", view.date)
        # ...and sizing uses T-1, not T.
        assert view.reference_price("TEST") == 103.0

    def test_mapped_ticker_uses_the_previous_calendar_valid_close(self, env):
        """The HK calendar closes the cutoff day, so the reference is 08-13."""
        feed, calendar = env
        view = _view(feed, calendar, mapping=HK_MAP)
        assert view.reference_price("TEST") == 102.0

    def test_falls_back_to_an_earlier_row_when_t_minus_1_is_missing(self, env):
        """Test B: no rows on 08-17/08-16, so the last row (08-15) is used."""
        feed, calendar = env
        view = _view(feed, calendar, date="2013-08-18", cutoff="2013-08-17")
        assert view.reference_price("TEST") == 104.0

    def test_none_when_there_is_no_observation_at_or_before_the_cutoff(self, env):
        """Test C: ``None`` has two causes -- no observation at all, or a last
        observation older than ``max_staleness_days``.  Here there is no row."""
        feed, calendar = env
        view = _view(feed, calendar, date="2013-08-09", cutoff="2013-08-08")
        assert view.reference_price("TEST") is None

    def test_requires_a_feed(self):
        with pytest.raises(RuntimeError, match="no data feed"):
            _view(None, None).reference_price("TEST")


class TestReferencePriceStaleness:
    """B2: ``reference_price`` is bounded by ``max_staleness_days``."""

    def test_mapped_ticker_gap_within_bound_falls_back(self, env):
        """The mapped calendar day has no row; the last data row is used."""
        feed, calendar = env
        # Loop day 08-18 makes 08-16 (Fri) the calendar-valid day, which has no
        # row; the fallback ignores the calendar and takes 08-15 (3 days old).
        view = _view(
            feed,
            calendar,
            date="2013-08-18",
            cutoff="2013-08-17",
            mapping=HK_MAP,
        )
        assert view.reference_price("TEST") == 104.0

    def test_mapped_ticker_gap_beyond_bound_returns_none(self, env):
        feed, calendar = env
        # The last row is 08-15 and the cutoff is 08-26: an 11-day gap.
        view = _view(
            feed,
            calendar,
            date="2013-08-27",
            cutoff="2013-08-26",
            mapping=HK_MAP,
        )
        assert view.reference_price("TEST") is None

    def test_unmapped_and_mapped_parity_on_gap(self, env):
        feed, calendar = env
        within = {"date": "2013-08-18", "cutoff": "2013-08-17"}
        mapped = _view(feed, calendar, mapping=HK_MAP, **within)
        unmapped = _view(feed, calendar, **within)
        assert (
            mapped.reference_price("TEST")
            == unmapped.reference_price("TEST")
            == 104.0
        )

        beyond = {"date": "2013-08-27", "cutoff": "2013-08-26"}
        mapped = _view(feed, calendar, mapping=HK_MAP, **beyond)
        unmapped = _view(feed, calendar, **beyond)
        assert mapped.reference_price("TEST") is None
        assert unmapped.reference_price("TEST") is None

    def test_reference_price_at_exact_bound(self, env):
        """A gap of exactly ``max_staleness_days`` is inclusive."""
        feed, calendar = env
        # 08-22 is exactly 7 days after the last row (08-15).
        view = _view(
            feed,
            calendar,
            date="2013-08-23",
            cutoff="2013-08-22",
            mapping=HK_MAP,
        )
        assert view.reference_price("TEST") == 104.0

    def test_max_staleness_days_zero(self, env):
        """A zero bound restricts sizing to the cutoff day itself."""
        feed, calendar = env
        at_cutoff = _view(
            feed,
            calendar,
            date=ANOMALY_LOOP_DAY,
            cutoff=ANOMALY_DAY,
            max_staleness_days=0,
        )
        assert at_cutoff.reference_price("TEST") == 103.0

        gap = _view(
            feed,
            calendar,
            date="2013-08-18",
            cutoff="2013-08-17",
            max_staleness_days=0,
        )
        assert gap.reference_price("TEST") is None

    def test_negative_max_staleness_days_raises(self):
        with pytest.raises(ValueError, match="max_staleness_days"):
            DataView(
                None,
                date=ANOMALY_LOOP_DAY,
                cutoff=ANOMALY_DAY,
                max_staleness_days=-1,
            )


class TestNoFeed:
    """A view without a feed fails loudly instead of silently returning None."""

    def test_get_price_requires_a_feed(self):
        with pytest.raises(RuntimeError, match="no data feed"):
            _view(None, None).get_price("TEST", ANOMALY_DAY)

    def test_get_series_requires_a_feed(self):
        with pytest.raises(RuntimeError, match="no data feed"):
            _view(None, None).get_series("TEST")

    def test_last_valid_day_requires_a_feed(self):
        with pytest.raises(RuntimeError, match="no data feed"):
            _view(None, None).last_valid_day("TEST")


class TestLastValidDay:
    def test_mapped_ticker_uses_prev_valid_day(self, env):
        """The HK calendar closes the anomaly day, so the last valid day is 08-13."""
        feed, calendar = env
        view = _view(feed, calendar, mapping=HK_MAP)
        assert view.last_valid_day("TEST") == ANOMALY_PREV
        assert view.get_price("TEST") == 102.0

    def test_unmapped_ticker_is_data_presence_only(self, env):
        feed, calendar = env
        view = _view(feed, calendar)
        assert view.last_valid_day("TEST") == ANOMALY_DAY
        assert view.get_price("TEST") == 103.0

    def test_last_valid_day_is_clamped_to_the_cutoff(self, env):
        feed, calendar = env
        view = _view(feed, calendar, cutoff="2013-08-12", mapping=HK_MAP)
        assert view.last_valid_day("TEST") == "2013-08-12"

    def test_mapped_price_on_a_calendar_invalid_day_is_none(self, env):
        feed, calendar = env
        view = _view(feed, calendar, mapping=HK_MAP)
        assert view.get_price("TEST", ANOMALY_DAY) is None
        # Unscoped, the same request is answered from data presence.
        assert _view(feed, calendar).get_price("TEST", ANOMALY_DAY) == 103.0

    def test_no_data_at_all(self, env):
        feed, calendar = env
        view = _view(feed, calendar, mapping=HK_MAP)
        assert view.last_valid_day("NOPE") is None
        assert view.get_price("NOPE") is None


@pytest.mark.skipif(
    not (MARKET_DATA_DIR / "2800.HK_eod.csv").exists()
    or not (MARKET_DATA_DIR / "holidays" / "HK.csv").exists(),
    reason="repo market_data fixtures are not present",
)
class TestRealAnomalousDay:
    """The regression that motivated 'get_series never filters by calendar'."""

    @pytest.fixture
    def feed(self):
        return DataFeed(CsvBackend(base_dir=str(MARKET_DATA_DIR)))

    @pytest.fixture
    def view(self, feed):
        return DataView(
            feed,
            date=ANOMALY_LOOP_DAY,
            cutoff=ANOMALY_DAY,
            calendar=CalendarProvider(feed),
            ticker_to_calendar_code={"2800.HK": "HK"},
        )

    def test_the_anomaly_exists_in_the_committed_fixtures(self, feed):
        assert ANOMALY_DAY in feed.get_holiday_dates("HK")
        assert (
            ANOMALY_DAY
            in feed.get_series("eod_prices", None, None, "2800.HK").index
        )

    def test_series_keeps_the_row_the_calendar_calls_a_holiday(self, view, feed):
        series = view.get_series("2800.HK", "2013-01-01", None)
        assert ANOMALY_DAY in series.index
        assert series.index[-1] == ANOMALY_DAY  # clamped to the cutoff only
        assert series.loc[ANOMALY_DAY] == feed.get_value(
            "eod_prices", ANOMALY_DAY, "2800.HK"
        )

    def test_scoped_last_valid_day_is_the_previous_observable_day(
        self, view, feed
    ):
        assert view.last_valid_day("2800.HK") == ANOMALY_PREV
        assert view.get_price("2800.HK") == feed.get_value(
            "eod_prices", ANOMALY_PREV, "2800.HK"
        )
        # ...while an unscoped view answers from data presence, as Phase 1 did.
        unscoped = DataView(feed, date=ANOMALY_LOOP_DAY, cutoff=ANOMALY_DAY)
        assert unscoped.last_valid_day("2800.HK") == ANOMALY_DAY
