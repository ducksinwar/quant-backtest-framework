"""The signal interface: strategies emit action groups, never orders."""

from __future__ import annotations

from abc import ABC, abstractmethod

from backtester.action_group_log import ActionGroupLogView
from backtester.actions import ActionGroup
from backtester.calendar_provider import CalendarProvider
from backtester.data_view import DataView
from backtester.position_books import PositionBook


class BaseSignal(ABC):
    """Abstract strategy: one ``generate_action_groups`` call per loop day.

    A signal is stateless and order-unaware.  It reads market data only through
    the T-1-clamped :class:`DataView`, its own emission history through the
    :class:`ActionGroupLogView` and its positions through the
    :class:`PositionBook`; it returns :class:`ActionGroup` objects.  It must not
    build orders (synthesis does that) and must not set ``action_group_id`` /
    ``emission_date`` (the log stamps both at emission).

    A signal is calendar-aware **only for tradability**: it never rejects an
    order (the engine has no check stage), so it emits nothing at all on a day
    its instrument's market is closed.  Calendar access is optional: a signal
    constructed without a provider is calendar-blind, which is the honest
    default for a strategy that does not declare a market.

    ``strategy_id`` is a required constructor argument: it keys the action-group
    log's per-strategy index and is carried on every emitted group.
    """

    def __init__(
        self,
        strategy_id: str,
        *,
        calendar_provider: CalendarProvider | None = None,
        ticker_to_calendar_code: dict[str, str] | None = None,
    ) -> None:
        if not isinstance(strategy_id, str) or not strategy_id:
            raise ValueError(
                "BaseSignal requires a non-empty strategy_id: it keys the "
                "action-group log and every emitted group"
            )
        self.strategy_id = strategy_id
        self._calendar = calendar_provider
        self._ticker_to_calendar_code = dict(ticker_to_calendar_code or {})

    def is_tradable(self, date: str, tickers: list[str]) -> bool:
        """True iff every ticker's market is open on ``date``.

        Unmapped tickers: **fail-closed** when a provider is configured -- a
        ticker with no calendar code raises ``ValueError`` rather than being
        treated as tradable.  Fail-closed is what keeps ``stderr == 0``: a
        silently-passed unmapped ticker could emit on a closed market and
        produce an execution-side data warning.  A missing code is a
        configuration error and must fail loudly.

        With no ``calendar_provider`` (the default) the signal is
        calendar-blind: every date is tradable and the mapping is not consulted.
        The mapping is copied at construction.
        """
        if self._calendar is None:
            return True
        for ticker in tickers:
            code = self._ticker_to_calendar_code.get(ticker)
            if code is None:
                raise ValueError(
                    f"no calendar code for ticker {ticker!r}: a signal "
                    f"constructed with a calendar provider must map every "
                    f"ticker it trades (fail-closed)"
                )
            if not self._calendar.is_valid_day(code, date):
                return False
        return True

    @abstractmethod
    def generate_action_groups(
        self,
        data_view: DataView,
        action_group_log: ActionGroupLogView,
        position_book: PositionBook,
    ) -> list[ActionGroup]:
        ...
