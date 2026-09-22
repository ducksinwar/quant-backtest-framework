import os
import warnings

import pandas as pd


class CsvBackend:
    def __init__(self, base_dir: str):
        self._base_dir = base_dir
        # Price series and holiday sets are cached in *separate* namespaces.
        # The separation is structural, not conventional: a ticker and a
        # calendar code may legitimately have the same name (``DE`` is both
        # Deere on the NYSE and the German calendar code), so a shared dict
        # would let one dataset return the other's object.
        self._price_cache: dict[str, pd.Series | None] = {}
        self._holiday_cache: dict[str, frozenset[str]] = {}
        self._warned_holiday_files: set[str] = set()

    def _load_csv(self, ticker: str) -> pd.Series | None:
        if ticker in self._price_cache:
            return self._price_cache[ticker]

        filename = f"{ticker}_eod.csv"
        filepath = os.path.join(self._base_dir, filename)
        try:
            df = pd.read_csv(filepath, parse_dates=["date"])
        except FileNotFoundError:
            self._price_cache[ticker] = None
            return None

        df["date"] = df["date"].dt.strftime("%Y-%m-%d")
        series = pd.Series(df["close"].values, index=df["date"])
        self._price_cache[ticker] = series
        return series

    def _load_holidays(self, code: str) -> frozenset[str]:
        """Holiday dates for *code* from ``{base_dir}/holidays/{CODE}.csv``.

        Mirrors ``_load_csv``: the backend owns the storage-path convention, the
        parsing and the per-code cache.  Unlike the price loaders there is no
        "missing means empty" branch -- a requested calendar code whose file
        does not exist raises ``FileNotFoundError`` naming the code and the
        expected path, because calendar codes are configuration identifiers and
        a typo must fail loudly rather than silently produce business days.
        """
        if code in self._holiday_cache:
            return self._holiday_cache[code]

        filepath = os.path.join(self._base_dir, "holidays", f"{code}.csv")
        try:
            df = pd.read_csv(filepath)
        except FileNotFoundError:
            raise FileNotFoundError(
                f"No holiday calendar file for code {code!r}: expected "
                f"'{filepath}'. Check the code for typos or add the file."
            ) from None

        if "date" not in df.columns:
            raise ValueError(
                f"Holiday file '{filepath}' has no 'date' column "
                f"(found columns: {list(df.columns)})."
            )
        if df["date"].isna().any():
            raise ValueError(
                f"Holiday file '{filepath}' has empty date cell(s); every row "
                f"must name a holiday as YYYY-MM-DD. A null cell would become "
                f"an inert entry that never matches a real date."
            )

        extra_columns = [c for c in df.columns if c != "date"]
        if extra_columns and filepath not in self._warned_holiday_files:
            self._warned_holiday_files.add(filepath)
            warnings.warn(
                f"Holiday file '{filepath}' contains additional column(s) "
                f"{extra_columns} that are not consumed in Phase 2 "
                f"(reserved for future half-day/hours support).",
                # The stack at warn time is:
                #   _load_holidays(1) -> CsvBackend.get_holiday_dates(2)
                #   -> DataFeed.get_holiday_dates(3) -> provider method(4)
                #   -> caller(5)
                # stacklevel=4 attributes the warning to the provider method,
                # which is the stable boundary: anything deeper varies with the
                # consumer, and stacklevel=2 would blame this backend method.
                stacklevel=4,
            )

        # The `date` column is read by name, never by position.
        normalized = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
        holidays = frozenset(normalized)
        self._holiday_cache[code] = holidays
        return holidays

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

    def get_series(
        self,
        dataset: str,
        start: str | None,
        end: str | None,
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
        if start is None and end is None:
            return series
        return series.loc[start:end]

    def get_holiday_dates(self, code: str) -> frozenset[str]:
        """Full holiday set for calendar *code* (``{base_dir}/holidays/{CODE}.csv``).

        Returns a ``frozenset`` so a caller cannot mutate the cached set.  In
        Phase 2 the whole file is returned; point-in-time vintages would add an
        ``as_of`` parameter here rather than a new dataset name.
        """
        return self._load_holidays(code)
