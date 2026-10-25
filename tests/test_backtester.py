import dataclasses
import warnings
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest
from backtester.backtest_engine import AssetClassConfig, BacktestConfig, Backtester, BacktestResult
from backtester.calendar_provider import CalendarProvider
from backtester.data.csv_backend import CsvBackend
from backtester.data.data_feed import DataFeed
from backtester.data.typed_providers.equity_price_provider import EquityPriceProvider
from backtester.instruments import Contract
from backtester.pricers.equity_pricer import EquityPricer
from backtester.snapshots import (
    LegSnapshot,
    PortfolioState,
    StructureSnapshot,
    TradeRecord,
    TradeSnapshot,
)
from backtester.actions import (
    Action,
    ActionGroup,
    ActionType,
    AggregationContext,
    ContractSpec,
    LegSpec,
    PROVENANCE_SIGNAL,
    Side,
    StructureSpec,
    TradeSpec,
)
from backtester.action_group_log import ActionGroupLog
from backtester.order_assembly import action_group_to_order_group
from backtester.orders import (
    Order,
    OrderGroup,
    OrderLeg,
    OrderOutcome,
    OrderSide,
)
from backtester.signals.sma_crossover import SMACrossoverSignal
from backtester.position_books import PositionBooks
from backtester.strategy_structure import StrategyStructure
from backtester.trade import Trade

#: Committed fixtures (the example's dataset).
MARKET_DATA_DIR = Path(__file__).resolve().parents[1] / "market_data"


def _group(action):
    return ActionGroup(
        action_group_id=None,
        provenance=PROVENANCE_SIGNAL,
        actions=(action,),
    )


def _new_trade(ticker, size, *, asset_class="equity", multiplier=None,
               tags=(), trade_id=None, structure_id="S1"):
    """A NEW action: open a trade, or extend one when ``trade_id`` is set."""
    spec_kwargs = {"asset_class": asset_class}
    if multiplier is not None:
        spec_kwargs["multiplier"] = multiplier
    if trade_id is not None and structure_id is not None:
        action = Action(
            type=ActionType.NEW,
            trade_id=trade_id,
            structure_id=structure_id,
            size=size,
        )
        return _group(action)
    structure = StructureSpec(
        legs=(
            LegSpec(
                ContractSpec(ticker, **spec_kwargs),
                Side.LONG if size >= 0 else Side.SHORT,
                abs(size),
            ),
        ),
        tags=tuple(tags),
    )
    if trade_id is None:
        action = Action(
            type=ActionType.NEW,
            spec=TradeSpec(structures=(structure,), tags=tuple(tags)),
        )
    else:
        action = Action(
            type=ActionType.NEW, spec=structure, trade_id=trade_id
        )
    return _group(action)


def _unwind(trade_id=None, structure_id=None, size=None):
    return _group(
        Action(
            type=ActionType.UNWIND,
            trade_id=trade_id,
            structure_id=structure_id,
            size=size,
        )
    )


def _make_mock_signal(orders_lookup=None):
    """Create a mock signal that returns pre-programmed action groups per date.

    The lookup values are already ActionGroups built by ``_new_trade`` /
    ``_unwind``.  The interface is
    ``generate_action_groups(data_view, action_group_log, position_book)``:
    the lookup is keyed by ``data_view.date`` (the loop day) and the T-1
    position book replaces the old portfolio_state / trade_history_snapshot
    arguments.
    """
    mock = MagicMock()

    def generate_action_groups(data_view, action_group_log=None, position_book=None):
        groups = (orders_lookup or {}).get(data_view.date, [])
        return list(groups)

    mock.generate_action_groups.side_effect = generate_action_groups
    return mock


def _make_csv(tmp_path, rows):
    """Write a tiny CSV for testing and return path."""
    csv_path = tmp_path / "TEST_eod.csv"
    csv_path.write_text("date,close\n" + "\n".join(f"{d},{p}" for d, p in rows))
    return str(tmp_path)


#: Holiday fixture content for the ``simple_csv`` temp base_dir.  The price CSV
#: and its ``holidays/`` subdir must now live in the *same* base_dir, because the
#: backend owns both path conventions.
_US_HOLIDAY_CSV = "date\n2024-01-04\n2024-02-02\n"
_UK_HOLIDAY_CSV = "date\n2024-01-05\n2024-01-06\n"


@pytest.fixture
def simple_csv(tmp_path):
    base = _make_csv(tmp_path, [
        ("2024-01-02", 100.0),
        ("2024-01-03", 101.0),
        ("2024-01-04", 102.0),
        ("2024-01-05", 103.0),
        ("2024-01-08", 104.0),
        ("2024-01-09", 105.0),
    ])
    # Deliberate duplication of tests/test_data/holidays/: the calendar
    # integration tests need a *controlled* price CSV (ticker TEST) with
    # engineered absent dates (2024-01-10/11), and tests/test_data/ has no
    # TEST_eod.csv -- only SPY_eod.csv, whose complete coverage would defeat
    # the gap assertions.  Committing a controlled TEST_eod.csv and retiring
    # simple_csv is a separate, deferred cleanup.
    holidays_dir = tmp_path / "holidays"
    holidays_dir.mkdir()
    (holidays_dir / "US.csv").write_text(_US_HOLIDAY_CSV)
    (holidays_dir / "UK.csv").write_text(_UK_HOLIDAY_CSV)
    return base


