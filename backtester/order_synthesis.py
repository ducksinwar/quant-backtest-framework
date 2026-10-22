"""ActionGroup -> order synthesis.

``OrderSynthesis.synthesize(action_groups, ctx, action_ids)`` runs the
configured plugin chain, then converts every ActionGroup into an
:class:`~backtester.orders.OrderGroup` via
:func:`action_group_to_order_group` and returns a ``tuple[OrderGroup, ...]`` --
exactly one OrderGroup per **input** ActionGroup, positionally aligned with the
appended records.  A synthesis rule that removes a group is a bug: synthesis
never rejects or drops, and rejection is exclusively conversion-stage.

**Layering.**  The converter also runs the synthesis rule chain: action group
synthesis and order conversion are colocated in ``OrderSynthesis``.  Netting
stays out-of-band (a future order-in / order-out module between conversion and
execution).

**Multi-action gate.**  The single-action subset's pipeline rejects any
ActionGroup with more than one Action here, before order conversion.  This is a
*pipeline* rejection, not a schema one: the schema accepts the ``actions``
tuple shape.

**Rule signature.**  Rules are ``rule(action_groups, ctx) -> list[ActionGroup]``
callables.  Rule-emitted groups are rejected until the stamping stage lands: a
rule may neither add a group that was never appended nor remove an input group.

All scopes are representable: whole-book (``trade_id=None``), whole-trade
(``trade_id`` set), and one structure (``trade_id`` and ``structure_id`` set,
optionally with a partial ``size``).

**Anchor formula.**  A structure-scoped modification expresses its size on the
anchor leg; every other leg's delta is the anchor delta scaled by
``leg.size / anchor.size``.  For a single-leg structure the ratio is ``1`` and
this reproduces the old engine's share-of-total distribution exactly;
multi-leg modification remains gated, so the formulas coincide on every
reachable path.
"""

from __future__ import annotations

import uuid

from backtester.actions import (
    Action,
    ActionGroup,
    ActionType,
    AggregationContext,
    Side,
    StructureSpec,
    TradeSpec,
)
from backtester.orders import Order, OrderGroup, OrderLeg, OrderSide

#: The documented default rule order.  Netting is an order-level module, not a
#: synthesis rule, so it is absent here.  No rule is implemented yet; the tuple
#: is the contract the synthesis plugins are registered against (Roll ->
#: AutoUnwind -> HedgeRebalance -> Scaling).
DEFAULT_RULE_ORDER: tuple[str, ...] = (
    "roll",
    "auto_unwind",
    "hedge_rebalance",
    "scaling",
)


def action_group_to_order_group(
    action_group: ActionGroup,
    action_ids: tuple[str, ...],
    ctx: AggregationContext,
) -> OrderGroup:
    """Materialize one ActionGroup as an atomic :class:`OrderGroup`.

    ``action_ids`` is parallel to ``action_group.actions``; every Order carries
    its producing action's id.  The single-action subset yields one action's
    orders; the loop is general so the schema's cardinality is not baked in.
    """
    action_ids = tuple(action_ids)
    if len(action_ids) != len(action_group.actions):
        raise ValueError(
            "action_ids must be parallel to action_group.actions"
        )
    produced: list[Order] = []
    for action_id, action in zip(action_ids, action_group.actions):
        produced.extend(
            _action_to_orders(
                action, action_id, ctx, action_group.strategy_id
            )
        )
    return OrderGroup(orders=tuple(produced))


def _action_to_orders(
    action: Action,
    action_id: str,
    ctx: AggregationContext,
    strategy_id: str,
) -> tuple[Order, ...]:
    """Convert one Action into its Order(s), in emission order."""
    if action.type is ActionType.NEW:
        if action.structure_id is not None:
            return (
                _partial_add_order(action, action_id, ctx, strategy_id),
            )
        if isinstance(action.spec, TradeSpec):
            return tuple(
                _content_order(action_id, structure, trade_id=None)
                for structure in action.spec.structures
            )
        _trade_state(action.trade_id, ctx, strategy_id)
        return (
            _content_order(action_id, action.spec, trade_id=action.trade_id),
        )
    if action.type is ActionType.UNWIND:
        return _unwind_orders(action, action_id, ctx, strategy_id)
    raise ValueError(  # pragma: no cover - ActionType is closed
        f"unsupported action {action.type!r}"
    )


# --- content (NEW) ------------------------------------------------------


def _order_leg(leg) -> OrderLeg:
    """Map a signed :class:`LegSpec` to a positive-magnitude ``OrderLeg``."""
    if leg.size is None:
        raise ValueError(
            "a NEW leg requires a size; UNWIND carries no content legs"
        )
    if leg.size == 0:
        raise ValueError("a NEW leg requires a non-zero size")
    spec = leg.contract_spec
    return OrderLeg(
        ticker=spec.ticker,
        side=OrderSide.BUY if leg.side is Side.LONG else OrderSide.SELL,
        quantity=abs(leg.size),
        asset_class=spec.asset_class,
        multiplier=spec.multiplier,
        currency=spec.currency,
        cost_leg=spec.cost_leg,
        tags=leg.tags,
        params=spec.params,
    )


