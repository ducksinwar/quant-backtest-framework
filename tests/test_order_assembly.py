"""Order assembly: book-state equivalence and the direct Order contract.

The corpus pins the converter against **book state**: each case applies the
produced ``Order`` objects to a stub book exactly as the engine's commit phase
does (group filled orders by ``action_id``; create a trade, extend a trade, or
apply signed leg deltas to a structure), then compares the resulting positions
with the pre-refactor expectations.

Every UNWIND scope is in the corpus: the whole book (``trade_id=None``), a whole
trade (``trade_id`` set), and one structure (``trade_id`` and ``structure_id``
set, optionally with a partial ``size``).  ``tests/test_backtester.py`` pins the
execution equivalence of the per-structure and whole-trade forms against the
live engine.
"""

import dataclasses
import uuid

import pytest

from backtester.action_group_log import ActionGroupLog
from backtester.actions import (
    Action,
    ActionGroup,
    ActionType,
    AggregationContext,
    ContractSpec,
    LegSpec,
    PROVENANCE_SIGNAL,
    Side,
    StructureSpec,
    TradeSpec,
)
from backtester.order_assembly import (
    DEFAULT_RULE_ORDER,
    OrderAssembly,
    action_group_to_order_group,
)
from backtester.orders import OrderGroup, OrderSide
from backtester.position_books import PositionBooks
from backtester.snapshots import (
    LegSnapshot,
    PortfolioState,
    StructureSnapshot,
    TradeSnapshot,
)

TRADE_ID = "T1"
STRUCTURE_ID = "S1"
ACTION_ID = "a1"


# --- books --------------------------------------------------------------


def _books(trade_id=TRADE_ID, structure_id=STRUCTURE_ID, ticker="SPY"):
    leg = LegSnapshot(
        ticker=ticker,
        asset_class="equity",
        size=100.0,
        entry_price=100.0,
        current_price=105.0,
        leg_id="L1",
    )
    structure = StructureSnapshot(legs=(leg,), structure_id=structure_id)
    trade = TradeSnapshot(trade_id=trade_id, structures=(structure,))
    return PositionBooks(
        PortfolioState(date="2024-01-05", trades=(trade,)), ()
    )


def _multi_leg_books(trade_id=TRADE_ID, structure_id=STRUCTURE_ID):
    structure = StructureSnapshot(
        legs=(_snapshot_leg("SPY", 100.0, "L1"),
              _snapshot_leg("QQQ", 50.0, "L2")),
        structure_id=structure_id,
    )
    trade = TradeSnapshot(trade_id=trade_id, structures=(structure,))
    return PositionBooks(
        PortfolioState(date="2024-01-05", trades=(trade,)), ()
    )


def _short_books(trade_id=TRADE_ID, structure_id=STRUCTURE_ID):
    structure = StructureSnapshot(
        legs=(_snapshot_leg("SPY", -100.0, "L1"),), structure_id=structure_id
    )
    trade = TradeSnapshot(trade_id=trade_id, structures=(structure,))
    return PositionBooks(
        PortfolioState(date="2024-01-05", trades=(trade,)), ()
    )


def _snapshot_leg(ticker="SPY", size=100.0, leg_id="L1"):
    return LegSnapshot(
        ticker=ticker,
        asset_class="equity",
        size=size,
        entry_price=100.0,
        current_price=105.0,
        leg_id=leg_id,
    )


def _ctx(books=None):
    return AggregationContext(
        date="2024-01-08",
        action_group_log=ActionGroupLog(),
        execution_log=None,
        position_books=_books() if books is None else books,
        calendar=None,
        config=None,
    )


# --- stub book state ----------------------------------------------------


def _state_trade(trade_id, *structures):
    return {"trade_id": trade_id, "structures": list(structures)}


def _state_structure(structure_id, *legs):
    return {"structure_id": structure_id, "legs": list(legs)}


