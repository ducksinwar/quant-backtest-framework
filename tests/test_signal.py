from dataclasses import dataclass
from unittest.mock import MagicMock

import pandas as pd
import pytest
from backtester.signals.base_signal import BaseSignal
from backtester.signals.sma_crossover import SMACrossoverSignal


@dataclass
class MockLegSnapshot:
    ticker: str = "SPY"
    instrument_type: str = "equity"
    size: float = 100.0
    entry_price: float = 450.0
    current_price: float = 455.0
    daily_total_pnl: tuple = ()
    component_pnls: dict = None
    risk_measures: dict = None

    def __post_init__(self):
        if self.component_pnls is None:
            self.component_pnls = {}
        if self.risk_measures is None:
            self.risk_measures = {}


@dataclass
class MockStructureSnapshot:
    legs: tuple = ()


@dataclass
class MockTradeSnapshot:
    trade_id: str = "trade_1"
    structures: tuple = ()


class TestBaseSignal:
    def test_cannot_instantiate_abstract(self):
        with pytest.raises(TypeError):
            BaseSignal()

    def test_cannot_instantiate_partial(self):
        class PartialSignal(BaseSignal):
            requires_portfolio_state = True

        with pytest.raises(TypeError):
            PartialSignal()

    def test_default_flags_are_false(self):
        class MySignal(BaseSignal):
            def generate_signals(self, current_date, portfolio_state=None, trade_history_snapshot=None):
                return []

        sig = MySignal()
        assert sig.requires_portfolio_state is False
        assert sig.requires_trade_history is False

    def test_flags_can_be_overridden(self):
        class MySignal(BaseSignal):
            requires_portfolio_state = True
            requires_trade_history = True

            def generate_signals(self, current_date, portfolio_state=None, trade_history_snapshot=None):
                return []

        sig = MySignal()
        assert sig.requires_portfolio_state is True
        assert sig.requires_trade_history is True


class TestSMACrossoverSignal:
    @pytest.fixture
    def mock_data_feed(self):
        feed = MagicMock()
        return feed

    @pytest.fixture
    def signal(self, mock_data_feed):
        return SMACrossoverSignal(
            short_window=5,
            long_window=20,
            tickers=["SPY"],
            notional=100_000.0,
            data_feed=mock_data_feed,
        )

    def make_price_series(self, prices, start_date="2024-01-01"):
        dates = pd.date_range(start=start_date, periods=len(prices), freq="B")
        dates_str = [d.strftime("%Y-%m-%d") for d in dates]
        return pd.Series(prices, index=dates_str)

    def make_portfolio_state(self, ticker="SPY", trade_id="trade_1"):
        leg = MockLegSnapshot(ticker=ticker)
        structure = MockStructureSnapshot(legs=(leg,))
        trade = MockTradeSnapshot(trade_id=trade_id, structures=(structure,))

        class PortfolioState:
            def __init__(self):
                self.date = "2024-06-01"
                self.trades = (trade,)

        return PortfolioState()

    def test_returns_new_when_short_above_long_and_not_in_position(
        self, signal, mock_data_feed
    ):
        short_prices = list(range(100, 130))  # rising
        long_prices = list(range(90, 120))  # lower but also rising
        combined = [min(s, l) for s, l in zip(short_prices, long_prices)]
        combined[-10:] = [500] * 10
        combined[-6:] = [600] * 6

        series = self.make_price_series(combined)
        mock_data_feed.get_series.return_value = series
        mock_data_feed.get_value.return_value = 500.0

        orders = signal.generate_signals("2024-06-15", portfolio_state=None)
        assert len(orders) == 1
        assert orders[0]["Action"] == "NEW"
        assert orders[0]["trade_id"] is None
        assert orders[0]["info"][0]["legs"][0]["ticker"] == "SPY"
        assert orders[0]["info"][0]["legs"][0]["size"] == int(100_000.0 / 500.0)

    def test_returns_unwind_when_short_below_long_and_in_position(
        self, signal, mock_data_feed
    ):
        combined = [500] * 30 + [100] * 30
        series = self.make_price_series(combined)
        mock_data_feed.get_series.return_value = series

        portfolio_state = self.make_portfolio_state()
        orders = signal.generate_signals("2024-06-15", portfolio_state=portfolio_state)
        assert len(orders) == 1
        assert orders[0]["Action"] == "UNWIND"
        assert orders[0]["trade_id"] == "trade_1"
        assert orders[0]["info"] == []

    def test_returns_empty_when_short_above_long_but_in_position(
        self, signal, mock_data_feed
    ):
        combined = list(range(100, 160))
        series = self.make_price_series(combined)
        mock_data_feed.get_series.return_value = series

        portfolio_state = self.make_portfolio_state()
        orders = signal.generate_signals("2024-06-15", portfolio_state=portfolio_state)
        assert orders == []

    def test_returns_empty_when_short_below_long_and_not_in_position(
        self, signal, mock_data_feed
    ):
        combined = list(range(159, 99, -1))
        series = self.make_price_series(combined)
        mock_data_feed.get_series.return_value = series

        orders = signal.generate_signals("2024-06-15", portfolio_state=None)
        assert orders == []

    def test_returns_empty_when_insufficient_data(self, signal, mock_data_feed):
        series = pd.Series([], dtype=float)
        mock_data_feed.get_series.return_value = series

        orders = signal.generate_signals("2024-06-15", portfolio_state=None)
        assert orders == []

    def test_returns_empty_when_not_enough_points_for_long_window(
        self, signal, mock_data_feed
    ):
        prices = [450.0] * 10
        series = self.make_price_series(prices)
        mock_data_feed.get_series.return_value = series

        orders = signal.generate_signals("2024-06-15", portfolio_state=None)
        assert orders == []

    def test_is_in_position_different_ticker(self, signal, mock_data_feed):
        combined = [500] * 30 + [100] * 30
        series = self.make_price_series(combined)
        mock_data_feed.get_series.return_value = series

        portfolio_state = self.make_portfolio_state(ticker="AAPL")
        orders = signal.generate_signals("2024-06-15", portfolio_state=portfolio_state)
        assert orders == []

    def test_requires_portfolio_state_is_true(self, signal):
        assert signal.requires_portfolio_state is True

    def test_requires_trade_history_is_false(self, signal):
        assert signal.requires_trade_history is False
