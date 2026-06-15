import numpy as np
import pandas as pd

from backtester.signals.base_signal import BaseSignal


class SMACrossoverSignal(BaseSignal):
    requires_portfolio_state = True

    def __init__(
        self,
        short_window: int,
        long_window: int,
        ticker: str,
        size: float,
        data_feed,
    ):
        self.short_window = short_window
        self.long_window = long_window
        self.ticker = ticker
        self.size = size
        self._data_feed = data_feed

    def generate_signals(
        self,
        current_date: str,
        portfolio_state: object | None = None,
        trade_history_snapshot: tuple | None = None,
    ) -> list[dict]:
        lookback = self.long_window + 100
        lookback_date = (
            pd.Timestamp(current_date) - pd.Timedelta(days=lookback)
        ).strftime("%Y-%m-%d")
        prev_date = (
            pd.Timestamp(current_date) - pd.Timedelta(days=1)
        ).strftime("%Y-%m-%d")

        series = self._data_feed.get_series(
            "eod_prices", lookback_date, prev_date, self.ticker
        )
        if series.empty:
            return []

        series = series.dropna()
        if len(series) < self.long_window:
            return []

        short_sma = series.rolling(window=self.short_window).mean()
        long_sma = series.rolling(window=self.long_window).mean()

        last_short = short_sma.iloc[-1]
        last_long = long_sma.iloc[-1]
        if pd.isna(last_short) or pd.isna(last_long):
            return []

        in_position = self._is_in_position(portfolio_state)

        if last_short > last_long and not in_position:
            return [
                {
                    "Action": "NEW",
                    "trade_id": None,
                    "info": [
                        {
                            "structure_id": None,
                            "legs": [
                                {"ticker": self.ticker, "size": self.size}
                            ],
                        }
                    ],
                }
            ]

        if last_short <= last_long and in_position:
            trade_id = self._find_trade_id_for_ticker(portfolio_state, self.ticker)
            return [
                {
                    "Action": "UNWIND",
                    "trade_id": trade_id,
                    "info": [],
                }
            ]

        return []

    def _is_in_position(self, portfolio_state) -> bool:
        if portfolio_state is None:
            return False

        for trade in getattr(portfolio_state, "trades", []):
            for structure in getattr(trade, "structures", []):
                for leg in getattr(structure, "legs", []):
                    if getattr(leg, "ticker", None) == self.ticker:
                        return True
        return False

    def _find_trade_id_for_ticker(self, portfolio_state, ticker: str) -> str | None:
        if portfolio_state is None:
            return None

        for trade in getattr(portfolio_state, "trades", []):
            for structure in getattr(trade, "structures", []):
                for leg in getattr(structure, "legs", []):
                    if getattr(leg, "ticker", None) == ticker:
                        return getattr(trade, "trade_id", None)
        return None
