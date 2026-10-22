"""Order schema: Order / OrderLeg / OrderSide / OrderGroup / OrderOutcome."""

import dataclasses

import pytest

from backtester.orders import (
    Order,
    OrderGroup,
    OrderLeg,
    OrderOutcome,
    OrderSide,
)


def _leg(**kwargs):
    kwargs.setdefault("ticker", "SPY")
    kwargs.setdefault("side", OrderSide.BUY)
    kwargs.setdefault("quantity", 100.0)
    return OrderLeg(**kwargs)


def _order(legs=None, **kwargs):
    return Order(
        action_id="a1",
        order_id="o1",
        legs=(_leg(),) if legs is None else legs,
        **kwargs,
    )


class TestOrderSide:
    def test_values(self):
        assert [s.value for s in OrderSide] == ["BUY", "SELL"]

    def test_coerces_from_string(self):
        assert OrderSide("BUY") is OrderSide.BUY
        assert OrderSide("SELL") is OrderSide.SELL


class TestOrderLeg:
    def test_constructs_with_required_fields(self):
        leg = _leg()
        assert leg.ticker == "SPY"
        assert leg.side is OrderSide.BUY
        assert leg.quantity == 100.0
        assert leg.asset_class is None
        assert leg.tags == ()
        assert leg.params == ()

    def test_side_is_coerced_from_string(self):
        assert _leg(side="SELL").side is OrderSide.SELL

    def test_tags_are_normalised_to_a_tuple(self):
        assert _leg(tags=["hedge"]).tags == ("hedge",)

    def test_params_are_stored_as_a_tuple(self):
        leg = _leg(params=[("strike", 5000), ("expiry", "2025-12-19")])
        assert leg.params == (("strike", 5000), ("expiry", "2025-12-19"))

    @pytest.mark.parametrize("quantity", [0, -1.0])
    def test_non_positive_quantity_is_rejected(self, quantity):
        with pytest.raises(ValueError, match="positive magnitude"):
            _leg(quantity=quantity)

    def test_is_frozen(self):
        leg = _leg()
        with pytest.raises(dataclasses.FrozenInstanceError):
            leg.quantity = 1.0


class TestOrder:
    def test_constructs_with_legs_and_ids(self):
        leg = _leg()
        order = _order(legs=(leg,))
        assert order.action_id == "a1"
        assert order.order_id == "o1"
        assert order.legs == (leg,)

    def test_requires_at_least_one_leg(self):
        with pytest.raises(ValueError, match="at least one leg"):
            _order(legs=())

    @pytest.mark.parametrize("bad", [{"ticker": "SPY"}, "SPY", None])
    def test_legs_must_hold_order_legs(self, bad):
        with pytest.raises(TypeError, match="OrderLeg"):
            _order(legs=(bad,))

    def test_is_frozen(self):
        order = _order()
        with pytest.raises(dataclasses.FrozenInstanceError):
            order.order_id = "o2"

    def test_defaults_to_no_book_target(self):
        order = _order()
        assert order.structure_id is None
        assert order.trade_id is None


class TestOrderOutcome:
    def test_values(self):
        assert [o.value for o in OrderOutcome] == ["FILLED", "BLOCKED"]

    def test_coerces_from_string(self):
        assert OrderOutcome("FILLED") is OrderOutcome.FILLED
        assert OrderOutcome("BLOCKED") is OrderOutcome.BLOCKED


class TestOrderGroup:
    def test_constructs_with_a_minted_id(self):
        group = OrderGroup(orders=(_order(),))
        assert len(group.order_group_id) == 32
        int(group.order_group_id, 16)
        assert len(group.orders) == 1

    def test_requires_at_least_one_order(self):
        with pytest.raises(ValueError, match="at least one order"):
            OrderGroup()

    def test_orders_must_hold_order_objects(self):
        with pytest.raises(TypeError, match="Order objects"):
            OrderGroup(orders=({"Action": "UNWIND"},))

    def test_is_frozen(self):
        group = OrderGroup(orders=(_order(),))
        with pytest.raises(dataclasses.FrozenInstanceError):
            group.orders = ()

    def test_two_groups_are_not_equal(self):
        assert OrderGroup(orders=(_order(),)) != OrderGroup(orders=(_order(),))
