from __future__ import annotations

import pandas as pd


class FxRateProvider:
    """Typed provider wrapping a DataFeed for daily FX spot rates.

    Caches the full derived conversion factor series per currency pair
    (direct -> inverse -> USD triangulation), keyed by ``(from, to)`` and
    independent of any simulation window. Slices on cache hits.

    FX data lives in ``market_data/`` under the standard pair convention
    (e.g. ``EURUSD_eod.csv``) and is served by the DataFeed under the
    ``"eod_prices"`` dataset with the pair name as the ticker. The pair
    convention is ``{from}{to}`` -- e.g. ``EURUSD`` is the amount of USD
    per 1 EUR. No backend changes are required.

    Conversion lookup order:
      1. from == to              -> 1.0
      2. direct pair {from}{to}  -> rate (amount of ``to`` per 1 ``from``)
      3. inverse pair {to}{from} -> 1.0 / rate
      4. USD triangulation       -> factor(from, USD) * factor(USD, to)
      5. missing rate            -> None
    """

    def __init__(self, data_feed):
        self._data_feed = data_feed
        self._factor_cache: dict[tuple[str, str], pd.Series] = {}
        self._missing_pairs: set[tuple[str, str]] = set()

    def get_conversion_factor(
        self, from_currency: str, to_currency: str, date: str
    ) -> float | None:
        """Point lookup: amount of *to_currency* per 1 unit of *from_currency*."""
        if from_currency == to_currency:
            return 1.0
        factor = self._get_factor_series(from_currency, to_currency)
        if factor is None:
            return None
        try:
            return float(factor.loc[date])
        except KeyError:
            return None

    def get_conversion_series(
        self,
        from_currency: str,
        to_currency: str,
        start: str,
        end: str,
    ) -> pd.Series | None:
        """Vectorized conversion series over the ``(start, end)`` range.

        Returns ``None`` when the pair is entirely unavailable (missing file)
        so the caller can skip conversion for the leg. Present-but-gappy data
        is returned with NaN so the caller's forward-fill handles the gaps.
        No day-by-day looping -- all pair resolution is vectorized.
        """
        if from_currency == to_currency:
            return pd.Series(1.0, index=self._range_index(start, end))
        factor = self._get_factor_series(from_currency, to_currency)
        if factor is None:
            return None
        return factor.loc[start:end].reindex(self._range_index(start, end))

    def _get_factor_series(
        self, from_currency: str, to_currency: str
    ) -> pd.Series | None:
        """Cached full derived factor series for the pair; None if missing."""
        key = (from_currency, to_currency)
        if key in self._factor_cache:
            return self._factor_cache[key]
        if key in self._missing_pairs:
            return None

        factor = self._try_full_direct_or_inverse(from_currency, to_currency)
        if factor is None:
            usd_from = self._try_full_direct_or_inverse(from_currency, "USD")
            to_usd = self._try_full_direct_or_inverse("USD", to_currency)
            if usd_from is None or to_usd is None:
                self._missing_pairs.add(key)
                return None
            factor = usd_from * to_usd

        self._factor_cache[key] = factor
        return factor

    def _try_full_direct_or_inverse(
        self, from_currency: str, to_currency: str
    ) -> pd.Series | None:
        """Direct/inverse on the full available range; never triangulates."""
        direct = self._data_feed.get_series(
            "eod_prices", None, None, f"{from_currency}{to_currency}"
        )
        if len(direct) > 0:
            return direct
        inverse = self._data_feed.get_series(
            "eod_prices", None, None, f"{to_currency}{from_currency}"
        )
        if len(inverse) > 0:
            return 1.0 / inverse
        return None

    @staticmethod
    def _range_index(start: str, end: str) -> pd.Index:
        return pd.Index(
            pd.bdate_range(start, end).strftime("%Y-%m-%d"), dtype=object
        )
