"""The execution seam: the backtest/live parity boundary.

``signal -> ActionGroup -> synthesis -> OrderGroup`` reaches its terminus
here.  :class:`ExecutionBackend` decides the whole group's outcome against the
loop day's market and returns one :class:`ExecutionReport` per order; the
engine writes the execution log and commits to the book **only on a fill**
(Flow A).  The backend never mutates engine state.

**Group atomicity.**  ``execute_group`` probes every order first.  If any order
fails its probe, the whole group is ``BLOCKED``: the failing orders record the
underlying reason (``DATA_MISSING``) and the orders that would have passed
record ``GROUP_ATOMICITY:<trigger_order_id>``.  If every probe passes, every
order fills at the loop day's close.

``SimulatedExecution`` absorbs the engine's old data-availability pre-check and
is therefore the single owner of that predicate and the single stderr warning
emitter.  Blocking is *market-driven non-fill only* -- there are no injected
outages.  ``fees`` is always ``None``: cost is the ``CostModel``'s job, and no
cost model is wired into the backend.

**All-or-nothing (as-built).**  ``SimulatedExecution`` fills an order in full
or blocks it entirely: there are no partial fills in the backtest.  Live
partial-fill handling is deferred; this is documented as-built behavior, not a
new decision.
"""

from __future__ import annotations

import warnings
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

from backtester.orders import OrderGroup, OrderOutcome, OrderSide


class ExecutionOutcome(str, Enum):
    """The terminal outcome of one execution event."""

    FILLED = "FILLED"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class LegFill:
    """One leg's fill detail: a **signed** size delta at the T close.

    A fill records the change in position, not the position: opening a long is
    positive, closing a long is negative, and closing a short is positive.
    """

    ticker: str
    size: float
    price: float


@dataclass(frozen=True)
class ExecutionContext:
    """Live engine state a backend may read (never mutate).

    ``active_trades`` is the **live** book, not the T-1 ``PositionBook``: the
    availability predicate and the unwind enumeration must see trades opened
    earlier on the same loop day, exactly as the absorbed availability
    pre-check did.  **Backends must treat this as immutable; violating this
    corrupts the engine's book.**

    ``date`` / ``action_group_id`` are the loop day and the emitted group's
    lineage; the backend copies them onto every report so the execution log
    keeps the ``order <-> action <-> group`` chain.

    There is deliberately no ``calendar`` field: calendar gating is signal-side
    (``BaseSignal.is_tradable``), so an execution backend never reads a
    calendar (availability is data-driven, not calendar-driven).
    """

    active_trades: tuple
    asset_class_configs: dict
    date: str
    action_group_id: str


@dataclass(frozen=True)
class ExecutionReport:
    """What execution decided for one order in a group.

    A ``FILLED`` report carries ``fill_time`` -- the loop day ``T`` as an ISO
    date string, no intraday component (the daily-close convention) -- and
    per-leg ``fills``.  A ``BLOCKED`` report carries ``blocked_code`` /
    ``blocked_by`` and no fills.  ``probe_status`` records what the order's own
    probe decided before group atomicity overrode it.  ``fill_id`` is left
    ``None`` by ``SimulatedExecution`` and minted by the execution log; a live
    broker may supply its own confirmation id instead.  ``fees`` is always
    ``None`` here.
    """

    order_id: str
    action_id: str
    order_group_id: str
    action_group_id: str
    date: str
    outcome: ExecutionOutcome
    probe_status: OrderOutcome | None = None
    blocked_by: str | None = None
    fill_id: str | None = None
    fill_time: str | None = None
    fees: float | None = None
    fills: tuple[LegFill, ...] = ()
    blocked_code: str | None = None
    #: Reserved for netting/transfers; unused until netting lands.
    internal_transfer: object | None = None


class ExecutionBackend(ABC):
    """The backtest/live parity boundary.

    ``execute_group`` decides a whole group's outcome and returns one
    :class:`ExecutionReport` per order; it must not mutate engine state.
    Persistence is the engine's and is gated on ``FILLED``, so a
    built-but-blocked structure is discarded before it is ever added to a
    trade.
    """

    @abstractmethod
    def execute_group(
        self, order_group: OrderGroup, ctx: ExecutionContext
    ) -> tuple[ExecutionReport, ...]:
        ...


