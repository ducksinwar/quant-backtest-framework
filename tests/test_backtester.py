import dataclasses
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock

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
from backtester.strategy_structure import StrategyStructure
from backtester.trade import Trade

# Committed holiday fixtures (mirrors the tests/test_data/SPY_eod.csv pattern).
# US.csv marks 2024-01-04 and 2024-02-02 as non-trading days.
HOLIDAY_DIR = Path(__file__).parent / "test_data" / "holidays"


def _make_mock_signal(orders_lookup=None, requires_portfolio=False, requires_history=False):
    """Create a mock signal that returns pre-programmed orders per date."""
    mock = MagicMock()
    type(mock).requires_portfolio_state = PropertyMock(return_value=requires_portfolio)
    type(mock).requires_trade_history = PropertyMock(return_value=requires_history)

    if orders_lookup:
        def generate_side_effect(current_date, portfolio_state=None, trade_history_snapshot=None):
            return orders_lookup.get(current_date, [])
        mock.generate_signals.side_effect = generate_side_effect
    else:
        mock.generate_signals.return_value = []

    return mock


def _make_csv(tmp_path, rows):
    """Write a tiny CSV for testing and return path."""
    csv_path = tmp_path / "TEST_eod.csv"
    csv_path.write_text("date,close\n" + "\n".join(f"{d},{p}" for d, p in rows))
    return str(tmp_path)


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
                {
                    "Action": "NEW",
                    "trade_id": None,
                    "info": [
                        {
                            "structure_id": None,
                            "legs": [{"ticker": "TEST", "size": 100, "asset_class": "equity"}],
                        }
                    ],
                }
            ],
            "2024-01-05": [
                {
                    "Action": "UNWIND",
                    "trade_id": None,
                    "info": [],
                }
            ],
        }
        signal = _make_mock_signal(orders_lookup=orders, requires_portfolio=False)

        bt_config = BacktestConfig(
            signal=signal,
            start_date="2024-01-02",
            end_date="2024-01-09",
            asset_class_configs={"equity": config},
            calendar_provider=CalendarProvider(),
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

        signal = _make_mock_signal(orders_lookup={}, requires_portfolio=False)
        bt_config = BacktestConfig(
            signal=signal,
            start_date="2024-01-02",
            end_date="2024-01-05",
            asset_class_configs={"equity": config},
            calendar_provider=CalendarProvider(),
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
                {
                    "Action": "NEW",
                    "trade_id": None,
                    "info": [
                        {
                            "structure_id": None,
                            "legs": [{"ticker": "TEST", "size": 100, "asset_class": "equity"}],
                        }
                    ],
                }
            ],
            "2024-01-08": [
                {
                    "Action": "UNWIND",
                    "trade_id": None,
                    "info": [],
                }
            ],
        }
        signal = _make_mock_signal(orders_lookup=orders, requires_portfolio=False)
        bt_config = BacktestConfig(
            signal=signal,
            start_date="2024-01-02",
            end_date="2024-01-09",
            asset_class_configs={"equity": config},
            calendar_provider=CalendarProvider(),
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
                {
                    "Action": "NEW",
                    "trade_id": None,
                    "info": [
                        {
                            "structure_id": None,
                            "legs": [{"ticker": "TEST", "size": 100, "asset_class": "equity"}],
                        }
                    ],
                }
            ],
        }
        signal = _make_mock_signal(orders_lookup=orders, requires_portfolio=False)
        bt_config = BacktestConfig(
            signal=signal,
            start_date="2024-01-02",
            end_date="2024-01-09",
            asset_class_configs={"equity": config},
            calendar_provider=CalendarProvider(),
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
                {
                    "Action": "NEW",
                    "trade_id": None,
                    "info": [
                        {
                            "structure_id": None,
                            "legs": [
                                {
                                    "ticker": "TEST",
                                    "size": 10,
                                    "multiplier": 50.0,
                                    "asset_class": "equity",
                                }
                            ],
                        }
                    ],
                }
            ],
        }
        signal = _make_mock_signal(orders_lookup=orders, requires_portfolio=False)
        bt_config = BacktestConfig(
            signal=signal,
            start_date="2024-01-02",
            end_date="2024-01-09",
            asset_class_configs={"equity": config},
            calendar_provider=CalendarProvider(),
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
                    {
                        "Action": "NEW",
                        "trade_id": None,
                        "info": [{"structure_id": None, "legs": [{"ticker": "X", "size": 100, "asset_class": "equity"}]}],
                    }
                ],
            },
            requires_portfolio=False,
        )

        # Business-days-only calendar (no holiday_dir), so 2024-02-02 -- a
        # Friday on which the provider has no price -- is a simulated day and
        # exercises the genuine missing-price path.
        bt_config = BacktestConfig(
            signal=signal,
            start_date="2024-02-01",
            end_date="2024-02-05",
            asset_class_configs={"equity": config},
            calendar_provider=CalendarProvider(),
            simulation_calendar_codes=None,
        )
        bt = Backtester(bt_config)
        result = bt.run()
        history = list(result.trade_history)

        leg = history[0].structure_history[0].legs[0]
        assert len(leg.daily_total_pnl) >= 2
        assert any(np.isnan(x) for x in leg.daily_total_pnl)


