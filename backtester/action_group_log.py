"""The append-only action-group log.

One :class:`ActionGroupLog` per backtest run.  Emission appends a record; the
record's facts are then written exactly once by ``ActionGroupRecord.finalize``
-- nothing is ever removed, and the accessors return the live records so the
facts are visible (see the types-and-ownership block in
:mod:`backtester.actions`).

Four indices make the *global* lookups cheap: by ``action_group_id`` (the
primary index), by ``strategy_id``, by ``structure_id`` and by ``trade_id``.
Each bucket is append-ordered, which is also emission order (the loop emits
once per day, in day order).  Bucket retrieval is O(1); the work after that is
proportional to the answer returned (``by_strategy(last_n_days=k)`` scans
backwards until ``k`` distinct emission dates are collected), and the
strategy-scoped view's ``by_structure`` filters the global structure bucket
linearly -- it has no strategy+structure index of its own.

**Per-action indexing.**  A record is indexed under **every** action's
``structure_id`` / ``trade_id``.  Within a single bucket a record appears
**once**, even if multiple actions reference the same id.  A creation
ActionGroup (no structure, no trade) appears in the log by ``action_group_id``
and ``strategy_id`` only, with no scope index.

"""

from __future__ import annotations

import uuid
from dataclasses import replace

from backtester.actions import (
    ActionGroup,
    ActionGroupRecord,
)


class ActionGroupLog:
    """Append-only record of every emitted ActionGroup, indexed four ways."""

    def __init__(self):
        self._records: list[ActionGroupRecord] = []
        self._by_strategy: dict[str, list[ActionGroupRecord]] = {}
        self._by_structure: dict[str, list[ActionGroupRecord]] = {}
        self._by_trade: dict[str, list[ActionGroupRecord]] = {}
        self._by_action_group_id: dict[str, ActionGroupRecord] = {}

    # --- writing --------------------------------------------------------

    def append(
        self, group: ActionGroup, emission_date: str
    ) -> ActionGroupRecord:
        """Record *group* as emitted on *emission_date* and return its record.

        The log owns the two fields a signal must leave unset: it stamps
        ``action_group_id`` (``uuid4().hex``) and ``emission_date``, and mints
        one ``action_id`` per action.  A signal that set either group field is
        a bug, not a preference, so this raises instead of silently
        overwriting.
        """
        if group.action_group_id is not None:
            raise ValueError(
                f"action_group_id is assigned by the log at emission, not by "
                f"the signal (got {group.action_group_id!r})"
            )
        if group.emission_date is not None:
            raise ValueError(
                f"emission_date is assigned by the log at emission, not by "
                f"the signal (got {group.emission_date!r})"
            )
        if not isinstance(emission_date, str) or not emission_date:
            raise ValueError(
                "emission_date must be a non-empty ISO date string"
            )

        stamped = replace(
            group,
            action_group_id=uuid.uuid4().hex,
            emission_date=emission_date,
        )
        if stamped.action_group_id in self._by_action_group_id:  # pragma: no cover
            raise RuntimeError(
                f"duplicate action_group_id {stamped.action_group_id!r} -- "
                f"uuid4 collision"
            )

        record = ActionGroupRecord(
            action_group=stamped,
            action_ids=tuple(
                uuid.uuid4().hex for _ in stamped.actions
            ),
        )
        self._records.append(record)
        self._by_action_group_id[stamped.action_group_id] = record
        self._by_strategy.setdefault(stamped.strategy_id, []).append(record)
        # Per-action indexing; within a bucket a record appears once even if
        # several actions reference the same id.
        structure_ids = {
            action.structure_id
            for action in stamped.actions
            if action.structure_id is not None
        }
        trade_ids = {
            action.trade_id
            for action in stamped.actions
            if action.trade_id is not None
        }
        for structure_id in structure_ids:
            self._by_structure.setdefault(structure_id, []).append(record)
        for trade_id in trade_ids:
            self._by_trade.setdefault(trade_id, []).append(record)
        return record

    def append_many(
        self, groups, emission_date: str
    ) -> tuple[ActionGroupRecord, ...]:
        """Append a day's patch, preserving its order."""
        return tuple(self.append(group, emission_date) for group in groups)

    # --- reading --------------------------------------------------------

    def __len__(self) -> int:
        return len(self._records)

    def __iter__(self):
        return iter(self._records)

    @property
    def records(self) -> tuple[ActionGroupRecord, ...]:
        """Every record, in emission order (live references, not copies)."""
        return tuple(self._records)

    def record_for(self, action_group_id: str) -> ActionGroupRecord | None:
        """The record for *action_group_id*, or ``None`` if never emitted."""
        return self._by_action_group_id.get(action_group_id)

    def by_strategy(
        self, strategy_id: str, last_n_days: int | None = None
    ) -> tuple[ActionGroupRecord, ...]:
        """Every record of *strategy_id*; optionally only the recent tail.

        ``last_n_days`` keeps the records of the last *n* **distinct emission
        dates** recorded for the strategy (inclusive of the latest), which is
        what a "did I already trade this week" rule wants; ``None`` keeps all.

        Cost is **O(records scanned)**, not O(1): the strategy's bucket is
        walked from the newest record backwards until ``n`` distinct dates have
        been seen (plus one record to detect the boundary).  Fine for the
        handful of recent days a cooldown rule asks for; a rule that wants a
        long window should keep its own state.
        """
        records = self._by_strategy.get(strategy_id, ())
        if last_n_days is None:
            return tuple(records)
        if last_n_days <= 0:
            return ()

        days: list[str] = []
        tail: list[ActionGroupRecord] = []
        for record in reversed(records):
            day = record.action_group.emission_date
            if day not in days:
                if len(days) == last_n_days:
                    break
                days.append(day)
            tail.append(record)
        tail.reverse()
        return tuple(tail)

    def by_structure(self, structure_id: str) -> tuple[ActionGroupRecord, ...]:
        """Every record naming *structure_id* in any action, in emission order."""
        return tuple(self._by_structure.get(structure_id, ()))

    def by_trade(self, trade_id: str) -> tuple[ActionGroupRecord, ...]:
        """Every record naming *trade_id* in any action, in emission order.

        Trade-scoped history for cooldown / scaling rules (e.g. "have I already
        extended this trade this week").  Only actions that carry a trade index
        here; a creation group (no trade, no structure) appears in none.
        """
        return tuple(self._by_trade.get(trade_id, ()))

    def last_action_group(
        self, strategy_id: str
    ) -> ActionGroupRecord | None:
        """The strategy's most recently emitted record, or ``None``."""
        records = self._by_strategy.get(strategy_id)
        return records[-1] if records else None

    def for_strategy(self, strategy_id: str) -> "ActionGroupLogView":
        """A read-only, strategy-scoped view (what signals receive)."""
        if not isinstance(strategy_id, str) or not strategy_id:
            raise ValueError("strategy_id must be a non-empty string")
        return ActionGroupLogView(self, strategy_id)


