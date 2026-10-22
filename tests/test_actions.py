"""Action schema, action-group log and position books."""

import dataclasses

import pytest

from backtester.action_group_log import ActionGroupLog, ActionGroupLogView
from backtester.actions import (
    Action,
    ActionGroup,
    ActionGroupRecord,
    ActionType,
    AggregationContext,
    ContractSpec,
    LegSpec,
    PROVENANCE_CONSTANTS,
    PROVENANCE_ROLL_RULE,
    PROVENANCE_SIGNAL,
    Side,
    StructureSpec,
    TradeSpec,
)
from backtester.execution_log import ExecutionLog
from backtester.orders import OrderOutcome
from backtester.position_books import Holding, PositionBook, PositionBooks
from backtester.snapshots import (
    LegSnapshot,
    PortfolioState,
    StructureSnapshot,
    TradeRecord,
    TradeSnapshot,
)


def _spec(ticker="SPY", **kwargs):
    return ContractSpec(ticker=ticker, **kwargs)


def _leg(ticker="SPY", side=Side.LONG, size=1.0, tags=()):
    return LegSpec(_spec(ticker), side, size, tags)


def _structure(ticker="SPY", side=Side.LONG, size=1.0):
    return StructureSpec(legs=(_leg(ticker, side, size),))


def _action(**kwargs):
    return Action(**kwargs)


def _group(
    actions,
    *,
    strategy_id="strat",
    provenance=PROVENANCE_SIGNAL,
):
    return ActionGroup(
        strategy_id=strategy_id,
        provenance=provenance,
        actions=tuple(actions),
    )


def _unwind_group(strategy_id="strat", structure_id=None, trade_id=None):
    return _group(
        (_action(type=ActionType.UNWIND, structure_id=structure_id,
                 trade_id=trade_id),),
        strategy_id=strategy_id,
    )


def _snapshot(trade_id="T1", structure_id="S1", ticker="SPY", size=100.0):
    leg = LegSnapshot(
        ticker=ticker,
        asset_class="equity",
        size=size,
        entry_price=100.0,
        current_price=105.0,
        leg_id="L1",
    )
    structure = StructureSnapshot(legs=(leg,), structure_id=structure_id)
    trade = TradeSnapshot(trade_id=trade_id, structures=(structure,))
    return PortfolioState(date="2024-01-05", trades=(trade,))


class TestActionTypeAndSide:
    def test_action_values_match_the_legacy_action_strings(self):
        assert [a.value for a in ActionType] == ["NEW", "UNWIND"]

    def test_action_accepts_its_string_value(self):
        assert ActionType("UNWIND") is ActionType.UNWIND
        assert ActionType("NEW") is ActionType.NEW

    def test_side_values(self):
        assert [s.value for s in Side] == ["LONG", "SHORT"]

    def test_provenance_constants_cover_signal_and_reserved_rules(self):
        assert PROVENANCE_SIGNAL in PROVENANCE_CONSTANTS
        assert PROVENANCE_ROLL_RULE in PROVENANCE_CONSTANTS
        assert {"signal", "scaling_rule"} <= PROVENANCE_CONSTANTS

    def test_netting_is_not_a_provenance(self):
        assert "netting_rule" not in PROVENANCE_CONSTANTS


class TestContractSpec:
    def test_is_frozen(self):
        spec = _spec()
        with pytest.raises(dataclasses.FrozenInstanceError):
            spec.ticker = "QQQ"

    def test_requires_a_non_empty_ticker(self):
        with pytest.raises(ValueError):
            ContractSpec(ticker="")

    def test_params_preserve_insertion_order(self):
        spec = ContractSpec(
            ticker="SPX",
            params=(("strike", 5000), ("expiry", "2025-12-19")),
        )
        assert list(spec.param_dict) == ["strike", "expiry"]

    @pytest.mark.parametrize(
        "key", ["ticker", "size", "tags", "asset_class", "structure_id"]
    )
    def test_reserved_leg_dict_keys_are_rejected_in_params(self, key):
        with pytest.raises(ValueError, match="reserved leg-dict key"):
            ContractSpec(ticker="SPY", params=((key, 1),))

    def test_params_must_be_pairs(self):
        with pytest.raises(TypeError):
            ContractSpec(ticker="SPY", params=[("strike", 1)])


