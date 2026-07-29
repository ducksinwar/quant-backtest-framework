import pandas as pd
import pytest
from backtester.cost_model import (
    BaseCostCalculator,
    CostModel,
    EquityCostCalculator,
)
from backtester.instruments import Contract, LegState
from backtester.strategy_structure import StrategyStructure
from backtester.trade import Trade


def _make_trade_with_open_event(
    trade_id, leg_id, asset_class, date, size, cost_exposures=None
):
    contract = Contract(ticker="SPY", asset_class=asset_class)
    leg = LegState(
        contract=contract, leg_id=leg_id,
        current_size=size, current_price=450.0,
    )
    structure = StrategyStructure(
        structure_id=f"s_{trade_id}", legs=[leg],
    )
    structure.open(date, cost_exposures=cost_exposures)
    trade = Trade(trade_id=trade_id)
    trade.structure_history = [structure]
    return trade


class TestBaseCostCalculator:
    def test_cannot_instantiate_abstract(self):
        with pytest.raises(TypeError):
            BaseCostCalculator()


class TestEquityCostCalculator:
    def test_compute_cost_single_event(self):
        calculator = EquityCostCalculator(bps=2.0)
        event = {
            "date": "2024-01-15",
            "cost_exposures": {"leg_1": {"notional_per_unit": 450.0}},
            "unit_size_change": 100.0,
            "cost_free": False,
        }
        cost = calculator.compute_cost("leg_1", event)
        expected = 450.0 * 100.0 * 2.0 / 10000.0
        assert cost == pytest.approx(expected)


class TestCostModel:
    def test_compute_costs_with_equity_calculator(self):
        trade = _make_trade_with_open_event(
            "t1", "leg_1", "equity", "2024-01-15", 100.0,
            cost_exposures={"leg_1": {"notional_per_unit": 450.0}},
        )
        calculators = {"equity": EquityCostCalculator(bps=2.0)}
        model = CostModel(calculators)
        result = model.compute_costs([trade])

        assert "leg_1" in result
        series = result["leg_1"]
        assert isinstance(series, pd.Series)
        assert series.index[0] == "2024-01-15"
        expected = 450.0 * 100.0 * 2.0 / 10000.0
        assert series.iloc[0] == pytest.approx(expected)

    def test_compute_costs_empty_trades(self):
        model = CostModel({"equity": EquityCostCalculator(bps=2.0)})
        result = model.compute_costs([])
        assert result == {}

    def test_compute_costs_cost_free_skipped(self):
        trade = _make_trade_with_open_event(
            "t1", "leg_1", "equity", "2024-01-15", 100.0,
            cost_exposures={"leg_1": {"notional_per_unit": 450.0}},
        )
        # Mark all events cost-free
        for s in trade.structure_history:
            for e in s.event_log:
                e["cost_free"] = True

        model = CostModel({"equity": EquityCostCalculator(bps=2.0)})
        result = model.compute_costs([trade])
        assert result == {}

    def test_compute_costs_unknown_asset_class_skipped(self):
        trade = _make_trade_with_open_event(
            "t1", "leg_1", "crypto", "2024-03-01", 100.0,
            cost_exposures={"leg_1": {"notional_per_unit": 450.0}},
        )
        model = CostModel({"equity": EquityCostCalculator(bps=2.0)})
        result = model.compute_costs([trade])
        assert result == {}

    def test_compute_costs_multiple_legs(self):
        c1 = Contract(ticker="SPY", asset_class="equity")
        leg1 = LegState(contract=c1, leg_id="leg_a", current_size=100.0, current_price=450.0)
        c2 = Contract(ticker="AAPL", asset_class="equity")
        leg2 = LegState(contract=c2, leg_id="leg_b", current_size=100.0, current_price=200.0)

        structure = StrategyStructure(
            structure_id="s1", legs=[leg1, leg2],
        )
        structure.open(
            "2024-05-01",
            cost_exposures={
                "leg_a": {"notional_per_unit": 450.0},
                "leg_b": {"notional_per_unit": 200.0},
            },
        )
        trade = Trade(trade_id="t1")
        trade.structure_history = [structure]

        calculators = {"equity": EquityCostCalculator(bps=2.0)}
        model = CostModel(calculators)
        result = model.compute_costs([trade])

        assert "leg_a" in result
        assert "leg_b" in result
        assert len(result["leg_a"]) == 1
        assert len(result["leg_b"]) == 1

    def test_compute_costs_partial_unwind(self):
        contract = Contract(ticker="SPY", asset_class="equity")
        leg = LegState(contract=contract, leg_id="leg_1", current_size=100.0, current_price=450.0)
        structure = StrategyStructure(
            structure_id="s1", legs=[leg],
        )
        structure.open(
            "2024-01-15",
            cost_exposures={"leg_1": {"notional_per_unit": 450.0}},
        )
        structure.unwind(
            "2024-01-22", fraction=0.5,
            cost_exposures={"leg_1": {"notional_per_unit": 455.0}},
        )
        trade = Trade(trade_id="t1")
        trade.structure_history = [structure]

        calculators = {"equity": EquityCostCalculator(bps=2.0)}
        model = CostModel(calculators)
        result = model.compute_costs([trade])

        series = result["leg_1"]
        assert len(series) == 2
        # First event: 450 * 100 * 2 / 10000
        assert series.loc["2024-01-15"] == pytest.approx(
            450.0 * 100.0 * 2.0 / 10000.0
        )
        # Second event: 455 * 50 * 2 / 10000 (half unwound)
        assert series.loc["2024-01-22"] == pytest.approx(
            455.0 * 50.0 * 2.0 / 10000.0
        )

    def test_compute_costs_same_day_aggregation(self):
        c1 = Contract(ticker="SPY", asset_class="equity")
        leg = LegState(contract=c1, leg_id="leg_a", current_size=100.0, current_price=450.0)
        s1 = StrategyStructure(
            structure_id="s1", legs=[leg],
        )
        s1.open(
            "2024-05-01",
            cost_exposures={"leg_a": {"notional_per_unit": 450.0}},
        )

        c2 = Contract(ticker="AAPL", asset_class="equity")
        leg2 = LegState(contract=c2, leg_id="leg_a", current_size=200.0, current_price=200.0)
        s2 = StrategyStructure(
            structure_id="s2", legs=[leg2],
        )
        s2.open(
            "2024-05-01",
            cost_exposures={"leg_a": {"notional_per_unit": 200.0}},
        )

        t1 = Trade(trade_id="t1")
        t1.structure_history = [s1]
        t2 = Trade(trade_id="t2")
        t2.structure_history = [s2]

        calculators = {"equity": EquityCostCalculator(bps=2.0)}
        model = CostModel(calculators)
        result = model.compute_costs([t1, t2])

        series = result["leg_a"]
        assert len(series) == 1
        expected = (
            450.0 * 100.0 * 2.0 / 10000.0
            + 200.0 * 200.0 * 2.0 / 10000.0
        )
        assert series.iloc[0] == pytest.approx(expected)