class ActionGroupLogView:
    """A strategy-scoped read-only window onto the log.

    The view cannot append and cannot see another strategy's records, so a
    signal can consult its own history without being able to rewrite it.
    """

    def __init__(self, log: ActionGroupLog, strategy_id: str):
        self._log = log
        self.strategy_id = strategy_id

    def __len__(self) -> int:
        return len(self._log.by_strategy(self.strategy_id))

    def __iter__(self):
        return iter(self._log.by_strategy(self.strategy_id))

    def records(self) -> tuple[ActionGroupRecord, ...]:
        return self._log.by_strategy(self.strategy_id)

    def recent(self, last_n_days: int) -> tuple[ActionGroupRecord, ...]:
        return self._log.by_strategy(self.strategy_id, last_n_days)

    def last_action_group(self) -> ActionGroupRecord | None:
        return self._log.last_action_group(self.strategy_id)

    def by_structure(self, structure_id: str) -> tuple[ActionGroupRecord, ...]:
        """This strategy's records naming *structure_id*, in emission order.

        A **linear filter** over the global structure bucket: the view has no
        strategy+structure index, so the cost is proportional to every record
        that ever named the structure.  That is the right trade for an audit
        read; add the compound index if a rule ever needs it hot.
        """
        return tuple(
            record
            for record in self._log.by_structure(structure_id)
            if record.action_group.strategy_id == self.strategy_id
        )

    def by_trade(self, trade_id: str) -> tuple[ActionGroupRecord, ...]:
        """This strategy's records naming *trade_id*, in emission order."""
        return tuple(
            record
            for record in self._log.by_trade(trade_id)
            if record.action_group.strategy_id == self.strategy_id
        )