def _content_order(
    action_id: str, structure: StructureSpec, trade_id: str | None
) -> Order:
    return Order(
        action_id=action_id,
        order_id=uuid.uuid4().hex,
        legs=tuple(_order_leg(leg) for leg in structure.legs),
        structure_id=None,
        trade_id=trade_id,
    )


def _partial_add_order(
    action: Action,
    action_id: str,
    ctx: AggregationContext,
    strategy_id: str,
) -> Order:
    _validate_structure_trade(action, ctx, strategy_id)
    structure = _structure_state(action, ctx, strategy_id)
    _gate_multi_leg(structure, "partial add")
    _gate_short(structure, "partial add")
    return Order(
        action_id=action_id,
        order_id=uuid.uuid4().hex,
        legs=_delta_legs(structure, float(action.size)),
        structure_id=action.structure_id,
        trade_id=action.trade_id,
    )


# --- UNWIND -------------------------------------------------------------


def _unwind_orders(
    action: Action,
    action_id: str,
    ctx: AggregationContext,
    strategy_id: str,
) -> tuple[Order, ...]:
    if action.structure_id is not None:
        _validate_structure_trade(action, ctx, strategy_id)
        structure = _structure_state(action, ctx, strategy_id)
        if action.size is not None:
            # Multi-leg and short structures are gated for *modifications*
            # only; a full-structure unwind is the atomic close.
            _gate_multi_leg(structure, "partial unwind")
            _gate_short(structure, "partial unwind")
            anchor = _anchor_size(structure)
            if action.size >= abs(anchor):
                raise ValueError(
                    f"partial-unwind size {action.size} must be less than "
                    f"the anchor leg's current size {abs(anchor)}"
                )
            legs = _delta_legs(structure, -float(action.size))
        else:
            legs = _full_close_legs(structure)
        return (
            Order(
                action_id=action_id,
                order_id=uuid.uuid4().hex,
                legs=legs,
                structure_id=action.structure_id,
                trade_id=action.trade_id,
            ),
        )

    if action.trade_id is not None:
        trade = _trade_state(action.trade_id, ctx, strategy_id)
        addressed = tuple(
            (structure, trade.trade_id) for structure in trade.structures
        )
    else:
        book = ctx.position_books.for_strategy(strategy_id)
        addressed = tuple(
            (structure, trade.trade_id)
            for trade in book.trades
            for structure in trade.structures
        )
        if not addressed:
            raise ValueError(
                "cannot unwind the whole book: the T-1 book is empty"
            )

    return tuple(
        Order(
            action_id=action_id,
            order_id=uuid.uuid4().hex,
            legs=_full_close_legs(structure),
            structure_id=structure.structure_id,
            trade_id=trade_id,
        )
        for structure, trade_id in addressed
    )


# --- leg deltas ---------------------------------------------------------


def _delta_legs(structure, anchor_delta: float) -> tuple[OrderLeg, ...]:
    """Per-leg deltas scaled from an anchor-leg delta.

    ``legs[0]`` is the anchor; every leg moves by
    ``leg.size * anchor_delta / anchor.size``.  A single-leg structure moves by
    exactly ``anchor_delta`` (the old engine's share-of-total result).
    """
    anchor = _anchor_size(structure)
    if anchor == 0:
        raise ValueError(
            "a modification requires a non-zero anchor size"
        )
    ratio = anchor_delta / anchor
    legs = []
    for leg in structure.legs:
        delta = leg.size * ratio
        if delta == 0:
            continue
        legs.append(
            OrderLeg(
                ticker=leg.ticker,
                side=OrderSide.BUY if delta > 0 else OrderSide.SELL,
                quantity=abs(delta),
                asset_class=leg.asset_class,
            )
        )
    if not legs:
        raise ValueError("a modification produced no leg deltas")
    return tuple(legs)


def _full_close_legs(structure) -> tuple[OrderLeg, ...]:
    legs = []
    for leg in structure.legs:
        if leg.size == 0:
            continue
        legs.append(
            OrderLeg(
                ticker=leg.ticker,
                side=OrderSide.SELL if leg.size > 0 else OrderSide.BUY,
                quantity=abs(leg.size),
                asset_class=leg.asset_class,
            )
        )
    if not legs:
        raise ValueError(
            f"structure {structure.structure_id!r} has no size to close"
        )
    return tuple(legs)


# --- book-dependent checks and gates ------------------------------------


def _validate_structure_trade(
    action: Action, ctx: AggregationContext, strategy_id: str
):
    """Fail loudly if a structure does not belong to the named trade.

    Raises a distinct "not present in the T-1 book" error when the structure
    is unknown, and a "belongs to trade" error when it is owned by a different
    trade; the two messages aid debugging.
    """
    if action.structure_id is None:
        return
    book = ctx.position_books.for_strategy(strategy_id)
    try:
        owner = book.trade_id_for_structure(action.structure_id)
    except ValueError:
        raise ValueError(
            f"structure {action.structure_id!r} is not present in the T-1 "
            f"book for strategy {strategy_id!r}"
        ) from None
    if owner != action.trade_id:
        raise ValueError(
            f"structure {action.structure_id!r} belongs to trade {owner!r}, "
            f"not trade {action.trade_id!r}"
        )


