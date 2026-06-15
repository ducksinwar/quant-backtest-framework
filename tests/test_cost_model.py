import pandas as pd
import pytest
from backtester.cost_model import CostModel, FixedCostModel
from backtester.instruments.instrument import Instrument
from backtester.structures.strategy_structure import StrategyStructure
from backtester.trades.trade import Trade


class TestCostModel:
    def test_cannot_instantiate_abstract(self):
        with pytest.raises(TypeError):
            CostModel()


class TestFixedCostModel:
    @pytest.fixture
    def leg(self):
        inst = Instrument(
            ticker="SPY", asset_class="equity", leg_id="leg_1"
        )
        inst.current_size = 100.0
        return inst

    @pytest.fixture
    def structure(self, leg):
        return StrategyStructure(structure_id="struct_1", legs=[leg])

    @pytest.fixture
    def trade(self, structure):
        t = Trade(trade_id="trade_1")
        t.add_structure(structure, "2024-01-15")
        return t

    def test_compute_costs_single_trade(self, trade):
        model = FixedCostModel(fees={"equity": 2.0})
        result = model.compute_costs([trade])

        assert "leg_1" in result
        series = result["leg_1"]
        assert isinstance(series, pd.Series)
        assert len(series) == 1
        assert series.index[0] == "2024-01-15"
        assert series.iloc[0] == pytest.approx(100.0 * 2.0 / 10000.0)  # 0.02

    def test_compute_costs_multiple_events(self, trade, structure):
        trade.add_to_structure(structure, "2024-01-20", 50.0)
        trade.unwind_structure(structure, "2024-01-25", fraction=1.0)

        model = FixedCostModel(fees={"equity": 2.0})
        result = model.compute_costs([trade])

        series = result["leg_1"]
        assert len(series) == 3
        assert series.index[0] == "2024-01-15"
        assert series.index[1] == "2024-01-20"
        assert series.index[2] == "2024-01-25"

    def test_compute_costs_different_asset_class(self):
        leg = Instrument(
            ticker="ES", asset_class="equity_future", leg_id="leg_fut"
        )
        leg.current_size = 10.0
        structure = StrategyStructure(structure_id="sf", legs=[leg])
        trade = Trade(trade_id="tf")
        trade.add_structure(structure, "2024-02-01")

        model = FixedCostModel(fees={"equity": 2.0, "equity_future": 1.5})
        result = model.compute_costs([trade])

        series = result["leg_fut"]
        expected = 10.0 * 1.5 / 10000.0
        assert series.iloc[0] == pytest.approx(expected)

    def test_compute_costs_unknown_asset_class_gets_zero_bps(self):
        leg = Instrument(
            ticker="SPY", asset_class="crypto", leg_id="leg_c"
        )
        leg.current_size = 100.0
        structure = StrategyStructure(structure_id="sc", legs=[leg])
        trade = Trade(trade_id="tc")
        trade.add_structure(structure, "2024-03-01")

        model = FixedCostModel(fees={"equity": 2.0})
        result = model.compute_costs([trade])

        series = result["leg_c"]
        assert series.iloc[0] == 0.0

    def test_compute_costs_partial_unwind(self, trade, structure):
        trade.unwind_structure(structure, "2024-01-22", fraction=0.5)

        model = FixedCostModel(fees={"equity": 2.0})
        result = model.compute_costs([trade])

        series = result["leg_1"]
        assert len(series) == 2
        assert series.index[0] == "2024-01-15"
        assert series.index[1] == "2024-01-22"

    def test_compute_costs_empty_trades(self):
        model = FixedCostModel(fees={"equity": 2.0})
        result = model.compute_costs([])
        assert result == {}

    def test_compute_costs_missing_leg_id_skipped(self):
        leg = Instrument(
            ticker="SPY", asset_class="equity", leg_id=""
        )
        leg.current_size = 100.0
        structure = StrategyStructure(structure_id="snl", legs=[leg])
        trade = Trade(trade_id="tnl")
        trade.add_structure(structure, "2024-04-01")

        model = FixedCostModel(fees={"equity": 2.0})
        result = model.compute_costs([trade])
        assert "" not in result

    def test_compute_costs_aggregates_same_day(self):
        leg = Instrument(
            ticker="SPY", asset_class="equity", leg_id="leg_a"
        )
        leg.current_size = 100.0
        s1 = StrategyStructure(structure_id="s1", legs=[leg])
        t1 = Trade(trade_id="t1")
        t1.add_structure(s1, "2024-05-01")

        leg2 = Instrument(
            ticker="AAPL", asset_class="equity", leg_id="leg_a"
        )
        leg2.current_size = 200.0
        s2 = StrategyStructure(structure_id="s2", legs=[leg2])
        t2 = Trade(trade_id="t2")
        t2.add_structure(s2, "2024-05-01")

        model = FixedCostModel(fees={"equity": 2.0})
        result = model.compute_costs([t1, t2])
        series = result["leg_a"]
        assert len(series) == 1
        expected = (100.0 + 200.0) * 2.0 / 10000.0
        assert series.iloc[0] == pytest.approx(expected)