def _signed(order_leg):
    return (
        order_leg.quantity
        if order_leg.side is OrderSide.BUY
        else -order_leg.quantity
    )


def _copy_state(book_state):
    return [
        {
            "trade_id": trade["trade_id"],
            "structures": [
                {
                    "structure_id": structure["structure_id"],
                    "legs": list(structure["legs"]),
                }
                for structure in trade["structures"]
            ],
        }
        for trade in book_state
    ]


def _apply_orders_to_stub_book(orders, book_state):
    """Apply ``Order`` objects to a stub book, mirroring the engine commit.

    ``book_state`` is a list of trades; a trade is ``{"trade_id": id,
    "structures": [...]}`` and a structure is ``{"structure_id": id, "legs":
    [(ticker, signed_size), ...]}``.  Filled orders are grouped by ``action_id``
    (the engine's rule): one group creates one trade, extends one trade with
    new structures, or applies signed deltas to existing structures.  Empty
    structures and empty trades are removed, matching the live book.
    """
    book = _copy_state(book_state)
    grouped: dict[str, list] = {}
    for order in orders:
        grouped.setdefault(order.action_id, []).append(order)

    for items in grouped.values():
        opens = any(
            order.structure_id is None and order.trade_id is None
            for order in items
        )
        targets = any(order.structure_id is not None for order in items)
        if opens and targets:
            raise ValueError("mixed open and target orders in one action")

        if opens:
            trade = _state_trade(None)
            for order in items:
                new_structure = _state_structure(None)
                new_structure["legs"] = [
                    (leg.ticker, _signed(leg)) for leg in order.legs
                ]
                trade["structures"].append(new_structure)
            book.append(trade)
            continue

        if items[0].structure_id is None:
            trade = _find_state_trade(book, items[0].trade_id)
            for order in items:
                new_structure = _state_structure(None)
                new_structure["legs"] = [
                    (leg.ticker, _signed(leg)) for leg in order.legs
                ]
                trade["structures"].append(new_structure)
            continue

        for order in items:
            trade = _find_state_trade(book, order.trade_id)
            structure = _find_state_structure(trade, order.structure_id)
            for leg in order.legs:
                _apply_leg_delta(structure, leg.ticker, _signed(leg))
            structure["legs"] = [
                (ticker, size) for ticker, size in structure["legs"] if size
            ]
            if not structure["legs"]:
                trade["structures"].remove(structure)

    book[:] = [trade for trade in book if trade["structures"]]
    return book


def _find_state_trade(book, trade_id):
    for trade in book:
        if trade["trade_id"] == trade_id:
            return trade
    raise AssertionError(f"trade {trade_id!r} not in stub book")


def _find_state_structure(trade, structure_id):
    for structure in trade["structures"]:
        if structure["structure_id"] == structure_id:
            return structure
    raise AssertionError(f"structure {structure_id!r} not in stub trade")


def _apply_leg_delta(structure, ticker, delta):
    for index, (existing, size) in enumerate(structure["legs"]):
        if existing == ticker:
            structure["legs"][index] = (ticker, size + delta)
            return
    structure["legs"].append((ticker, delta))


# --- action-group builders ---------------------------------------------


def _leg(ticker, side, size, **spec_kwargs):
    return LegSpec(ContractSpec(ticker, **spec_kwargs), side, size)


def _ag(actions, *, provenance=PROVENANCE_SIGNAL):
    return ActionGroup(
        action_group_id=None,
        provenance=provenance,
        actions=tuple(actions),
    )


def _create(structures, *, tags=()):
    return _ag(
        (
            Action(
                type=ActionType.NEW,
                spec=TradeSpec(structures=tuple(structures), tags=tuple(tags)),
            ),
        )
    )


def _extend(structure, *, trade_id=TRADE_ID):
    return _ag((Action(type=ActionType.NEW, spec=structure, trade_id=trade_id),))


