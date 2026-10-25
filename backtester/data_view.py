"""A truncated, T-1-clamped view of market data.

A :class:`DataView` is built once per loop day for the day ``T`` with
``cutoff = T - 1`` (the calendar day before ``T``), and is the only data handle
a signal receives.  Two rules make the no-look-ahead convention structural:

* ``get_price`` **raises** when asked for an ``as_of`` after the cutoff.  The
  loop day's own close is not observable through the view.
* ``get_series`` **clamps ``end`` down to the cutoff**.  ``start`` is never
  clamped: a strategy's pre-backtest lookback must keep working, and a ``start``
  before the instrument's first data point simply returns the shorter available
  series (the ``Series.loc[start:end]`` behaviour -- no raise).
* :meth:`DataView.reference_price` is the sizing read -- the last observable
  close at or before the cutoff, **bounded by ``max_staleness_days``**.  It
  never reads the loop day's own data.  A gap longer than the bound resolves
  to ``None``, which the caller's price guard handles.

Terminology: **T-1** means the *calendar day before T* -- the cutoff, a
structural bound -- and is not the same thing as an instrument's **previous
observable day** (:meth:`DataView.last_valid_day`), which can be several
calendar days earlier when the market was closed.

Per-instrument calendar scoping
-------------------------------
``ticker_to_calendar_code`` (``BacktestConfig``) maps a ticker to its holiday
calendar code.  Scoping applies **only to ``as_of`` / last-valid-day
resolution**: for a mapped ticker, ``last_valid_day`` is the last day the
instrument's calendar considers valid before the loop day, and an explicit
``as_of`` on a calendar-invalid day resolves to ``None`` (no observation).
An unmapped ticker gets no calendar scoping at all -- data presence only.

``get_price`` and ``last_valid_day`` keep their pre-staleness semantics: a
mapped ticker's ``as_of=None`` read resolves to its last calendar-valid day and
does **not** bridge a data gap at that day.  ``reference_price`` -- the sizing
read, not a general price read -- is the only place a gap is bridged: when the
resolved day has no data row it scans back for the last data row at or before
the cutoff regardless of calendar, so mapped and unmapped tickers size
identically across a gap.  The staleness bound is then applied to that day.

``get_series`` deliberately does **not** consult the calendar.  Clamping a
series to ``prev_valid_day`` would drop rows the data path keeps: in the
committed ``market_data/`` fixtures there are days (e.g. 2800.HK 2013-08-14,
SXRT.DE 2015-12-25) where a price row exists on a day the holiday file lists as
a holiday, and dropping such a row shifts the moving averages -- and therefore
the emitted signals.  Series rows are end-clamped to the cutoff and nothing
else.
"""

from __future__ import annotations

import datetime


class DataViewCutoffError(ValueError):
    """A caller asked for data at or after the loop day."""