class TestLegSpecSignMapping:
    def test_long_keeps_the_size(self):
        assert LegSpec(_spec(), Side.LONG, 100).signed_size == 100

    def test_short_negates_the_size(self):
        assert LegSpec(_spec(), Side.SHORT, 100).signed_size == -100

    def test_none_size_stays_none(self):
        assert LegSpec(_spec(), Side.LONG, None).signed_size is None

    def test_side_accepts_its_string_value(self):
        assert LegSpec(_spec(), "SHORT", 1).side is Side.SHORT

    def test_negative_size_is_rejected(self):
        with pytest.raises(ValueError, match="must be non-negative"):
            LegSpec(_spec(), Side.LONG, -100)

    def test_zero_and_positive_sizes_are_accepted(self):
        assert LegSpec(_spec(), Side.LONG, 0).size == 0
        assert LegSpec(_spec(), Side.LONG, 100).size == 100

    def test_tags_are_normalised_to_a_tuple(self):
        assert LegSpec(_spec(), Side.LONG, 1, ["hedge"]).tags == ("hedge",)

    def test_non_numeric_size_is_rejected(self):
        with pytest.raises(TypeError):
            LegSpec(_spec(), Side.LONG, "100")


class TestSpecObjects:
    def test_structure_spec_is_frozen(self):
        spec = _structure()
        with pytest.raises(dataclasses.FrozenInstanceError):
            spec.legs = ()

    def test_structure_spec_legs_must_hold_leg_specs(self):
        with pytest.raises(TypeError, match="LegSpec"):
            StructureSpec(legs=({"ticker": "SPY"},))

    def test_structure_tags_normalised(self):
        assert StructureSpec(legs=(), tags=["a"]).tags == ("a",)

    def test_trade_spec_structures_must_hold_structure_specs(self):
        with pytest.raises(TypeError, match="StructureSpec"):
            TradeSpec(structures=({"legs": []},))

    def test_trade_spec_normalises_and_holds_tags(self):
        spec = TradeSpec(structures=(_structure(),), tags=["t1", "t2"])
        assert spec.tags == ("t1", "t2")
        assert len(spec.structures) == 1


class TestActionShapeMatrix:
    """The construction-time matrix, row by row (unlisted shapes fail loud)."""

    def test_new_create_with_trade_spec(self):
        action = Action(
            type=ActionType.NEW,
            spec=TradeSpec(structures=(_structure(),)),
        )
        assert action.trade_id is None and action.size is None

    def test_new_extend_with_structure_spec(self):
        action = Action(
            type=ActionType.NEW, spec=_structure(), trade_id="T1"
        )
        assert action.structure_id is None

    def test_new_partial_add(self):
        action = Action(
            type=ActionType.NEW, trade_id="T1", structure_id="S1", size=5
        )
        assert action.spec is None

    def test_new_create_rejects_a_trade_id(self):
        with pytest.raises(ValueError, match="carries no trade_id"):
            Action(
                type=ActionType.NEW,
                spec=TradeSpec(structures=(_structure(),)),
                trade_id="T1",
            )

    def test_new_create_rejects_a_size(self):
        with pytest.raises(ValueError, match="carries no size"):
            Action(
                type=ActionType.NEW,
                spec=TradeSpec(structures=(_structure(),)),
                size=5,
            )

    def test_new_create_requires_structures(self):
        with pytest.raises(ValueError, match="at least one structure"):
            Action(type=ActionType.NEW, spec=TradeSpec())

    def test_new_create_structure_requires_legs(self):
        with pytest.raises(ValueError, match="at least one leg"):
            Action(
                type=ActionType.NEW,
                spec=TradeSpec(structures=(StructureSpec(legs=()),)),
            )

    def test_new_extend_requires_a_trade_id(self):
        with pytest.raises(ValueError, match="needs a trade_id"):
            Action(type=ActionType.NEW, spec=_structure())

    def test_new_extend_requires_legs(self):
        with pytest.raises(ValueError, match="at least one leg"):
            Action(
                type=ActionType.NEW,
                spec=StructureSpec(legs=()),
                trade_id="T1",
            )

    def test_new_with_neither_spec_nor_structure(self):
        with pytest.raises(ValueError, match="needs a TradeSpec"):
            Action(type=ActionType.NEW)

    def test_partial_add_needs_a_positive_size(self):
        with pytest.raises(ValueError, match="positive size"):
            Action(
                type=ActionType.NEW, trade_id="T1", structure_id="S1",
                size=0,
            )
        with pytest.raises(ValueError, match="positive size"):
            Action(type=ActionType.NEW, trade_id="T1", structure_id="S1")

    def test_partial_add_needs_a_trade_id(self):
        with pytest.raises(ValueError, match="needs trade_id"):
            Action(
                type=ActionType.NEW, structure_id="S1", size=5
            )

    def test_partial_add_rejects_a_spec(self):
        with pytest.raises(ValueError, match="carries no spec"):
            Action(
                type=ActionType.NEW, trade_id="T1", structure_id="S1",
                size=5, spec=_structure(),
            )

    def test_unwind_full_structure(self):
        action = Action(
            type=ActionType.UNWIND, trade_id="T1", structure_id="S1"
        )
        assert action.size is None

    def test_unwind_structure_requires_a_trade_id(self):
        with pytest.raises(ValueError, match="needs trade_id"):
            Action(type=ActionType.UNWIND, structure_id="S1")

    def test_unwind_partial_structure(self):
        action = Action(
            type=ActionType.UNWIND, trade_id="T1", structure_id="S1",
            size=40,
        )
        assert action.size == 40

    def test_unwind_whole_trade(self):
        Action(type=ActionType.UNWIND, trade_id="T1")

    def test_unwind_whole_book(self):
        Action(type=ActionType.UNWIND)

    def test_unwind_size_requires_a_structure(self):
        with pytest.raises(ValueError, match="requires a structure_id"):
            Action(type=ActionType.UNWIND, trade_id="T1", size=40)

    def test_unwind_size_must_be_positive(self):
        with pytest.raises(ValueError, match="positive amount"):
            Action(
                type=ActionType.UNWIND, trade_id="T1", structure_id="S1",
                size=0,
            )

    def test_unwind_rejects_a_spec(self):
        with pytest.raises(ValueError, match="carries no spec"):
            Action(
                type=ActionType.UNWIND, structure_id="S1", spec=_structure()
            )

    def test_spec_must_be_a_known_type(self):
        with pytest.raises(TypeError, match="Action.spec"):
            Action(type=ActionType.NEW, spec={"not": "a spec"})

    def test_size_must_be_numeric(self):
        with pytest.raises(TypeError, match="Action.size"):
            Action(
                type=ActionType.UNWIND, structure_id="S1", size="40"
            )

    def test_type_accepts_its_string_value(self):
        assert Action(type="UNWIND").type is ActionType.UNWIND


