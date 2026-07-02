import numpy as np
import pandas as pd

from backtester.signals.base_signal import BaseSignal


class SMACrossoverSignal(BaseSignal):
    requires_portfolio_state = True

    def __init__(
        self,
        short_window: int,
        long_window: int,
        tickers: list[str],
        notional: float,
        data_feed,
    ):
        self.short_window = short_window
        self.long_window = long_window
        self.tickers = tickers
        self.notional = notional
        self._data_feed = data_feed

    def generate_signals(
        self,
        current_date: str,
        portfolio_state: object | None = None,
        trade_history_snapshot: tuple | None = None,
    ) -> list[dict]:
        orders: list[dict] = []
        for ticker in self.tickers:
            order = self._generate_for_ticker(ticker, current_date, portfolio_state)
            if order is not None:
                orders.append(order)
        return orders

    def _generate_for_ticker(
        self, ticker: str, current_date: str, portfolio_state
    ) -> dict | None:
        lookback = self.long_window + 100
        lookback_date = (
            pd.Timestamp(current_date) - pd.Timedelta(days=lookback)
        ).strftime("%Y-%m-%d")
        prev_date = (
            pd.Timestamp(current_date) - pd.Timedelta(days=1)
        ).strftime("%Y-%m-%d")

        series = self._data_feed.get_series(
            "eod_prices", lookback_date, prev_date, ticker
        )
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

        in_position = self._is_in_position(portfolio_state, ticker)

        if last_short > last_long and not in_position:
            price = self._data_feed.get_value("eod_prices", current_date, ticker)
            if price is None or price <= 0:
                return None
            shares = int(self.notional / price)
            if shares <= 0:
                return None
            return {
                "Action": "NEW",
                "trade_id": None,
                "info": [
                    {
                        "structure_id": None,
                        "legs": [{"ticker": ticker, "size": shares}],
                    }
                ],
            }

        if last_short <= last_long and in_position:
            trade_id = self._find_trade_id_for_ticker(portfolio_state, ticker)
            return {
                "Action": "UNWIND",
                "trade_id": trade_id,
                "info": [],
            }

        return None

    def _is_in_position(self, portfolio_state, ticker: str) -> bool:
        if portfolio_state is None:
            return False

        for trade in getattr(portfolio_state, "trades", []):
            for structure in getattr(trade, "structures", []):
                for leg in getattr(structure, "legs", []):
                    if getattr(leg, "ticker", None) == ticker:
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
