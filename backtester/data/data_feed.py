import pandas as pd


class DataFeed:
    def __init__(self, backend):
        self._backend = backend

    def get_value(
        self, dataset: str, date: str, ticker: str = None
    ) -> float | None:
        return self._backend.get_value(dataset, date, ticker)

    def get_series(
        self,
        dataset: str,
        start: str,
        end: str,
        ticker: str = None,
    ) -> pd.Series:
        return self._backend.get_series(dataset, start, end, ticker)
