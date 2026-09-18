import pandas as pd
import pytest
from backtester.data.typed_providers.fx_rate_provider import FxRateProvider


class _MockFeed:
    """In-memory DataFeed stand-in backed by a dict of ticker -> Series."""

    def __init__(self, data: dict[str, pd.Series]):
        self._data = data

    def get_value(self, dataset, date, ticker=None, **params):
        series = self._data.get(ticker)
        if series is None or date not in series.index:
            return None
        return float(series.loc[date])

    def get_series(self, dataset, start=None, end=None, ticker=None, **params):
        series = self._data.get(ticker)
        if series is None:
            return pd.Series(dtype=float)
        if start is None and end is None:
            return series
        return series.loc[start:end]


def _daily(values: list[float], start="2024-01-01"):
    idx = pd.bdate_range(start, periods=len(values))
    return pd.Series(values, index=idx.strftime("%Y-%m-%d"))


@pytest.fixture
def provider():
    feed = _MockFeed({
        "EURUSD": _daily([1.10, 1.12, 1.11, 1.13]),
        "USDHKD": _daily([7.80, 7.81, 7.79, 7.82]),
        "USDJPY": _daily([118.0, 117.0, 116.0, 117.5]),
    })
    return FxRateProvider(feed)


class TestGetConversionFactor:
    def test_same_currency(self, provider):
        assert provider.get_conversion_factor("USD", "USD", "2024-01-02") == 1.0

    def test_direct_pair(self, provider):
        assert provider.get_conversion_factor(
            "EUR", "USD", "2024-01-02"
        ) == pytest.approx(1.12)

    def test_inverse_pair(self, provider):
        # USDHKD at 2024-01-03 (index 2) is 7.79; HKD -> USD = 1 / 7.79
        assert provider.get_conversion_factor(
            "HKD", "USD", "2024-01-03"
        ) == pytest.approx(1.0 / 7.79)

    def test_usd_triangulation(self, provider):
        # USDJPY at 2024-01-03 (index 2) is 116.0; USDHKD is 7.79.
        expected = (1.0 / 116.0) * 7.79
        assert provider.get_conversion_factor(
            "JPY", "HKD", "2024-01-03"
        ) == pytest.approx(expected)

    def test_missing_rate_returns_none(self, provider):
        assert provider.get_conversion_factor(
            "GBP", "USD", "2024-01-03"
        ) is None


class TestGetConversionSeries:
    def test_direct_pair_series(self, provider):
        s = provider.get_conversion_series("EUR", "USD", "2024-01-02", "2024-01-04")
        assert s.tolist() == pytest.approx([1.12, 1.11, 1.13])

    def test_inverse_pair_series(self, provider):
        s = provider.get_conversion_series("HKD", "USD", "2024-01-02", "2024-01-04")
        assert s.tolist() == pytest.approx([1.0 / 7.81, 1.0 / 7.79, 1.0 / 7.82])

    def test_triangulated_series(self, provider):
        s = provider.get_conversion_series("JPY", "HKD", "2024-01-02", "2024-01-04")
        # USDJPY at 01-02..01-04 = [117.0, 116.0, 117.5];
        # USDHKD at 01-02..01-04 = [7.81, 7.79, 7.82].
        usd_jpy = _daily([118.0, 117.0, 116.0, 117.5]).loc["2024-01-02":"2024-01-04"]
        usd_hkd = _daily([7.80, 7.81, 7.79, 7.82]).loc["2024-01-02":"2024-01-04"]
        expected = (1.0 / usd_jpy) * usd_hkd
        assert s.tolist() == pytest.approx(expected.tolist())

    def test_same_currency_series(self, provider):
        s = provider.get_conversion_series("USD", "USD", "2024-01-02", "2024-01-04")
        assert (s == 1.0).all()

    def test_missing_pair_returns_none(self, provider):
        assert provider.get_conversion_series(
            "GBP", "USD", "2024-01-02", "2024-01-04"
        ) is None

    def test_reindexes_to_requested_range(self, provider):
        s = provider.get_conversion_series("EUR", "USD", "2024-01-01", "2024-01-03")
        idx = pd.bdate_range("2024-01-01", "2024-01-03").strftime("%Y-%m-%d")
        assert list(s.index) == list(idx)


class TestProviderCache:
    def test_semantic_series_cached_and_reused(self, provider):
        s1 = provider.get_conversion_series("EUR", "USD", "2024-01-02", "2024-01-03")
        s2 = provider.get_conversion_series("EUR", "USD", "2024-01-03", "2024-01-04")
        assert s1.tolist() == pytest.approx([1.12, 1.11])
        assert s2.tolist() == pytest.approx([1.11, 1.13])
        assert provider._factor_cache[("EUR", "USD")].tolist() == pytest.approx(
            [1.10, 1.12, 1.11, 1.13]
        )

    def test_missing_pair_cached_in_missing_set(self, provider):
        assert provider.get_conversion_series(
            "GBP", "USD", "2024-01-02", "2024-01-04"
        ) is None
        assert ("GBP", "USD") in provider._missing_pairs

    def test_triangulated_pair_is_cached_only_as_final(self, provider):
        s = provider.get_conversion_series("JPY", "HKD", "2024-01-02", "2024-01-03")
        assert s.tolist() == pytest.approx([1.0 / 117.0 * 7.81, 1.0 / 116.0 * 7.79])
        assert ("JPY", "HKD") in provider._factor_cache
        assert ("JPY", "USD") not in provider._factor_cache
        assert ("USD", "HKD") not in provider._factor_cache