class TestBacktesterPortfolioState:
    def test_portfolio_state_passed_when_flag_true(self, simple_csv):
        backend = CsvBackend(base_dir=simple_csv)
        data_feed = DataFeed(backend)
        provider = EquityPriceProvider(data_feed)
        pricer = EquityPricer(provider)
        config = AssetClassConfig(pricer=pricer, risk_measures=[])

        signal = _make_mock_signal(requires_portfolio=True, requires_history=False)

        bt_config = BacktestConfig(
            signal=signal,
            start_date="2024-01-02",
            end_date="2024-01-05",
            asset_class_configs={"equity": config},
            calendar_provider=CalendarProvider(),
            simulation_calendar_codes=None,
        )
        bt = Backtester(bt_config)
        bt.run()

        for call in signal.generate_signals.call_args_list:
            _, kwargs = call
            if kwargs.get("portfolio_state") is not None:
                assert isinstance(kwargs["portfolio_state"], PortfolioState)
                break

    def test_trade_history_snapshot_passed_when_flag_true(self, simple_csv):
        backend = CsvBackend(base_dir=simple_csv)
        data_feed = DataFeed(backend)
        provider = EquityPriceProvider(data_feed)
        pricer = EquityPricer(provider)
        config = AssetClassConfig(pricer=pricer, risk_measures=[])

        signal = _make_mock_signal(requires_portfolio=False, requires_history=True)

        bt_config = BacktestConfig(
            signal=signal,
            start_date="2024-01-02",
            end_date="2024-01-05",
            asset_class_configs={"equity": config},
            calendar_provider=CalendarProvider(),
            simulation_calendar_codes=None,
        )
        bt = Backtester(bt_config)
        bt.run()

        for call in signal.generate_signals.call_args_list:
            _, kwargs = call
            if kwargs.get("trade_history_snapshot") is not None:
                assert isinstance(kwargs["trade_history_snapshot"], tuple)
                break

    def test_snapshot_none_when_flags_false(self, simple_csv):
        backend = CsvBackend(base_dir=simple_csv)
        data_feed = DataFeed(backend)
        provider = EquityPriceProvider(data_feed)
        pricer = EquityPricer(provider)
        config = AssetClassConfig(pricer=pricer, risk_measures=[])

        signal = _make_mock_signal(requires_portfolio=False, requires_history=False)

        bt_config = BacktestConfig(
            signal=signal,
            start_date="2024-01-02",
            end_date="2024-01-05",
            asset_class_configs={"equity": config},
            calendar_provider=CalendarProvider(),
            simulation_calendar_codes=None,
        )
        bt = Backtester(bt_config)
        bt.run()

        for call in signal.generate_signals.call_args_list:
            _, kwargs = call
            assert kwargs["portfolio_state"] is None
            assert kwargs["trade_history_snapshot"] is None