def _partial_add(*, trade_id=TRADE_ID, structure_id=STRUCTURE_ID, size=25.0):
    return _ag(
        (
            Action(
                type=ActionType.NEW,
                trade_id=trade_id,
                structure_id=structure_id,
                size=size,
            ),
        )
    )


def _unwind(*, trade_id=None, structure_id=None, size=None):
    return _ag(
        (
            Action(
                type=ActionType.UNWIND,
                trade_id=trade_id,
                structure_id=structure_id,
                size=size,
            ),
        )
    )


def _convert(group, ctx=None):
    return action_group_to_order_group(
        group, (ACTION_ID,), _ctx() if ctx is None else ctx
    )


_INPUT_BOOK = [
    _state_trade(TRADE_ID, _state_structure(STRUCTURE_ID, ("SPY", 100.0)))
]

#: (name, input book state, ActionGroup, expected book state)
BOOK_CORPUS = [
    (
        "new_single_leg",
        [],
        _create(
            (
                StructureSpec(
                    legs=(
                        _leg("SPY", Side.LONG, 379, asset_class="equity",
                             currency="USD"),
                    )
                ),
            ),
            tags=("short_ma:89.82", "long_ma:87.51"),
        ),
        [
            _state_trade(
                None,
                _state_structure(None, ("SPY", 379)),
            )
        ],
    ),
    (
        "new_multi_leg_including_a_short_leg",
        [],
        _create(
            (
                StructureSpec(
                    legs=(
                        _leg("HSI", Side.LONG, 10,
                             asset_class="equity_future", multiplier=50),
                        _leg("SPY", Side.SHORT, 200,
                             asset_class="equity", currency="USD"),
                    )
                ),
            ),
        ),
        [
            _state_trade(
                None,
                _state_structure(None, ("HSI", 10), ("SPY", -200)),
            )
        ],
    ),
    (
        "new_single_short_leg",
        [],
        _create(
            (
                StructureSpec(
                    legs=(
                        _leg("QQQ", Side.SHORT, 100, asset_class="equity",
                             currency="USD"),
                    )
                ),
            ),
        ),
        [_state_trade(None, _state_structure(None, ("QQQ", -100)))],
    ),
    (
        "new_leg_with_params_cost_leg_and_tags",
        [],
        _create(
            (
                StructureSpec(
                    legs=(
                        LegSpec(
                            ContractSpec(
                                "SPX",
                                asset_class="equity_option",
                                multiplier=100,
                                cost_leg=True,
                                params=(("strike", 5000),
                                        ("expiry", "2025-12-19")),
                            ),
                            Side.LONG,
                            5,
                            ("hedge",),
                        ),
                    )
                ),
            ),
        ),
        [_state_trade(None, _state_structure(None, ("SPX", 5)))],
    ),
    (
        "unwind_all_fan_out",
        _INPUT_BOOK,
        _unwind(),
        [],
    ),
    (
        "unwind_one_structure_fully",
        _INPUT_BOOK,
        _unwind(trade_id=TRADE_ID, structure_id=STRUCTURE_ID),
        [],
    ),
    (
        "unwind_one_structure_partially",
        _INPUT_BOOK,
        _unwind(trade_id=TRADE_ID, structure_id=STRUCTURE_ID, size=40),
        [_state_trade(TRADE_ID, _state_structure(STRUCTURE_ID, ("SPY", 60)))],
    ),
    (
        "new_multi_structure",
        [],
        _create(
            (
                StructureSpec(legs=(
                    _leg("SPY", Side.LONG, 100, asset_class="equity",
                         currency="USD"),)),
                StructureSpec(legs=(
                    _leg("HSI", Side.LONG, 10,
                         asset_class="equity_future", multiplier=50),
                    _leg("SPY", Side.SHORT, 200, asset_class="equity",
                         currency="USD"))),
            ),
        ),
        [
            _state_trade(
                None,
                _state_structure(None, ("SPY", 100)),
                _state_structure(None, ("HSI", 10), ("SPY", -200)),
            )
        ],
    ),
    (
        "new_add_structures_to_existing_trade",
        _INPUT_BOOK,
        _extend(
            StructureSpec(legs=(
                _leg("SPY", Side.LONG, 50, asset_class="equity",
                     currency="USD"),))
        ),
        [
            _state_trade(
                TRADE_ID,
                _state_structure(STRUCTURE_ID, ("SPY", 100)),
                _state_structure(None, ("SPY", 50)),
            )
        ],
    ),
    (
        "new_partial_add_to_structure",
        _INPUT_BOOK,
        _partial_add(size=25),
        [_state_trade(TRADE_ID, _state_structure(STRUCTURE_ID, ("SPY", 125)))],
    ),
    (
        "unwind_whole_trade",
        _INPUT_BOOK,
        _unwind(trade_id=TRADE_ID),
        [],
    ),
]

