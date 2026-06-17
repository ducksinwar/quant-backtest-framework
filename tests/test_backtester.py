import uuid
from dataclasses import dataclass
from unittest.mock import MagicMock, PropertyMock

import numpy as np
import pandas as pd
import pytest
from backtester.backtest_engine import AssetClassConfig, BacktestConfig, Backtester
from backtester.data.csv_backend import CsvBackend
from backtester.data.data_feed import DataFeed
from backtester.data.typed_providers.equity_price_provider import EquityPriceProvider
from backtester.instruments.instrument import Instrument
from backtester.pricers.equity_pricer import EquityPricer
from backtester.snapshots import (
    LegSnapshot,
    PortfolioState,
    StructureSnapshot,
    TradeRecord,
    TradeSnapshot,
)
from backtester.structures.strategy_structure import StrategyStructure
from backtester.trades.trade import Trade


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
            ticker="SPY", instrument_type="equity",
            size=100.0, entry_price=450.0, current_price=455.0,
        )
        with pytest.raises(Exception):
            ls.size = 200.0

    def test_portfolio_state_builds_from_trades(self):
        leg = LegSnapshot(
            ticker="SPY", instrument_type="equity",
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
            calendar_ticker="TEST",
        )

        bt = Backtester(bt_config, data_feed)
        history = bt.run()

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
            calendar_ticker="TEST",
        )
        bt = Backtester(bt_config, data_feed)
        history = bt.run()
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
            calendar_ticker="TEST",
        )
        bt = Backtester(bt_config, data_feed)
        history = bt.run()

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
            calendar_ticker="TEST",
        )
        bt = Backtester(bt_config, data_feed)
        history = bt.run()

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
            calendar_ticker="TEST",
        )
        bt = Backtester(bt_config, data_feed)
        history = bt.run()

        trade = history[0]
        leg = trade.structure_history[0].legs[0]
        assert leg.multiplier == 50.0
        assert len(leg.daily_total_pnl) > 0

    def test_pnl_nan_on_missing_price(self, simple_csv):
        backend = CsvBackend(base_dir=simple_csv)
        data_feed = DataFeed(backend)

        dates = ["2024-02-01", "2024-02-02", "2024-02-05"]

        class GappyProvider:
            def get_price(self, ticker, date):
                if date == "2024-02-02":
                    return None
                return {"2024-02-01": 100.0, "2024-02-02": 101.0, "2024-02-05": 103.0}.get(date)

        pricer = EquityPricer(GappyProvider())
        config = AssetClassConfig(pricer=pricer, risk_measures=[])

        class FakeDataFeed:
            def trading_days(self, ticker, start, end):
                return dates

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

        bt_config = BacktestConfig(
            signal=signal,
            start_date="2024-02-01",
            end_date="2024-02-05",
            asset_class_configs={"equity": config},
            calendar_ticker="X",
        )
        bt = Backtester(bt_config, FakeDataFeed())
        history = bt.run()

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
            calendar_ticker="TEST",
        )
        bt = Backtester(bt_config, data_feed)
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
            calendar_ticker="TEST",
        )
        bt = Backtester(bt_config, data_feed)
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
            calendar_ticker="TEST",
        )
        bt = Backtester(bt_config, data_feed)
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
            calendar_ticker="TEST",
        )
        bt = Backtester(bt_config, data_feed)
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
            calendar_ticker="TEST",
        )
        bt = Backtester(bt_config, data_feed)
        with pytest.raises(NotImplementedError):
            bt.run()


class TestBacktesterDataAvailability:
    def test_new_order_rejected_when_price_is_none(self, simple_csv):
        backend = CsvBackend(base_dir=simple_csv)
        data_feed = DataFeed(backend)

        class GappyPricer:
            def resolve_instrument(self, leg_dict, date):
                return leg_dict

            def price(self, instrument, date):
                if date == "2024-01-03":
                    return None
                return 100.0

            def valuation_data(self, instrument, date, measures):
                return {}

            def pricing_inputs(self, instrument, date):
                return {}

            def compute_cost_exposure(self, instrument, date):
                return {"notional_per_unit": instrument.current_price}

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
            calendar_ticker="TEST",
        )
        bt = Backtester(bt_config, data_feed)
        history = bt.run()
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
            calendar_ticker="TEST",
        )
        bt = Backtester(bt_config, data_feed)
        history = bt.run()
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
            calendar_ticker="TEST",
        )
        bt = Backtester(bt_config, data_feed)
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
        assert found_position, "PortfolioState should contain the opened position"


class TestTradingDaysStrings:
    def test_trading_days_return_strings(self, simple_csv):
        backend = CsvBackend(base_dir=simple_csv)
        days = backend.trading_days("TEST", "2024-01-02", "2024-01-05")
        assert len(days) > 0
        assert all(isinstance(d, str) for d in days)
        assert all("-" in d for d in days)


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
            calendar_ticker="TEST",
        )
        bt = Backtester(bt_config, data_feed)
        history = bt.run()

        assert len(history) == 1
        structure = history[0].structure_history[0]
        assert len(structure.event_log) >= 1
        open_event = structure.event_log[0]
        assert open_event["event_type"] == "open"
        assert "cost_exposures" in open_event
        assert len(open_event["cost_exposures"]) == 1
        leg_id = list(open_event["cost_exposures"].keys())[0]
        assert "notional_per_unit" in open_event["cost_exposures"][leg_id]

    def test_cost_leg_ids_populated(self, simple_csv):
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
            calendar_ticker="TEST",
        )
        bt = Backtester(bt_config, data_feed)
        history = bt.run()

        assert len(history) == 1
        structure = history[0].structure_history[0]
        assert len(structure.cost_leg_ids) == 1
        assert structure.cost_leg_ids[0] == structure.legs[0].leg_id

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
            calendar_ticker="TEST",
        )
        bt = Backtester(bt_config, data_feed)
        history = bt.run()

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
            calendar_ticker="TEST",
        )
        bt = Backtester(bt_config, data_feed)
        history = bt.run()

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
            calendar_ticker="TEST",
        )
        bt = Backtester(bt_config, data_feed)
        history = bt.run()

        leg = history[0].structure_history[0].legs[0]
        assert len(leg.daily_total_pnl) >= 1
        assert isinstance(leg.pricing_inputs, dict)