class SimulatedExecution(ExecutionBackend):
    """Historical fills at the loop day's close.

    Single owner of the data-availability predicate (absorbed from the engine's
    pre-check) and therefore the single warning emitter.  **Stateless:** it
    holds no market-data, cost or position state -- every input arrives through
    the ``OrderGroup`` and ``ExecutionContext``.
    """

    def __init__(self):
        # Stateless by design; the explicit constructor documents that there is
        # nothing to configure and nothing to hold between calls.
        pass

    def execute_group(self, order_group, ctx):
        probes = [self._probe_order(order, ctx) for order in order_group.orders]
        failures = [
            (index, reason)
            for index, (available, _fills, reason) in enumerate(probes)
            if not available
        ]
        if failures:
            trigger_index, _trigger_reason = failures[0]
            trigger_id = order_group.orders[trigger_index].order_id
            warnings.warn(
                f"Order rejected on {ctx.date}: data not available "
                f"for all instruments."
            )
            return tuple(
                self._report(
                    order,
                    order_group,
                    ctx,
                    outcome=ExecutionOutcome.BLOCKED,
                    probe_status=(
                        OrderOutcome.FILLED
                        if available
                        else OrderOutcome.BLOCKED
                    ),
                    blocked_by=(
                        reason
                        if not available
                        else f"GROUP_ATOMICITY:{trigger_id}"
                    ),
                    blocked_code=(
                        "DATA_MISSING"
                        if not available
                        else "GROUP_ATOMICITY"
                    ),
                )
                for order, (available, _fills, reason) in zip(
                    order_group.orders, probes
                )
            )
        return tuple(
            self._report(
                order,
                order_group,
                ctx,
                outcome=ExecutionOutcome.FILLED,
                probe_status=OrderOutcome.FILLED,
                fill_time=ctx.date,
                fills=fills,
            )
            for order, (_available, fills, _reason) in zip(
                order_group.orders, probes
            )
        )

    @staticmethod
    def _report(order, order_group, ctx, **kwargs):
        return ExecutionReport(
            order_id=order.order_id,
            action_id=order.action_id,
            order_group_id=order_group.order_group_id,
            action_group_id=ctx.action_group_id,
            date=ctx.date,
            **kwargs,
        )

    # --- availability probe (absorbed from the old pre-check) -----------
    #
    # The probe returns ``(available, fills, reason)``: it resolves/prices each
    # leg exactly once and the fills are built from those same results, so a
    # filled order never re-calls the pricer.  Probes always run for every
    # order so a blocked group can report each order's own probe status.

    def _probe_order(self, order, ctx):
        if order.structure_id is None:
            return self._probe_new(order, ctx)
        return self._probe_target(order, ctx)

    def _probe_new(self, order, ctx):
        fills = []
        for leg in order.legs:
            asset_class = leg.asset_class
            if asset_class is None:
                raise ValueError(
                    "Leg is missing required 'asset_class' field."
                )
            cfg = ctx.asset_class_configs.get(asset_class)
            if cfg is None:
                raise ValueError(f"Unknown asset class: {asset_class}")
            pricer = cfg.pricer
            contract = pricer.resolve_instrument(
                leg_dict_from_order_leg(leg), ctx.date
            )
            if contract is None:
                return False, (), "DATA_MISSING"
            price = pricer.price(contract, ctx.date)
            if price is None:
                return False, (), "DATA_MISSING"
            fills.append(
                LegFill(
                    ticker=leg.ticker,
                    size=signed_order_quantity(leg),
                    price=price,
                )
            )
        return True, tuple(fills), None

    def _probe_target(self, order, ctx):
        trade = self._find_active_trade(order.trade_id, ctx)
        if trade is None:
            return False, (), "DATA_MISSING"
        structure = self._find_structure(trade, order.structure_id)
        if structure is None:
            return False, (), "DATA_MISSING"
        fills = []
        for leg in order.legs:
            leg_state = self._match_leg(structure, leg.ticker)
            if leg_state is None:
                return False, (), "DATA_MISSING"
            asset_class = leg_state.contract.asset_class
            cfg = ctx.asset_class_configs.get(asset_class)
            if cfg is None:
                raise ValueError(f"Unknown asset class: {asset_class}")
            price = cfg.pricer.price(leg_state.contract, ctx.date)
            if price is None:
                return False, (), "DATA_MISSING"
            fills.append(
                LegFill(
                    ticker=leg_state.contract.ticker,
                    size=signed_order_quantity(leg),
                    price=price,
                )
            )
        return True, tuple(fills), None

    @staticmethod
    def _match_leg(structure, ticker):
        for leg_state in structure.legs:
            if leg_state.contract.ticker == ticker:
                return leg_state
        return None

    @staticmethod
    def _find_active_trade(trade_id, ctx):
        for trade in ctx.active_trades:
            if trade.trade_id == trade_id:
                return trade
        return None

    @staticmethod
    def _find_structure(trade, structure_id):
        for structure in trade.active_structures:
            if structure.structure_id == structure_id:
                return structure
        return None


