"""SMACrossoverSignal emits action groups; BaseSignal requires a strategy_id."""

from unittest.mock import MagicMock

import pandas as pd
import pytest

from backtester.action_group_log import ActionGroupLog
from backtester.actions import ActionGroup, ActionType, PROVENANCE_SIGNAL, Side
from backtester.data_view import DataView
from backtester.position_books import PositionBooks
from backtester.signals.base_signal import BaseSignal
from backtester.signals.sma_crossover import SMACrossoverSignal
from backtester.snapshots import (
    LegSnapshot,
    PortfolioState,
    StructureSnapshot,
    TradeSnapshot,
)

STRATEGY_ID = "sma_crossover"


def _position_book(ticker="SPY", trade_id="trade_1", structure_id="S1", size=100.0):
    leg = LegSnapshot(
        ticker=ticker,
        asset_class="equity",
        size=size,
        entry_price=450.0,
        current_price=455.0,
        leg_id="L1",
    )
    structure = StructureSnapshot(legs=(leg,), structure_id=structure_id)
    trade = TradeSnapshot(trade_id=trade_id, structures=(structure,))
    state = PortfolioState(date="2024-06-14", trades=(trade,))
    return PositionBooks(state, ()).for_strategy(STRATEGY_ID)


class TestBaseSignal:
    def test_cannot_instantiate_abstract(self):
        with pytest.raises(TypeError):
            BaseSignal(STRATEGY_ID)

    def test_cannot_instantiate_partial(self):
        class PartialSignal(BaseSignal):
            pass

        with pytest.raises(TypeError):
            PartialSignal(STRATEGY_ID)

    def test_requires_a_non_empty_strategy_id(self):
        class MySignal(BaseSignal):
            def generate_action_groups(
                self, data_view, action_group_log, position_book
            ):
                return []

        with pytest.raises(ValueError, match="strategy_id"):
            MySignal("")
        assert MySignal(STRATEGY_ID).strategy_id == STRATEGY_ID

    def test_the_signal_interface_is_generate_action_groups(self):
        assert hasattr(BaseSignal, "generate_action_groups")
        assert getattr(
            BaseSignal.generate_action_groups, "__isabstractmethod__", False
        )


class _StubCalendar:
    """``is_valid_day`` over an explicit ``(code, date)`` closed set."""

    def __init__(self, closed=()):
        self.closed = set(closed)

    def is_valid_day(self, code, date):
        return (code, date) not in self.closed


class _TradableSignal(BaseSignal):
    def generate_action_groups(self, data_view, action_group_log, position_book):
        return []


class TestIsTradable:
    def test_is_calendar_blind_without_a_provider(self):
        signal = _TradableSignal("s")
        assert signal.is_tradable("2024-06-15", ["SPY"]) is True

    def test_open_day_is_tradable(self):
        signal = _TradableSignal(
            "s",
            calendar_provider=_StubCalendar(),
            ticker_to_calendar_code={"SPY": "US"},
        )
        assert signal.is_tradable("2024-06-14", ["SPY"]) is True

    def test_closed_day_is_not_tradable(self):
        signal = _TradableSignal(
            "s",
            calendar_provider=_StubCalendar({("US", "2024-06-14")}),
            ticker_to_calendar_code={"SPY": "US"},
        )
        assert signal.is_tradable("2024-06-14", ["SPY"]) is False

    def test_every_ticker_must_be_open(self):
        signal = _TradableSignal(
            "s",
            calendar_provider=_StubCalendar({("HK", "2024-06-14")}),
            ticker_to_calendar_code={"SPY": "US", "2800.HK": "HK"},
        )
        assert signal.is_tradable("2024-06-14", ["SPY", "2800.HK"]) is False

    def test_unmapped_ticker_fails_closed(self):
        signal = _TradableSignal(
            "s",
            calendar_provider=_StubCalendar(),
            ticker_to_calendar_code={"SPY": "US"},
        )
        with pytest.raises(ValueError, match="no calendar code"):
            signal.is_tradable("2024-06-14", ["QQQ"])

    def test_the_mapping_is_copied(self):
        mapping = {"SPY": "US"}
        signal = _TradableSignal(
            "s",
            calendar_provider=_StubCalendar(),
            ticker_to_calendar_code=mapping,
        )
        mapping["SPY"] = "HK"
        assert signal.is_tradable("2024-06-14", ["SPY"]) is True