def _structure_state(
    action: Action, ctx: AggregationContext, strategy_id: str
):
    """The book's structure snapshot for ``action.structure_id`` (fail-loud)."""
    book = ctx.position_books.for_strategy(strategy_id)
    for trade in book.trades:
        for structure in trade.structures:
            if structure.structure_id == action.structure_id:
                return structure
    raise ValueError(
        f"no active trade holds structure {action.structure_id!r} in the T-1 "
        f"position book"
    )


def _trade_state(
    trade_id: str, ctx: AggregationContext, strategy_id: str
):
    """The T-1 trade snapshot for ``trade_id`` (fail-loud)."""
    book = ctx.position_books.for_strategy(strategy_id)
    for trade in book.trades:
        if trade.trade_id == trade_id:
            return trade
    raise ValueError(
        f"no active trade {trade_id!r} in the T-1 position book for strategy "
        f"{strategy_id!r}"
    )


def _anchor_size(structure) -> float:
    """The signed size of the structure's anchor leg (``legs[0]``)."""
    return structure.legs[0].size


def _gate_multi_leg(structure, label: str):
    """Reject a modification on a multi-leg structure (gated, not fixed).

    Multi-leg modification is future engine-program surface: the anchor
    formula scales every leg from the anchor, while the old engine distributed
    by **share-of-total**.  The two coincide only for a single leg, so a
    multi-leg modification is ambiguous below a structure.
    """
    if len(structure.legs) > 1:
        raise ValueError(
            f"a {label} on a multi-leg structure is not supported by the "
            f"single-action subset (multi-leg modification is gated)"
        )


def _gate_short(structure, label: str):
    """Reject a modification on a short structure (gated, not fixed).

    The engine's partial add/unwind runs in the wrong direction on a short
    (signed-size semantics are not yet wired to the book); gated until the
    engine program lands.
    """
    if _anchor_size(structure) < 0:
        raise ValueError(
            f"a {label} on a short structure is not supported by the "
            f"single-action subset (short-structure modification is gated)"
        )


class OrderSynthesis:
    """The plugin chain plus the ActionGroup -> order conversion."""

    def __init__(self, rules=()):
        self._rules = tuple(rules)
        for rule in self._rules:
            if not callable(rule):
                raise TypeError(
                    f"synthesis rule {rule!r} is not callable; a rule is "
                    f"rule(action_groups, ctx) -> action_groups"
                )

    @property
    def rules(self) -> tuple:
        return self._rules

    def synthesize(
        self,
        action_groups,
        ctx: AggregationContext,
        action_ids,
    ) -> tuple[OrderGroup, ...]:
        """Run the rules, then convert each surviving group to an OrderGroup.

        ``action_ids`` is parallel to ``action_groups`` (one tuple of ids per
        group, itself parallel to that group's actions).  Returns one
        OrderGroup per **input** group, positionally aligned with the appended
        records.  A rule that removes an input group fails loudly: synthesis
        does not reject or drop.
        """
        action_groups = list(action_groups)
        action_ids = tuple(tuple(ids) for ids in action_ids)
        if len(action_ids) != len(action_groups):
            raise ValueError(
                "action_ids must be parallel to action_groups"
            )
        ids_by_group = {
            group.action_group_id: ids
            for group, ids in zip(action_groups, action_ids)
        }

        working = list(action_groups)
        for rule in self._rules:
            working = list(rule(working, ctx))

        input_ids = [group.action_group_id for group in action_groups]
        if any(gid is None for gid in input_ids):
            raise ValueError(
                "synthesize() requires action groups that were appended to "
                "the log first: action_group_id is assigned at emission"
            )
        known = set(input_ids)
        survivors: dict[str, ActionGroup] = {}
        for group in working:
            gid = group.action_group_id
            if gid is None:
                raise ValueError(
                    "synthesize() received an ActionGroup with no "
                    "action_group_id; it must be appended to the log first"
                )
            if gid not in known:
                raise ValueError(
                    "a synthesis rule emitted an ActionGroup that was never "
                    "appended to the log; rule-emitted groups are rejected "
                    "until the stamping stage lands"
                )
            if gid in survivors:
                raise ValueError(
                    f"duplicate action_group_id {gid!r} in one day's patch"
                )
            if len(group.actions) > 1:
                raise ValueError(
                    "multi-action ActionGroups are not supported by the "
                    "single-action subset: the pipeline rejects groups with "
                    "more than one Action until the engine program lands"
                )
            if len(ids_by_group[gid]) != len(group.actions):
                raise ValueError(
                    "action_ids must be parallel to each group's actions"
                )
            survivors[gid] = group

        out: list[OrderGroup] = []
        for gid in input_ids:
            if gid not in survivors:
                raise ValueError(
                    "a synthesis rule removed an ActionGroup; synthesis does "
                    "not drop or reject groups (rejection is conversion-stage)"
                )
            out.append(
                action_group_to_order_group(
                    survivors[gid], ids_by_group[gid], ctx
                )
            )
        return tuple(out)