_CORPUS_IDS = [case[0] for case in BOOK_CORPUS]


@pytest.mark.parametrize(
    "name,book,group,expected", BOOK_CORPUS, ids=_CORPUS_IDS
)
def test_converter_produces_expected_book_state(name, book, group, expected):
    orders = _convert(group).orders
    assert _apply_orders_to_stub_book(orders, book) == expected


@pytest.mark.parametrize(
    "name,book,group,expected", BOOK_CORPUS, ids=_CORPUS_IDS
)
def test_every_order_carries_lineage_and_a_unique_id(
    name, book, group, expected
):
    orders = _convert(group).orders
    assert orders
    for order in orders:
        assert order.action_id == ACTION_ID
        assert len(order.order_id) == 32
        int(order.order_id, 16)
        assert order.legs
    assert len({order.order_id for order in orders}) == len(orders)


#: name -> [(structure_id, trade_id, [(ticker, side, quantity), ...]), ...]
EXPECTED_ORDERS = {
    "new_single_leg": [
        (None, None, [("SPY", OrderSide.BUY, 379)]),
    ],
    "new_multi_leg_including_a_short_leg": [
        (None, None, [("HSI", OrderSide.BUY, 10),
                      ("SPY", OrderSide.SELL, 200)]),
    ],
    "new_single_short_leg": [
        (None, None, [("QQQ", OrderSide.SELL, 100)]),
    ],
    "new_leg_with_params_cost_leg_and_tags": [
        (None, None, [("SPX", OrderSide.BUY, 5)]),
    ],
    "unwind_all_fan_out": [
        (STRUCTURE_ID, TRADE_ID, [("SPY", OrderSide.SELL, 100)]),
    ],
    "unwind_one_structure_fully": [
        (STRUCTURE_ID, TRADE_ID, [("SPY", OrderSide.SELL, 100)]),
    ],
    "unwind_one_structure_partially": [
        (STRUCTURE_ID, TRADE_ID, [("SPY", OrderSide.SELL, 40)]),
    ],
    "new_multi_structure": [
        (None, None, [("SPY", OrderSide.BUY, 100)]),
        (None, None, [("HSI", OrderSide.BUY, 10),
                      ("SPY", OrderSide.SELL, 200)]),
    ],
    "new_add_structures_to_existing_trade": [
        (None, TRADE_ID, [("SPY", OrderSide.BUY, 50)]),
    ],
    "new_partial_add_to_structure": [
        (STRUCTURE_ID, TRADE_ID, [("SPY", OrderSide.BUY, 25)]),
    ],
    "unwind_whole_trade": [
        (STRUCTURE_ID, TRADE_ID, [("SPY", OrderSide.SELL, 100)]),
    ],
}


@pytest.mark.parametrize(
    "name,book,group,expected", BOOK_CORPUS, ids=_CORPUS_IDS
)
def test_order_targets_and_legs(name, book, group, expected):
    orders = _convert(group).orders
    actual = [
        (
            order.structure_id,
            order.trade_id,
            [(leg.ticker, leg.side, leg.quantity) for leg in order.legs],
        )
        for order in orders
    ]
    assert actual == EXPECTED_ORDERS[name]


