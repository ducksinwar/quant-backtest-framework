import pandas as pd

from backtester.actions import (
    Action,
    ActionGroup,
    ActionType,
    ContractSpec,
    LegSpec,
    PROVENANCE_SIGNAL,
    Side,
    StructureSpec,
    TradeSpec,
)
from backtester.signals.base_signal import BaseSignal


class SMACrossoverSignal(BaseSignal):
    """Long-only SMA crossover over a fixed ticker list (the reference example).

    Per ticker, evaluated independently: emit a ``NEW`` action group when the
    short SMA is above the long SMA and the strategy holds nothing, and an
    ``UNWIND`` action group for the held structure when it crosses back below.
    Nothing else is emitted -- the signal is stateless and derives "am I in this
    position?" from the T-1 position book it is handed.

    Entry sizing converts the target notional into **fractional** shares with
    ``notional / price``, where ``price`` is
    :meth:`~backtester.data_view.DataView.reference_price` -- the T-1 reference
    close (the last observable, calendar-valid close at or before the cutoff).
    The signal holds **no market-data feed of its own**: every read goes through
    the ``DataView``.  The existing guards are preserved: a missing or
    non-positive price skips the entry, and a non-positive computed size skips
    it too (reachable only for a non-positive ``notional``).

    Calendar gating is signal-side: per ticker, the entry/unwind is skipped
    entirely unless :meth:`BaseSignal.is_tradable` says the market is open on
    the loop day.  There is no engine check stage to reject the order later,
    so emitting nothing is what keeps a closed day silent (``stderr == 0``).
    """

    def __init__(
        self,
        short_window: int,
        long_window: int,
        tickers: list[str],
        notional: float,
        ticker_currency: dict[str, str] | None = None,
        *,
        strategy_id: str,
        calendar_provider=None,
        ticker_to_calendar_code: dict[str, str] | None = None,
    ):
        super().__init__(
            strategy_id=strategy_id,
            calendar_provider=calendar_provider,
            ticker_to_calendar_code=ticker_to_calendar_code,
        )
        self.short_window = short_window
        self.long_window = long_window
        self.tickers = tickers
        self.notional = notional
        self.ticker_currency = ticker_currency or {}

    def generate_action_groups(
        self, data_view, action_group_log, position_book
    ) -> list[ActionGroup]:
        """One action group per ticker that wants a change, in ticker order.

        ``action_group_log`` is the strategy's own emission history; this signal
        is stateless and does not read it, but the interface carries it for
        cooldown / duplicate-suppression rules.
        """
        groups: list[ActionGroup] = []
        for ticker in self.tickers:
            group = self._group_for_ticker(
                ticker, data_view, position_book
            )
            if group is not None:
                groups.append(group)
        return groups

    def _group_for_ticker(
        self, ticker: str, data_view, position_book
    ) -> ActionGroup | None:
        current_date = data_view.date
        if not self.is_tradable(current_date, [ticker]):
            return None
        lookback = self.long_window + 100
        lookback_date = (
            pd.Timestamp(current_date) - pd.Timedelta(days=lookback)
        ).strftime("%Y-%m-%d")
        prev_date = (
            pd.Timestamp(current_date) - pd.Timedelta(days=1)
        ).strftime("%Y-%m-%d")

        series = data_view.get_series(ticker, lookback_date, prev_date)
        if series.empty:
            return None

        series = series.dropna()
        if len(series) < self.long_window:
            return None

        short_sma = series.rolling(window=self.short_window).mean()
        long_sma = series.rolling(window=self.long_window).mean()

        last_short = short_sma.iloc[-1]
        last_long = long_sma.iloc[-1]
        if pd.isna(last_short) or pd.isna(last_long):
            return None

        holding = position_book.find_holding(ticker)

        if last_short > last_long and holding is None:
            price = data_view.reference_price(ticker)
            if price is None or price <= 0:
                return None
            shares = self.notional / price
            if shares <= 0:
                return None
            return ActionGroup(
                action_group_id=None,
                strategy_id=self.strategy_id,
                provenance=PROVENANCE_SIGNAL,
                actions=(
                    Action(
                        type=ActionType.NEW,
                        spec=TradeSpec(
                            structures=(
                                StructureSpec(
                                    legs=(
                                        LegSpec(
                                            contract_spec=self._long_spec(
                                                ticker
                                            ),
                                            side=Side.LONG,
                                            size=shares,
                                        ),
                                    ),
                                ),
                            ),
                            tags=(
                                f"short_ma:{last_short:.2f}",
                                f"long_ma:{last_long:.2f}",
                            ),
                        ),
                    ),
                ),
            )

        if last_short <= last_long and holding is not None:
            # The holding carries both addresses; pass them explicitly so the
            # converter never has to resolve the trade from the book.
            return ActionGroup(
                action_group_id=None,
                strategy_id=self.strategy_id,
                provenance=PROVENANCE_SIGNAL,
                actions=(
                    Action(
                        type=ActionType.UNWIND,
                        trade_id=holding.trade_id,
                        structure_id=holding.structure_id,
                    ),
                ),
            )

        return None

    def _long_spec(self, ticker: str) -> ContractSpec:
        """The spec a new long leg opens with."""
        return ContractSpec(
            ticker=ticker,
            asset_class="equity",
            currency=self.ticker_currency.get(ticker, "USD"),
        )