class TestBacktesterUnknownAssetClass:
    def test_raises_on_unknown_asset_class(self, simple_csv):
        backend = CsvBackend(base_dir=simple_csv)
        data_feed = DataFeed(backend)
        provider = EquityPriceProvider(data_feed)
        pricer = EquityPricer(provider)
        config = AssetClassConfig(pricer=pricer, risk_measures=[])

        orders = {
            "2024-01-02": [
                {
                    "Action": "NEW",
                    "trade_id": None,
                    "info": [
                        {
                            "structure_id": None,
                            "legs": [{"ticker": "TEST", "size": 100, "asset_class": "fx_option"}],
                        }
                    ],
                }
            ],
        }
        signal = _make_mock_signal(orders_lookup=orders, requires_portfolio=False)
        bt_config = BacktestConfig(
            signal=signal,
            start_date="2024-01-02",
            end_date="2024-01-05",
            asset_class_configs={"equity": config},
            calendar_provider=CalendarProvider(),
            simulation_calendar_codes=None,
        )
        bt = Backtester(bt_config)
        with pytest.raises(ValueError, match="Unknown asset class"):
            bt.run()


class TestBacktesterRoll:
    def test_roll_raises_not_implemented(self, simple_csv):
        backend = CsvBackend(base_dir=simple_csv)
        data_feed = DataFeed(backend)
        provider = EquityPriceProvider(data_feed)
        pricer = EquityPricer(provider)
        config = AssetClassConfig(pricer=pricer, risk_measures=[])

        orders = {
            "2024-01-02": [
                {"Action": "ROLL", "trade_id": "some_id", "info": []}
            ],
        }
        signal = _make_mock_signal(orders_lookup=orders, requires_portfolio=False)
        bt_config = BacktestConfig(
            signal=signal,
            start_date="2024-01-02",
            end_date="2024-01-05",
            asset_class_configs={"equity": config},
            calendar_provider=CalendarProvider(),
            simulation_calendar_codes=None,
        )
        bt = Backtester(bt_config)
        with pytest.raises(NotImplementedError):
            bt.run()