def test_new_leg_carries_contract_extras():
    group = _create(
        (
            StructureSpec(
                legs=(
                    LegSpec(
                        ContractSpec(
                            "SPX",
                            asset_class="equity_option",
                            multiplier=100,
                            cost_leg=True,
                            params=(("strike", 5000),
                                    ("expiry", "2025-12-19")),
                        ),
                        Side.LONG,
                        5,
                        ("hedge",),
                    ),
                )
            ),
        )
    )
    leg = _convert(group).orders[0].legs[0]
    assert leg.asset_class == "equity_option"
    assert leg.multiplier == 100
    assert leg.cost_leg is True
    assert leg.tags == ("hedge",)
    assert leg.params == (("strike", 5000), ("expiry", "2025-12-19"))


class TestBuildOrderGroups:
    def test_one_order_group_per_action_group_positionally_aligned(self):
        log = ActionGroupLog()
        create = log.append(
            _create((StructureSpec(legs=(
                _leg("SPY", Side.LONG, 100, asset_class="equity"),)),)),
            "2024-01-08",
        )
        unwind = log.append(
            _unwind(trade_id=TRADE_ID, structure_id=STRUCTURE_ID),
            "2024-01-08",
        )

        groups = OrderAssembly().build_order_groups(
            [create.action_group, unwind.action_group],
            _ctx(),
            [create.action_ids, unwind.action_ids],
        )

        assert isinstance(groups, tuple) and len(groups) == 2
        assert all(isinstance(g, OrderGroup) for g in groups)
        assert groups[0].orders[0].action_id == create.action_ids[0]
        assert groups[1].orders[0].action_id == unwind.action_ids[0]
        assert groups[0].orders[0].structure_id is None
        assert groups[1].orders[0].structure_id == STRUCTURE_ID
        assert groups[1].orders[0].trade_id == TRADE_ID

    def test_order_group_id_is_minted_and_never_enters_the_order(self):
        log = ActionGroupLog()
        stamped = log.append(
            _create((StructureSpec(legs=(
                _leg("SPY", Side.LONG, 100),)),)), "2024-01-08"
        )
        group = OrderAssembly().build_order_groups(
            [stamped.action_group], _ctx(), [stamped.action_ids]
        )[0]
        assert len(group.order_group_id) == 32
        int(group.order_group_id, 16)
        assert group.order_group_id not in group.orders[0].order_id

    def test_order_ids_are_minted_on_the_orders(self):
        log = ActionGroupLog()
        stamped = log.append(
            _create((StructureSpec(legs=(
                _leg("SPY", Side.LONG, 100),)),)), "2024-01-08"
        )
        group = OrderAssembly().build_order_groups(
            [stamped.action_group], _ctx(), [stamped.action_ids]
        )[0]
        assert len(group.orders[0].order_id) == 32
        int(group.orders[0].order_id, 16)

    def test_action_ids_must_be_parallel_to_the_groups(self):
        log = ActionGroupLog()
        stamped = log.append(
            _create((StructureSpec(legs=(
                _leg("SPY", Side.LONG, 100),)),)), "2024-01-08"
        )
        with pytest.raises(ValueError, match="parallel to action_groups"):
            OrderAssembly().build_order_groups([stamped.action_group], _ctx(), [])

    def test_action_ids_must_be_parallel_to_each_group(self):
        log = ActionGroupLog()
        stamped = log.append(
            _create((StructureSpec(legs=(
                _leg("SPY", Side.LONG, 100),)),)), "2024-01-08"
        )
        with pytest.raises(ValueError, match="parallel"):
            OrderAssembly().build_order_groups(
                [stamped.action_group], _ctx(), [()]
            )

    def test_unstamped_action_group_is_rejected(self):
        with pytest.raises(ValueError, match="assigned at emission"):
            OrderAssembly().build_order_groups(
                [_create((StructureSpec(legs=(
                    _leg("SPY", Side.LONG, 100),)),))],
                _ctx(),
                [(ACTION_ID,)],
            )

    def test_duplicate_action_group_id_is_rejected(self):
        log = ActionGroupLog()
        stamped = log.append(
            _create((StructureSpec(legs=(
                _leg("SPY", Side.LONG, 100),)),)), "2024-01-08"
        )
        with pytest.raises(ValueError, match="duplicate action_group_id"):
            OrderAssembly().build_order_groups(
                [stamped.action_group, stamped.action_group],
                _ctx(),
                [stamped.action_ids, stamped.action_ids],
            )

    def test_empty_patch(self):
        assert OrderAssembly().build_order_groups([], _ctx(), []) == ()