class TestActionGroup:
    def test_is_frozen(self):
        group = _group((_action(type=ActionType.UNWIND),))
        with pytest.raises(dataclasses.FrozenInstanceError):
            group.strategy_id = "other"

    def test_requires_at_least_one_action(self):
        with pytest.raises(ValueError, match="at least one Action"):
            ActionGroup(
                strategy_id="s", provenance=PROVENANCE_SIGNAL, actions=()
            )

    def test_requires_a_strategy_id(self):
        with pytest.raises(ValueError, match="strategy_id"):
            ActionGroup(
                strategy_id="",
                provenance=PROVENANCE_SIGNAL,
                actions=(_action(type=ActionType.UNWIND),),
            )

    def test_unknown_provenance_is_rejected(self):
        with pytest.raises(ValueError, match="unknown provenance"):
            ActionGroup(
                strategy_id="s",
                provenance="made_up",
                actions=(_action(type=ActionType.UNWIND),),
            )

    def test_actions_must_hold_action_objects(self):
        with pytest.raises(TypeError, match="Action objects"):
            ActionGroup(
                strategy_id="s",
                provenance=PROVENANCE_SIGNAL,
                actions=({"type": "UNWIND"},),
            )

    def test_signals_own_neither_id_nor_emission_date(self):
        group = _group((_action(type=ActionType.UNWIND),))
        assert group.action_group_id is None
        assert group.emission_date is None


class TestSchemaOnlyRecords:
    def test_action_group_record_wraps_a_group(self):
        group = _group((_action(type=ActionType.UNWIND),))
        record = ActionGroupRecord(action_group=group, action_ids=("a1",))
        assert record.order_ids == ()
        assert record.order_outcomes == ()
        assert record.group_note is None


