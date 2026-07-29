from unittest.mock import MagicMock

import pytest
from backtester.instruments import Contract
from backtester.pricers.base_pricer import BasePricer
from backtester.pricers.equity_pricer import EquityPricer


class TestBasePricer:
    def test_cannot_instantiate_abstract(self):
        with pytest.raises(TypeError):
            BasePricer()

    def test_cannot_instantiate_partial_implementation(self):
        class PartialPricer(BasePricer):
            def price(self, contract, date):
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
    def contract(self):
        return Contract(ticker="SPY", asset_class="equity")

    def test_price_delegates_to_provider(self, pricer, mock_provider, contract):
        mock_provider.get_price.return_value = 450.75
        result = pricer.price(contract, "2024-01-15")
        mock_provider.get_price.assert_called_once_with("SPY", "2024-01-15")
        assert result == 450.75

    def test_price_returns_none_when_provider_returns_none(
        self, pricer, mock_provider, contract
    ):
        mock_provider.get_price.return_value = None
        result = pricer.price(contract, "2024-01-15")
        assert result is None

    def test_valuation_data_returns_empty_dict(self, pricer, contract):
        result = pricer.valuation_data(contract, "2024-01-15", ["delta"])
        assert result == {}

    def test_valuation_data_returns_empty_dict_for_no_measures(
        self, pricer, contract
    ):
        result = pricer.valuation_data(contract, "2024-01-15", [])
        assert result == {}

    def test_resolve_instrument_pass_through(self, pricer):
        leg_dict = {"ticker": "SPY", "size": 100, "asset_class": "equity", "multiplier": 1.0}
        result = pricer.resolve_instrument(leg_dict, "2024-01-15")
        assert isinstance(result, Contract)
        assert result.ticker == "SPY"
        assert result.asset_class == "equity"
        assert "size" not in result.params

    def test_resolve_instrument_preserves_extra_keys(self, pricer):
        leg_dict = {"ticker": "0700.HK", "size": 1000, "multiplier": 1.0, "currency": "HKD"}
        result = pricer.resolve_instrument(leg_dict, "2024-01-15")
        assert isinstance(result, Contract)
        assert result.ticker == "0700.HK"
        assert result.currency == "HKD"
        assert result.multiplier == 1.0

    def test_pricing_inputs_returns_empty_dict(self, pricer, contract):
        result = pricer.pricing_inputs(contract, "2024-01-15")
        assert result == {}

    def test_compute_cost_exposure_fetches_from_provider(
        self, pricer, mock_provider, contract
    ):
        mock_provider.get_price.return_value = 450.75
        result = pricer.compute_cost_exposure(contract, "2024-01-15")
        mock_provider.get_price.assert_called_with("SPY", "2024-01-15")
        assert result == {"notional_per_unit": 450.75}

    def test_compute_cost_exposure_fetches_from_provider_not_state(
        self, pricer, mock_provider
    ):
        contract = Contract(ticker="AAPL", asset_class="equity")
        mock_provider.get_price.return_value = 175.0
        result = pricer.compute_cost_exposure(contract, "2024-06-01")
        mock_provider.get_price.assert_called_once_with("AAPL", "2024-06-01")
        assert result == {"notional_per_unit": 175.0}

    def test_equity_pricer_is_instance_of_base_pricer(self, mock_provider):
        pricer = EquityPricer(mock_provider)
        assert isinstance(pricer, BasePricer)