class TestPluginChain:
    def test_default_rule_order_is_the_documented_chain(self):
        assert DEFAULT_RULE_ORDER == (
            "roll",
            "auto_unwind",
            "hedge_rebalance",
            "scaling",
        )

    def test_rules_run_in_configured_order(self):
        calls = []

        def rule_a(groups, ctx):
            calls.append("a")
            return list(groups)

        def rule_b(groups, ctx):
            calls.append("b")
            return list(groups)

        log = ActionGroupLog()
        stamped = log.append(
            _create((StructureSpec(legs=(
                _leg("SPY", Side.LONG, 100),)),)), "2024-01-08"
        )
        OrderAssembly([rule_a, rule_b]).build_order_groups(
            [stamped.action_group], _ctx(), [stamped.action_ids]
        )
        assert calls == ["a", "b"]

    def test_a_rule_that_removes_a_group_fails_loud(self):
        log = ActionGroupLog()
        remove_me = log.append(
            _create((StructureSpec(legs=(
                _leg("SPY", Side.LONG, 100),)),)), "2024-01-08"
        )
        keep_me = log.append(
            _create((StructureSpec(legs=(
                _leg("QQQ", Side.LONG, 200),)),)), "2024-01-08"
        )

        def remove_spy(groups, ctx):
            return [
                g
                for g in groups
                if g.actions[0].spec.structures[0].legs[0].contract_spec.ticker
                != "SPY"
            ]

        with pytest.raises(ValueError, match="removed an ActionGroup"):
            OrderAssembly([remove_spy]).build_order_groups(
                [remove_me.action_group, keep_me.action_group],
                _ctx(),
                [remove_me.action_ids, keep_me.action_ids],
            )

    def test_a_rule_may_not_emit_a_group_never_appended(self):
        log = ActionGroupLog()
        keep = log.append(
            _create((StructureSpec(legs=(
                _leg("SPY", Side.LONG, 100),)),)), "2024-01-08"
        )

        def add_clone(groups, ctx):
            return list(groups) + [
                dataclasses.replace(
                    keep.action_group, action_group_id=uuid.uuid4().hex
                )
            ]

        with pytest.raises(ValueError, match="never appended"):
            OrderAssembly([add_clone]).build_order_groups(
                [keep.action_group], _ctx(), [keep.action_ids]
            )

    def test_non_callable_rule_is_rejected(self):
        with pytest.raises(TypeError, match="not callable"):
            OrderAssembly(["scaling"])

    def test_rules_property_is_the_configured_tuple(self):
        def rule(groups, ctx):
            return groups

        assert OrderAssembly([rule]).rules == (rule,)
        assert OrderAssembly().rules == ()