class TestActionGroupRecord:
    def _record(self):
        group = _group((_action(type=ActionType.UNWIND),))
        return ActionGroupRecord(action_group=group, action_ids=("a1",))

    def test_action_ids_must_be_parallel_to_actions(self):
        group = _group((_action(type=ActionType.UNWIND),))
        with pytest.raises(ValueError, match="parallel"):
            ActionGroupRecord(action_group=group, action_ids=())

    def test_action_ids_are_read_only(self):
        record = self._record()
        with pytest.raises(AttributeError):
            record.action_ids = ("a2",)

    def test_order_ids_and_outcomes_are_read_only(self):
        record = self._record()
        with pytest.raises(AttributeError):
            record.order_ids = ("o2",)
        with pytest.raises(AttributeError):
            record.order_outcomes = (OrderOutcome.FILLED,)

    def test_finalize_is_write_once(self):
        record = self._record()
        record.finalize(("o1",), (OrderOutcome.FILLED,))
        with pytest.raises(RuntimeError, match="write-once"):
            record.finalize(("o2",), (OrderOutcome.FILLED,))

    def test_requires_at_least_one_order_id(self):
        record = self._record()
        with pytest.raises(ValueError, match="at least one order_id"):
            record.finalize((), ())

    def test_requires_parallel_order_outcomes(self):
        record = self._record()
        with pytest.raises(ValueError, match="parallel to order_ids"):
            record.finalize(
                ("o1",),
                (OrderOutcome.FILLED, OrderOutcome.FILLED),
            )

    def test_requires_order_outcome_values(self):
        record = self._record()
        with pytest.raises(TypeError, match="OrderOutcome"):
            record.finalize(
                ("o1",),
                ("FILLED",),
            )

    def test_group_note_must_be_a_string_or_none(self):
        record = self._record()
        with pytest.raises(TypeError, match="group_note"):
            record.finalize(
                ("o1",),
                (OrderOutcome.FILLED,),
                7,
            )

    def test_failed_validation_leaves_the_record_unfinalized(self):
        record = self._record()
        with pytest.raises(ValueError, match="at least one order_id"):
            record.finalize((), ())
        # The sentinel is set only on success, so a later valid call works.
        record.finalize(("o1",), (OrderOutcome.FILLED,))
        assert record.order_ids == ("o1",)
        assert record.order_outcomes == (OrderOutcome.FILLED,)

    def test_finalize_records_facts_and_allows_blocked_outcome(self):
        record = self._record()
        record.finalize(
            ("o1",),
            (OrderOutcome.BLOCKED,),
            "modelled flat after partial fill",
        )
        assert record.order_ids == ("o1",)
        assert record.order_outcomes == (OrderOutcome.BLOCKED,)
        assert record.group_note == "modelled flat after partial fill"


class TestActionGroupLogAppend:
    def test_append_stamps_id_and_emission_date(self):
        log = ActionGroupLog()
        record = log.append(_unwind_group(), "2024-01-02")
        assert len(record.action_group.action_group_id) == 32
        int(record.action_group.action_group_id, 16)
        assert record.action_group.emission_date == "2024-01-02"
        assert record.order_ids == ()
        assert record.order_outcomes == ()
        assert record.group_note is None
        assert len(record.action_ids) == 1

    def test_append_many_preserves_order(self):
        log = ActionGroupLog()
        records = log.append_many(
            [
                _group(
                    (_action(
                        type=ActionType.NEW,
                        spec=TradeSpec(structures=(_structure(),)),
                    ),)
                ),
                _unwind_group(),
            ],
            "2024-01-02",
        )
        assert [r.action_group.actions[0].type for r in records] == [
            ActionType.NEW,
            ActionType.UNWIND,
        ]
        assert len(log) == 2

    def test_signal_assigned_id_is_rejected(self):
        log = ActionGroupLog()
        stamped = ActionGroup(
            strategy_id="s",
            provenance=PROVENANCE_SIGNAL,
            actions=(_action(type=ActionType.UNWIND),),
            action_group_id="abc",
        )
        with pytest.raises(ValueError, match="assigned by the log"):
            log.append(stamped, "2024-01-02")

    def test_signal_assigned_emission_date_is_rejected(self):
        log = ActionGroupLog()
        stamped = ActionGroup(
            strategy_id="s",
            provenance=PROVENANCE_SIGNAL,
            actions=(_action(type=ActionType.UNWIND),),
            emission_date="2024-01-02",
        )
        with pytest.raises(ValueError, match="assigned by the log"):
            log.append(stamped, "2024-01-03")

    def test_empty_emission_date_is_rejected(self):
        with pytest.raises(ValueError, match="emission_date"):
            ActionGroupLog().append(_unwind_group(), "")


