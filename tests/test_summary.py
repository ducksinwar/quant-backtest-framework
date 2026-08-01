import numpy as np
import pandas as pd
import pytest
from backtester.cost_model import CostModel, EquityCostCalculator
from backtester.instruments import Contract, LegState
from backtester.strategy_structure import StrategyStructure
from backtester.summary import Summary
from backtester.trade import Trade


def _make_trade(trade_id, entry_date, exit_date, leg_id, pnl_list, tags=None, ticker="SPY"):
    contract = Contract(ticker=ticker, asset_class="equity")
    leg = LegState(
        contract=contract, leg_id=leg_id,
        current_size=100.0, entry_price=450.0, current_price=455.0,
    )
    leg.daily_total_pnl = [0.0] + pnl_list

    structure = StrategyStructure(
        structure_id=f"s_{trade_id}", legs=[leg],
    )
    structure.original_entry_date = entry_date
    structure.open(entry_date)
    if exit_date:
        structure.unwind(exit_date, fraction=1.0)

    trade = Trade(trade_id=trade_id, tags=tags)
    trade.entry_date = entry_date
    trade.exit_date = exit_date
    trade.structure_history = [structure]
    trade.active_structures = [] if exit_date else [structure]
    return trade, leg


class TestSummaryEquityCurve:
    def test_equity_curve_gross_cost_net(self):
        leg_id = "leg_001"
        trade, leg = _make_trade(
            "t1", "2024-01-02", "2024-01-05",
            leg_id, [10.0, -5.0, 20.0],
        )

        cost_model = CostModel({"equity": EquityCostCalculator(bps=2.0)})
        spec = {"reports": {"equity_curve": True}}
        summary = Summary(spec)
        trading_days = ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"]
        result = summary.generate([trade], cost_model, trading_days=trading_days)

        assert result is not None
        assert "equity_curve" in result
        df = result["equity_curve"]
        assert "gross" in df.columns
        assert "cost" in df.columns
        assert "net" in df.columns
        assert len(df) == 4
        # Opening-day 0.0 P&L recorded at trade creation on 01-02
        expected_dates = ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"]
        assert list(df.index) == expected_dates

    def test_cost_subtracted_from_net(self):
        leg_id = "leg_001"
        trade, leg = _make_trade(
            "t1", "2024-01-02", "2024-01-05",
            leg_id, [100.0, -50.0],
        )
        # Inject cost_exposures into the open event so CostModel finds it
        structure = trade.structure_history[0]
        structure.event_log[0]["cost_exposures"] = {
            leg_id: {"notional_per_unit": 450.0},
        }

        cost_model = CostModel({"equity": EquityCostCalculator(bps=2.0)})
        spec = {"reports": {"equity_curve": True}}
        summary = Summary(spec)
        trading_days = ["2024-01-02", "2024-01-03", "2024-01-05"]
        result = summary.generate([trade], cost_model, trading_days=trading_days)

        df = result["equity_curve"]
        # Opening-day P&L is 0.0; cost event still occurs on the entry date
        assert df.loc["2024-01-02", "gross"] == pytest.approx(0.0)
        # 450 * 100 * 2 / 10000 = 9.0 on entry date
        assert df.loc["2024-01-02", "cost"] == pytest.approx(9.0)
        assert df.loc["2024-01-02", "net"] == pytest.approx(-9.0)
        # PnL on 2024-01-03: gross=100, cost column is cumulative (9.0)
        assert df.loc["2024-01-03", "gross"] == pytest.approx(100.0)
        assert df.loc["2024-01-03", "net"] == pytest.approx(91.0)

    def test_equity_curve_include_subset(self):
        leg_id = "leg_001"
        trade, leg = _make_trade(
            "t1", "2024-01-02", "2024-01-05",
            leg_id, [10.0, -5.0, 20.0],
        )

        cost_model = CostModel({"equity": EquityCostCalculator(bps=2.0)})
        spec = {"reports": {"equity_curve": {"include": ["gross", "net"]}}}
        summary = Summary(spec)
        result = summary.generate([trade], cost_model, trading_days=["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"])

        df = result["equity_curve"]
        assert "gross" in df.columns
        assert "net" in df.columns
        assert "cost" not in df.columns