class TestConverterFailLoud:
    def test_unwind_of_an_unknown_structure(self):
        with pytest.raises(ValueError, match="not present in the T-1 book"):
            _convert(_unwind(trade_id=TRADE_ID, structure_id="NOPE"))

    def test_unwind_of_an_unknown_trade(self):
        with pytest.raises(ValueError, match="no active trade"):
            _convert(_unwind(trade_id="T_NOPE"))

    def test_extend_of_an_unknown_trade(self):
        with pytest.raises(ValueError, match="no active trade"):
            _convert(
                _extend(
                    StructureSpec(legs=(
                        _leg("SPY", Side.LONG, 50, asset_class="equity"),)),
                    trade_id="T_NOPE",
                )
            )

    def test_extend_of_a_known_trade_succeeds(self):
        order = _convert(
            _extend(
                StructureSpec(legs=(
                    _leg("SPY", Side.LONG, 50, asset_class="equity"),))
            )
        ).orders[0]
        assert order.structure_id is None
        assert order.trade_id == TRADE_ID
        assert order.legs[0].side is OrderSide.BUY
        assert order.legs[0].quantity == 50

    def test_unwind_of_an_empty_book(self):
        books = PositionBooks()
        with pytest.raises(ValueError, match="book is empty"):
            _convert(_unwind(), _ctx(books))

    def test_new_create_without_structures_fails_at_construction(self):
        with pytest.raises(ValueError, match="at least one structure"):
            _create(())

    def test_new_structure_without_legs_fails_at_construction(self):
        with pytest.raises(ValueError, match="at least one leg"):
            _create((StructureSpec(legs=()),))

    def test_new_leg_without_a_size(self):
        with pytest.raises(ValueError, match="requires a size"):
            _convert(
                _create((StructureSpec(legs=(
                    _leg("SPY", Side.LONG, None),)),))
            )

    def test_partial_unwind_size_requires_a_structure(self):
        with pytest.raises(ValueError, match="requires a structure_id"):
            _unwind(trade_id=TRADE_ID, size=40)

    def test_size_must_be_positive(self):
        with pytest.raises(ValueError, match="positive"):
            _partial_add(size=0)
        with pytest.raises(ValueError, match="positive"):
            _unwind(trade_id=TRADE_ID, structure_id=STRUCTURE_ID, size=0)

    def test_partial_unwind_is_bounded_by_the_anchor(self):
        with pytest.raises(ValueError, match="less than the anchor"):
            _convert(
                _unwind(trade_id=TRADE_ID, structure_id=STRUCTURE_ID,
                        size=100)
            )

    def test_structure_trade_mismatch_fails_loud(self):
        books = PositionBooks(
            PortfolioState(
                date="2024-01-05",
                trades=(
                    TradeSnapshot(
                        trade_id="T_OTHER",
                        structures=(
                            StructureSnapshot(
                                legs=(_snapshot_leg(),),
                                structure_id=STRUCTURE_ID,
                            ),
                        ),
                    ),
                ),
            ),
            (),
        )
        with pytest.raises(ValueError, match="belongs to trade"):
            _convert(
                _unwind(trade_id=TRADE_ID, structure_id=STRUCTURE_ID),
                _ctx(books),
            )

    def test_structure_missing_from_book_fails_loud(self):
        with pytest.raises(ValueError, match="not present in the T-1 book"):
            _convert(_unwind(trade_id=TRADE_ID, structure_id="S_MISSING"))

    def test_zero_anchor_partial_add_fails_loud(self):
        structure = StructureSnapshot(
            legs=(_snapshot_leg("SPY", 0.0),), structure_id=STRUCTURE_ID
        )
        trade = TradeSnapshot(trade_id=TRADE_ID, structures=(structure,))
        books = PositionBooks(
            PortfolioState(date="2024-01-05", trades=(trade,)), ()
        )
        with pytest.raises(ValueError, match="non-zero anchor"):
            _convert(_partial_add(), _ctx(books))


