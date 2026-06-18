import pytest
from backtester.instruments.instrument import Instrument
from backtester.structures.strategy_structure import StrategyStructure


class TestStrategyStructure:
    @pytest.fixture
    def leg(self):
        inst = Instrument(ticker="SPY", asset_class="equity", leg_id="leg_1")
        inst.current_size = 100.0
        return inst

    @pytest.fixture
    def structure(self, leg):
        return StrategyStructure(
            structure_id="struct_1", legs=[leg], cost_leg_ids=["leg_1"],
        )

    def test_cost_leg_ids_stored(self, structure, leg):
        assert structure.cost_leg_ids == ["leg_1"]

    def test_cost_leg_ids_defaults_empty(self, leg):
        s = StrategyStructure(structure_id="s1", legs=[leg])
        assert s.cost_leg_ids == []

    def test_open_records_event(self, structure):
        structure.open("2024-01-15", cost_exposures={"leg_1": {"notional_per_unit": 100.0}})
        assert len(structure.event_log) == 1
        event = structure.event_log[0]
        assert event["event_type"] == "open"
        assert event["date"] == "2024-01-15"
        assert event["unit_size_change"] == 100.0
        assert event["cost_exposures"] == {"leg_1": {"notional_per_unit": 100.0}}
        assert event["cost_leg_id"] == "leg_1"
        assert event["cost_free"] is False

    def test_open_without_cost_exposures(self, structure):
        structure.open("2024-01-15")
        assert structure.event_log[0]["cost_exposures"] == {}
        assert structure.event_log[0]["cost_leg_id"] == "leg_1"

    def test_open_sets_original_entry_date(self, structure):
        assert structure.original_entry_date is None
        structure.open("2024-02-01")
        assert structure.original_entry_date == "2024-02-01"

    def test_open_does_not_overwrite_original_entry_date(self, structure):
        structure.original_entry_date = "2024-01-01"
        structure.open("2024-02-01")
        assert structure.original_entry_date == "2024-01-01"

    def test_add_size_records_event(self, structure):
        structure.open("2024-01-15", cost_exposures={"leg_1": {"notional_per_unit": 100.0}})
        add_exposure = {"leg_1": {"notional_per_unit": 110.0}}
        structure.add_size("2024-01-20", 50.0, cost_exposures=add_exposure)
        assert len(structure.event_log) == 2
        event = structure.event_log[1]
        assert event["event_type"] == "partial add"
        assert event["date"] == "2024-01-20"
        assert event["unit_size_change"] == 50.0
        assert event["cost_exposures"] == add_exposure

    def test_add_size_scales_legs(self, structure):
        structure.legs[0].entry_price = 440.0
        structure.legs[0].current_price = 450.0
        structure.open("2024-01-15")
        structure.add_size("2024-01-20", 50.0)
        assert structure.legs[0].current_size == 150.0
        assert structure.legs[0].entry_price == pytest.approx(443.3333333333333)

    def test_unwind_full_close_records_event(self, structure):
        structure.open("2024-01-15")
        unwind_exposure = {"leg_1": {"notional_per_unit": 105.0}}
        structure.unwind("2024-01-25", fraction=1.0, cost_exposures=unwind_exposure)
        event = structure.event_log[-1]
        assert event["event_type"] == "full close"
        assert event["date"] == "2024-01-25"
        assert event["unit_size_change"] == 100.0
        assert event["cost_exposures"] == unwind_exposure
        assert event["cost_free"] is False

    def test_unwind_full_close_reduces_size_to_zero(self, structure):
        structure.open("2024-01-15")
        structure.unwind("2024-01-25", fraction=1.0)
        assert structure.legs[0].current_size == 0.0

    def test_unwind_partial_records_event(self, structure):
        structure.open("2024-01-15")
        structure.unwind("2024-01-22", fraction=0.5)
        event = structure.event_log[-1]
        assert event["event_type"] == "partial unwind"
        assert event["date"] == "2024-01-22"
        assert event["unit_size_change"] == 50.0

    def test_unwind_partial_reduces_size_proportionally(self, structure):
        structure.open("2024-01-15")
        structure.unwind("2024-01-22", fraction=0.3)
        assert structure.legs[0].current_size == 70.0

    def test_roll_raises_not_implemented(self, structure):
        new_structure = StrategyStructure(structure_id="struct_2", legs=[])
        with pytest.raises(NotImplementedError):
            structure.roll(new_structure, "2024-02-01")

    def test_tags_stored(self, leg):
        structure = StrategyStructure(
            structure_id="struct_1", legs=[leg], tags=["alpha", "momentum"]
        )
        assert structure.tags == ["alpha", "momentum"]

    def test_tags_default_none(self, leg):
        structure = StrategyStructure(structure_id="struct_1", legs=[leg])
        assert structure.tags is None

    def test_original_entry_date_unchanged_by_add_unwind(self, structure):
        structure.legs[0].entry_price = 440.0
        structure.legs[0].current_price = 450.0
        structure.open("2024-01-15")
        assert structure.original_entry_date == "2024-01-15"
        structure.add_size("2024-01-20", 50.0)
        assert structure.original_entry_date == "2024-01-15"
        structure.unwind("2024-01-22", fraction=0.3)
        assert structure.original_entry_date == "2024-01-15"

    def test_multiple_events_in_log(self, structure):
        structure.open("2024-01-02")
        structure.add_size("2024-01-05", 20.0)
        structure.unwind("2024-01-10", fraction=0.5)
        structure.unwind("2024-01-15", fraction=1.0)
        event_types = [e["event_type"] for e in structure.event_log]
        assert event_types == ["open", "partial add", "partial unwind", "full close"]