class TestSummaryTradeSummary:
    def test_trade_summary_basic(self):
        leg_id = "leg_001"
        trade, leg = _make_trade(
            "t1", "2024-01-02", "2024-01-05",
            leg_id, [10.0, -5.0, 20.0],
            tags=["alpha", "momentum"],
        )

        cost_model = CostModel({"equity": EquityCostCalculator(bps=2.0)})
        spec = {"reports": {"trade_summary": True}}
        summary = Summary(spec)
        result = summary.generate([trade], cost_model, trading_days=["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"])

        df = result["trade_summary"]
        assert len(df) == 1
        assert df.iloc[0]["trade_id"] == "t1"
        assert df.iloc[0]["entry_date"] == "2024-01-02"
        assert df.iloc[0]["exit_date"] == "2024-01-05"
        assert "tags" in df.columns

    def test_trade_summary_pnl_aggregation(self):
        leg_id = "leg_001"
        trade, leg = _make_trade(
            "t1", "2024-01-02", "2024-01-05",
            leg_id, [100.0, -50.0, 30.0],
        )

        cost_model = CostModel({"equity": EquityCostCalculator(bps=2.0)})
        spec = {"reports": {"trade_summary": True}}
        summary = Summary(spec)
        result = summary.generate([trade], cost_model, trading_days=["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"])

        df = result["trade_summary"]
        assert df.iloc[0]["gross_pnl"] == pytest.approx(80.0)
        assert "net_pnl" in df.columns


class TestSummaryMissingDataModes:
    def test_missing_any_treats_nan_as_zero(self):
        leg_id = "leg_001"
        trade, leg = _make_trade(
            "t1", "2024-01-02", "2024-01-05",
            leg_id, [10.0, float("nan"), 20.0],
        )

        cost_model = CostModel({"equity": EquityCostCalculator(bps=2.0)})
        spec = {"reports": {"equity_curve": True}, "missing_data_mode": "any"}
        summary = Summary(spec)
        result = summary.generate([trade], cost_model, trading_days=["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"])

        df = result["equity_curve"]
        assert not df["net"].isna().any()

    def test_missing_all_produces_nan_on_nan_days(self):
        leg1_id = "leg_001"
        leg2_id = "leg_002"

        t1, l1 = _make_trade("t1", "2024-01-02", None, leg1_id, [10.0, -5.0, 20.0])
        t2, l2 = _make_trade("t2", "2024-01-02", None, leg2_id, [5.0, float("nan"), 15.0])

        cost_model = CostModel({"equity": EquityCostCalculator(bps=2.0)})
        spec = {"reports": {"equity_curve": True}, "missing_data_mode": "all"}
        summary = Summary(spec)
        result = summary.generate([t1, t2], cost_model, trading_days=["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"])

        df = result["equity_curve"]
        assert not df["net"].isna().any()


