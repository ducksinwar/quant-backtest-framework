from unittest.mock import MagicMock

import pytest
from backtester.instruments.instrument import Instrument
from backtester.pricers.base_pricer import BasePricer
from backtester.pricers.equity_pricer import EquityPricer


class TestBasePricer:
    def test_cannot_instantiate_abstract(self):
        with pytest.raises(TypeError):
            BasePricer()

    def test_cannot_instantiate_partial_implementation(self):
        class PartialPricer(BasePricer):
            def price(self, instrument, date):
                return 100.0

        with pytest.raises(TypeError):
            PartialPricer()


class TestEquityPricer:
    @pytest.fixture
    def mock_provider(self):
        return MagicMock()

    @pytest.fixture
    def pricer(self, mock_provider):
        return EquityPricer(mock_provider)

    @pytest.fixture
    def instrument(self):
        inst = Instrument(ticker="SPY", asset_class="equity")
        inst.current_price = 450.75
        return inst

    def test_price_delegates_to_provider(self, pricer, mock_provider, instrument):
        mock_provider.get_price.return_value = 450.75
        result = pricer.price(instrument, "2024-01-15")
        mock_provider.get_price.assert_called_once_with("SPY", "2024-01-15")
        assert result == 450.75

    def test_price_returns_none_when_provider_returns_none(
        self, pricer, mock_provider, instrument
    ):
        mock_provider.get_price.return_value = None
        result = pricer.price(instrument, "2024-01-15")
        assert result is None

    def test_valuation_data_returns_empty_dict(self, pricer, instrument):
        result = pricer.valuation_data(instrument, "2024-01-15", ["delta"])
        assert result == {}

    def test_valuation_data_returns_empty_dict_for_no_measures(
        self, pricer, instrument
    ):
        result = pricer.valuation_data(instrument, "2024-01-15", [])
        assert result == {}

    def test_resolve_instrument_pass_through(self, pricer):
        leg_dict = {"ticker": "SPY", "size": 100, "asset_class": "equity"}
        result = pricer.resolve_instrument(leg_dict, "2024-01-15")
        assert result is leg_dict
        assert result == {"ticker": "SPY", "size": 100, "asset_class": "equity"}

    def test_resolve_instrument_preserves_extra_keys(self, pricer):
        leg_dict = {
            "ticker": "0700.HK",
            "size": 1000,
            "multiplier": 1.0,
            "currency": "HKD",
        }
        result = pricer.resolve_instrument(leg_dict, "2024-01-15")
        assert result == leg_dict

    def test_pricing_inputs_returns_empty_dict(self, pricer, instrument):
        result = pricer.pricing_inputs(instrument, "2024-01-15")
        assert result == {}

    def test_compute_cost_exposure_returns_notional_per_unit(self, pricer, instrument):
        result = pricer.compute_cost_exposure(instrument, "2024-01-15")
        assert result == {"notional_per_unit": 450.75}

    def test_equity_pricer_is_instance_of_base_pricer(self, mock_provider):
        pricer = EquityPricer(mock_provider)
        assert isinstance(pricer, BasePricer)