class TestSnapshots:
    def test_leg_snapshot_frozen(self):
        ls = LegSnapshot(
            ticker="SPY", asset_class="equity",
            size=100.0, entry_price=450.0, current_price=455.0,
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            ls.size = 200.0

    def test_portfolio_state_builds_from_trades(self):
        leg = LegSnapshot(
            ticker="SPY", asset_class="equity",
            size=100.0, entry_price=450.0, current_price=455.0,
        )
        structure = StructureSnapshot(legs=(leg,))
        trade = TradeSnapshot(trade_id="t1", structures=(structure,))
        ps = PortfolioState(date="2024-01-15", trades=(trade,))
        assert ps.date == "2024-01-15"
        assert ps.trades[0].trade_id == "t1"
        assert ps.trades[0].structures[0].legs[0].ticker == "SPY"

    def test_trade_record_fields(self):
        tr = TradeRecord(
            trade_id="t1", entry_date="2024-01-02",
            exit_date=None, tags=("alpha",), is_open=True,
        )
        assert tr.trade_id == "t1"
        assert tr.exit_date is None
        assert tr.is_open is True

    def test_trade_record_closed(self):
        tr = TradeRecord(
            trade_id="t2", entry_date="2024-01-02",
            exit_date="2024-02-01", tags=(), is_open=False,
        )
        assert tr.is_open is False


class TestBacktesterBasic:
    def test_backtester_opens_and_closes_trade(self, simple_csv):
        backend = CsvBackend(base_dir=simple_csv)
        data_feed = DataFeed(backend)
        provider = EquityPriceProvider(data_feed)
        pricer = EquityPricer(provider)

        config = AssetClassConfig(pricer=pricer, risk_measures=[])

        orders = {
            "2024-01-02": [
                _new_trade("TEST", 100)
            ],
            "2024-01-05": [
                _unwind()
            ],
        }
        signal = _make_mock_signal(orders_lookup=orders)

        bt_config = BacktestConfig(
            signal=signal,
            start_date="2024-01-02",
            end_date="2024-01-09",
            asset_class_configs={"equity": config},
            calendar_provider=CalendarProvider(data_feed),
            simulation_calendar_codes=None,
        )

        bt = Backtester(bt_config)
        result = bt.run()
        history = list(result.trade_history)

        assert len(history) == 1
        trade = history[0]
        assert trade.entry_date == "2024-01-02"
        assert trade.exit_date is not None
        assert len(trade.structure_history) == 1

    def test_trade_history_returned(self, simple_csv):
        backend = CsvBackend(base_dir=simple_csv)
        data_feed = DataFeed(backend)
        provider = EquityPriceProvider(data_feed)
        pricer = EquityPricer(provider)
        config = AssetClassConfig(pricer=pricer, risk_measures=[])

        signal = _make_mock_signal(orders_lookup={})
        bt_config = BacktestConfig(
            signal=signal,
            start_date="2024-01-02",
            end_date="2024-01-05",
            asset_class_configs={"equity": config},
            calendar_provider=CalendarProvider(data_feed),
            simulation_calendar_codes=None,
        )
        bt = Backtester(bt_config)
        result = bt.run()
        history = list(result.trade_history)
        assert history == []

    def test_entry_and_exit_dates_set(self, simple_csv):
        backend = CsvBackend(base_dir=simple_csv)
        data_feed = DataFeed(backend)
        provider = EquityPriceProvider(data_feed)
        pricer = EquityPricer(provider)
        config = AssetClassConfig(pricer=pricer, risk_measures=[])

        orders = {
            "2024-01-03": [
                _new_trade("TEST", 100)
            ],
            "2024-01-08": [
                _unwind()
            ],
        }
        signal = _make_mock_signal(orders_lookup=orders)
        bt_config = BacktestConfig(
            signal=signal,
            start_date="2024-01-02",
            end_date="2024-01-09",
            asset_class_configs={"equity": config},
            calendar_provider=CalendarProvider(data_feed),
            simulation_calendar_codes=None,
        )
        bt = Backtester(bt_config)
        result = bt.run()
        history = list(result.trade_history)

        assert len(history) == 1
        trade = history[0]
        assert trade.entry_date == "2024-01-03"
        assert trade.exit_date == "2024-01-08"


class TestBacktesterPnl:
    def test_pnl_accumulation(self, simple_csv):
        backend = CsvBackend(base_dir=simple_csv)
        data_feed = DataFeed(backend)
        provider = EquityPriceProvider(data_feed)
        pricer = EquityPricer(provider)
        config = AssetClassConfig(pricer=pricer, risk_measures=[])

        orders = {
            "2024-01-02": [
                _new_trade("TEST", 100)
            ],
        }
        signal = _make_mock_signal(orders_lookup=orders)
        bt_config = BacktestConfig(
            signal=signal,
            start_date="2024-01-02",
            end_date="2024-01-09",
            asset_class_configs={"equity": config},
            calendar_provider=CalendarProvider(data_feed),
            simulation_calendar_codes=None,
        )
        bt = Backtester(bt_config)
        result = bt.run()
        history = list(result.trade_history)

        trade = history[0]
        leg = trade.structure_history[0].legs[0]
        assert len(leg.daily_total_pnl) > 0
        assert leg.current_price == 105.0
        assert leg.entry_price == 100.0

    def test_pnl_with_multiplier(self, simple_csv):
        backend = CsvBackend(base_dir=simple_csv)
        data_feed = DataFeed(backend)
        provider = EquityPriceProvider(data_feed)
        pricer = EquityPricer(provider)
        config = AssetClassConfig(pricer=pricer, risk_measures=[])

        orders = {
            "2024-01-02": [
                _new_trade("TEST", 10, multiplier=50.0)
            ],
        }
        signal = _make_mock_signal(orders_lookup=orders)
        bt_config = BacktestConfig(
            signal=signal,
            start_date="2024-01-02",
            end_date="2024-01-09",
            asset_class_configs={"equity": config},
            calendar_provider=CalendarProvider(data_feed),
            simulation_calendar_codes=None,
        )
        bt = Backtester(bt_config)
        result = bt.run()
        history = list(result.trade_history)

        trade = history[0]
        leg = trade.structure_history[0].legs[0]
        assert leg.contract.multiplier == 50.0
        assert len(leg.daily_total_pnl) > 0

    def test_pnl_nan_on_missing_price(self):
        """A genuine data gap on a trading day still produces NaN."""
        class GappyProvider:
            def get_price(self, ticker, date):
                if date == "2024-02-02":
                    return None
                return {"2024-02-01": 100.0, "2024-02-02": 101.0, "2024-02-05": 103.0}.get(date)

        pricer = EquityPricer(GappyProvider())
        config = AssetClassConfig(pricer=pricer, risk_measures=[])

        signal = _make_mock_signal(
            orders_lookup={
                "2024-02-01": [
                    _new_trade("X", 100)
                ],
            },
        )

        # simulation_calendar_codes=None declares "no holiday calendars", so
        # 2024-02-02 -- a Friday on which the provider has no price -- is a
        # simulated day and exercises the genuine missing-price path.  This
        # test is about the missing-price path, not calendars, and None never
        # reaches the backend, so a MagicMock feed is sufficient here.
        bt_config = BacktestConfig(
            signal=signal,
            start_date="2024-02-01",
            end_date="2024-02-05",
            asset_class_configs={"equity": config},
            calendar_provider=CalendarProvider(MagicMock()),
            simulation_calendar_codes=None,
        )
        bt = Backtester(bt_config)
        result = bt.run()
        history = list(result.trade_history)

        leg = history[0].structure_history[0].legs[0]
        assert len(leg.daily_total_pnl) >= 2
        assert any(np.isnan(x) for x in leg.daily_total_pnl)


class TestBacktesterPositionBook:
    """The T-1 position book is always built and passed; no flag gates it."""

    def _run(self, simple_csv, signal, start="2024-01-02", end="2024-01-05"):
        backend = CsvBackend(base_dir=simple_csv)
        data_feed = DataFeed(backend)
        provider = EquityPriceProvider(data_feed)
        pricer = EquityPricer(provider)
        config = AssetClassConfig(pricer=pricer, risk_measures=[])
        bt_config = BacktestConfig(
            signal=signal,
            start_date=start,
            end_date=end,
            asset_class_configs={"equity": config},
            calendar_provider=CalendarProvider(data_feed),
            simulation_calendar_codes=None,
        )
        return Backtester(bt_config).run()

    def test_book_and_log_are_always_passed(self, simple_csv):
        captured = []

        def capture(data_view, action_group_log, position_book):
            captured.append((data_view, action_group_log, position_book))
            return []

        signal = _make_mock_signal()
        signal.generate_action_groups.side_effect = capture
        self._run(simple_csv, signal)

        assert len(captured) == 4  # 2024-01-02 .. 2024-01-05
        for data_view, action_group_log, position_book in captured:
            assert data_view.cutoff < data_view.date
            assert isinstance(
                position_book.portfolio_state, (PortfolioState, type(None))
            )
            assert isinstance(position_book.trade_history, tuple)
            assert isinstance(action_group_log, ActionGroupLog)

    def test_book_holds_the_open_position_from_the_next_day(self, simple_csv):
        captured = []

        def capture(data_view, action_group_log, position_book):
            captured.append((data_view.date, position_book))
            if data_view.date == "2024-01-02":
                return [
                    _new_trade("TEST", 100)
                ]
            return []

        signal = _make_mock_signal()
        signal.generate_action_groups.side_effect = capture
        self._run(simple_csv, signal)

        books = dict(captured)
        assert books["2024-01-02"].portfolio_state is None  # nothing held yet
        book = books["2024-01-03"]
        holding = book.find_holding("TEST")
        assert holding is not None
        assert holding.leg.size == 100.0
        assert holding.structure_id
        assert book.is_in_position("TEST") is True
        assert (
            book.trade_id_for_structure(holding.structure_id)
            == holding.trade_id
        )

    def test_action_group_log_grows_across_the_run(self, simple_csv):
        seen_lengths = []

        def capture(data_view, action_group_log, position_book):
            seen_lengths.append(len(action_group_log))
            if data_view.date == "2024-01-02":
                return [
                    _new_trade("TEST", 100)
                ]
            return []

        signal = _make_mock_signal()
        signal.generate_action_groups.side_effect = capture
        self._run(simple_csv, signal)

        # The live log: empty before the first emission and one record
        # richer from the next day on.
        assert seen_lengths == [0, 1, 1, 1]


class TestBacktesterUnknownAssetClass:
    def test_raises_on_unknown_asset_class(self, simple_csv):
        backend = CsvBackend(base_dir=simple_csv)
        data_feed = DataFeed(backend)
        provider = EquityPriceProvider(data_feed)
        pricer = EquityPricer(provider)
        config = AssetClassConfig(pricer=pricer, risk_measures=[])

        orders = {
            "2024-01-02": [
                _new_trade("TEST", 100, asset_class="fx_option")
            ],
        }
        signal = _make_mock_signal(orders_lookup=orders)
        bt_config = BacktestConfig(
            signal=signal,
            start_date="2024-01-02",
            end_date="2024-01-05",
            asset_class_configs={"equity": config},
            calendar_provider=CalendarProvider(data_feed),
            simulation_calendar_codes=None,
        )
        bt = Backtester(bt_config)
        with pytest.raises(ValueError, match="Unknown asset class"):
            bt.run()


class TestBacktesterDataAvailability:
    def test_new_order_blocked_when_price_is_none(self, simple_csv):
        backend = CsvBackend(base_dir=simple_csv)
        data_feed = DataFeed(backend)

        class GappyPricer:
            def resolve_instrument(self, leg_dict, date):
                return Contract(ticker=leg_dict.get("ticker", ""), asset_class="equity")

            def price(self, contract, date):
                if date == "2024-01-03":
                    return None
                return 100.0

            def valuation_data(self, contract, date, measures):
                return {}

            def pricing_inputs(self, contract, date):
                return {}

            def compute_cost_exposure(self, contract, date):
                return {"notional_per_unit": 100.0}

        pricer = GappyPricer()
        config = AssetClassConfig(pricer=pricer, risk_measures=[])

        orders = {
            "2024-01-03": [
                _new_trade("TEST", 100)
            ],
        }
        signal = _make_mock_signal(orders_lookup=orders)
        bt_config = BacktestConfig(
            signal=signal,
            start_date="2024-01-02",
            end_date="2024-01-05",
            asset_class_configs={"equity": config},
            calendar_provider=CalendarProvider(data_feed),
            simulation_calendar_codes=None,
        )
        bt = Backtester(bt_config)
        with pytest.warns(UserWarning, match="data not available"):
            result = bt.run()
        history = list(result.trade_history)
        assert history == []

        # The group became orders handed to execution; the block is the order
        # outcome and the execution-log status.
        records = bt.action_group_log.records
        assert len(records) == 1
        record = records[0]
        assert record.order_ids
        assert record.order_outcomes == (OrderOutcome.BLOCKED,)
        assert record.group_note is None

        exec_records = bt.execution_log.records
        assert len(exec_records) == 1
        assert exec_records[0].status == "BLOCKED"
        assert exec_records[0].blocked_code == "DATA_MISSING"
        assert exec_records[0].fill_id is None
        assert exec_records[0].fills == ()
        assert exec_records[0].order_id == record.order_ids[0]
        assert exec_records[0].action_group_id == records[0].action_group.action_group_id

    def test_unwind_order_not_rejected_when_price_available(self, simple_csv):
        backend = CsvBackend(base_dir=simple_csv)
        data_feed = DataFeed(backend)
        provider = EquityPriceProvider(data_feed)
        pricer = EquityPricer(provider)
        config = AssetClassConfig(pricer=pricer, risk_measures=[])

        orders = {
            "2024-01-02": [
                _new_trade("TEST", 100)
            ],
            "2024-01-05": [
                _unwind()
            ],
        }
        signal = _make_mock_signal(orders_lookup=orders)
        bt_config = BacktestConfig(
            signal=signal,
            start_date="2024-01-02",
            end_date="2024-01-09",
            asset_class_configs={"equity": config},
            calendar_provider=CalendarProvider(data_feed),
            simulation_calendar_codes=None,
        )
        bt = Backtester(bt_config)
        result = bt.run()
        history = list(result.trade_history)
        assert len(history) == 1
        assert history[0].exit_date is not None


class TestBacktesterSnapshotSemantics:
    def test_snapshot_contains_t_minus_1_prices(self, simple_csv):
        """Verify that snapshots built BEFORE PnL contain T-1 close prices."""
        backend = CsvBackend(base_dir=simple_csv)
        data_feed = DataFeed(backend)
        provider = EquityPriceProvider(data_feed)
        pricer = EquityPricer(provider)
        config = AssetClassConfig(pricer=pricer, risk_measures=[])

        captured_states = []
        call_count = [0]

        def step_side_effect(data_view, action_group_log=None, position_book=None):
            if position_book.portfolio_state is not None:
                captured_states.append(
                    (data_view.date, position_book.portfolio_state)
                )
            call_count[0] += 1
            if call_count[0] == 1:
                return [
                    _new_trade("TEST", 100)
                ]
            return []

        signal = _make_mock_signal()
        signal.generate_action_groups.side_effect = step_side_effect

        bt_config = BacktestConfig(
            signal=signal,
            start_date="2024-01-02",
            end_date="2024-01-05",
            asset_class_configs={"equity": config},
            calendar_provider=CalendarProvider(data_feed),
            simulation_calendar_codes=None,
        )
        bt = Backtester(bt_config)
        bt.run()

        assert len(captured_states) >= 2

        # First snapshot: on or after entry date, should see position
        found_position = False
        for date_str, state in captured_states:
            if state.trades:
                trade = state.trades[0]
                if trade.structures:
                    leg = trade.structures[0].legs[0]
                    found_position = True
                    assert leg.ticker == "TEST"
                    assert leg.size == 100.0
                    # On entry day (2024-01-02), the snapshot for that day
                    # is built BEFORE PnL, so current_price should be the
                    # entry price (100.0), not the next day's close.
                    if date_str == "2024-01-03" or date_str == "2024-01-02":
                        assert leg.current_price == 100.0, (
                            f"Snapshot on {date_str} should show T-1 close "
                            f"(100.0), got {leg.current_price}"
                        )
        assert found_position, "PortfolioState should contain the opened position"


class TestBacktesterCostExposure:
    def test_cost_exposures_passed_to_trade_on_new(self, simple_csv):
        backend = CsvBackend(base_dir=simple_csv)
        data_feed = DataFeed(backend)
        provider = EquityPriceProvider(data_feed)
        pricer = EquityPricer(provider)
        config = AssetClassConfig(pricer=pricer, risk_measures=[])

        orders = {
            "2024-01-02": [
                _new_trade("TEST", 100)
            ],
        }
        signal = _make_mock_signal(orders_lookup=orders)
        bt_config = BacktestConfig(
            signal=signal,
            start_date="2024-01-02",
            end_date="2024-01-05",
            asset_class_configs={"equity": config},
            calendar_provider=CalendarProvider(data_feed),
            simulation_calendar_codes=None,
        )
        bt = Backtester(bt_config)
        result = bt.run()
        history = list(result.trade_history)

        assert len(history) == 1
        structure = history[0].structure_history[0]
        assert len(structure.event_log) >= 1
        open_event = structure.event_log[0]
        assert open_event["event_type"] == "open"
        assert "cost_exposures" in open_event
        assert len(open_event["cost_exposures"]) == 1
        leg_id = list(open_event["cost_exposures"].keys())[0]
        assert "notional_per_unit" in open_event["cost_exposures"][leg_id]

    def test_cost_exposures_on_unwind(self, simple_csv):
        backend = CsvBackend(base_dir=simple_csv)
        data_feed = DataFeed(backend)
        provider = EquityPriceProvider(data_feed)
        pricer = EquityPricer(provider)
        config = AssetClassConfig(pricer=pricer, risk_measures=[])

        orders = {
            "2024-01-02": [
                _new_trade("TEST", 100)
            ],
            "2024-01-05": [
                _unwind()
            ],
        }
        signal = _make_mock_signal(orders_lookup=orders)
        bt_config = BacktestConfig(
            signal=signal,
            start_date="2024-01-02",
            end_date="2024-01-09",
            asset_class_configs={"equity": config},
            calendar_provider=CalendarProvider(data_feed),
            simulation_calendar_codes=None,
        )
        bt = Backtester(bt_config)
        result = bt.run()
        history = list(result.trade_history)

        assert len(history) == 1
        structure = history[0].structure_history[0]
        assert len(structure.event_log) >= 2
        close_event = structure.event_log[-1]
        assert close_event["event_type"] == "full close"
        assert "cost_exposures" in close_event
        assert len(close_event["cost_exposures"]) == 1


class TestBacktesterRecordPricingInputs:
    def test_pricing_inputs_not_recorded_when_flag_false(self, simple_csv):
        backend = CsvBackend(base_dir=simple_csv)
        data_feed = DataFeed(backend)
        provider = EquityPriceProvider(data_feed)
        pricer = EquityPricer(provider)
        config = AssetClassConfig(pricer=pricer, record_pricing_inputs=False)

        orders = {
            "2024-01-02": [
                _new_trade("TEST", 100)
            ],
        }
        signal = _make_mock_signal(orders_lookup=orders)
        bt_config = BacktestConfig(
            signal=signal,
            start_date="2024-01-02",
            end_date="2024-01-05",
            asset_class_configs={"equity": config},
            calendar_provider=CalendarProvider(data_feed),
            simulation_calendar_codes=None,
        )
        bt = Backtester(bt_config)
        result = bt.run()
        history = list(result.trade_history)

        leg = history[0].structure_history[0].legs[0]
        assert leg.pricing_inputs == {}

    def test_pricing_inputs_recorded_when_flag_true(self, simple_csv):
        backend = CsvBackend(base_dir=simple_csv)
        data_feed = DataFeed(backend)
        provider = EquityPriceProvider(data_feed)
        pricer = EquityPricer(provider)
        config = AssetClassConfig(pricer=pricer, record_pricing_inputs=True)

        orders = {
            "2024-01-02": [
                _new_trade("TEST", 100)
            ],
        }
        signal = _make_mock_signal(orders_lookup=orders)
        bt_config = BacktestConfig(
            signal=signal,
            start_date="2024-01-02",
            end_date="2024-01-05",
            asset_class_configs={"equity": config},
            calendar_provider=CalendarProvider(data_feed),
            simulation_calendar_codes=None,
        )
        bt = Backtester(bt_config)
        result = bt.run()
        history = list(result.trade_history)

        leg = history[0].structure_history[0].legs[0]
        assert len(leg.daily_total_pnl) >= 1
        assert isinstance(leg.pricing_inputs, dict)


class TestBacktesterPricingInputsNanPadding:
    def test_pricing_inputs_nan_padded_for_missing_keys(self, simple_csv):
        backend = CsvBackend(base_dir=simple_csv)
        data_feed = DataFeed(backend)

        class GappyInputsPricer:
            def __init__(self):
                self._call_count = 0

            def resolve_instrument(self, leg_dict, date):
                return Contract(
                    ticker=leg_dict.get("ticker", ""), asset_class="equity"
                )

            def price(self, contract, date):
                return 100.0 + self._call_count

            def valuation_data(self, contract, date, measures):
                return {}

            def pricing_inputs(self, contract, date):
                self._call_count += 1
                if self._call_count == 1:
                    return {"spot": 100.0}
                if self._call_count == 2:
                    return {}
                if self._call_count == 3:
                    return {"spot": 102.0, "rate": 0.05}
                if self._call_count == 4:
                    return {"spot": 104.0}
                return {}

            def compute_cost_exposure(self, contract, date):
                return {"notional_per_unit": 100.0}

        pricer = GappyInputsPricer()
        config = AssetClassConfig(
            pricer=pricer, risk_measures=[], record_pricing_inputs=True,
        )

        orders = {
            "2024-01-02": [_new_trade("TEST", 100)],
        }
        signal = _make_mock_signal(orders_lookup=orders)
        bt_config = BacktestConfig(
            signal=signal, start_date="2024-01-02", end_date="2024-01-08",
            asset_class_configs={"equity": config},
            calendar_provider=CalendarProvider(data_feed),
            simulation_calendar_codes=None,
        )
        bt = Backtester(bt_config)
        result = bt.run()
        history = list(result.trade_history)

        leg = history[0].structure_history[0].legs[0]
        spot = leg.pricing_inputs.get("spot", [])
        assert len(spot) == 5
        assert spot == pytest.approx(
            [100.0, float("nan"), 102.0, 104.0, float("nan")], nan_ok=True,
        )

        rate = leg.pricing_inputs.get("rate", [])
        assert len(rate) == 5
        assert rate == pytest.approx(
            [float("nan"), float("nan"), 0.05, float("nan"), float("nan")],
            nan_ok=True,
        )


class TestBacktesterOrderRejectionWarning:
    def test_order_rejection_emits_warning(self, simple_csv):
        backend = CsvBackend(base_dir=simple_csv)
        data_feed = DataFeed(backend)

        class GappyPricer:
            def resolve_instrument(self, leg_dict, date):
                return Contract(ticker=leg_dict.get("ticker", ""), asset_class="equity")

            def price(self, contract, date):
                if date == "2024-01-03":
                    return None
                return 100.0

            def valuation_data(self, contract, date, measures):
                return {}

            def pricing_inputs(self, contract, date):
                return {}

            def compute_cost_exposure(self, contract, date):
                return {"notional_per_unit": 100.0}

        pricer = GappyPricer()
        config = AssetClassConfig(pricer=pricer, risk_measures=[])

        orders = {
            "2024-01-03": [
                _new_trade("TEST", 100)
            ],
        }
        signal = _make_mock_signal(orders_lookup=orders)
        bt_config = BacktestConfig(
            signal=signal,
            start_date="2024-01-02",
            end_date="2024-01-05",
            asset_class_configs={"equity": config},
            calendar_provider=CalendarProvider(data_feed),
            simulation_calendar_codes=None,
        )
        bt = Backtester(bt_config)
        with pytest.warns(UserWarning, match="data not available"):
            bt.run()


class TestBacktesterTradeHistorySnapshot:
    def test_trade_history_snapshot_reflects_open_and_closed(self, simple_csv):
        backend = CsvBackend(base_dir=simple_csv)
        data_feed = DataFeed(backend)
        provider = EquityPriceProvider(data_feed)
        pricer = EquityPricer(provider)
        config = AssetClassConfig(pricer=pricer, risk_measures=[])

        captured_snapshots = []
        call_count = [0]

        def step_side_effect(data_view, action_group_log=None, position_book=None):
            captured_snapshots.append(
                (data_view.date, position_book.trade_history)
            )
            call_count[0] += 1
            if call_count[0] == 1:
                return [
                    _new_trade("TEST", 100)
                ]
            elif call_count[0] == 2:
                return [
                    _unwind()
                ]
            return []

        signal = _make_mock_signal()
        signal.generate_action_groups.side_effect = step_side_effect

        bt_config = BacktestConfig(
            signal=signal,
            start_date="2024-01-02",
            end_date="2024-01-05",
            asset_class_configs={"equity": config},
            calendar_provider=CalendarProvider(data_feed),
            simulation_calendar_codes=None,
        )
        bt = Backtester(bt_config)
        bt.run()

        assert len(captured_snapshots) >= 3

        open_found = False
        closed_found = False
        for date_str, snapshot in captured_snapshots:
            for record in snapshot:
                if record.is_open and record.exit_date is None:
                    open_found = True
                if not record.is_open and record.exit_date is not None:
                    closed_found = True

        assert open_found, "TradeRecord with is_open=True should appear before close"
        assert closed_found, "TradeRecord with is_open=False, exit_date set should appear after close"


class TestUnwindShapeEquivalence:
    """Per-structure UNWIND == whole-trade UNWIND, execution-identical.

    Both forms are representable as action groups; this converts both into
    ``Order`` groups and drives them through the engine's check -> execute ->
    commit path to prove the equivalence on a single-structure trade.
    """

    def _engine(self, simple_csv):
        backend = CsvBackend(base_dir=simple_csv)
        data_feed = DataFeed(backend)
        pricer = EquityPricer(EquityPriceProvider(data_feed))
        config = AssetClassConfig(pricer=pricer, risk_measures=[])
        return Backtester(
            BacktestConfig(
                signal=_make_mock_signal(),
                start_date="2024-01-02",
                end_date="2024-01-05",
                asset_class_configs={"equity": config},
                calendar_provider=CalendarProvider(data_feed),
                simulation_calendar_codes=None,
            )
        )

    def _ctx_for(self, trade=None):
        if trade is None:
            books = PositionBooks()
        else:
            leg = LegSnapshot(
                ticker="TEST",
                asset_class="equity",
                size=100.0,
                entry_price=100.0,
                current_price=105.0,
                leg_id="L1",
            )
            structure = StructureSnapshot(
                legs=(leg,),
                structure_id=trade.active_structures[0].structure_id,
            )
            books = PositionBooks(
                PortfolioState(
                    date="2024-01-05",
                    trades=(
                        TradeSnapshot(trade_id=trade.trade_id,
                                      structures=(structure,)),
                    ),
                ),
                (),
            )
        return AggregationContext(
            date="2024-01-03",
            action_group_log=ActionGroupLog(),
            execution_log=None,
            position_books=books,
            calendar=None,
            config=None,
        )

    def _dispatch(self, bt, group, date, trade=None):
        from backtester.execution import SimulatedExecution

        record = bt.action_group_log.append(group, date)
        order_group = action_group_to_order_group(
            record.action_group, record.action_ids, self._ctx_for(trade)
        )
        bt._dispatch_synthesized_order(
            record, order_group, date, SimulatedExecution()
        )
        return record

    def _engine_with_open_trade(self, simple_csv):
        bt = self._engine(simple_csv)
        self._dispatch(bt, _new_trade("TEST", 100), "2024-01-02")
        return bt, bt.active_trades[0]

    def test_per_structure_unwind_reproduces_whole_trade_unwind(
        self, simple_csv
    ):
        whole_bt, whole_trade = self._engine_with_open_trade(simple_csv)
        self._dispatch(
            whole_bt,
            _unwind(trade_id=whole_trade.trade_id),
            "2024-01-03",
            trade=whole_trade,
        )

        per_bt, per_trade = self._engine_with_open_trade(simple_csv)
        structure_id = per_trade.active_structures[0].structure_id
        self._dispatch(
            per_bt,
            _unwind(trade_id=per_trade.trade_id, structure_id=structure_id),
            "2024-01-03",
            trade=per_trade,
        )

        assert whole_trade.entry_date == per_trade.entry_date == "2024-01-02"
        assert whole_trade.exit_date == per_trade.exit_date == "2024-01-03"
        assert whole_trade.active_structures == per_trade.active_structures
        assert whole_trade.active_structures == []
        assert whole_bt.active_trades == per_bt.active_trades == []

        whole_events = whole_trade.structure_history[0].event_log
        per_events = per_trade.structure_history[0].event_log
        assert [e["event_type"] for e in whole_events] == [
            "open",
            "full close",
        ]
        assert [e["event_type"] for e in per_events] == ["open", "full close"]
        for whole_event, per_event in zip(whole_events, per_events):
            assert whole_event["date"] == per_event["date"]
            # Leg ids are generated per engine, so compare the economics:
            # the size deltas and the per-leg cost exposures.
            assert sorted(whole_event["leg_size_changes"].values()) == sorted(
                per_event["leg_size_changes"].values()
            )
            assert sorted(
                e["notional_per_unit"]
                for e in whole_event["cost_exposures"].values()
            ) == sorted(
                e["notional_per_unit"]
                for e in per_event["cost_exposures"].values()
            )

        assert (
            whole_trade.structure_history[0].legs[0].current_size
            == per_trade.structure_history[0].legs[0].current_size
            == 0.0
        )


class TestDuplicateStructureMods:
    """B3a: two same-day actions may not target one structure."""

    def _engine(self, simple_csv, side_effect):
        backend = CsvBackend(base_dir=simple_csv)
        data_feed = DataFeed(backend)
        pricer = EquityPricer(EquityPriceProvider(data_feed))
        config = AssetClassConfig(pricer=pricer, risk_measures=[])
        signal = _make_mock_signal()
        signal.generate_action_groups.side_effect = side_effect
        return Backtester(
            BacktestConfig(
                signal=signal,
                start_date="2024-01-02",
                end_date="2024-01-05",
                asset_class_configs={"equity": config},
                calendar_provider=CalendarProvider(data_feed),
                simulation_calendar_codes=None,
            )
        )

    def _two_structure_trade(self):
        structure = StructureSpec(
            legs=(
                LegSpec(
                    ContractSpec("TEST", asset_class="equity"),
                    Side.LONG,
                    10.0,
                ),
            )
        )
        return _group(
            Action(
                type=ActionType.NEW,
                spec=TradeSpec(structures=(structure, structure)),
            )
        )

    def test_two_groups_targeting_same_structure_raise(self, simple_csv):
        def side_effect(data_view, action_group_log=None, position_book=None):
            if data_view.date == "2024-01-02":
                return [_new_trade("TEST", 100)]
            if data_view.date == "2024-01-03":
                holding = position_book.find_holding("TEST")
                return [
                    _unwind(
                        trade_id=holding.trade_id,
                        structure_id=holding.structure_id,
                    ),
                    _unwind(
                        trade_id=holding.trade_id,
                        structure_id=holding.structure_id,
                    ),
                ]
            return []

        bt = self._engine(simple_csv, side_effect)
        with pytest.raises(ValueError, match="targeted by multiple actions"):
            bt.run()

    def test_two_groups_targeting_distinct_structures_succeed(
        self, simple_csv
    ):
        def side_effect(data_view, action_group_log=None, position_book=None):
            if data_view.date == "2024-01-02":
                return [self._two_structure_trade()]
            if data_view.date == "2024-01-03":
                trade = position_book.trades[0]
                return [
                    _unwind(
                        trade_id=trade.trade_id,
                        structure_id=structure.structure_id,
                    )
                    for structure in trade.structures
                ]
            return []

        bt = self._engine(simple_csv, side_effect)
        result = bt.run()

        assert len(result.trade_history) == 1
        assert result.trade_history[0].exit_date == "2024-01-03"
        assert bt.active_trades == []

    def test_whole_trade_unwind_then_structure_unwind_raises(
        self, simple_csv
    ):
        def side_effect(data_view, action_group_log=None, position_book=None):
            if data_view.date == "2024-01-02":
                return [_new_trade("TEST", 100)]
            if data_view.date == "2024-01-03":
                holding = position_book.find_holding("TEST")
                return [
                    _unwind(trade_id=holding.trade_id),
                    _unwind(
                        trade_id=holding.trade_id,
                        structure_id=holding.structure_id,
                    ),
                ]
            return []

        bt = self._engine(simple_csv, side_effect)
        with pytest.raises(ValueError, match="targeted by multiple actions"):
            bt.run()

    def test_whole_book_unwind_then_any_structure_unwind_raises(
        self, simple_csv
    ):
        def side_effect(data_view, action_group_log=None, position_book=None):
            if data_view.date == "2024-01-02":
                return [_new_trade("TEST", 100)]
            if data_view.date == "2024-01-03":
                holding = position_book.find_holding("TEST")
                return [
                    _unwind(),
                    _unwind(
                        trade_id=holding.trade_id,
                        structure_id=holding.structure_id,
                    ),
                ]
            return []

        bt = self._engine(simple_csv, side_effect)
        with pytest.raises(ValueError, match="targeted by multiple actions"):
            bt.run()


class TestCommitPreconditionTripwire:
    """B3b: the commit guard fires independently of the upstream guards."""

    def _engine(self, simple_csv):
        backend = CsvBackend(base_dir=simple_csv)
        data_feed = DataFeed(backend)
        pricer = EquityPricer(EquityPriceProvider(data_feed))
        config = AssetClassConfig(pricer=pricer, risk_measures=[])
        return Backtester(
            BacktestConfig(
                signal=_make_mock_signal(orders_lookup={}),
                start_date="2024-01-02",
                end_date="2024-01-05",
                asset_class_configs={"equity": config},
                calendar_provider=CalendarProvider(data_feed),
                simulation_calendar_codes=None,
            )
        )

    def _open_trade(self, bt, size=40.0):
        from backtester.execution import SimulatedExecution

        record = bt.action_group_log.append(
            _new_trade("TEST", size), "2024-01-02"
        )
        ctx = AggregationContext(
            date="2024-01-02",
            action_group_log=ActionGroupLog(),
            execution_log=None,
            position_books=PositionBooks(),
            calendar=None,
            config=None,
        )
        order_group = action_group_to_order_group(
            record.action_group, record.action_ids, ctx
        )
        bt._dispatch_synthesized_order(
            record, order_group, "2024-01-02", SimulatedExecution()
        )
        return bt.active_trades[0]

    def _order_group(self, record, structure_id, trade_id, ticker="TEST",
                     quantity=10.0):
        return OrderGroup(
            orders=(
                Order(
                    action_id=record.action_ids[0],
                    order_id="order-1",
                    legs=(OrderLeg(ticker, OrderSide.SELL, quantity),),
                    structure_id=structure_id,
                    trade_id=trade_id,
                ),
            )
        )

    def test_commit_raises_when_trade_missing(self, simple_csv):
        bt = self._engine(simple_csv)
        record = bt.action_group_log.append(
            _unwind(trade_id="missing"), "2024-01-03"
        )
        order_group = self._order_group(
            record, "structure-1", "missing"
        )
        with pytest.raises(RuntimeError, match="commit invariant violated"):
            bt._commit_order_group(
                order_group, record, "2024-01-03", ()
            )

    def test_commit_raises_when_structure_missing(self, simple_csv):
        bt = self._engine(simple_csv)
        trade = self._open_trade(bt)
        record = bt.action_group_log.append(
            _unwind(trade_id=trade.trade_id, structure_id="missing"),
            "2024-01-03",
        )
        order_group = self._order_group(
            record, "missing", trade.trade_id
        )
        with pytest.raises(RuntimeError, match="commit invariant violated"):
            bt._commit_order_group(
                order_group, record, "2024-01-03", ()
            )

    def test_commit_raises_when_unmatched_leg_ticker(self, simple_csv):
        """The order leg's ticker is not in the target structure."""
        bt = self._engine(simple_csv)
        trade = self._open_trade(bt)
        structure = trade.active_structures[0]
        record = bt.action_group_log.append(
            _unwind(
                trade_id=trade.trade_id,
                structure_id=structure.structure_id,
            ),
            "2024-01-03",
        )
        order_group = self._order_group(
            record,
            structure.structure_id,
            trade.trade_id,
            ticker="WRONG_TICKER",
        )
        with pytest.raises(RuntimeError, match="commit invariant violated"):
            bt._commit_order_group(
                order_group, record, "2024-01-03", ()
            )

    def test_commit_raises_when_unwind_exceeds_size(self, simple_csv):
        bt = self._engine(simple_csv)
        trade = self._open_trade(bt, size=40.0)
        structure = trade.active_structures[0]
        record = bt.action_group_log.append(
            _unwind(
                trade_id=trade.trade_id,
                structure_id=structure.structure_id,
            ),
            "2024-01-03",
        )
        order_group = self._order_group(
            record,
            structure.structure_id,
            trade.trade_id,
            quantity=60.0,
        )
        with pytest.raises(RuntimeError, match="commit invariant violated"):
            bt._commit_order_group(
                order_group, record, "2024-01-03", ()
            )


class TestBacktesterActionGroupLog:
    """The loop's action-group pipeline: emission, finalize and the id chain."""

    def test_dispatched_record_carries_the_order_id(self, simple_csv):
        backend = CsvBackend(base_dir=simple_csv)
        data_feed = DataFeed(backend)
        pricer = EquityPricer(EquityPriceProvider(data_feed))
        config = AssetClassConfig(pricer=pricer, risk_measures=[])

        orders = {
            "2024-01-02": [
                _new_trade("TEST", 100)
            ],
        }
        signal = _make_mock_signal(orders_lookup=orders)
        bt = Backtester(
            BacktestConfig(
                signal=signal,
                start_date="2024-01-02",
                end_date="2024-01-05",
                asset_class_configs={"equity": config},
                calendar_provider=CalendarProvider(data_feed),
                simulation_calendar_codes=None,
            )
        )
        result = bt.run()

        records = bt.action_group_log.records
        assert len(records) == 1
        record = records[0]
        assert record.action_group.actions[0].type is ActionType.NEW
        assert record.action_group.emission_date == "2024-01-02"
        assert len(record.action_group.action_group_id) == 32
        assert record.order_ids
        assert record.order_outcomes == (OrderOutcome.FILLED,)
        assert len(record.action_ids) == len(record.action_group.actions)
        # Every accessor hands back the same live record, and the order id
        # never entered the legacy dict that execution consumed.
        assert bt.action_group_log.record_for(record.action_group.action_group_id) is record
        assert bt.action_group_log.records[-1] is record
        assert len(result.trade_history) == 1

    def test_no_action_groups_on_a_quiet_day(self, simple_csv):
        backend = CsvBackend(base_dir=simple_csv)
        data_feed = DataFeed(backend)
        pricer = EquityPricer(EquityPriceProvider(data_feed))
        config = AssetClassConfig(pricer=pricer, risk_measures=[])

        signal = _make_mock_signal(orders_lookup={})
        bt = Backtester(
            BacktestConfig(
                signal=signal,
                start_date="2024-01-02",
                end_date="2024-01-05",
                asset_class_configs={"equity": config},
                calendar_provider=CalendarProvider(data_feed),
                simulation_calendar_codes=None,
            )
        )
        bt.run()

        assert bt.action_group_log.records == ()
        assert len(bt.action_group_log) == 0

    def test_whole_trade_unwind_round_trips_through_the_loop(self, simple_csv):
        backend = CsvBackend(base_dir=simple_csv)
        data_feed = DataFeed(backend)
        pricer = EquityPricer(EquityPriceProvider(data_feed))
        config = AssetClassConfig(pricer=pricer, risk_measures=[])

        def side_effect(data_view, action_group_log=None, position_book=None):
            if data_view.date == "2024-01-02":
                return [_new_trade("TEST", 100)]
            if data_view.date == "2024-01-03":
                holding = position_book.find_holding("TEST")
                assert holding is not None
                return [_unwind(trade_id=holding.trade_id)]
            return []

        signal = _make_mock_signal()
        signal.generate_action_groups.side_effect = side_effect
        bt = Backtester(
            BacktestConfig(
                signal=signal,
                start_date="2024-01-02",
                end_date="2024-01-05",
                asset_class_configs={"equity": config},
                calendar_provider=CalendarProvider(data_feed),
                simulation_calendar_codes=None,
            )
        )
        result = bt.run()

        assert len(result.trade_history) == 1
        assert result.trade_history[0].exit_date == "2024-01-03"
        assert bt.active_trades == []
        # The whole-trade UNWIND action group indexed under its trade_id.
        whole = bt.action_group_log.records[-1]
        assert whole.action_group.actions[0].type is ActionType.UNWIND
        assert (
            whole.action_group.actions[0].trade_id
            == result.trade_history[0].trade_id
        )
        assert bt.action_group_log.by_trade(
            whole.action_group.actions[0].trade_id
        ) == (whole,)


class TestBacktesterExecutionSeam:
    """The loop's execution seam: report -> log -> trade linkage (5b-1)."""

    def _run(self, simple_csv, orders, start, end):
        backend = CsvBackend(base_dir=simple_csv)
        data_feed = DataFeed(backend)
        pricer = EquityPricer(EquityPriceProvider(data_feed))
        config = AssetClassConfig(pricer=pricer, risk_measures=[])
        bt = Backtester(
            BacktestConfig(
                signal=_make_mock_signal(orders_lookup=orders),
                start_date=start,
                end_date=end,
                asset_class_configs={"equity": config},
                calendar_provider=CalendarProvider(data_feed),
                simulation_calendar_codes=None,
            )
        )
        return bt, bt.run()

    def test_fill_writes_execution_log_and_trade_linkage(self, simple_csv):
        orders = {
            "2024-01-02": [
                _new_trade("TEST", 100)
            ],
        }
        bt, result = self._run(simple_csv, orders, "2024-01-02", "2024-01-05")

        assert len(result.trade_history) == 1
        trade = result.trade_history[0]
        exec_records = bt.execution_log.records
        assert len(exec_records) == 1
        rec = exec_records[0]
        assert rec.status == "FILLED"
        assert rec.fill_time == "2024-01-02"
        assert rec.fill_id and len(rec.fill_id) == 32
        assert rec.fills and rec.fills[0].ticker == "TEST"
        assert rec.fills[0].size == 100.0

        # trade <-> execution linkage
        assert trade.order_id == rec.order_id
        assert trade.fill_id == rec.fill_id
        assert trade.execution_marker == "external"
        assert bt.execution_log.record_for_fill(trade.fill_id) is rec
        assert (
            bt.action_group_log.records[0].action_group.action_group_id
            == rec.action_group_id
        )

    def test_built_but_blocked_structure_is_never_persisted(self, simple_csv):
        backend = CsvBackend(base_dir=simple_csv)
        data_feed = DataFeed(backend)

        class GappyPricer:
            def resolve_instrument(self, leg_dict, date):
                return Contract(
                    ticker=leg_dict.get("ticker", ""), asset_class="equity"
                )

            def price(self, contract, date):
                return None if date == "2024-01-03" else 100.0

            def valuation_data(self, contract, date, measures):
                return {}

            def pricing_inputs(self, contract, date):
                return {}

            def compute_cost_exposure(self, contract, date):
                return {"notional_per_unit": 100.0}

        config = AssetClassConfig(pricer=GappyPricer(), risk_measures=[])
        orders = {
            "2024-01-03": [
                _new_trade("TEST", 100)
            ],
        }
        bt = Backtester(
            BacktestConfig(
                signal=_make_mock_signal(orders_lookup=orders),
                start_date="2024-01-02",
                end_date="2024-01-05",
                asset_class_configs={"equity": config},
                calendar_provider=CalendarProvider(data_feed),
                simulation_calendar_codes=None,
            )
        )
        with pytest.warns(UserWarning, match="data not available"):
            result = bt.run()

        # Flow A: nothing was added then removed -- the build is discarded
        # before persistence, so no trade exists and no orphan structure does.
        assert list(result.trade_history) == []
        assert bt.active_trades == []
        assert len(bt.execution_log) == 1
        assert bt.execution_log.records[0].status == "BLOCKED"

    def test_unwind_pre_mutation_cost_timing(self, simple_csv, monkeypatch):
        from backtester.strategy_structure import StrategyStructure

        events = []
        original_unwind = StrategyStructure.unwind

        def unwinding(self, date, fraction=1.0, cost_exposures=None):
            events.append("unwind")
            return original_unwind(
                self, date, fraction=fraction,
                cost_exposures=cost_exposures,
            )

        monkeypatch.setattr(StrategyStructure, "unwind", unwinding)

        backend = CsvBackend(base_dir=simple_csv)
        data_feed = DataFeed(backend)

        class TracePricer(EquityPricer):
            def compute_cost_exposure(self, contract, date):
                events.append("cost")
                return super().compute_cost_exposure(contract, date)

        pricer = TracePricer(EquityPriceProvider(data_feed))
        config = AssetClassConfig(pricer=pricer, risk_measures=[])
        orders = {
            "2024-01-02": [
                _new_trade("TEST", 100)
            ],
            "2024-01-05": [
                _unwind()
            ],
        }
        bt = Backtester(
            BacktestConfig(
                signal=_make_mock_signal(orders_lookup=orders),
                start_date="2024-01-02",
                end_date="2024-01-09",
                asset_class_configs={"equity": config},
                calendar_provider=CalendarProvider(data_feed),
                simulation_calendar_codes=None,
            )
        )
        bt.run()

        # The unwind cost exposure must be computed *before* the unwind event.
        assert "unwind" in events
        unwind_idx = events.index("unwind")
        assert "cost" in events[:unwind_idx]


class TestCalendarGating:
    """Calendar gating is signal-side; the engine has no check stage."""

    def test_engine_no_longer_gates_on_the_calendar(self, simple_csv):
        """A price row on a union-closed day now fills: no engine check."""
        backend = CsvBackend(base_dir=simple_csv)
        data_feed = DataFeed(backend)
        pricer = EquityPricer(EquityPriceProvider(data_feed))
        config = AssetClassConfig(pricer=pricer, risk_measures=[])

        # 2024-01-04 is a US holiday, has a price row, and the US+UK union
        # keeps the day.  The retired check chain used to reject this.
        signal = _make_mock_signal(
            orders_lookup={"2024-01-04": [_new_trade("TEST", 100)]}
        )
        bt = Backtester(
            BacktestConfig(
                signal=signal,
                start_date="2024-01-02",
                end_date="2024-01-09",
                asset_class_configs={"equity": config},
                calendar_provider=CalendarProvider(data_feed),
                simulation_calendar_codes=["US", "UK"],
                ticker_to_calendar_code={"TEST": "US"},
            )
        )
        result = bt.run()

        assert len(result.trade_history) == 1
        assert bt.execution_log.records[0].status == "FILLED"

    def test_a_missing_price_still_blocks_at_execution(self, simple_csv):
        """A consistent-closed day has no row, so execution blocks + warns."""
        backend = CsvBackend(base_dir=simple_csv)
        data_feed = DataFeed(backend)
        pricer = EquityPricer(EquityPriceProvider(data_feed))
        config = AssetClassConfig(pricer=pricer, risk_measures=[])

        signal = _make_mock_signal(
            orders_lookup={"2024-02-02": [_new_trade("TEST", 100)]}
        )
        bt = Backtester(
            BacktestConfig(
                signal=signal,
                start_date="2024-01-02",
                end_date="2024-02-05",
                asset_class_configs={"equity": config},
                calendar_provider=CalendarProvider(data_feed),
                simulation_calendar_codes=["US", "UK"],
                ticker_to_calendar_code={"TEST": "US"},
            )
        )
        with pytest.warns(UserWarning, match="data not available"):
            result = bt.run()

        assert list(result.trade_history) == []
        record = bt.action_group_log.records[0]
        assert record.order_outcomes == (OrderOutcome.BLOCKED,)
        assert bt.execution_log.records[0].status == "BLOCKED"

    def test_unmapped_ticker_is_calendar_blind(self, simple_csv):
        backend = CsvBackend(base_dir=simple_csv)
        data_feed = DataFeed(backend)
        pricer = EquityPricer(EquityPriceProvider(data_feed))
        config = AssetClassConfig(pricer=pricer, risk_measures=[])

        signal = _make_mock_signal(
            orders_lookup={"2024-01-04": [_new_trade("TEST", 100)]}
        )
        bt = Backtester(
            BacktestConfig(
                signal=signal,
                start_date="2024-01-02",
                end_date="2024-01-09",
                asset_class_configs={"equity": config},
                calendar_provider=CalendarProvider(data_feed),
                simulation_calendar_codes=["US", "UK"],
            )
        )
        assert len(bt.run().trade_history) == 1


@pytest.fixture(scope="module")
def sma_run():
    """The real SMA example once; the four HK-closed dates are pinned on it."""
    if not (MARKET_DATA_DIR / "2800.HK_eod.csv").exists():
        pytest.skip("repo market_data fixtures are not present")
    backend = CsvBackend(base_dir=str(MARKET_DATA_DIR))
    data_feed = DataFeed(backend)
    mapping = {"SPY": "US", "QQQ": "US", "2800.HK": "HK", "SXRT.DE": "DE"}
    pricer = EquityPricer(
        EquityPriceProvider(data_feed), ticker_to_calendar_code=mapping
    )
    calendar = CalendarProvider(data_feed)
    signal = SMACrossoverSignal(
        short_window=20,
        long_window=50,
        tickers=list(mapping),
        notional=100_000,
        ticker_currency={"2800.HK": "HKD", "SXRT.DE": "EUR"},
        calendar_provider=calendar,
        ticker_to_calendar_code=mapping,
    )
    bt = Backtester(
        BacktestConfig(
            signal=signal,
            start_date="2000-01-01",
            end_date="2025-12-31",
            asset_class_configs={
                "equity": AssetClassConfig(pricer=pricer, risk_measures=[])
            },
            calendar_provider=calendar,
            simulation_calendar_codes=["US", "HK", "DE"],
            ticker_to_calendar_code=mapping,
            data_feed=data_feed,
        )
    )
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = bt.run()
    return bt, result, [str(w.message) for w in caught]


class TestSmaCalendarGating:
    FOUR = ("2009-01-26", "2009-01-27", "2009-01-28", "2012-04-04")

    def test_no_action_group_record_exists_on_the_four_hk_closed_days(
        self, sma_run
    ):
        bt, _result, _warnings = sma_run
        emitted = {
            record.action_group.emission_date
            for record in bt.action_group_log.records
        }
        for day in self.FOUR:
            assert day not in emitted

    def test_the_trades_close_on_the_next_open_day(self, sma_run):
        """Pre-C reject -> T+1 re-emit; post-C non-emission -> same exit."""
        _bt, result, _warnings = sma_run
        exits = {
            trade.exit_date
            for trade in result.trade_history
            if trade.structure_history[0].legs[0].contract.ticker == "2800.HK"
        }
        assert "2009-01-29" in exits  # next HK open after 01-26/27/28
        assert "2012-04-05" in exits  # next HK open after 04-04

    def test_every_record_is_finalized_and_none_rejected(self, sma_run):
        """No rejection path: 457 records, every one carries its facts."""
        bt, _result, _warnings = sma_run
        records = bt.action_group_log.records
        assert len(records) == 457
        assert all(record.order_ids for record in records)

    def test_the_run_emits_no_warnings(self, sma_run):
        _bt, _result, caught = sma_run
        assert caught == []


class TestCalendarIntegration:
    """The CalendarProvider, not the price data, defines the simulation loop."""

    def test_calendar_is_authoritative_over_data_derived_days(self, simple_csv):
        """A calendar holiday is skipped even though the price CSV has it,
        and a calendar trading day with no price data is still iterated."""
        backend = CsvBackend(base_dir=simple_csv)
        data_feed = DataFeed(backend)
        provider = EquityPriceProvider(data_feed)
        pricer = EquityPricer(provider)
        config = AssetClassConfig(pricer=pricer, risk_measures=[])

        orders = {
            "2024-01-02": [
                _new_trade("TEST", 100)
            ],
        }
        signal = _make_mock_signal(orders_lookup=orders)

        bt_config = BacktestConfig(
            signal=signal,
            start_date="2024-01-02",
            end_date="2024-01-11",
            asset_class_configs={"equity": config},
            calendar_provider=CalendarProvider(data_feed),
            simulation_calendar_codes=["US"],
        )
        bt = Backtester(bt_config)
        result = bt.run()

        # 2024-01-04 exists in the price CSV (close 102.0) but US.csv marks
        # it a holiday, so the calendar -- not the data -- wins.
        assert "2024-01-04" in data_feed.get_series("eod_prices", None, None, "TEST").index
        assert "2024-01-04" not in result.trading_days

        # The calendar runs to 2024-01-11: 01-06/07 are a weekend, 01-04 is a
        # holiday, and 01-10/01-11 are business days with no price data at all.
        # Under the old data-derived calendar those last two could never appear.
        assert result.trading_days == (
            "2024-01-02",
            "2024-01-03",
            "2024-01-05",
            "2024-01-08",
            "2024-01-09",
            "2024-01-10",
            "2024-01-11",
        )

        trade = list(result.trade_history)[0]
        leg = trade.structure_history[0].legs[0]
        # Entry day (0.0) plus one PnL entry per subsequent simulated day.
        assert len(leg.daily_total_pnl) == 7
        # 2024-01-10/11 lie outside the price CSV -> NaN; current_price is
        # frozen at the last valid mark (105.0 on 2024-01-09).
        assert np.isnan(leg.daily_total_pnl[5])
        assert np.isnan(leg.daily_total_pnl[6])
        assert leg.current_price == 105.0

    def test_union_calendar_keeps_single_code_holiday(self, simple_csv):
        """A day closed in one code but open in another stays in the union."""
        backend = CsvBackend(base_dir=simple_csv)
        data_feed = DataFeed(backend)
        provider = EquityPriceProvider(data_feed)
        pricer = EquityPricer(provider)
        config = AssetClassConfig(pricer=pricer, risk_measures=[])

        signal = _make_mock_signal(orders_lookup={})

        bt_config = BacktestConfig(
            signal=signal,
            start_date="2024-01-02",
            end_date="2024-01-09",
            asset_class_configs={"equity": config},
            calendar_provider=CalendarProvider(data_feed),
            simulation_calendar_codes=["US", "UK"],
        )
        bt = Backtester(bt_config)
        result = bt.run()

        # US is closed 2024-01-04, UK is closed 2024-01-05; neither is a
        # holiday in *every* code, so the union keeps both.
        assert "2024-01-04" in result.trading_days
        assert "2024-01-05" in result.trading_days

        us_only = BacktestConfig(
            signal=signal,
            start_date="2024-01-02",
            end_date="2024-01-09",
            asset_class_configs={"equity": config},
            calendar_provider=CalendarProvider(data_feed),
            simulation_calendar_codes=["US"],
        )
        us_only_days = Backtester(us_only).run().trading_days
        assert "2024-01-04" not in us_only_days
