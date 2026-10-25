"""Action schema: the strategy-side description of *what a strategy wants*.

The pipeline is::

    signal -> list[ActionGroup] -> ActionGroupLog (id + emission date assigned)
           -> OrderAssembly.build_order_groups(groups, ctx, action_ids)
           -> tuple[OrderGroup, ...] -> the execution path

The object a signal emits is an :class:`ActionGroup`; the stage that turns it
into orders is **action group synthesis**, and its log is the
:class:`~backtester.action_group_log.ActionGroupLog`.

**Who assigns what.**  A signal builds :class:`ActionGroup` objects with
``action_group_id=None`` and ``emission_date=None``; it owns neither identifier.
The backtester's daily loop assigns both when it appends the group to the
:class:`~backtester.action_group_log.ActionGroupLog` at emission:
``action_group_id`` is a ``uuid.uuid4().hex`` string and ``emission_date`` is
:attr:`AggregationContext.date` (the loop asserts the two agree).  The log also
mints one ``action_id`` per action, parallel to ``action_group.actions``.
``provenance`` is drawn from :data:`PROVENANCE_CONSTANTS` -- ``"signal"`` for
alpha emissions, rule names for mechanical emissions by synthesis rules.

**Identity and scope.**  An Action names a book scope.  ``trade_id`` scopes a
trade-level operation (a NEW that extends an existing trade, or an UNWIND of a
whole trade); ``structure_id`` scopes a structure-level operation (an UNWIND of
one structure, or a partial add), which always also names its ``trade_id``; a
NEW that creates a trade and an UNWIND of the whole book carry neither.

**Structure vs trade.**  A structure is the atomic unit of *modification*: its
legs move in lockstep, so an operation never acts below a structure.  It is
*not* the unit of *creation*: a NEW opens a **trade** whose :class:`TradeSpec`
may contain multiple structures (scaling-in / grouping).  A multi-leg
instrument (call spread, straddle, FX forward, basket) is **one structure with
multiple legs**.

**Anchor leg.**  ``StructureSpec.legs[0]`` is the **anchor** leg.  A
modification size is expressed on the anchor; the other legs scale
proportionally.  This single convention is what lets the signed-size formula
below be stated on one number.

**Signed size.**  ``anchor_current`` is the anchor leg's signed book size.
The action size is a positive magnitude; the new anchor magnitude is
``|anchor_new| = |anchor_current| + (NEW ? +size : -size)`` and the
sign is re-applied: ``anchor_new = sign(anchor_current) * |anchor_new|``.  An
Action is direction-agnostic; the order delta's side comes from the leg's
:class:`Side`.

**Fractional policy (interim).**  An action keeps exact fractional values.
Conversion carries them into ``OrderLeg.quantity`` unchanged: equity uses
adjusted data and fractional shares are fine, so nothing rounds.  Lot rounding
is deferred; no lot-sizing config exists.  A future reduction that would zero
the size is refused at action construction (``size > 0``), not expressed as a
zero-sized modification.

**Append-only log, write-once facts.**  Append-only means *no record is ever
removed*, not that records are immutable: ``ActionGroupLog.append`` creates the
record, and the loop writes its ``order_ids``, ``order_outcomes`` and
``group_note`` exactly once through ``ActionGroupRecord.finalize``.  Accessors
hand back live references.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from backtester.orders import OrderOutcome

if TYPE_CHECKING:  # pragma: no cover - typing only, avoids an import cycle
    from backtester.action_group_log import ActionGroupLog
    from backtester.backtest_engine import BacktestConfig
    from backtester.calendar_provider import CalendarProvider
    from backtester.execution_log import ExecutionLog
    from backtester.position_books import PositionBooks


class ActionType(str, Enum):
    """The action a patch asks for; 1:1 with the ``Action`` strings.

    The single-action subset implements ``NEW`` and ``UNWIND``.  ``ROLL`` is
    future engine-program surface (the engine still refuses it) and is not a
    member of this closed set.
    """

    NEW = "NEW"
    UNWIND = "UNWIND"


class Side(str, Enum):
    """Leg direction.  ``LONG`` keeps the size, ``SHORT`` negates it."""

    LONG = "LONG"
    SHORT = "SHORT"


#: Documented provenance constants.  ``"signal"`` is the value alpha emissions
#: carry; the rule names are the mechanical emissions of synthesis rules.
#: ``roll_rule`` is a **conscious reserved constant** -- roll is future work,
#: not a corpse.  ``netting_rule`` is deliberately absent: netting is an
#: order-level module, not an action-group source.
PROVENANCE_SIGNAL = "signal"
PROVENANCE_ROLL_RULE = "roll_rule"
PROVENANCE_AUTO_UNWIND_RULE = "auto_unwind_rule"
PROVENANCE_HEDGE_REBALANCE_RULE = "hedge_rebalance_rule"
PROVENANCE_SCALING_RULE = "scaling_rule"

PROVENANCE_CONSTANTS: frozenset[str] = frozenset(
    {
        PROVENANCE_SIGNAL,
        PROVENANCE_ROLL_RULE,
        PROVENANCE_AUTO_UNWIND_RULE,
        PROVENANCE_HEDGE_REBALANCE_RULE,
        PROVENANCE_SCALING_RULE,
    }
)

#: Leg-dict keys that carry no contract identity and are therefore not part of
#: :class:`ContractSpec`: ``size`` and ``tags`` are carried by ``LegSpec``,
#: ``structure_id``/``leg_id`` are pure engine plumbing and are never re-emitted
#: by the converter.
LEG_DICT_INFRA_KEYS: frozenset[str] = frozenset(
    {"size", "tags", "structure_id", "leg_id"}
)

#: Every key :class:`ContractSpec` knows about, in converter emission order.
CONTRACT_SPEC_KEYS: tuple[str, ...] = (
    "ticker",
    "asset_class",
    "multiplier",
    "currency",
    "cost_leg",
)


@dataclass(frozen=True)
class ContractSpec:
    """Immutable copy of a leg dict's contract fields (no ``size``).

    ``params`` holds the instrument-specific extras (``strike``, ``expiry``,
    ``tenor``, ...) in their original insertion order, as ``(key, value)``
    pairs so the spec stays hashable and order-preserving.
    """

    ticker: str
    asset_class: str | None = None
    multiplier: float | None = None
    currency: str | None = None
    cost_leg: bool | None = None
    params: tuple[tuple[str, object], ...] = ()

    def __post_init__(self):
        if not isinstance(self.ticker, str) or not self.ticker:
            raise ValueError("ContractSpec.ticker must be a non-empty string")
        if not isinstance(self.params, tuple):
            raise TypeError(
                "ContractSpec.params must be a tuple of (key, value) pairs"
            )
        reserved = set(CONTRACT_SPEC_KEYS) | LEG_DICT_INFRA_KEYS
        for key, _ in self.params:
            if not isinstance(key, str) or not key:
                raise ValueError(
                    "ContractSpec.params keys must be non-empty strings"
                )
            if key in reserved:
                raise ValueError(
                    f"ContractSpec.params must not hold the reserved leg-dict "
                    f"key {key!r}; it belongs to a named field."
                )

    @property
    def param_dict(self) -> dict:
        """The extras as a plain dict (insertion order preserved)."""
        return dict(self.params)


@dataclass(frozen=True)
class LegSpec:
    """One leg: what, which way, how much."""

    contract_spec: ContractSpec
    side: Side
    size: float | None
    tags: tuple[str, ...] = ()

    def __post_init__(self):
        object.__setattr__(self, "side", Side(self.side))
        object.__setattr__(self, "tags", tuple(self.tags or ()))
        if self.size is not None and not isinstance(self.size, (int, float)):
            raise TypeError(
                f"LegSpec.size must be a number or None, got "
                f"{type(self.size).__name__}"
            )
        if self.size is not None and self.size < 0:
            raise ValueError(
                "LegSpec.size must be non-negative; direction is carried by side"
            )

    @property
    def signed_size(self):
        """``size if LONG else -size`` (the converter's sign mapping)."""
        if self.size is None:
            return None
        return self.size if self.side is Side.LONG else -self.size


@dataclass(frozen=True)
class StructureSpec:
    """A structure's atomic content: its legs and its tags.

    ``legs[0]`` is the **anchor** leg (see the module docstring).  A content
    spec; legs are non-empty whenever this describes new content, validated by
    the owning :class:`Action`.  The structure's id is engine-assigned, so a
    content structure carries none -- a reference to an *existing* structure is
    what :attr:`Action.structure_id` is for.
    """

    legs: tuple[LegSpec, ...] = ()
    tags: tuple[str, ...] = ()

    def __post_init__(self):
        object.__setattr__(self, "legs", tuple(self.legs or ()))
        object.__setattr__(self, "tags", tuple(self.tags or ()))
        for leg in self.legs:
            if not isinstance(leg, LegSpec):
                raise TypeError(
                    "StructureSpec.legs must hold LegSpec objects"
                )


@dataclass(frozen=True)
class TradeSpec:
    """A new trade's content: its structures and its trade-level tags.

    ``tags`` is the trade-level tag carrier; conversion does not copy it onto
    the orders, and the commit phase applies it when a new trade is created.
    """

    structures: tuple[StructureSpec, ...] = ()
    tags: tuple[str, ...] = ()

    def __post_init__(self):
        object.__setattr__(self, "structures", tuple(self.structures or ()))
        object.__setattr__(self, "tags", tuple(self.tags or ()))
        for structure in self.structures:
            if not isinstance(structure, StructureSpec):
                raise TypeError(
                    "TradeSpec.structures must hold StructureSpec objects"
                )


@dataclass(frozen=True)
class Action:
    """One action on one scope, with at most one content spec.

    Construction-time matrix (any unlisted shape is rejected fail-loud)::

        type    spec            trade_id    structure_id  size
        NEW     TradeSpec       --          --            --
        NEW     StructureSpec   set         --            --
        NEW     --              set         set           >0 (partial add)
        UNWIND  --              set         set           >0 (partial)
        UNWIND  --              set         set           --  (full)
        UNWIND  --              set         --            --
        UNWIND  --              --          --            --

    ``trade_id`` is required on every structure-scoped UNWIND, exactly as it is
    on a partial add; the converter validates it against the book.  A
    partial-unwind ``size`` upper bound (``< |anchor_current|``) is
    *conversion-time*: it needs the book, so it is not enforced here.
    """

    type: ActionType
    spec: TradeSpec | StructureSpec | None = None
    trade_id: str | None = None
    structure_id: str | None = None
    size: float | None = None

    def __post_init__(self):
        object.__setattr__(self, "type", ActionType(self.type))
        if self.spec is not None and not isinstance(
            self.spec, (TradeSpec, StructureSpec)
        ):
            raise TypeError(
                "Action.spec must be a TradeSpec, a StructureSpec, or None"
            )
        if self.size is not None and not isinstance(self.size, (int, float)):
            raise TypeError(
                f"Action.size must be a number or None, got "
                f"{type(self.size).__name__}"
            )
        self._validate_shape()

    # --- shape validation (fail-loud on any unlisted shape) -------------

    def _validate_new(self):
        if self.structure_id is not None:
            # Partial add to an existing structure (delta hedging).
            if self.spec is not None:
                raise ValueError(
                    "a partial-add Action carries no spec; it grows an "
                    "existing structure"
                )
            if self.trade_id is None:
                raise ValueError(
                    "a partial-add Action needs trade_id and structure_id"
                )
            if self.size is None or self.size <= 0:
                raise ValueError(
                    "a partial-add Action needs a positive size"
                )
            return
        if self.size is not None:
            raise ValueError(
                "a NEW Action that creates or extends a trade carries no "
                "size"
            )
        if isinstance(self.spec, TradeSpec):
            if self.trade_id is not None:
                raise ValueError(
                    "a trade-creating Action carries no trade_id"
                )
            if not self.spec.structures:
                raise ValueError(
                    "a trade-creating Action needs at least one structure"
                )
            for structure in self.spec.structures:
                if not structure.legs:
                    raise ValueError(
                        "a trade-creating structure needs at least one leg"
                    )
        elif isinstance(self.spec, StructureSpec):
            if self.trade_id is None:
                raise ValueError(
                    "a trade-extending Action needs a trade_id"
                )
            if not self.spec.legs:
                raise ValueError(
                    "a trade-extending Action needs at least one leg"
                )
        else:
            raise ValueError(
                "a NEW Action needs a TradeSpec (create) or a StructureSpec "
                "(extend)"
            )

    def _validate_unwind(self):
        if self.spec is not None:
            raise ValueError(
                "an UNWIND Action carries no spec; it addresses an "
                "existing scope"
            )
        if self.structure_id is not None and self.trade_id is None:
            raise ValueError(
                "a structure-scoped UNWIND Action needs trade_id and "
                "structure_id"
            )
        if self.size is not None:
            if self.structure_id is None:
                raise ValueError(
                    "an UNWIND size requires a structure_id"
                )
            if self.size <= 0:
                raise ValueError(
                    "an UNWIND size must be a positive amount"
                )

    def _validate_shape(self):
        if self.type is ActionType.NEW:
            self._validate_new()
        else:
            self._validate_unwind()


@dataclass(frozen=True)
class ActionGroup:
    """One strategic decision producing one or more Actions.

    A strategy may emit multiple ActionGroups per loop day — one per decision.
    The single-action subset emits exactly one Action per group; the tuple shape
    is the schema's, and the pipeline (not this class) gates groups with more
    than one Action.

    ``action_group_id`` / ``emission_date`` are assigned by the log at emission.
    There is deliberately **no** group-level ``tags``: trade-level tags ride
    :class:`TradeSpec`, and there is no replacement-lineage field (replacement
    belongs to the scaling rule, which is future work).
    """

    provenance: str
    actions: tuple[Action, ...]
    action_group_id: str | None = None
    emission_date: str | None = None

    def __post_init__(self):
        object.__setattr__(self, "actions", tuple(self.actions or ()))
        if not self.actions:
            raise ValueError("an ActionGroup requires at least one Action")
        if self.provenance not in PROVENANCE_CONSTANTS:
            raise ValueError(f"unknown provenance {self.provenance!r}")
        for action in self.actions:
            if not isinstance(action, Action):
                raise TypeError(
                    "ActionGroup.actions must hold Action objects"
                )


class ActionGroupRecord:
    """One emitted ActionGroup plus its downstream facts.

    The record is created by :meth:`ActionGroupLog.append`, which mints
    ``action_ids`` parallel to ``action_group.actions``.  Its facts --
    ``order_ids``, ``order_outcomes`` and ``group_note`` -- are written exactly
    once, together, by :meth:`finalize`; there is no other mutation path.  The
    record is never removed from the log.

    Write-once is tracked by a private ``_finalized`` flag, never by a data
    field: ``order_ids`` is a fact, and a fact must not double as state.
    """

    __slots__ = (
        "action_group",
        "_action_ids",
        "_finalized",
        "_order_ids",
        "_order_outcomes",
        "_group_note",
    )

    def __init__(
        self, action_group: ActionGroup, action_ids: tuple[str, ...]
    ):
        action_ids = tuple(action_ids)
        if len(action_ids) != len(action_group.actions):
            raise ValueError(
                "action_ids must be parallel to action_group.actions"
            )
        self.action_group = action_group
        self._action_ids = action_ids
        self._finalized = False
        self._order_ids: tuple[str, ...] = ()
        self._order_outcomes: tuple[OrderOutcome, ...] = ()
        self._group_note: str | None = None

    @property
    def action_ids(self) -> tuple[str, ...]:
        return self._action_ids

    @property
    def order_ids(self) -> tuple[str, ...]:
        return self._order_ids

    @property
    def order_outcomes(self) -> tuple[OrderOutcome, ...]:
        return self._order_outcomes

    @property
    def group_note(self) -> str | None:
        return self._group_note

    def finalize(
        self,
        order_ids: tuple[str, ...],
        order_outcomes: tuple[OrderOutcome, ...],
        group_note: str | None = None,
    ) -> None:
        """Write the record's facts exactly once, enforcing their invariants.

        ``order_ids`` must be non-empty and parallel to ``order_outcomes``;
        every outcome must be an :class:`~backtester.orders.OrderOutcome`; and
        ``group_note`` must be a string or ``None``.  Raises ``RuntimeError``
        on a second call.  Validation happens **before** ``_finalized`` is
        set, so a failed call leaves the record unfinalized and a later valid
        call succeeds.
        """
        if self._finalized:
            raise RuntimeError("ActionGroupRecord.finalize is write-once")
        order_ids = tuple(order_ids)
        order_outcomes = tuple(order_outcomes)
        if group_note is not None and not isinstance(group_note, str):
            raise TypeError("group_note must be a string or None")
        if not order_ids:
            raise ValueError("finalize requires at least one order_id")
        if len(order_ids) != len(order_outcomes):
            raise ValueError(
                "order_outcomes must be parallel to order_ids"
            )
        if any(
            not isinstance(outcome, OrderOutcome)
            for outcome in order_outcomes
        ):
            raise TypeError(
                "order_outcomes must hold OrderOutcome values"
            )
        self._order_ids = order_ids
        self._order_outcomes = order_outcomes
        self._group_note = group_note
        self._finalized = True


@dataclass(frozen=True)
class AggregationContext:
    """Everything synthesis and its rules may read for one loop day.

    Frozen: a mutable context handed to every rule would be a cross-rule
    contamination hazard.  ``date`` is the loop day T; ``action_group_log`` is
    the run's log (rules may read any strategy's records), ``position_books``
    the T-1 position snapshot, ``calendar`` the run's provider and ``config``
    the run's :class:`~backtester.backtest_engine.BacktestConfig`.
    ``execution_log`` is the run's live execution log (``None`` is legal for
    unit stubs that do not exercise execution).
    """

    date: str
    action_group_log: "ActionGroupLog"
    execution_log: "ExecutionLog | None"
    position_books: "PositionBooks"
    calendar: "CalendarProvider | None"
    config: "BacktestConfig | None"