class DataView:
    """Market data as of the previous day, for one loop day."""

    def __init__(
        self,
        data_feed,
        *,
        date: str,
        cutoff: str,
        calendar=None,
        dataset: str = "eod_prices",
        ticker_to_calendar_code: dict[str, str] | None = None,
        max_staleness_days: int = 7,
    ):
        if not isinstance(date, str) or not date:
            raise ValueError("DataView.date must be a non-empty ISO date string")
        if not isinstance(cutoff, str) or not cutoff:
            raise ValueError(
                "DataView.cutoff must be a non-empty ISO date string"
            )
        if cutoff >= date:
            raise ValueError(
                f"DataView cutoff {cutoff!r} is not before the loop day "
                f"{date!r}; a view may never expose the loop day's own data"
            )
        self._feed = data_feed
        self._date = date
        self._cutoff = cutoff
        self._calendar = calendar
        self._dataset = dataset
        self._ticker_to_calendar_code = dict(ticker_to_calendar_code or {})
        if max_staleness_days < 0:
            raise ValueError(
                f"DataView.max_staleness_days must be >= 0, got "
                f"{max_staleness_days!r}"
            )
        self._max_staleness_days = max_staleness_days

    # --- identity -------------------------------------------------------

    @property
    def date(self) -> str:
        """The loop day ``T`` (context only -- never a data entitlement)."""
        return self._date

    @property
    def cutoff(self) -> str:
        """The last date this view may expose (``T - 1``)."""
        return self._cutoff

    @property
    def dataset(self) -> str:
        return self._dataset

    def calendar_code_for(self, ticker: str) -> str | None:
        """The ticker's calendar code, or ``None`` when unmapped."""
        return self._ticker_to_calendar_code.get(ticker)

    # --- data access ----------------------------------------------------

    def _require_feed(self):
        if self._feed is None:
            raise RuntimeError(
                "DataView has no data feed (BacktestConfig.data_feed is "
                "None); market data is not available to this signal"
            )

    def last_valid_day(self, ticker: str) -> str | None:
        """Last date at which *ticker* may be observed through this view.

        Mapped tickers resolve through ``CalendarProvider.prev_valid_day`` (the
        last calendar-valid day strictly before the loop day), clamped to the
        cutoff; unmapped tickers fall back to data presence -- the last row at
        or before the cutoff.
        """
        self._require_feed()
        code = self.calendar_code_for(ticker)
        if code is not None and self._calendar is not None:
            return min(self._calendar.prev_valid_day(code, self._date), self._cutoff)

        series = self._feed.get_series(self._dataset, None, self._cutoff, ticker)
        if series is None or len(series) == 0:
            return None
        return str(series.index[-1])

    def get_price(self, ticker: str, as_of: str | None = None) -> float | None:
        """One price observation, ``as_of=None`` meaning the last valid day.

        Raises :class:`DataViewCutoffError` when ``as_of`` is after the cutoff.
        For a mapped ticker an ``as_of`` on a calendar-invalid day has no
        observation and returns ``None``.
        """
        self._require_feed()
        if as_of is None:
            as_of = self.last_valid_day(ticker)
            if as_of is None:
                return None
        as_of = str(as_of)
        if as_of > self._cutoff:
            raise DataViewCutoffError(
                f"get_price({ticker!r}, {as_of!r}) is beyond the data view "
                f"cutoff {self._cutoff!r}: the loop day's own data is not "
                f"visible to a signal"
            )

        code = self.calendar_code_for(ticker)
        if code is not None and self._calendar is not None:
            if not self._calendar.is_valid_day(code, as_of):
                return None
        return self._feed.get_value(self._dataset, as_of, ticker)

    def get_series(
        self, ticker: str, start: str | None = None, end: str | None = None
    ):
        """The instrument's series, end-clamped to the cutoff.

        ``start`` is passed through untouched (a pre-backtest lookback is the
        caller's business) and rows are never filtered by calendar -- only the
        end of the window is clamped.  A window that starts before the
        instrument's first data point returns the shorter available series, and
        a window entirely beyond the cutoff is simply empty.
        """
        self._require_feed()
        clamped_end = self._cutoff if end is None else min(str(end), self._cutoff)
        return self._feed.get_series(
            self._dataset, start, clamped_end, ticker
        )

    def reference_price(self, ticker: str) -> float | None:
        """The **T-1 reference close** used for sizing.

        The last observable close at or before the construction-validated
        cutoff, **bounded by** ``max_staleness_days`` (default 7): a gap beyond
        the bound resolves to ``None`` and the caller's price guard handles it.

        Resolution starts from :meth:`last_valid_day` (calendar-valid for a
        mapped ticker, data-presence otherwise).  If that day has no data row --
        the mapped-ticker gap case -- resolution falls back to the last data row
        at or before the cutoff **regardless of calendar**, so mapped and
        unmapped tickers size identically across a gap.  The staleness bound is
        applied to whatever day the scan lands on.

        Two guarantees are structural, not conventional:

        * The loop day's own close is unreachable: construction rejects a
          ``cutoff`` on or after ``date``, and resolution never scans beyond the
          cutoff, so ``reference_price`` cannot return T's row even when one
          exists in the feed.
        * ``None`` has exactly two causes: there is no observation at or before
          the cutoff, or the last observation is more than
          ``max_staleness_days`` before it.
        """
        day = self.last_valid_day(ticker)
        if day is None:
            return None
        value = self._feed.get_value(self._dataset, day, ticker)
        if value is None:
            day = self._last_data_day_at_or_before_cutoff(ticker)
            if day is None:
                return None
            value = self._feed.get_value(self._dataset, day, ticker)
        staleness = (
            datetime.date.fromisoformat(str(self._cutoff)[:10])
            - datetime.date.fromisoformat(str(day)[:10])
        ).days
        if staleness > self._max_staleness_days:
            return None
        return value

    def _last_data_day_at_or_before_cutoff(self, ticker: str) -> str | None:
        """The last data row at or before the cutoff, ignoring the calendar."""
        series = self._feed.get_series(
            self._dataset, None, self._cutoff, ticker
        )
        if series is None or len(series) == 0:
            return None
        return str(series.index[-1])
