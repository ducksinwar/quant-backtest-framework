"""Calendar math over holiday dates served by the data layer.

The provider is **I/O-free**: it holds no directory, no file handles and no
cache.  All holiday data is fetched from a ``DataFeed`` (§3.4), which delegates
to its swappable backend -- the same contract that serves price series.  Every
public method is therefore a pure function of its arguments plus the feed, and
all three are controlled exclusively by the *call-time* declaration (the codes
passed in), never by construction state.

This module deliberately imports no pandas: the only date arithmetic it needs is
day-level, and ``datetime`` keeps the provider's dependency surface identical to
the rest of the engine core.
"""

from __future__ import annotations

import datetime

#: Opaque calendar code meaning "every calendar day is valid".
ALL_CODE = "all"

#: ``next_valid_day`` gives up after this many days and raises ``RuntimeError``.
_MAX_LOOKAHEAD_DAYS = 1000


def _calendar_day(value: str) -> datetime.date:
    """Normalize *value* to a calendar day, truncating any time component.

    The single normalization point for this module: both ``is_valid_day`` and
    ``next_valid_day`` parse their input exactly once, here.  Anything ISO-like
    is accepted -- ``"2024-01-04"``, ``"2024-01-04 23:00:00"``, a
    timezone-suffixed timestamp -- because only the leading ``YYYY-MM-DD`` is
    significant.  The truncation of the time component is explicit rather than
    incidental.
    """
    return datetime.date.fromisoformat(str(value)[:10])


class CalendarProvider:
    """Shared service that resolves trading-day calendars.

    Calendars are identified by opaque *holiday codes* (Bloomberg-style, e.g.
    ``"US"``, ``"HK"``).  Each code maps to a set of full non-trading days
    served by the ``DataFeed``'s backend (``get_holiday_dates``).  The two
    per-code primitives are called ``is_valid_day`` / ``next_valid_day`` because
    the same methods will serve trading, settlement and fixing calendars alike,
    while the union method keeps the name ``trading_days`` because it produces
    the simulation calendar consumed by ``BacktestResult.trading_days`` /
    ``Summary``.

    There is no "no-holidays" mode: an unknown or empty code fails loudly with
    ``FileNotFoundError`` rather than silently degrading to business days.
    Passing ``None`` / ``[]`` to ``trading_days`` is an explicit *declaration*
    that this run has no holiday calendars -- it is not a fallback.
    """

    def __init__(self, data_feed):
        self._feed = data_feed

    # --- public API -----------------------------------------------------

    def trading_days(
        self, holiday_codes: list[str] | None, start: str, end: str
    ) -> list[str]:
        """Union simulation calendar over ``[start, end]`` (both inclusive).

        * ``"all"`` present        -> every calendar day in range (weekends
          included).  Short-circuits before any holiday lookup, so ``all.csv``
          is never requested and ``"all"`` is never modelled as an empty
          holiday set (which would wrongly drop weekends).
        * ``None`` or ``[]``       -> all Mon-Fri business days in range.  An
          explicit "no holiday calendars" declaration: no warning.
        * otherwise                -> union of the codes' trading days, i.e.
          business days minus the *intersection* of their holiday sets.  A day
          is dropped only if it is a holiday in *every* listed code.  A holiday
          that falls on a weekend is naturally ignored because it is not in the
          business-day base.

        Returns sorted ``YYYY-MM-DD`` strings; ``[]`` when the range is empty.
        """
        start_day = _calendar_day(start)
        end_day = _calendar_day(end)

        if holiday_codes and ALL_CODE in holiday_codes:
            return _day_strings(start_day, end_day)

        days = [d for d in _day_strings(start_day, end_day) if _is_business_day(d)]
        if not holiday_codes:
            return days

        holiday_sets = [self._feed.get_holiday_dates(code) for code in holiday_codes]
        common_holidays = set(holiday_sets[0]).intersection(*holiday_sets[1:])
        return [d for d in days if d not in common_holidays]

    def is_valid_day(self, holiday_code: str, date: str) -> bool:
        """Whether ``date`` is a valid day for a single calendar code.

        ``"all"`` is always valid.  Otherwise the code's holiday set is
        resolved **first** and the weekday/membership test happens after it, so
        an unknown or empty code raises ``FileNotFoundError`` on *any* input
        date -- including a weekend, which would otherwise short-circuit to
        ``False`` and mask a configuration typo.
        """
        if holiday_code == ALL_CODE:
            return True

        holidays = self._feed.get_holiday_dates(holiday_code)
        day = _calendar_day(date)
        if day.weekday() >= 5:
            return False
        return day.isoformat() not in holidays

    def next_valid_day(self, holiday_code: str, date: str) -> str:
        """First valid day strictly after ``date`` for a single code.

        ``"all"`` -> the next calendar day.  Otherwise the code's holiday set is
        resolved **before** any day is examined (same fail-loud ordering as
        ``is_valid_day``), then advance day by day until a Mon-Fri non-holiday
        is found.  Raises ``RuntimeError`` if no valid day is found within
        ``_MAX_LOOKAHEAD_DAYS`` days, so a malformed or empty calendar cannot
        loop forever.
        """
        start_day = _calendar_day(date)
        if holiday_code == ALL_CODE:
            return (start_day + datetime.timedelta(days=1)).isoformat()

        holidays = self._feed.get_holiday_dates(holiday_code)
        current = start_day
        for _ in range(_MAX_LOOKAHEAD_DAYS):
            current = current + datetime.timedelta(days=1)
            if current.weekday() < 5 and current.isoformat() not in holidays:
                return current.isoformat()

        raise RuntimeError(
            f"next_valid_day could not find a valid day for calendar "
            f"{holiday_code!r} within {_MAX_LOOKAHEAD_DAYS} days after "
            f"{start_day.isoformat()!r}; the calendar is malformed or "
            f"effectively empty."
        )


# --- module-level helpers ------------------------------------------------

def _day_strings(start: datetime.date, end: datetime.date) -> list[str]:
    """Every calendar day in ``[start, end]`` as ``YYYY-MM-DD``.

    Returns ``[]`` when ``start > end``.
    """
    if start > end:
        return []
    return [
        (start + datetime.timedelta(days=offset)).isoformat()
        for offset in range((end - start).days + 1)
    ]


def _is_business_day(day: str) -> bool:
    """Mon-Fri test on a normalized ``YYYY-MM-DD`` string."""
    return _calendar_day(day).weekday() < 5
