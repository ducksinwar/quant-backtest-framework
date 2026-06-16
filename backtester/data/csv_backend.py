import os

import pandas as pd


class CsvBackend:
    def __init__(self, base_dir: str):
        self._base_dir = base_dir
        self._cache: dict[str, pd.Series] = {}

    def _load_csv(self, ticker: str) -> pd.Series | None:
        if ticker in self._cache:
            return self._cache[ticker]

        filename = f"{ticker}_eod.csv"
        filepath = os.path.join(self._base_dir, filename)
        try:
            df = pd.read_csv(filepath, parse_dates=["date"])
        except FileNotFoundError:
            self._cache[ticker] = None
            return None

        df["date"] = df["date"].dt.strftime("%Y-%m-%d")
        series = pd.Series(df["close"].values, index=df["date"])
        self._cache[ticker] = series
        return series

    def get_value(
        self, dataset: str, date: str, ticker: str = None, **params
    ) -> float | None:
        if dataset != "eod_prices":
            return None
        if ticker is None:
            return None

        series = self._load_csv(ticker)
        if series is None:
            return None
        try:
            val = series.loc[date]
            return float(val)
        except KeyError:
            return None

    def trading_days(self, ticker: str, start: str, end: str) -> list[str]:
        series = self._load_csv(ticker)
        if series is None:
            return []
        mask = (series.index >= start) & (series.index <= end)
        return [str(d) for d in series.index[mask]]

    def get_series(
        self,
        dataset: str,
        start: str,
        end: str,
        ticker: str = None,
        **params,
    ) -> pd.Series:
        if dataset != "eod_prices":
            return pd.Series(dtype=float)
        if ticker is None:
            return pd.Series(dtype=float)

        series = self._load_csv(ticker)
        if series is None:
            return pd.Series(dtype=float)
        return series.loc[start:end]