class TestGates:
    def test_multi_action_group_is_rejected_before_conversion(self):
        log = ActionGroupLog()
        two = _ag((Action(type=ActionType.UNWIND),
                   Action(type=ActionType.UNWIND)))
        stamped = log.append(two, "2024-01-08")
        with pytest.raises(ValueError, match="single-action"):
            OrderAssembly().build_order_groups(
                [stamped.action_group], _ctx(), [stamped.action_ids]
            )

    def test_multi_leg_partial_add_is_rejected(self):
        with pytest.raises(ValueError, match="multi-leg"):
            _convert(_partial_add(), _ctx(_multi_leg_books()))

    def test_short_structure_partial_add_is_rejected(self):
        with pytest.raises(ValueError, match="short"):
            _convert(_partial_add(), _ctx(_short_books()))

    def test_short_structure_partial_unwind_is_rejected(self):
        with pytest.raises(ValueError, match="short"):
            _convert(
                _unwind(trade_id=TRADE_ID, structure_id=STRUCTURE_ID,
                        size=40),
                _ctx(_short_books()),
            )


class TestUnwindScopes:
    """All UNWIND scopes are representable, and may be enumerated."""

    def _two_structure_books(self):
        trade = TradeSnapshot(
            trade_id=TRADE_ID,
            structures=(
                StructureSnapshot(legs=(_snapshot_leg(),), structure_id="S1"),
                StructureSnapshot(
                    legs=(
                        LegSnapshot(
                            ticker="QQQ",
                            asset_class="equity",
                            size=50.0,
                            entry_price=200.0,
                            current_price=210.0,
                            leg_id="L2",
                        ),
                    ),
                    structure_id="S2",
                ),
            ),
        )
        return PositionBooks(
            PortfolioState(date="2024-01-05", trades=(trade,)), ()
        )

    def test_two_structures_may_be_enumerated_as_two_action_groups(self):
        log = ActionGroupLog()
        records = [
            log.append(
                _unwind(trade_id=TRADE_ID, structure_id=structure_id),
                "2024-01-08",
            )
            for structure_id in ("S1", "S2")
        ]

        out = OrderAssembly().build_order_groups(
            [record.action_group for record in records],
            _ctx(self._two_structure_books()),
            [record.action_ids for record in records],
        )

        orders = [g.orders[0] for g in out]
        assert [order.structure_id for order in orders] == ["S1", "S2"]
        assert {order.trade_id for order in orders} == {TRADE_ID}

    def test_unwind_all_and_whole_trade_forms(self):
        log = ActionGroupLog()
        stamped = log.append(_unwind(), "2024-01-08")

        out = OrderAssembly().build_order_groups(
            [stamped.action_group], _ctx(), [stamped.action_ids]
        )
        order = out[0].orders[0]
        assert order.structure_id == STRUCTURE_ID
        assert order.trade_id == TRADE_ID
        assert order.legs[0].side is OrderSide.SELL
        assert order.legs[0].quantity == 100

        whole = log.append(
            _unwind(trade_id=TRADE_ID), "2024-01-08"
        )
        whole_order = OrderAssembly().build_order_groups(
            [whole.action_group], _ctx(), [whole.action_ids]
        )[0].orders[0]
        assert whole_order.structure_id == STRUCTURE_ID
        assert whole_order.trade_id == TRADE_ID

    def test_whole_book_unwind_fans_out_one_order_per_structure(self):
        books = self._two_structure_books()
        group = _convert(_unwind(), _ctx(books))
        assert len(group.orders) == 2
        assert [o.structure_id for o in group.orders] == ["S1", "S2"]
        assert [_signed(o.legs[0]) for o in group.orders] == [-100.0, -50.0]


class TestContentMapping:
    def test_one_structure_maps_to_one_order(self):
        """Assembly never decomposes: one created structure is one order."""
        log = ActionGroupLog()
        records = [
            log.append(
                _create((StructureSpec(legs=(
                    _leg(f"T{i}", Side.LONG, 1),)),)), "2024-01-08"
            )
            for i in range(3)
        ]
        out = OrderAssembly().build_order_groups(
            [record.action_group for record in records],
            _ctx(),
            [record.action_ids for record in records],
        )
        assert len(out) == 3
        assert [len(g.orders) for g in out] == [1, 1, 1]
