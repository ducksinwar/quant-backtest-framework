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
        start: str | None,
        end: str | None,
        ticker: str = None,
        **params,
    ) -> pd.Series:
        return self._backend.get_series(dataset, start, end, ticker, **params)

    def get_holiday_dates(self, code: str) -> frozenset[str]:
        """Holiday dates for calendar *code* (see ``CalendarProvider``, §3.5).

        Unlike ``get_value`` / ``get_series`` -- which return empty results for
        an unknown ticker and let the NaN/missing-data mechanics absorb it --
        this raises ``FileNotFoundError`` for an unknown code: a calendar code
        is a configuration identifier, not a ticker to degrade on.
        """
        return self._backend.get_holiday_dates(code)