def signed_order_quantity(leg) -> float:
    """The leg's signed delta: ``+quantity`` for BUY, ``-quantity`` for SELL."""
    return leg.quantity if leg.side is OrderSide.BUY else -leg.quantity


def leg_dict_from_order_leg(leg) -> dict:
    """Map an :class:`~backtester.orders.OrderLeg` to the pricer leg dict.

    The inverse of the converter's leg mapping; ``size`` is signed by the
    order's side and the instrument-specific extras come last, in order.
    """
    out: dict = {"ticker": leg.ticker, "size": signed_order_quantity(leg)}
    if leg.asset_class is not None:
        out["asset_class"] = leg.asset_class
    if leg.multiplier is not None:
        out["multiplier"] = leg.multiplier
    if leg.currency is not None:
        out["currency"] = leg.currency
    if leg.cost_leg is not None:
        out["cost_leg"] = leg.cost_leg
    if leg.tags:
        out["tags"] = list(leg.tags)
    for key, value in leg.params:
        out[key] = value
    return out


def write_cost_exposures(structure, date: str, asset_class_configs: dict) -> dict:
    """Write a filled structure event's ``cost_exposures`` from the pricer.

    Called by the commit phase for a **filled** structure only, and -- on the
    unwind path -- **before** the lifecycle method mutates any size, so the
    per-unit metrics reflect the pre-unwind state.  Values come solely from the
    pricer's asset-agnostic, per-unit ``compute_cost_exposure``; the writer never
    computes ``fill_price * size`` (that is equity-only and would silently break
    derivative exposures such as vega/DV01 per unit).  Sizes stay on the event's
    ``leg_size_changes`` and the ``CostModel`` combines them with these per-unit
    metrics.

    The ``compute_cost_exposure`` call happens in the **commit phase**, which is
    execution-side: reading data at the loop day ``T`` is permitted there, and
    this is not an order-side (``<= T-1``) read.
    """
    result: dict = {}
    if not structure.legs:
        return result

    # Ledgered wart: the pricer is selected from legs[0]'s asset class for the
    # whole structure (verbatim from the removed ``_compute_cost_exposures``).
    # Wrong for a mixed-asset-class structure; harmless until Phase 4.
    asset_class = structure.legs[0].contract.asset_class
    cfg = asset_class_configs.get(asset_class)
    if cfg is None:
        return result
    pricer = cfg.pricer

    for leg_state in structure.legs:
        if not leg_state.cost_leg:
            continue
        exposure = pricer.compute_cost_exposure(leg_state.contract, date)
        if exposure is None:
            warnings.warn(
                f"compute_cost_exposure returned None for leg "
                f"{leg_state.leg_id} on {date}; treating as cost-free for "
                f"this event."
            )
            continue
        result[leg_state.leg_id] = exposure

    # Preserve existing behaviour: for a single-leg structure whose cost_leg
    # was not explicitly marked, treat the sole leg as cost-bearing.
    if not result and len(structure.legs) == 1:
        sole = structure.legs[0]
        exposure = pricer.compute_cost_exposure(sole.contract, date)
        if exposure is not None:
            result[sole.leg_id] = exposure

    return result
