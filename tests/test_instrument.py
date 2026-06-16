import pytest
from backtester.instruments.instrument import Instrument


class TestInstrument:
    def test_default_values(self):
        inst = Instrument(ticker="SPY", asset_class="equity")
        assert inst.ticker == "SPY"
        assert inst.asset_class == "equity"
        assert inst.multiplier == 1.0
        assert inst.currency == "USD"
        assert inst.tags is None
        assert inst.leg_id == ""
        assert inst.params == {}
        assert inst.daily_total_pnl == []
        assert inst.current_price == 0.0
        assert inst.current_size == 0.0
        assert inst.entry_price == 0.0
        assert inst.pricing_inputs == {}

    def test_custom_values(self):
        inst = Instrument(
            ticker="0005.HK",
            asset_class="equity",
            multiplier=100.0,
            currency="HKD",
            tags=["dividend", "large_cap"],
            leg_id="leg_001",
            params={"sector": "financials"},
        )
        assert inst.ticker == "0005.HK"
        assert inst.asset_class == "equity"
        assert inst.multiplier == 100.0
        assert inst.currency == "HKD"
        assert inst.tags == ["dividend", "large_cap"]
        assert inst.leg_id == "leg_001"
        assert inst.params == {"sector": "financials"}

    def test_daily_total_pnl_append(self):
        inst = Instrument(ticker="SPY", asset_class="equity")
        inst.daily_total_pnl.append(150.0)
        inst.daily_total_pnl.append(-50.0)
        assert inst.daily_total_pnl == [150.0, -50.0]

    def test_current_price_update(self):
        inst = Instrument(ticker="SPY", asset_class="equity")
        inst.current_price = 450.75
        assert inst.current_price == 450.75

    def test_current_size_update(self):
        inst = Instrument(ticker="SPY", asset_class="equity")
        inst.current_size = 100.0
        assert inst.current_size == 100.0

    def test_entry_price_update(self):
        inst = Instrument(ticker="SPY", asset_class="equity")
        inst.entry_price = 440.25
        assert inst.entry_price == 440.25

    def test_pricing_inputs_append(self):
        inst = Instrument(ticker="SPY", asset_class="equity")
        inst.pricing_inputs.setdefault("implied_vol", []).append(22.5)
        inst.pricing_inputs.setdefault("implied_vol", []).append(23.0)
        assert inst.pricing_inputs["implied_vol"] == [22.5, 23.0]

    def test_params_default_factory_isolates_instances(self):
        inst1 = Instrument(ticker="A", asset_class="equity")
        inst2 = Instrument(ticker="B", asset_class="equity")
        inst1.params["key"] = "val"
        assert inst2.params == {}

    def test_pricing_inputs_default_factory_isolates_instances(self):
        inst1 = Instrument(ticker="A", asset_class="equity")
        inst2 = Instrument(ticker="B", asset_class="equity")
        inst1.pricing_inputs.setdefault("iv", []).append(1.0)
        assert inst2.pricing_inputs == {}

    def test_none_tags_allowed(self):
        inst = Instrument(ticker="SPY", asset_class="equity", tags=None)
        assert inst.tags is None

    def test_futures_instrument(self):
        inst = Instrument(
            ticker="ES",
            asset_class="equity_future",
            multiplier=50.0,
            params={"expiry": "2025-09-19"},
        )
        assert inst.asset_class == "equity_future"
        assert inst.multiplier == 50.0
        assert inst.params["expiry"] == "2025-09-19"
