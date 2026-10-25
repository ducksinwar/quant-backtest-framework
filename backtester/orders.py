"""Order schema: the strategy-side market instruction.

The pipeline is::

    signal -> list[ActionGroup] -> ActionGroupLog
           -> OrderAssembly.build_order_groups(groups, ctx, action_ids)
           -> tuple[OrderGroup, ...] -> execution -> book commit

An :class:`OrderGroup` is the atomic execution unit: conversion produces one per
ActionGroup, and execution fills the whole group or blocks the whole group.

**Signed by side.**  :class:`OrderLeg` carries a *positive* quantity magnitude
and an :class:`OrderSide`; the sign is applied when the instruction reaches the
book.  This is the opposite convention to :class:`~backtester.actions.LegSpec`,
whose ``size`` is signed by :class:`~backtester.actions.Side`.

**Lineage vs book target.**  :attr:`Order.action_id` names the action that
produced the order.  :attr:`Order.structure_id` and :attr:`Order.trade_id` name
the book target: an existing structure/trade, or ``None`` to create one.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum


class OrderSide(str, Enum):
    """The direction of one market instruction."""

    BUY = "BUY"
    SELL = "SELL"


@dataclass(frozen=True)
class OrderLeg:
    """One leg of a market instruction.

    ``quantity`` is a positive magnitude; the leg's direction is carried by
    ``side``.  ``params`` holds the instrument-specific extras in insertion
    order as ``(key, value)`` pairs so the leg stays hashable.
    """

    ticker: str
    side: OrderSide
    quantity: float
    asset_class: str | None = None
    multiplier: float | None = None
    currency: str | None = None
    cost_leg: bool | None = None
    tags: tuple[str, ...] = ()
    params: tuple[tuple[str, object], ...] = ()

    def __post_init__(self):
        object.__setattr__(self, "side", OrderSide(self.side))
        object.__setattr__(self, "tags", tuple(self.tags or ()))
        object.__setattr__(self, "params", tuple(self.params or ()))
        if self.quantity <= 0:
            raise ValueError(
                f"OrderLeg.quantity must be a positive magnitude, got "
                f"{self.quantity!r}"
            )


@dataclass(frozen=True)
class Order:
    """One structure operation as a market instruction.

    ``action_id`` is lineage: the action that produced this order.  The book
    target is an existing ``StrategyStructure`` (``structure_id``) and/or an
    existing ``Trade`` (``trade_id``); ``None`` means this order creates one.
    ``legs`` is non-empty and holds only :class:`OrderLeg` objects.
    """

    action_id: str
    order_id: str
    legs: tuple[OrderLeg, ...]
    structure_id: str | None = None
    trade_id: str | None = None

    def __post_init__(self):
        object.__setattr__(self, "legs", tuple(self.legs or ()))
        if not self.legs:
            raise ValueError("an Order must contain at least one leg")
        for leg in self.legs:
            if not isinstance(leg, OrderLeg):
                raise TypeError("Order.legs must hold OrderLeg objects")


class OrderOutcome(str, Enum):
    """Whether one order produced a position change."""

    FILLED = "FILLED"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class OrderGroup:
    """One ActionGroup's orders, executed atomically.

    ``order_group_id`` is minted unconditionally at construction.  ``orders``
    is non-empty and holds only :class:`Order` objects; each order carries its
    own ``order_id`` and ``action_id`` lineage.
    """

    order_group_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    orders: tuple[Order, ...] = ()

    def __post_init__(self):
        object.__setattr__(self, "orders", tuple(self.orders or ()))
        if not self.orders:
            raise ValueError("an OrderGroup must contain at least one order")
        for order in self.orders:
            if not isinstance(order, Order):
                raise TypeError("OrderGroup.orders must hold Order objects")