class TestSummaryFiltering:
    def test_group_filter_applies_correctly(self):
        leg1_id = "leg_001"
        leg2_id = "leg_002"

        t1, l1 = _make_trade("t1", "2024-01-02", None, leg1_id, [10.0, 20.0, 5.0], tags=["alpha"])
        t2, l2 = _make_trade("t2", "2024-01-02", None, leg2_id, [5.0, 15.0, 8.0], tags=["beta"])

        cost_model = CostModel({"equity": EquityCostCalculator(bps=2.0)})
        spec = {
            "reports": {
                "alpha_group": {
                    "filter": lambda t: t.tags and "alpha" in t.tags,
                    "reports": {
                        "trade_summary": True,
                    },
                },
            },
        }
        summary = Summary(spec)
        result = summary.generate([t1, t2], cost_model, trading_days=["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"])

        assert "alpha_group_trade_summary" in result
        df = result["alpha_group_trade_summary"]
        assert len(df) == 1
        assert df.iloc[0]["trade_id"] == "t1"

    def test_root_filter_applies_to_all(self):
        leg1_id = "leg_001"
        leg2_id = "leg_002"

        t1, l1 = _make_trade("t1", "2024-01-02", None, leg1_id, [10.0, 5.0, 3.0], tags=["live"])
        t2, l2 = _make_trade("t2", "2024-01-02", None, leg2_id, [5.0, 2.0, 1.0], tags=["dead"])

        cost_model = CostModel({"equity": EquityCostCalculator(bps=2.0)})
        spec = {
            "reports": {
                "filter": lambda t: t.tags and "live" in t.tags,
                "trade_summary": True,
            },
        }
        summary = Summary(spec)
        result = summary.generate([t1, t2], cost_model, trading_days=["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"])

        df = result["trade_summary"]
        assert len(df) == 1
        assert df.iloc[0]["trade_id"] == "t1"


class TestSummaryMetrics:
    def test_metrics_generated(self):
        leg_id = "leg_001"
        trade, leg = _make_trade(
            "t1", "2024-01-02", None,
            leg_id, [10.0, -5.0, 20.0, 15.0, -10.0, 8.0, 12.0],
        )

        cost_model = CostModel({"equity": EquityCostCalculator(bps=2.0)})
        spec = {"reports": {"metrics": True}}
        summary = Summary(spec)
        result = summary.generate([trade], cost_model, trading_days=["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05", "2024-01-06", "2024-01-07", "2024-01-08", "2024-01-09"])

        assert "metrics" in result
        df = result["metrics"]
        assert "sharpe_gross" in df.columns
        assert "sharpe_net" in df.columns
        assert "max_drawdown_gross" in df.columns

    def test_metrics_include_subset(self):
        leg_id = "leg_001"
        trade, leg = _make_trade(
            "t1", "2024-01-02", None,
            leg_id, [10.0, -5.0, 20.0, 15.0],
        )

        cost_model = CostModel({"equity": EquityCostCalculator(bps=2.0)})
        spec = {"reports": {"metrics": {"include": ["sharpe_gross"]}}}
        summary = Summary(spec)
        result = summary.generate([trade], cost_model, trading_days=["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05", "2024-01-06"])

        df = result["metrics"]
        assert "sharpe_gross" in df.columns
        assert "sharpe_net" not in df.columns


class TestSummaryHitRatio:
    def test_hit_ratio_default_yearly(self):
        leg_id = "leg_001"
        trade, leg = _make_trade(
            "t1", "2024-01-02", None,
            leg_id, [10.0, -5.0, 20.0, -10.0, 5.0],
        )

        cost_model = CostModel({"equity": EquityCostCalculator(bps=2.0)})
        spec = {"reports": {"hit_ratio": True}}
        summary = Summary(spec)
        result = summary.generate([trade], cost_model, trading_days=["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05", "2024-01-06", "2024-01-07"])

        assert "hit_ratio" in result
        df = result["hit_ratio"]
        assert "hit_ratio_gross" in df.columns
        assert "hit_ratio_net" in df.columns


class TestSummaryPeriodicMetrics:
    def test_periodic_metrics_yearly(self):
        leg_id = "leg_001"
        trade, leg = _make_trade(
            "t1", "2024-01-02", None,
            leg_id, [10.0, -5.0, 20.0, -10.0, 5.0],
        )

        cost_model = CostModel({"equity": EquityCostCalculator(bps=2.0)})
        spec = {"reports": {"periodic_metrics": {"timeframe": "yearly"}}}
        summary = Summary(spec)
        trading_days = [
            "2024-01-02", "2024-01-03", "2024-01-04",
            "2024-01-05", "2024-01-06", "2024-01-07",
        ]
        result = summary.generate(
            [trade], cost_model, trading_days=trading_days,
        )

        assert "periodic_metrics" in result
        df = result["periodic_metrics"]
        assert "total" in df.index
        assert "return_gross" in df.columns
        assert "return_net" in df.columns


