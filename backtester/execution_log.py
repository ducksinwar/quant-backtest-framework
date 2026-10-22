"""The append-only execution log (Task 5b-1).

One record per **order outcome**; a group-atomic block writes one record per
order in the group.  Unlike the action-group log, whose records are updated in
place as an action group is processed, an execution record is write-once and
terminal: a ``FILLED`` or ``BLOCKED`` outcome is final and is never edited.
``order_id`` may recur across records (to accommodate live partial fills or a
fill followed later by a cancel); ``fill_id`` is unique per record.

**Lineage.**  The record reserves the full
``order <-> action <-> group`` chain end-to-end: ``order_id`` / ``action_id`` /
``order_group_id`` -> ``action_group_id`` -> the ActionGroup's actions'
``trade_id`` / ``structure_id``.  ``probe_status`` records what the order's own
probe decided, and ``blocked_by`` names the reason (``DATA_MISSING`` or
``GROUP_ATOMICITY:<trigger_order_id>``).  Netting lineage hangs off the same
chain.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from backtester.execution import ExecutionOutcome, ExecutionReport
from backtester.orders import OrderOutcome


@dataclass(frozen=True)
class ExecutionRecord:
    """One terminal order outcome (write-once).

    ``status`` is ``"FILLED"`` or ``"BLOCKED"``; ``blocked_code`` is set only
    for the latter.  A filled record carries a ``fill_id``; a blocked one does
    not.  ``internal_transfer`` is reserved for netting/transfers and unused in
    5b-1.
    """

    execution_id: str
    order_id: str
    action_id: str
    order_group_id: str
    action_group_id: str
    strategy_id: str
    date: str
    status: str
    probe_status: OrderOutcome | None = None
    blocked_by: str | None = None
    fill_id: str | None = None
    fill_time: str | None = None
    fees: float | None = None
    blocked_code: str | None = None
    fills: tuple = ()
    internal_transfer: object | None = None


class ExecutionLog:
    """Append-only, write-once log of execution events, indexed two ways."""

    def __init__(self):
        self._records: list[ExecutionRecord] = []
        self._by_fill_id: dict[str, ExecutionRecord] = {}
        self._by_order: dict[str, list[ExecutionRecord]] = {}

    def append(self, report: ExecutionReport) -> ExecutionRecord:
        """Append one report as one write-once record and return it.

        A ``FILLED`` report with no ``fill_id`` gets a minted ``uuid4().hex``;
        a report that already carries one (a live broker confirmation) keeps it.
        A ``BLOCKED`` report must not carry a ``fill_id``.
        """
        if not isinstance(report, ExecutionReport):
            raise TypeError(
                f"ExecutionLog.append expects an ExecutionReport, got "
                f"{type(report).__name__}"
            )

        fill_id = report.fill_id
        if report.outcome is ExecutionOutcome.FILLED:
            if fill_id is None:
                fill_id = uuid.uuid4().hex
            if fill_id in self._by_fill_id:  # pragma: no cover
                raise RuntimeError(
                    f"duplicate fill_id {fill_id!r}: fill ids are unique per "
                    f"record"
                )
        elif fill_id is not None:
            raise ValueError(
                "a blocked execution event must not carry a fill_id"
            )

        record = ExecutionRecord(
            execution_id=uuid.uuid4().hex,
            order_id=report.order_id,
            action_id=report.action_id,
            order_group_id=report.order_group_id,
            action_group_id=report.action_group_id,
            strategy_id=report.strategy_id,
            date=report.date,
            status=report.outcome.value,
            probe_status=report.probe_status,
            blocked_by=report.blocked_by,
            fill_id=fill_id,
            fill_time=report.fill_time,
            fees=report.fees,
            blocked_code=report.blocked_code,
            fills=tuple(report.fills),
            internal_transfer=report.internal_transfer,
        )
        self._records.append(record)
        self._by_order.setdefault(report.order_id, []).append(record)
        if fill_id is not None:
            self._by_fill_id[fill_id] = record
        return record

    def __len__(self) -> int:
        return len(self._records)

    def __iter__(self):
        return iter(self._records)

    @property
    def records(self) -> tuple[ExecutionRecord, ...]:
        """Every record, in append order (immutable snapshots)."""
        return tuple(self._records)

    def record_for_fill(self, fill_id: str) -> ExecutionRecord | None:
        """The record carrying *fill_id*, or ``None``."""
        return self._by_fill_id.get(fill_id)

    def records_for_order(self, order_id: str) -> tuple[ExecutionRecord, ...]:
        """Every record for *order_id*, in append order (may be empty)."""
        return tuple(self._by_order.get(order_id, ()))