class TestActionGroupLogIndices:
    def _log(self):
        log = ActionGroupLog()
        log.append(_unwind_group(strategy_id="a"), "2024-01-02")
        log.append(
            _unwind_group(strategy_id="a", structure_id="S1", trade_id="T1"),
            "2024-01-02",
        )
        log.append(_unwind_group(strategy_id="b"), "2024-01-03")
        log.append(_unwind_group(strategy_id="a"), "2024-01-04")
        return log

    def test_by_strategy(self):
        log = self._log()
        assert len(log.by_strategy("a")) == 3
        assert len(log.by_strategy("b")) == 1
        assert log.by_strategy("nope") == ()

    def test_by_strategy_last_n_days_keeps_whole_days(self):
        log = self._log()
        assert len(log.by_strategy("a", 1)) == 1
        assert len(log.by_strategy("a", 2)) == 3
        assert len(log.by_strategy("a", 0)) == 0
        assert len(log.by_strategy("a")) == 3

    def test_by_structure(self):
        log = self._log()
        assert len(log.by_structure("S1")) == 1
        assert log.by_structure("S1")[0].action_group.strategy_id == "a"
        assert log.by_structure("S9") == ()

    def test_by_structure_indexes_addressing_actions_only(self):
        log = ActionGroupLog()
        log.append(
            _unwind_group(structure_id="S1", trade_id="T1"), "2024-01-02"
        )
        # A creation group names no structure, so it indexes under none.
        log.append(
            _group(
                (_action(
                    type=ActionType.NEW,
                    spec=TradeSpec(structures=(_structure(),)),
                ),)
            ),
            "2024-01-02",
        )
        assert len(log.by_structure("S1")) == 1
        assert log.by_structure("new") == ()

    def test_by_trade_indexes_trade_level_actions(self):
        log = ActionGroupLog()
        log.append(
            _group(
                (_action(type=ActionType.UNWIND, trade_id="T1"),)
            ),
            "2024-01-02",
        )
        log.append(_unwind_group(), "2024-01-02")  # unwind-all, no trade index
        assert len(log.by_trade("T1")) == 1
        assert log.by_trade("T9") == ()

    def test_per_action_indexing_appears_once_per_bucket(self):
        # A multi-action group referencing the same structure twice indexes
        # the record once (the once-per-bucket clause).
        log = ActionGroupLog()
        record = log.append(
            _group(
                (
                    _action(type=ActionType.UNWIND, trade_id="T1",
                            structure_id="S1"),
                    _action(type=ActionType.UNWIND, trade_id="T1",
                            structure_id="S1"),
                )
            ),
            "2024-01-02",
        )
        assert log.by_structure("S1") == (record,)
        # A group naming two different structures indexes under both.
        log.append(
            _group(
                (
                    _action(type=ActionType.UNWIND, trade_id="T1",
                            structure_id="S2"),
                    _action(type=ActionType.UNWIND, trade_id="T1",
                            structure_id="S3"),
                )
            ),
            "2024-01-02",
        )
        assert len(log.by_structure("S2")) == 1
        assert len(log.by_structure("S3")) == 1

    def test_record_for(self):
        log = self._log()
        record = log.by_strategy("b")[0]
        assert (
            log.record_for(record.action_group.action_group_id) is record
        )
        assert log.record_for("missing") is None

    def test_last_action_group(self):
        log = self._log()
        assert (
            log.last_action_group("a").action_group.emission_date
            == "2024-01-04"
        )
        assert (
            log.last_action_group("b").action_group.emission_date
            == "2024-01-03"
        )
        assert log.last_action_group("nope") is None

    def test_records_are_live_references(self):
        log = self._log()
        record = log.last_action_group("a")
        record.finalize(("o1",), (OrderOutcome.FILLED,))

        assert (
            log.record_for(record.action_group.action_group_id) is record
        )
        assert log.by_strategy("a")[-1] is record
        assert log.records[-1] is record
        assert (
            log.record_for(
                record.action_group.action_group_id
            ).order_ids
            == ("o1",)
        )

    def test_records_are_append_only(self):
        log = self._log()
        before = list(log.records)
        log.append(_unwind_group(strategy_id="a"), "2024-01-05")
        assert list(log.records)[: len(before)] == before

    def test_for_strategy_view_is_scoped(self):
        log = self._log()
        view = log.for_strategy("a")
        assert isinstance(view, ActionGroupLogView)
        assert view.strategy_id == "a"
        assert len(view) == 3
        assert {r.action_group.strategy_id for r in view} == {"a"}
        assert view.last_action_group() is log.last_action_group("a")
        assert len(view.recent(1)) == 1
        assert view.by_structure("S1")[0].action_group.strategy_id == "a"
        assert view.by_structure("S1") == view.records()[1:2]

    def test_for_strategy_view_does_not_expose_other_strategies(self):
        log = self._log()
        assert log.for_strategy("b").by_structure("S1") == ()

    def test_for_strategy_requires_an_id(self):
        with pytest.raises(ValueError):
            ActionGroupLog().for_strategy("")

    def test_view_has_no_append(self):
        view = self._log().for_strategy("a")
        assert not hasattr(view, "append")


