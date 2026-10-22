import dataclasses

import pytest

from backtester.execution import (
    ExecutionOutcome,
    ExecutionReport,
    LegFill,
)
from backtester.execution_log import ExecutionLog, ExecutionRecord
from backtester.orders import OrderOutcome


def _report(**kw):
    base = dict(
        order_id="o1", action_id="a1", order_group_id="g1",
        action_group_id="i1", strategy_id="s", date="2024-01-02",
        outcome=ExecutionOutcome.FILLED, probe_status=OrderOutcome.FILLED,
        fill_time="2024-01-02", fills=(LegFill("SPY", 5.0, 100.0),),
    )
    base.update(kw)
    return ExecutionReport(**base)


class TestExecutionLog:
    def test_append_mints_fill_id_on_fill(self):
        log = ExecutionLog()
        rec = log.append(_report())
        assert rec.fill_id and len(rec.fill_id) == 32
        assert rec.status == "FILLED"
        assert log.record_for_fill(rec.fill_id) is rec

    def test_append_respects_a_supplied_fill_id(self):
        log = ExecutionLog()
        rec = log.append(_report(fill_id="broker-confirm-7"))
        assert rec.fill_id == "broker-confirm-7"
        assert log.record_for_fill("broker-confirm-7") is rec

    def test_blocked_record_has_no_fill_id(self):
        rec = ExecutionLog().append(_report(
            outcome=ExecutionOutcome.BLOCKED, fill_id=None,
            fill_time=None, fills=(), blocked_code="DATA_MISSING",
        ))
        assert rec.fill_id is None
        assert rec.status == "BLOCKED" and rec.blocked_code == "DATA_MISSING"

    def test_blocked_report_with_a_fill_id_is_rejected(self):
        with pytest.raises(ValueError, match="must not carry a fill_id"):
            ExecutionLog().append(_report(
                outcome=ExecutionOutcome.BLOCKED, fill_id="x",
            ))

    def test_append_rejects_non_report(self):
        with pytest.raises(TypeError):
            ExecutionLog().append(object())

    def test_record_is_write_once(self):
        rec = ExecutionLog().append(_report())
        with pytest.raises(dataclasses.FrozenInstanceError):
            rec.status = "BLOCKED"

    def test_one_record_per_event_and_order_may_recur(self):
        log = ExecutionLog()
        a = log.append(_report(fills=(LegFill("SPY", 5.0, 100.0),)))
        b = log.append(_report(fills=(LegFill("SPY", -5.0, 101.0),)))
        assert len(log) == 2 and list(log) == [a, b]
        assert a.execution_id != b.execution_id
        assert a.fill_id != b.fill_id
        assert log.records_for_order("o1") == (a, b)
        assert log.records == (a, b)

    def test_linkage_action_group_order_fill(self):
        log = ExecutionLog()
        rec = log.append(_report(action_group_id="i9", order_id="o9"))
        assert rec.action_group_id == "i9"
        assert rec.order_id == "o9"
        assert rec.fill_id is not None
        assert log.record_for_fill(rec.fill_id).action_group_id == "i9"

    def test_record_fields_are_carried_from_the_report(self):
        rec = ExecutionLog().append(_report(
            strategy_id="strat", action_id="a9", order_group_id="g9",
            fees=None, internal_transfer=None,
        ))
        assert isinstance(rec, ExecutionRecord)
        assert rec.strategy_id == "strat"
        assert rec.action_id == "a9"
        assert rec.order_group_id == "g9"
        assert rec.fees is None
        assert rec.internal_transfer is None

    def test_group_atomicity_fields_are_carried(self):
        rec = ExecutionLog().append(_report(
            outcome=ExecutionOutcome.BLOCKED, fill_time=None, fills=(),
            blocked_code="GROUP_ATOMICITY",
            probe_status=OrderOutcome.FILLED,
            blocked_by="GROUP_ATOMICITY:o2",
        ))
        assert rec.status == "BLOCKED"
        assert rec.probe_status is OrderOutcome.FILLED
        assert rec.blocked_by == "GROUP_ATOMICITY:o2"
        assert rec.blocked_code == "GROUP_ATOMICITY"
