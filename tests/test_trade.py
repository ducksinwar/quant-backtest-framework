import pytest
from backtester.instruments import Contract, LegState
from backtester.strategy_structure import StrategyStructure
from backtester.trade import Trade


class TestTrade:
    @pytest.fixture
    def leg(self):
        contract = Contract(ticker="SPY", asset_class="equity")
        return LegState(
            contract=contract, leg_id="leg_1",
            current_size=100.0, current_price=450.0, entry_price=440.0,
        )

    @pytest.fixture
    def structure(self, leg):
        return StrategyStructure(structure_id="struct_1", legs=[leg])

    @pytest.fixture
    def trade(self):
        return Trade(trade_id="trade_1", tags=["alpha"])

    def test_add_structure_sets_entry_date(self, trade, structure):
        trade.add_structure(structure, "2024-01-15")
        assert trade.entry_date == "2024-01-15"

    def test_add_structure_appends_to_active(self, trade, structure):
        trade.add_structure(structure, "2024-01-15")
        assert len(trade.active_structures) == 1
        assert trade.active_structures[0] is structure

    def test_add_structure_appends_to_history(self, trade, structure):
        trade.add_structure(structure, "2024-01-15")
        assert len(trade.structure_history) == 1
        assert trade.structure_history[0] is structure

    def test_add_structure_records_open_event(self, trade, structure):
        trade.add_structure(structure, "2024-01-15")
        assert len(structure.event_log) == 1
        assert structure.event_log[0]["event_type"] == "open"

    def test_entry_date_not_overwritten(self, trade, structure):
        trade.add_structure(structure, "2024-01-15")
        s2 = StrategyStructure(
            structure_id="struct_2",
            legs=[LegState(
                contract=Contract(ticker="SPY", asset_class="equity"),
                leg_id="leg_2", current_size=50.0,
            )],
        )
        trade.add_structure(s2, "2024-02-01")
        assert trade.entry_date == "2024-01-15"

    def test_unwind_full_sets_exit_date(self, trade, structure):
        trade.add_structure(structure, "2024-01-15")
        trade.unwind_structure(structure, "2024-01-25", fraction=1.0)
        assert trade.exit_date == "2024-01-25"

    def test_unwind_full_removes_from_active(self, trade, structure):
        trade.add_structure(structure, "2024-01-15")
        trade.unwind_structure(structure, "2024-01-25", fraction=1.0)
        assert len(trade.active_structures) == 0

    def test_unwind_full_keeps_in_history(self, trade, structure):
        trade.add_structure(structure, "2024-01-15")
        trade.unwind_structure(structure, "2024-01-25", fraction=1.0)
        assert len(trade.structure_history) == 1

    def test_unwind_partial_does_not_set_exit_date(self, trade, structure):
        trade.add_structure(structure, "2024-01-15")
        trade.unwind_structure(structure, "2024-01-22", fraction=0.5)
        assert trade.exit_date is None

    def test_unwind_partial_keeps_in_active(self, trade, structure):
        trade.add_structure(structure, "2024-01-15")
        trade.unwind_structure(structure, "2024-01-22", fraction=0.5)
        assert len(trade.active_structures) == 1

    def test_unwind_partial_fraction_zero_three(self, trade, structure):
        trade.add_structure(structure, "2024-01-15")
        trade.unwind_structure(structure, "2024-01-22", fraction=0.3)
        assert structure.legs[0].current_size == pytest.approx(70.0)

    def test_exit_date_set_when_last_structure_closed(self, trade, structure):
        trade.add_structure(structure, "2024-01-15")
        s2 = StrategyStructure(
            structure_id="struct_2",
            legs=[LegState(
                contract=Contract(ticker="AAPL", asset_class="equity"),
                leg_id="leg_2", current_size=50.0,
            )],
        )
        trade.add_structure(s2, "2024-02-01")
        trade.unwind_structure(structure, "2024-02-10", fraction=1.0)
        assert trade.exit_date is None
        trade.unwind_structure(s2, "2024-02-15", fraction=1.0)
        assert trade.exit_date == "2024-02-15"

    def test_add_to_structure_increases_size(self, trade, structure):
        trade.add_structure(structure, "2024-01-15")
        trade.add_to_structure(structure, "2024-01-20", 50.0)
        assert structure.legs[0].current_size == 150.0

    def test_add_to_structure_updates_entry_price(self, trade, structure):
        trade.add_structure(structure, "2024-01-15")
        trade.add_to_structure(structure, "2024-01-20", 50.0)
        assert structure.legs[0].entry_price == pytest.approx(443.3333333333333)

    def test_add_to_structure_records_partial_add_event(self, trade, structure):
        trade.add_structure(structure, "2024-01-15")
        trade.add_to_structure(structure, "2024-01-20", 50.0)
        assert len(structure.event_log) == 2
        assert structure.event_log[1]["event_type"] == "partial add"

    def test_exit_date_none_initially(self, trade):
        assert trade.exit_date is None

    def test_entry_date_none_initially(self, trade):
        assert trade.entry_date is None

    def test_tags_stored(self):
        trade = Trade(trade_id="t1", tags=["alpha", "momentum"])
        assert trade.tags == ["alpha", "momentum"]

    def test_tags_default_none(self):
        trade = Trade(trade_id="t1")
        assert trade.tags is None

    def test_roll_structure_calls_roll(self, trade, structure):
        trade.add_structure(structure, "2024-01-15")
        new_structure = StrategyStructure(
            structure_id="struct_2",
            legs=[LegState(
                contract=Contract(ticker="SPY", asset_class="equity"),
                leg_id="leg_2",
            )],
        )
        with pytest.raises(NotImplementedError):
            trade.roll_structure(structure, new_structure, "2024-02-01")