class TestSMACrossoverSignal:
    @pytest.fixture
    def feed(self):
        return MagicMock()

    @pytest.fixture
    def signal(self):
        return SMACrossoverSignal(
            short_window=5,
            long_window=20,
            tickers=["SPY"],
            notional=100_000.0,
            strategy_id=STRATEGY_ID,
        )

    @pytest.fixture
    def action_group_log(self):
        return ActionGroupLog().for_strategy(STRATEGY_ID)

    @pytest.fixture
    def flat_book(self):
        return PositionBooks().for_strategy(STRATEGY_ID)

    def make_price_series(self, prices, start_date="2024-01-01"):
        dates = pd.date_range(start=start_date, periods=len(prices), freq="B")
        dates_str = [d.strftime("%Y-%m-%d") for d in dates]
        return pd.Series(prices, index=dates_str)

    def rising_series(self):
        """A series whose short SMA ends above its long SMA."""
        combined = [min(s, l) for s, l in zip(range(100, 130), range(90, 120))]
        combined[-10:] = [500] * 10
        combined[-6:] = [600] * 6
        return self.make_price_series(combined)

    def falling_series(self):
        """A series whose short SMA ends below its long SMA."""
        return self.make_price_series([500] * 30 + [100] * 30)

    def make_view(self, feed, series, date="2024-06-15"):
        feed.get_series.return_value = series
        feed.get_value.return_value = 500.0
        return DataView(feed, date=date, cutoff="2024-06-14")

    def test_strategy_id_is_required(self):
        with pytest.raises(TypeError):
            SMACrossoverSignal(
                short_window=5,
                long_window=20,
                tickers=["SPY"],
                notional=100_000.0,
            )

    def test_signal_holds_no_market_data_feed(self, signal):
        """Ruling: the feed lives in the view, not in the signal."""
        for name in ("_data_feed", "data_feed"):
            assert not hasattr(signal, name)

    def test_new_group_when_short_above_long_and_flat(
        self, signal, feed, action_group_log, flat_book
    ):
        view = self.make_view(feed, self.rising_series())

        groups = signal.generate_action_groups(
            view, action_group_log, flat_book
        )

        assert len(groups) == 1
        group = groups[0]
        assert isinstance(group, ActionGroup)
        assert group.strategy_id == STRATEGY_ID
        assert group.provenance == PROVENANCE_SIGNAL
        # Signals own neither identifier; the loop stamps both at emission.
        assert group.action_group_id is None
        assert group.emission_date is None

        action = group.actions[0]
        assert action.type is ActionType.NEW
        assert action.trade_id is None
        assert action.structure_id is None

        structure = action.spec.structures[0]
        leg = structure.legs[0]
        assert leg.contract_spec.ticker == "SPY"
        assert leg.contract_spec.asset_class == "equity"
        assert leg.contract_spec.currency == "USD"
        assert leg.side is Side.LONG
        assert leg.size == int(100_000.0 / 500.0)

    def test_entry_tags_ride_the_trade_spec(
        self, signal, feed, action_group_log, flat_book
    ):
        series = self.rising_series()
        view = self.make_view(feed, series)

        group = signal.generate_action_groups(
            view, action_group_log, flat_book
        )[0]

        clean = series.dropna()
        short_sma = clean.rolling(window=5).mean().iloc[-1]
        long_sma = clean.rolling(window=20).mean().iloc[-1]
        assert group.actions[0].spec.tags == (
            f"short_ma:{short_sma:.2f}",
            f"long_ma:{long_sma:.2f}",
        )

    def test_alpha_series_comes_through_the_data_view(
        self, signal, feed, action_group_log, flat_book
    ):
        view = self.make_view(feed, self.rising_series())

        signal.generate_action_groups(view, action_group_log, flat_book)

        # The first read is the alpha lookback; sizing's last-valid-day
        # resolution may add a later series read for an unmapped ticker.
        args = feed.get_series.call_args_list[0].args
        expected_start = (
            pd.Timestamp("2024-06-15") - pd.Timedelta(days=120)
        ).strftime("%Y-%m-%d")
        assert args == ("eod_prices", expected_start, "2024-06-14", "SPY")

    def test_entry_size_uses_the_t_minus_1_reference_price(
        self, signal, feed, action_group_log, flat_book
    ):
        """Sizing is fractional and reads the T-1 reference close."""
        series = self.rising_series()
        view = self.make_view(feed, series)
        feed.get_value.return_value = 250.0

        group = signal.generate_action_groups(
            view, action_group_log, flat_book
        )[0]

        assert group.actions[0].spec.structures[0].legs[0].size == 400.0
        # reference_price == get_price(ticker): last observable row <= cutoff.
        feed.get_value.assert_called_once_with(
            "eod_prices", series.index[-1], "SPY"
        )

    def _gated_signal(self, closed):
        return SMACrossoverSignal(
            short_window=5,
            long_window=20,
            tickers=["SPY"],
            notional=100_000.0,
            strategy_id=STRATEGY_ID,
            calendar_provider=_StubCalendar(closed),
            ticker_to_calendar_code={"SPY": "US"},
        )

    def test_no_emission_on_a_closed_market_day(
        self, feed, action_group_log, flat_book
    ):
        signal = self._gated_signal({("US", "2024-06-15")})
        view = self.make_view(feed, self.rising_series())

        assert signal.generate_action_groups(
            view, action_group_log, flat_book
        ) == []
        feed.get_series.assert_not_called()

    def test_an_unwind_is_suppressed_on_a_closed_market_day(
        self, feed, action_group_log
    ):
        signal = self._gated_signal({("US", "2024-06-15")})
        view = self.make_view(feed, self.falling_series())

        assert signal.generate_action_groups(
            view, action_group_log, _position_book()
        ) == []

    def test_an_open_market_day_emits_as_usual(
        self, feed, action_group_log, flat_book
    ):
        signal = self._gated_signal(set())
        view = self.make_view(feed, self.rising_series())

        assert len(
            signal.generate_action_groups(view, action_group_log, flat_book)
        ) == 1

    def test_no_entry_when_the_price_is_missing(
        self, signal, feed, action_group_log, flat_book
    ):
        view = self.make_view(feed, self.rising_series())
        feed.get_value.return_value = None

        assert signal.generate_action_groups(
            view, action_group_log, flat_book
        ) == []

    def test_unwind_group_when_short_below_long_and_in_position(
        self, signal, feed, action_group_log
    ):
        view = self.make_view(feed, self.falling_series())

        groups = signal.generate_action_groups(
            view, action_group_log, _position_book()
        )

        assert len(groups) == 1
        action = groups[0].actions[0]
        assert action.type is ActionType.UNWIND
        assert action.structure_id == "S1"
        assert action.spec is None
        assert action.size is None
        # The holding supplies both addresses; the signal passes them through.
        assert action.trade_id == "trade_1"

    def test_unwind_group_addresses_the_held_short_structure(
        self, signal, feed, action_group_log
    ):
        view = self.make_view(feed, self.falling_series())

        group = signal.generate_action_groups(
            view, action_group_log, _position_book(size=-100.0)
        )[0]

        assert group.actions[0].type is ActionType.UNWIND
        assert group.actions[0].structure_id == "S1"

    def test_no_group_when_above_and_in_position(
        self, signal, feed, action_group_log
    ):
        view = self.make_view(feed, self.make_price_series(list(range(100, 160))))

        assert signal.generate_action_groups(
            view, action_group_log, _position_book()
        ) == []

    def test_no_group_when_below_and_flat(
        self, signal, feed, action_group_log, flat_book
    ):
        view = self.make_view(
            feed, self.make_price_series(list(range(159, 99, -1)))
        )

        assert signal.generate_action_groups(
            view, action_group_log, flat_book
        ) == []

    def test_no_group_on_an_empty_series(
        self, signal, feed, action_group_log, flat_book
    ):
        view = self.make_view(feed, pd.Series([], dtype=float))

        assert signal.generate_action_groups(
            view, action_group_log, flat_book
        ) == []

    def test_no_group_when_there_are_too_few_points(
        self, signal, feed, action_group_log, flat_book
    ):
        view = self.make_view(feed, self.make_price_series([450.0] * 10))

        assert signal.generate_action_groups(
            view, action_group_log, flat_book
        ) == []

    def test_no_group_for_a_different_ticker(
        self, signal, feed, action_group_log
    ):
        view = self.make_view(feed, self.falling_series())

        book = _position_book(ticker="AAPL")

        assert signal.generate_action_groups(
            view, action_group_log, book
        ) == []

    def test_one_group_per_ticker_in_ticker_order(
        self, feed, action_group_log, flat_book
    ):
        signal = SMACrossoverSignal(
            short_window=5,
            long_window=20,
            tickers=["SPY", "QQQ"],
            notional=100_000.0,
            strategy_id=STRATEGY_ID,
        )
        view = self.make_view(feed, self.rising_series())

        groups = signal.generate_action_groups(
            view, action_group_log, flat_book
        )

        assert [
            g.actions[0].spec.structures[0].legs[0].contract_spec.ticker
            for g in groups
        ] == ["SPY", "QQQ"]

    def test_signal_returns_action_groups_never_target_trade_dicts(
        self, signal, feed, action_group_log, flat_book
    ):
        view = self.make_view(feed, self.rising_series())

        groups = signal.generate_action_groups(
            view, action_group_log, flat_book
        )

        assert all(isinstance(g, ActionGroup) for g in groups)
        assert not any(isinstance(g, dict) for g in groups)
