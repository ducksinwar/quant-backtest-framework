import pandas as pd


class DataFeed:
    def __init__(self, backend):
        self._backend = backend

    def get_value(
        self, dataset: str, date: str, ticker: str = None, **params
    ) -> float | None:
        return self._backend.get_value(dataset, date, ticker, **params)

    def get_series(
        self,
        dataset: str,
        start: str,
        end: str,
        ticker: str = None,
        **params,
    ) -> pd.Series:
        return self._backend.get_series(dataset, start, end, ticker, **params)

    def trading_days(self, ticker: str, start: str, end: str) -> list[str]:
        return self._backend.trading_days(ticker, start, end)