class TestBacktesterDataAvailability:
    def test_new_order_rejected_when_price_is_none(self, simple_csv):
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
                {
                    "Action": "NEW",
                    "trade_id": None,
                    "info": [
                        {
                            "structure_id": None,
                            "legs": [
                                {"ticker": "TEST", "size": 100, "asset_class": "equity"}
                            ],
                        }
                    ],
                }
            ],
        }
        signal = _make_mock_signal(orders_lookup=orders, requires_portfolio=False)
        bt_config = BacktestConfig(
            signal=signal,
            start_date="2024-01-02",
            end_date="2024-01-05",
            asset_class_configs={"equity": config},
            calendar_provider=CalendarProvider(),
            simulation_calendar_codes=None,
        )
        bt = Backtester(bt_config)
        result = bt.run()
        history = list(result.trade_history)
        assert history == []

    def test_unwind_order_not_rejected_when_price_available(self, simple_csv):
        backend = CsvBackend(base_dir=simple_csv)
        data_feed = DataFeed(backend)
        provider = EquityPriceProvider(data_feed)
        pricer = EquityPricer(provider)
        config = AssetClassConfig(pricer=pricer, risk_measures=[])

        orders = {
            "2024-01-02": [
                {
                    "Action": "NEW",
                    "trade_id": None,
                    "info": [
                        {
                            "structure_id": None,
                            "legs": [
                                {"ticker": "TEST", "size": 100, "asset_class": "equity"}
                            ],
                        }
                    ],
                }
            ],
            "2024-01-05": [
                {"Action": "UNWIND", "trade_id": None, "info": []}
            ],
        }
        signal = _make_mock_signal(orders_lookup=orders, requires_portfolio=False)
        bt_config = BacktestConfig(
            signal=signal,
            start_date="2024-01-02",
            end_date="2024-01-09",
            asset_class_configs={"equity": config},
            calendar_provider=CalendarProvider(),
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

        def capture_side_effect(current_date, portfolio_state=None, trade_history_snapshot=None):
            if portfolio_state is not None:
                captured_states.append((current_date, portfolio_state))
            return []

        signal = _make_mock_signal(requires_portfolio=True, requires_history=False)
        signal.generate_signals.side_effect = capture_side_effect

        # Open trade on day 1 so we can inspect snapshots
        # Use the direct signal approach: first call returns NEW, rest empty
        call_count = [0]

        def step_side_effect(current_date, portfolio_state=None, trade_history_snapshot=None):
            if portfolio_state is not None:
                captured_states.append((current_date, portfolio_state))
            call_count[0] += 1
            if call_count[0] == 1:
                return [
                    {
                        "Action": "NEW",
                        "trade_id": None,
                        "info": [
                            {
                                "structure_id": None,
                                "legs": [
                                    {"ticker": "TEST", "size": 100, "asset_class": "equity"}
                                ],
                            }
                        ],
                    }
                ]
            return []

        signal.generate_signals.side_effect = step_side_effect

        bt_config = BacktestConfig(
            signal=signal,
            start_date="2024-01-02",
            end_date="2024-01-05",
            asset_class_configs={"equity": config},
            calendar_provider=CalendarProvider(),
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
                {
                    "Action": "NEW",
                    "trade_id": None,
                    "info": [
                        {
                            "structure_id": None,
                            "legs": [
                                {"ticker": "TEST", "size": 100, "asset_class": "equity"}
                            ],
                        }
                    ],
                }
            ],
        }
        signal = _make_mock_signal(orders_lookup=orders, requires_portfolio=False)
        bt_config = BacktestConfig(
            signal=signal,
            start_date="2024-01-02",
            end_date="2024-01-05",
            asset_class_configs={"equity": config},
            calendar_provider=CalendarProvider(),
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
                {
                    "Action": "NEW",
                    "trade_id": None,
                    "info": [
                        {
                            "structure_id": None,
                            "legs": [
                                {"ticker": "TEST", "size": 100, "asset_class": "equity"}
                            ],
                        }
                    ],
                }
            ],
            "2024-01-05": [
                {"Action": "UNWIND", "trade_id": None, "info": []}
            ],
        }
        signal = _make_mock_signal(orders_lookup=orders, requires_portfolio=False)
        bt_config = BacktestConfig(
            signal=signal,
            start_date="2024-01-02",
            end_date="2024-01-09",
            asset_class_configs={"equity": config},
            calendar_provider=CalendarProvider(),
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
                {
                    "Action": "NEW",
                    "trade_id": None,
                    "info": [
                        {
                            "structure_id": None,
                            "legs": [
                                {"ticker": "TEST", "size": 100, "asset_class": "equity"}
                            ],
                        }
                    ],
                }
            ],
        }
        signal = _make_mock_signal(orders_lookup=orders, requires_portfolio=False)
        bt_config = BacktestConfig(
            signal=signal,
            start_date="2024-01-02",
            end_date="2024-01-05",
            asset_class_configs={"equity": config},
            calendar_provider=CalendarProvider(),
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
                {
                    "Action": "NEW",
                    "trade_id": None,
                    "info": [
                        {
                            "structure_id": None,
                            "legs": [
                                {"ticker": "TEST", "size": 100, "asset_class": "equity"}
                            ],
                        }
                    ],
                }
            ],
        }
        signal = _make_mock_signal(orders_lookup=orders, requires_portfolio=False)
        bt_config = BacktestConfig(
            signal=signal,
            start_date="2024-01-02",
            end_date="2024-01-05",
            asset_class_configs={"equity": config},
            calendar_provider=CalendarProvider(),
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
            "2024-01-02": [{
                "Action": "NEW", "trade_id": None,
                "info": [{"structure_id": None, "legs": [
                    {"ticker": "TEST", "size": 100, "asset_class": "equity"}
                ]}],
            }],
        }
        signal = _make_mock_signal(orders_lookup=orders, requires_portfolio=False)
        bt_config = BacktestConfig(
            signal=signal, start_date="2024-01-02", end_date="2024-01-08",
            asset_class_configs={"equity": config},
            calendar_provider=CalendarProvider(),
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
                {
                    "Action": "NEW",
                    "trade_id": None,
                    "info": [
                        {
                            "structure_id": None,
                            "legs": [
                                {"ticker": "TEST", "size": 100, "asset_class": "equity"}
                            ],
                        }
                    ],
                }
            ],
        }
        signal = _make_mock_signal(orders_lookup=orders, requires_portfolio=False)
        bt_config = BacktestConfig(
            signal=signal,
            start_date="2024-01-02",
            end_date="2024-01-05",
            asset_class_configs={"equity": config},
            calendar_provider=CalendarProvider(),
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

        def capture_side_effect(current_date, portfolio_state=None, trade_history_snapshot=None):
            if trade_history_snapshot is not None:
                captured_snapshots.append((current_date, trade_history_snapshot))
            return []

        signal = _make_mock_signal(requires_portfolio=False, requires_history=True)
        signal.generate_signals.side_effect = capture_side_effect

        call_count = [0]

        def step_side_effect(current_date, portfolio_state=None, trade_history_snapshot=None):
            if trade_history_snapshot is not None:
                captured_snapshots.append((current_date, trade_history_snapshot))
            call_count[0] += 1
            if call_count[0] == 1:
                return [
                    {
                        "Action": "NEW",
                        "trade_id": None,
                        "info": [
                            {
                                "structure_id": None,
                                "legs": [
                                    {"ticker": "TEST", "size": 100, "asset_class": "equity"}
                                ],
                            }
                        ],
                    }
                ]
            elif call_count[0] == 2:
                return [
                    {"Action": "UNWIND", "trade_id": None, "info": []}
                ]
            return []

        signal.generate_signals.side_effect = step_side_effect

        bt_config = BacktestConfig(
            signal=signal,
            start_date="2024-01-02",
            end_date="2024-01-05",
            asset_class_configs={"equity": config},
            calendar_provider=CalendarProvider(),
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
                {
                    "Action": "NEW",
                    "trade_id": None,
                    "info": [
                        {
                            "structure_id": None,
                            "legs": [
                                {"ticker": "TEST", "size": 100, "asset_class": "equity"}
                            ],
                        }
                    ],
                }
            ],
        }
        signal = _make_mock_signal(orders_lookup=orders, requires_portfolio=False)

        bt_config = BacktestConfig(
            signal=signal,
            start_date="2024-01-02",
            end_date="2024-01-11",
            asset_class_configs={"equity": config},
            calendar_provider=CalendarProvider(holiday_dir=HOLIDAY_DIR),
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

        signal = _make_mock_signal(orders_lookup={}, requires_portfolio=False)

        bt_config = BacktestConfig(
            signal=signal,
            start_date="2024-01-02",
            end_date="2024-01-09",
            asset_class_configs={"equity": config},
            calendar_provider=CalendarProvider(holiday_dir=HOLIDAY_DIR),
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
            calendar_provider=CalendarProvider(holiday_dir=HOLIDAY_DIR),
            simulation_calendar_codes=["US"],
        )
        us_only_days = Backtester(us_only).run().trading_days
        assert "2024-01-04" not in us_only_days