class TestAggregationContext:
    def test_holds_the_loop_day_and_its_services(self):
        log = ActionGroupLog()
        books = PositionBooks()
        execution_log = ExecutionLog()
        ctx = AggregationContext(
            date="2024-01-02",
            action_group_log=log,
            execution_log=execution_log,
            position_books=books,
            calendar=None,
            config=None,
        )
        assert ctx.date == "2024-01-02"
        assert ctx.action_group_log is log
        assert ctx.execution_log is execution_log

    def test_is_frozen(self):
        ctx = AggregationContext(
            date="2024-01-02",
            action_group_log=ActionGroupLog(),
            execution_log=None,
            position_books=PositionBooks(),
            calendar=None,
            config=None,
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            ctx.date = "2024-01-03"


class TestPositionBooks:
    def test_for_strategy_returns_the_full_book_identity(self):
        state = _snapshot()
        books = PositionBooks(state, ())
        book = books.for_strategy("whatever")
        assert book is books.for_strategy("another")
        assert book is books.full()
        assert book.portfolio_state is state

    def test_for_strategy_requires_an_id(self):
        with pytest.raises(ValueError):
            PositionBooks().for_strategy("")

    def test_empty_book(self):
        book = PositionBooks().full()
        assert book.trades == ()
        assert book.find_holding("SPY") is None
        assert book.is_in_position("SPY") is False
        assert book.trade_history == ()

    def test_find_holding_reports_address_and_leg(self):
        book = PositionBooks(_snapshot(), ()).full()
        holding = book.find_holding("SPY")
        assert isinstance(holding, Holding)
        assert (holding.trade_id, holding.structure_id) == ("T1", "S1")
        assert holding.leg.size == 100.0
        assert book.is_in_position("SPY") is True
        assert book.find_holding("QQQ") is None

    def test_find_holding_uses_snapshot_order(self):
        first = _snapshot(trade_id="T1", structure_id="S1", ticker="SPY")
        second = _snapshot(trade_id="T2", structure_id="S2", ticker="SPY")
        state = PortfolioState(
            date="2024-01-05", trades=first.trades + second.trades
        )
        book = PositionBooks(state, ()).full()
        assert book.find_holding("SPY").trade_id == "T1"

    def test_structure_to_trade(self):
        book = PositionBooks(_snapshot(), ()).full()
        assert book.structure_to_trade() == {"S1": "T1"}
        assert book.trade_id_for_structure("S1") == "T1"

    def test_one_structure_in_two_active_trades_is_ambiguous(self):
        first = _snapshot(trade_id="T1", structure_id="S1")
        second = _snapshot(trade_id="T2", structure_id="S1")
        state = PortfolioState(
            date="2024-01-05", trades=first.trades + second.trades
        )
        book = PositionBooks(state, ()).full()
        with pytest.raises(ValueError, match="do not map to exactly one"):
            book.trade_id_for_structure("S1")

    def test_unknown_structure_fails_loud(self):
        book = PositionBooks(_snapshot(), ()).full()
        with pytest.raises(ValueError, match="no active trade holds structure"):
            book.trade_id_for_structure("S9")

    def test_trade_history_records_are_wrapped(self):
        record = TradeRecord(
            trade_id="T1",
            entry_date="2024-01-02",
            exit_date=None,
            tags=("a",),
            is_open=True,
        )
        book = PositionBooks(None, (record,)).full()
        assert book.trade_history == (record,)

    def test_book_is_frozen(self):
        book = PositionBooks().full()
        with pytest.raises(dataclasses.FrozenInstanceError):
            book.portfolio_state = None

    def test_position_book_is_constructible_directly(self):
        book = PositionBook()
        assert book.portfolio_state is None
