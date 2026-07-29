import pytest
from backtester.instruments import Contract, LegState


class TestContract:
    def test_default_values(self):
        c = Contract(ticker="SPY", asset_class="equity")
        assert c.ticker == "SPY"
        assert c.asset_class == "equity"
        assert c.multiplier == 1.0
        assert c.currency == "USD"
        assert c.params == {}

    def test_custom_values(self):
        c = Contract(
            ticker="0005.HK",
            asset_class="equity",
            multiplier=100.0,
            currency="HKD",
            params={"sector": "financials"},
        )
        assert c.ticker == "0005.HK"
        assert c.multiplier == 100.0
        assert c.currency == "HKD"
        assert c.params == {"sector": "financials"}

    def test_params_default_factory_isolates_instances(self):
        c1 = Contract(ticker="A", asset_class="equity")
        c2 = Contract(ticker="B", asset_class="equity")
        c1.params["key"] = "val"
        assert c2.params == {}

    def test_frozen(self):
        c = Contract(ticker="SPY", asset_class="equity")
        with pytest.raises(Exception):
            c.ticker = "QQQ"

    def test_futures_contract(self):
        c = Contract(
            ticker="ES",
            asset_class="equity_future",
            multiplier=50.0,
            params={"expiry": "2025-09-19"},
        )
        assert c.asset_class == "equity_future"
        assert c.multiplier == 50.0
        assert c.params["expiry"] == "2025-09-19"


class TestLegState:
    def test_requires_contract(self):
        c = Contract(ticker="SPY", asset_class="equity")
        ls = LegState(contract=c)
        assert ls.contract is c
        assert ls.leg_id == ""
        assert ls.current_price == 0.0
        assert ls.current_size == 0.0
        assert ls.entry_price == 0.0
        assert ls.daily_total_pnl == []
        assert ls.valuation_data == {}
        assert ls.pricing_inputs == {}
        assert ls.cost_leg is False
        assert ls.tags is None

    def test_custom_values(self):
        c = Contract(ticker="AAPL", asset_class="equity")
        ls = LegState(
            contract=c,
            leg_id="leg_001",
            current_price=150.0,
            current_size=100.0,
            entry_price=148.0,
            cost_leg=True,
            tags=["alpha", "momentum"],
        )
        assert ls.contract.ticker == "AAPL"
        assert ls.leg_id == "leg_001"
        assert ls.current_price == 150.0
        assert ls.current_size == 100.0
        assert ls.entry_price == 148.0
        assert ls.cost_leg is True
        assert ls.tags == ["alpha", "momentum"]

    def test_tags_default_none(self):
        c = Contract(ticker="SPY", asset_class="equity")
        ls = LegState(contract=c)
        assert ls.tags is None

    def test_daily_total_pnl_append(self):
        c = Contract(ticker="SPY", asset_class="equity")
        ls = LegState(contract=c)
        ls.daily_total_pnl.append(150.0)
        ls.daily_total_pnl.append(-50.0)
        assert ls.daily_total_pnl == [150.0, -50.0]

    def test_current_price_update(self):
        c = Contract(ticker="SPY", asset_class="equity")
        ls = LegState(contract=c)
        ls.current_price = 450.75
        assert ls.current_price == 450.75

    def test_current_size_update(self):
        c = Contract(ticker="SPY", asset_class="equity")
        ls = LegState(contract=c)
        ls.current_size = 100.0
        assert ls.current_size == 100.0

    def test_entry_price_update(self):
        c = Contract(ticker="SPY", asset_class="equity")
        ls = LegState(contract=c)
        ls.entry_price = 440.25
        assert ls.entry_price == 440.25

    def test_valuation_data_setdefault(self):
        c = Contract(ticker="SPY", asset_class="equity")
        ls = LegState(contract=c)
        ls.valuation_data.setdefault("delta", []).append(0.55)
        ls.valuation_data.setdefault("delta", []).append(0.56)
        assert ls.valuation_data["delta"] == [0.55, 0.56]

    def test_pricing_inputs_default_factory_isolates_instances(self):
        c1 = Contract(ticker="A", asset_class="equity")
        c2 = Contract(ticker="B", asset_class="equity")
        ls1 = LegState(contract=c1, pricing_inputs={"iv": [22.0]})
        ls2 = LegState(contract=c2)
        assert ls2.pricing_inputs == {}

    def test_pricing_inputs_setdefault_isolates_instances(self):
        c1 = Contract(ticker="A", asset_class="equity")
        c2 = Contract(ticker="B", asset_class="equity")
        ls1 = LegState(contract=c1)
        ls1.pricing_inputs.setdefault("iv", []).append(1.0)
        ls2 = LegState(contract=c2)
        assert ls2.pricing_inputs == {}

    def test_repr_shows_key_fields(self):
        c = Contract(ticker="SPY", asset_class="equity")
        ls = LegState(contract=c, leg_id="abc123", current_size=50.0)
        r = repr(ls)
        assert "SPY" in r
        assert "abc123" in r
        assert "50.0" in r

    def test_pricing_inputs_append(self):
        c = Contract(ticker="SPY", asset_class="equity")
        ls = LegState(contract=c)
        ls.pricing_inputs.setdefault("implied_vol", []).append(22.5)
        ls.pricing_inputs.setdefault("implied_vol", []).append(23.0)
        assert ls.pricing_inputs["implied_vol"] == [22.5, 23.0]