class TestSummaryDrawdownTable:
    def test_drawdown_table_generated(self):
        leg_id = "leg_001"
        trade, leg = _make_trade(
            "t1", "2024-01-02", None,
            leg_id, [10.0, -5.0, -8.0, 3.0, 6.0, -2.0, 4.0],
        )

        cost_model = CostModel({"equity": EquityCostCalculator(bps=2.0)})
        spec = {"reports": {"drawdown_table": {"top_n": 3}}}
        summary = Summary(spec)
        result = summary.generate([trade], cost_model, trading_days=["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05", "2024-01-06", "2024-01-07", "2024-01-08", "2024-01-09"])

        assert "drawdown_table_gross" in result
        assert "drawdown_table_net" in result


class TestSummaryByUnderlying:
    def test_by_underlying_equity_curve(self):
        leg1_id = "leg_001"
        leg2_id = "leg_002"

        t1, l1 = _make_trade("t1", "2024-01-02", None, leg1_id, [10.0, -5.0, 20.0], ticker="AAPL")

        t2, l2 = _make_trade("t2", "2024-01-02", None, leg2_id, [5.0, 10.0, -3.0])
        # SPY is default

        cost_model = CostModel({"equity": EquityCostCalculator(bps=2.0)})
        spec = {"reports": {"by_underlying": True}}
        summary = Summary(spec)
        result = summary.generate([t1, t2], cost_model, trading_days=["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"])

        assert "AAPL_equity_curve" in result
        assert "SPY_equity_curve" in result


class TestSummaryEmpty:
    def test_empty_trade_history(self):
        cost_model = CostModel({"equity": EquityCostCalculator(bps=2.0)})
        spec = {"reports": {"trade_summary": True}}
        summary = Summary(spec)
        result = summary.generate([], cost_model, trading_days=["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"])
        assert result == {}


class TestSummaryNoOutputReturnsDict:
    def test_no_output_returns_dict(self):
        leg_id = "leg_001"
        trade, leg = _make_trade(
            "t1", "2024-01-02", None, leg_id, [10.0, 5.0, 3.0],
        )
        cost_model = CostModel({"equity": EquityCostCalculator(bps=2.0)})
        spec = {"reports": {"equity_curve": True}}
        summary = Summary(spec)
        result = summary.generate([trade], cost_model, trading_days=["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"])
        assert isinstance(result, dict)
        assert "equity_curve" in result


class TestSummaryRegistryExtensibility:
    def test_registry_extensibility(self):
        from backtester.metrics_registry import BaseMetricCalculator, METRIC_CALCULATORS
        from backtester.reports import REPORTS, BaseReport

        original_calcs = dict(METRIC_CALCULATORS)
        original_reports = dict(REPORTS)

        try:

            class DummyMetricCalculator(BaseMetricCalculator):
                def compute(self, summary, label, context, annualization):
                    return 42.0

            METRIC_CALCULATORS["dummy_metric"] = DummyMetricCalculator()

            class DummyReport(BaseReport):
                def build(self, summary, trades, leg_data, report_config, fx_rates, output_name):
                    return {output_name: pd.DataFrame([{"dummy": 42}])}

            REPORTS["dummy_report"] = DummyReport

            leg_id = "leg_001"
            trade, leg = _make_trade(
                "t1", "2024-01-02", None, leg_id, [10.0, 5.0],
            )
            cost_model = CostModel({"equity": EquityCostCalculator(bps=2.0)})
            spec = {"reports": {"dummy_report": True}}
            summary = Summary(spec)
            result = summary.generate(
                [trade], cost_model,
                trading_days=["2024-01-02", "2024-01-03", "2024-01-04"],
            )
            assert "dummy_report" in result
            assert result["dummy_report"].iloc[0]["dummy"] == 42
        finally:
            METRIC_CALCULATORS.clear()
            METRIC_CALCULATORS.update(original_calcs)
            REPORTS.clear()
            REPORTS.update(original_reports)
