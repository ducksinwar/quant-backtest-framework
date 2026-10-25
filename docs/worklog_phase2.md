# Phase 2 Work Log

**Start:** 2026‑06‑18 &nbsp;|&nbsp; **End:** — &nbsp;|&nbsp; **Status:** In progress

## Table of Contents

| Step | Date | Topic | Section |
|------|------|-------|---------|
| 1 | 06‑18 | Design notes: CalendarProvider + OrderGenerator + Phase 2 plan | [§ Design notes](#2026-06-18--design-notes-calendarprovider-ordergenerator-phase2-plan) |
| 2 | 07‑25 | Documentation restructuring: archive Phase 1, rename + move docs | [§ Docs restructure](#2026-07-25--documentation-restructuring-archive-phase1-rename--move-docs) |
| 3 | 09‑20 | Task 4: CalendarProvider + remove the `calendar_ticker` surrogate | [§ Task 4](#2026-09-20--task-4-calendarprovider--remove-the-calendar_ticker-surrogate) |
| 4 | 09‑21 | Refactor: CalendarProvider onto the DataFeed/backend contract | [§ Refactor](#2026-09-21--refactor-calendarprovider-onto-the-datafeedbackend-contract) |
| 5 | 09‑26 | Task 5a: Signal intent interface, pass-through synthesis, intent log | [§ Task 5a](#2026-09-26--task-5a-signal-intent-interface-pass-through-synthesis-intent-log) |
| 6 | 09‑29 | Task 5b‑1: execution seam, execution log, cost-writer swap | [§ Task 5b‑1](#2026-09-29--task-5b1-execution-seam-execution-log-cost-writer-swap) |
| 7 | 10‑04 | Task 5b‑2: CalendarValidationRule, check chain, Contract calendar fields, doc-sync | [§ Task 5b‑2](#2026-10-04--task-5b2-calendarvalidationrule-check-chain-contract-calendar-fields-doc-sync) |
| 8 | 10‑06 | Intent identity/scope re-work: trade-level NEW, three UNWIND scopes, netting-agnostic dispositions | [§ Intent re-work](#2026-10-06--intent-identityscope-re-work) |
| 9 | 10‑14 | Single-action subset: schema restructure + rename (`ActionGroup`) + doc lock | [§ Single-action subset](#2026-10-14--single-action-subset-schema-restructure--rename--doc-lock) |
| 10 | 10‑17 | Structure-scoped ops: `trade_id` required, resolver path removed | [§ Required trade_id](#2026-10-17--structure-scoped-ops-trade_id-required-resolver-path-removed) |
| 11 | 10‑19 | Action-layer disposition taxonomy: `DISPATCHED` / `REJECTED` / `REPLACED`, per-action facts, prose migration | [§ Disposition taxonomy](#2026-10-19--action-layer-disposition-taxonomy) |
| 12 | 10‑21 | Phase A: unwired order layer (`Order` / `OrderLeg` / `OrderSide`) | [§ Phase A](#2026-10-21--phase-a-unwired-order-layer) |
| 13 | 10‑22 | Phase B: wire `Order` through conversion, execution and book commit | [§ Phase B](#2026-10-22--phase-b-wire-order-through-conversion-execution-and-book-commit) |
| 14 | 10‑22 | Phase C: SMA T‑1 fractional sizing, `is_tradable`, remove check rules + disposition taxonomy | [§ Phase C](#2026-10-22--phase-c-sma-t1-fractional-sizing-is_tradable-remove-check-rules--disposition-taxonomy) |
---

## 2026-06-18 – Design notes: CalendarProvider, OrderGenerator, Phase 2 plan

### Prompt
We need to update design_notes.md to capture the Phase 2 architecture, specifically the
separation of the OrderGenerator from the Signal and the introduction of the CalendarProvider
and its first rule (CalendarValidationRule).

### Changes applied to design_notes.md
**8‑point update across ToC, §3.5–§3.15, §5, §8.4, and all cross‑references:**

1. **ToC** — Added §3.5 CalendarProvider and §3.8 OrderGenerator; renumbered all downstream sections by +2 (final range: 3.5–3.15).

2. **New §3.5 CalendarProvider** — Describes a shared service for trading‑day calendars. Covers:
   - Holiday calendar model (Bloomberg‑style codes, multi‑code per instrument).
   - Default calendar (business days if no codes; `"all"` for every calendar day).
   - Multi‑asset handling: union (simulation loop) vs. intersection (order execution).
   - Core methods: `trading_days`, `is_trading_day`, `next_trading_day`.
   - Signal data scoping via the OrderGenerator.
   - Phase 2 implementation: CSV holiday files first; PIT holidays deferred.
   - Phase 1 status: not yet implemented; `calendar_ticker` is a temporary surrogate.

3. **New §3.8 OrderGenerator** — Stateless component between alpha signal and backtester. Covers:
   - Alpha intent format (e.g. `{"action": "BUY", "ticker": "SPY", "target_size": 200}`).
   - Rule‑chain pattern — initialized with a list of `OrderRule` instances, runs each in sequence.
   - CalendarValidationRule as the first concrete rule: checks each leg's holiday codes; rejects entire order if any leg is on holiday (no partial trade, no postponing).
   - Future rules: ScalingRule, DeltaHedgeRule, RollRule, TradingSchedule.
   - TradingSchedule: adjusts fixed‑frequency schedules via CalendarProvider, stateless.

4. **Signal §3.7 — updated "Separation of alpha and execution" paragraph:**
   - Documents Phase 1 behaviour (signals produce TargetTrade dicts directly).
   - Documents Phase 2 plan (signals produce pure intent dicts; OrderGenerator handles mechanics).
   - Existing helper modules (ScalingModule etc.) will migrate into OrderRules.

5. **Backtester §3.9 — added Phase 2 pipeline note:**
   - In the daily loop's "Request and execute today's orders" step, added a note that Phase 2 will call signal for alpha intents, then pass them through the OrderGenerator to obtain TargetTrade orders.

6. **Section renumbering — all headings and cross‑references updated:**
   - Old 3.5 → 3.6, 3.6 → 3.7, 3.7 → 3.9, 3.8 → 3.10, 3.9 → 3.11, 3.10 → 3.12, 3.11 → 3.13, 3.12 → 3.14, 3.13 → 3.15.
   - All 14 cross‑references in the document updated to new numbers.

7. **§5 Phase 2 implementation plan — rewritten:**
   - Tasks 1‑3 added: CalendarProvider implementation, OrderGenerator + CalendarValidationRule, backtester pipeline update.
   - Original Phase 2 tasks (FoldGenerator, nested param selection, Summary aggregation) renumbered to 4‑6.

8. **§8.4 Phase 2 description — added calendar system bullet:**
   - Introduce CalendarProvider (§3.5), replace temporary `calendar_ticker`, load from CSV initially, PIT holidays deferred to SQL pipeline.

### Agent output summary
File modified:
- design_notes.md — 148 lines changed (+107, -41). Inserted 2 new sections (§3.5, §3.8), renumbered 9 section headings, updated all cross‑references, expanded §5 and §8.4.

New file:
- work_log_phase2.md — created with Phase 2 work log header and first entry.

Files unchanged:
- All backtester source files (no code changes — design notes only).

Final section numbering:
```
3.5 CalendarProvider → 3.6 Pricer → 3.7 Signal → 3.8 OrderGenerator
→ 3.9 Backtester → 3.10 Summary → 3.11 Data Extractor
→ 3.12 PnL Attribution → 3.13 Cost Model → 3.14 Persistence
→ 3.15 Architecture summary
```

### Manual changes
- None

### Suggested commit message
```
docs: add CalendarProvider and OrderGenerator to Phase 2 design

- Insert §3.5 CalendarProvider with holiday calendar model, union/intersection
  logic, core methods (trading_days, is_trading_day, next_trading_day)
- Insert §3.8 OrderGenerator with swappable OrderRule chain; first concrete
  rule being CalendarValidationRule
- Update Signal §3.7 to document Phase 2 separation of alpha intents from
  mechanical execution
- Update Backtester §3.9 with note about signal→OrderGenerator→execution
  pipeline for Phase 2
- Renumber all §3.x sections: CalendarProvider → 3.5, OrderGenerator → 3.8,
  all downstream sections shifted by +2
- Update all cross-references to match new section numbering
- Add CalendarProvider + OrderGenerator tasks to Phase 2 implementation plan
- Add calendar system bullet to §8.4 Phase 2 description
- Create work_log_phase2.md; archive old work_log.md (Phase 1 complete)
```

## 2026-07-25 – Documentation restructuring: archive Phase 1, rename + move docs

### Prompt
Documentation housekeeping for Phase 1 completion and Phase 2 start. Move and rename
Phase 1/Phase 2 documentation files into a standard `docs/` directory, with Phase 1
materials archived under `docs/archive/`.

### Changes applied

- **Created `docs/archive/`** directory.
- **`work_log_phase1.md`** → **`docs/archive/worklog_phase1.md`** — archived Phase 1 work log.
- **`PHASE2_PLAN.md`** → **`docs/phase2_plan.md`** — renamed to lowercase with underscores, moved into `docs/`.
- **`work_log_phase2.md`** → **`docs/worklog_phase2.md`** — moved into `docs/`.
- **`docs/worklog_phase2.md`** — appended this entry describing the restructuring.

### Manual changes
- None

### Suggested commit message
```
docs: archive Phase 1 worklog, move Phase 2 docs into docs/
```

## 2026-07-27 – Task 1: Summary refactoring – pluggable MetricCalculator & BaseReport registries

### Prompt
Implement Task 1 of Phase 2: refactor the Summary module to use pluggable
MetricCalculator and BaseReport registries, following the same pattern as the
CostModel. The Summary becomes a thin data coordinator that exposes public
cached-series helpers; all report-building and metric-computation logic moves
out of Summary into registry-backed classes.

### Changes applied

- **Created `backtester/metrics_registry.py`** – `BaseMetricCalculator` ABC with
  `compute()` method; 8 concrete calculator classes (Return, ReturnPct, Sharpe,
  MaxDrawdown, MaxDrawdownPct, AnnualizedReturn, Calmar, HitRatio); module-level
  `METRIC_CALCULATORS` dict; `CAPITAL_DEPENDENT_METRICS` set; shared
  `_compute_metrics_row` helper used by both MetricsReport and
  PeriodicMetricsReport.

- **Created `backtester/reports/` package** (8 files):
  - `_base.py` – `BaseReport` ABC with `build()` signature accepting (summary,
    trades, leg_data, report_config, fx_rates, output_name).
  - `equity_curve.py` – `EquityCurveReport`
  - `trade_summary.py` – `TradeSummaryReport`
  - `metrics.py` – `MetricsReport` (uses metric registry + `_compute_metrics_row`)
  - `periodic_metrics.py` – `PeriodicMetricsReport` (per-period metric rows +
    total row via `_compute_metrics_row`)
  - `hit_ratio.py` – `HitRatioReport`
  - `drawdown_table.py` – `DrawdownTableReport` (includes private static
    `_compute_drawdown_table_from_cum`, moved from Summary)
  - `by_underlying.py` – `ByUnderlyingReport` (uses REPORTS registry directly
    for sub-reports)

- **`__init__.py`** re-exports `BaseReport` and the `REPORTS` dict mapping report
  name strings to concrete report classes.

- **Deleted `backtester/metrics_calculators.py`** – all old pure functions
  superseded by the calculator registry.

- **`backtester/summary.py`** – removed all 7 `_build_*` methods and
  `_compute_drawdown_table_from_cum`; promoted `_get_daily_series`,
  `_get_cumulative_series`, `_get_trade_totals` to public (dropped leading
  underscore); rewrote `_build_report` to dispatch via REPORTS registry; made
  `_normalize_config` a `@staticmethod`; added `capital` property (set from
  `self._capital` in `generate()`); initialised `_capital = None` in
  `__init__`.

- **`tests/test_summary.py`** – added `TestSummaryRegistryExtensibility` class
  verifying that registering a dummy calculator + dummy report and calling
  `generate()` produces the expected output. Test restores original registries
  after running.

### Backward compatibility
All 128 pre-existing tests pass without modification. 146 total tests pass
(128 + 18 summary including the new registry-extensibility test).

### Manual changes
- None

### Suggested commit message
```
refactor: pluggable MetricCalculator and BaseReport registries for Summary

- Add BaseMetricCalculator ABC + 8 concrete calculators in
  backtester/metrics_registry.py with module-level METRIC_CALCULATORS
  registry and CAPITAL_DEPENDENT_METRICS set
- Add BaseReport ABC + 7 concrete report classes in backtester/reports/
  package with module-level REPORTS registry
- Remove backtester/metrics_calculators.py (pure functions superseded)
- Refactor backtester/summary.py: remove all _build_* methods, promote
  getters to public, dispatch via REPORTS registry, add capital property
- Move _compute_drawdown_table_from_cum to DrawdownTableReport
- Add registry-extensibility test in tests/test_summary.py
- All 146 tests pass (128 existing + 18 summary)
```

## 2026-07-27 – PeriodicMetrics hit‑ratio exclusion + documentation sync

### Prompt
Finalise Task 1 of Phase 2: apply the hit‑ratio exclusion fix in PeriodicMetricsReport
and update design_notes.md and README.md to reflect the completed refactoring.

### Changes applied

- **`backtester/reports/periodic_metrics.py`** – Added module‑level `_EXCLUDED_METRICS =
  {"hit_ratio"}`; compute an `_eligible` tuple from `METRIC_CALCULATORS` excluding
  hit_ratio. Used `_eligible` everywhere periodic_metrics iterates the metric registry
  (want/needs detection, label_include construction). When `include` is `None`,
  `label_include` is now set to `list(_eligible)` instead of `None`, preventing
  `_compute_metrics_row` from falling back to the full registry (which would reintroduce
  hit_ratio).
  Result: hit_ratio columns no longer appear in any `periodic_metrics` output sheet.

- **`design_notes.md`** — Three updates:
  1. §2 project structure tree: replaced `summary.py (standard reports)` with
     `(thin data coordinator)`; added `metrics_registry.py` and the `reports/` directory
     with all its files (`_base.py`, `equity_curve.py`, etc.).
  2. §3.10 metrics row: renamed percentage column names to the new convention
     (`return_pct_gross`, `return_pct_net`, `max_drawdown_pct_gross`,
     `max_drawdown_pct_net`).
  3. §3.10 Internal architecture: replaced the future‑tense Phase 2 plan paragraph with
     a present‑tense description of the current `BaseMetricCalculator` registry,
     `BaseReport` registry, and the `Summary`'s role as a thin data coordinator.

- **`README.md`** — Two updates:
  1. Project Structure tree: removed `metrics_calculators.py`, added
     `metrics_registry.py` and the `reports/` directory with all files, updated
     `summary.py` description from "Performance reports" to "Thin data coordinator".
  2. Architecture summary paragraph: updated the CostModel/Summary sentence to describe
     the pluggable `BaseReport` registry and reusable `BaseMetricCalculator` classes.

### Manual changes
- Update Calmar calculator to first check if mdd is in context before computing mdd
- In `PeriodicMetricsReport.build()`, after building `cum_period` from the full
  cumulative series, added `cum_period = cum_period - cum_period.iloc[0]` to rebase
  the period's cumulative P&L to zero. This prevents future metrics that rely on the
  absolute cumulative level from inadvertently including pre-period P&L. Existing
  drawdown metrics are mathematically unchanged. All tests pass.

### Suggested commit message
```
fix: exclude hit_ratio from periodic_metrics; sync docs with refactoring

- periodic_metrics.py: add _EXCLUDED_METRICS and _eligible tuple to ensure
  hit_ratio is never computed in periodic_metrics output regardless of
  `include` setting
- design_notes.md: update §2 file tree, §3.10 percentage column names
  (return_pct_gross etc.), and §3.10 internal architecture paragraph
- README.md: update project structure tree and architecture summary
- All 146 tests pass; output comparison confirms hit_ratio absent from
  periodic_metrics sheets
```

## 2026-07-28 – DrawdownTable report: rename columns + add trough value

### Prompt
Clean up the drawdown table report to eliminate confusing naming and add the
missing cumulative trough value. No mathematical logic changes — only rename
variables, rename columns, and add one new column.

### Changes applied

- **`backtester/reports/drawdown_table.py`** — `_compute_drawdown_table_from_cum`:
  - Renamed local variable `trough` → `drawdown_val` (both branches of the
    underwater-period state machine).
  - Renamed dictionary key `"depth"` → `"drawdown"` in both period dicts.
  - Added new dictionary key `"trough" = peak_val + drawdown_val` (the actual
    cumulative P&L value at the trough date, computed from the negative
    drawdown_val offset).
  - Updated sort key from `x["depth"]` → `x["drawdown"]`.
  
- **`backtester/reports/drawdown_table.py`** — `build`:
  - Column `"depth_pct"` → `"drawdown_pct"` (still computed from the drawdown
    value, still negative).
  - Added `_reorder_columns()` helper to enforce a logical column order:
    `start, end, trough_date, peak, trough, drawdown, underwater_days`
    (with `drawdown_pct` after `drawdown` when capital is present).

### Test impact
No test changes needed — the only drawdown_table test checks for key presence
(`"drawdown_table_gross"`, `"drawdown_table_net"`) and does not inspect column
names. All 146 tests pass.

### Manual changes
- Worklog entry appended.

### Suggested commit message
```
refactor: rename drawdown table columns and add cumulative trough

- Rename depth->drawdown, depth_pct->drawdown_pct in DrawdownTableReport
- Add trough column (cumulative P&L at trough date)
- Rename internal variable trough->drawdown_val for clarity
- Add _reorder_columns helper for logical column ordering
- All 146 tests pass (no test changes required)
```

---

## 2026-07-28 – Docs: fix stale column name in design notes

### Prompt
Task 1 final validation found a stale column name in design_notes.md:
`depth_pct` → `drawdown_pct` to match the refactored drawdown table.

### Change
- `design_notes.md` §3.10, line 888: `depth_pct` → `drawdown_pct`.

### Test impact
None — docs-only change. All 146 tests pass.

### Suggested commit message
```
docs: fix stale depth_pct -> drawdown_pct in design notes §3.10
```

---

## 2026-07-28 – Task 2: Contract / LegState split + remove cost_leg_id

### Prompt
Split the monolithic `Instrument` class into an immutable `Contract`
and a mutable `LegState`, update all consumers, remove the legacy
`cost_leg_id` field from the event log, and clean up the dead
`cost_leg_ids` field from `StrategyStructure`.

### Changes applied

- **Deleted** `backtester/instruments/instrument.py` and
  `backtester/instruments/__init__.py`.
- **Created** `backtester/instruments.py` with `Contract` (frozen
  dataclass) and `LegState` (mutable dataclass) including a new
  `pricing_inputs_history` time‑series field.
- **`BasePricer`** gains `_INFRA_KEYS` and `_build_contract()`;
  all abstract method signatures accept `Contract`.
- **`EquityPricer`** updated to use `contract.ticker`; `compute_cost_exposure`
  now fetches the market price from its provider, not from position state.
- **`Backtester`** updated end‑to‑end: `_compute_pnl_for_date`,
  `_compute_risk_for_date`, `_check_data_available`, `_build_portfolio_state`,
  `_compute_cost_exposures`, `_build_structure_from_info`, and
  `_resolve_and_price_leg` all use `LegState`/`Contract`.  The
  `_record_pricing_inputs_nan` method and `_collect_cost_leg_ids` are
  deleted.  `_INFRA_KEYS` is removed from the backtester.
- **`_compute_pnl_for_date`** now uses `leg_state.pricing_inputs_history`:
  on valid days, appends each key's value from the snapshot and `NaN`
  for already‑known keys absent from the snapshot; on `None`‑price days,
  appends `NaN` for all known keys.
- **`StrategyStructure`** no longer records `cost_leg_id` in event log
  entries.  The `_cost_leg_id_from_exposures` helper and the
  `cost_leg_ids` field/parameter are removed.
- **`Snapshots.LegSnapshot`**: `instrument_type` → `asset_class`.
- **`Summary._extract_leg_data`**: reads explicit fields from
  `LegState` and `contract`; valuation‑data and pricing‑input‑history
  time series are built as `pd.Series` aligned to the P&L index.
  `multiplier`, `tags`, and `params` are now explicit top‑level keys
  in the leg‑data dict.
- **`CostModel`**: `leg.asset_class` → `leg.contract.asset_class`.
- **All 8 test files** updated to import `Contract`/`LegState`,
  construct them correctly, and remove `cost_leg_ids` arguments.
  New test added: `test_compute_cost_exposure_fetches_from_provider_not_state`.
- **`design_notes.md`** and **`README.md`** updated.

### Key design notes
- `size` is now correctly excluded from `Contract.params` (never leaked).
- `roll()` is stubbed (raises `NotImplementedError`); no event dict to update.
- `_on_order` and `_add_leg_to_structure` do not exist in the current codebase.
- Single‑leg cost‑exposure fallback in `_compute_cost_exposures` preserved
  with a comment explaining the default behavior.
- `_check_data_available` now builds a lightweight `Contract` via
  `resolve_instrument` (minor behavioral change, no impact).
- All 150 tests pass on the first run (only 2 snapshots/assertion fixes
  needed — `LegSnapshot` vs `LegState` attribute access, and
  `pricing_inputs_history` being empty when the pricer returns no inputs).
- **Breaking change** for any serialized Phase 1 `trade_history` — old
  `cost_leg_id` keys may remain in event dicts but are ignored by the
  `CostModel`.
- **Forward note**: future task will decompose `asset_class` into
  broad `asset_class` + `instrument_type`.

### Manual changes
- None

### Suggested commit message
```
refactor: split Instrument into Contract + LegState; remove cost_leg_id

- Introduce frozen Contract dataclass and mutable LegState dataclass
  in backtester/instruments.py, replacing the monolithic Instrument
- Pricers accept Contract (never LegState); compute_cost_exposure
  fetches market price from provider, not position state
- _INFRA_KEYS moves from Backtester to BasePricer._build_contract()
- Remove cost_leg_id from event log entries in StrategyStructure;
  delete _cost_leg_id_from_exposures helper
- Remove dead cost_leg_ids field/param from StrategyStructure; delete
  _collect_cost_leg_ids from Backtester
- Replace dynamic setattr (_pricing_input_keys) with proper
  pricing_inputs_history dict on LegState; _compute_pnl_for_date
  appends NaN for missing keys to keep series aligned
- snapshots.LegSnapshot: instrument_type -> asset_class
- Summary: valuation_data and pricing_inputs_history time series built
  as pd.Series in leg-data dicts; multiplier/tags/params are explicit
  top-level keys
- Add test for compute_cost_exposure fetching from provider not state
- Update all 8 test files, design_notes.md §3.1 (rewritten), and README.md
- All 150 tests pass
```

---

## 2026-07-29 -- Phase 2C Risk Bridge design: RiskPosition spec

### Prompt
Update the Phase 2C placeholder in phase2_plan.md with a detailed design
description for the Risk Bridge, capturing the `RiskPosition` dataclass and
its role as the single interface between the backtester, live system, and
risk engine.

### Changes applied

- **`docs/phase2_plan.md`** — Phase 2C section replaced old placeholder
  bullet points with six detailed bullets describing:
  - `RiskPosition` dataclass fields (instrument identity, net size,
    current price, per‑unit greeks).
  - Backtester produces a daily time series by netting `LegState` per
    ticker (equity scope); netting key expands to contract‑specific
    parameters (strike, expiry) when options/futures are added.
  - Live position system produces the same `RiskPosition` objects from
    its blotter, giving the risk engine a single unified interface.
  - The risk engine never imports `LegState` or backtester internals —
    it depends only on `RiskPosition`.
  - Gross trade/leg detail is excluded from `RiskPosition` (the event
    log and trade history already cover margin/funding/settlement).
  - Backtester and live system remain independent pillars aligned on
    risk analytics.

### Manual changes
- Appended this worklog entry.

### Suggested commit message
```
docs: flesh out Phase 2C Risk Bridge design with RiskPosition spec
```

---

## 2026-07-29 -- Move `tags` from `Contract` to `LegState`

### Prompt
Tags are operational labels assigned by the strategy, not instrument identity.
Move `tags` from the immutable `Contract` to the mutable `LegState`.

### Changes applied

- **`backtester/instruments.py`** -- Removed `tags: list[str] | None = None`
  from `Contract`; added `tags: list[str] | None = None` to `LegState` with
  a docstring noting that tags are optional operational labels, not part of
  instrument identity.
- **`backtester/pricers/base_pricer.py`** -- Removed `tags=resolved.get("tags")`
  from `_build_contract`.  `"tags"` remains in `_INFRA_KEYS` so the key is
  still excluded from `Contract.params`.
- **`backtester/backtest_engine.py`** -- `_resolve_and_price_leg` now passes
  `tags=leg_dict.get("tags")` when constructing `LegState`.
- **`backtester/summary.py`** -- `_extract_leg_data` reads
  `leg_state.tags` instead of `leg_state.contract.tags`.
- **`tests/test_instrument.py`** -- Removed `tags` assertions from
  `TestContract` (`test_default_values`, `test_custom_values`,
  `test_none_tags_allowed` deleted).  Added `assert ls.tags is None` to
  `TestLegState.test_requires_contract`, `tags=["alpha", "momentum"]` to
  `test_custom_values`, and a new `test_tags_default_none`.
- **`design_notes.md` S3.1** -- Removed `tags` from the `Contract` field
  list; added `tags` to the `LegState` field list with description.

### Test impact
All 150 tests pass.  No test file constructs `Contract` with `tags=...`
outside of `test_instrument.py` (which is updated).

### Manual changes
- None

### Suggested commit message
```
refactor: move tags from Contract to LegState

Tags are operational labels assigned by the strategy (e.g. strategy name,
asset sub-class), not part of instrument identity.  Move them from the
immutable Contract to the mutable LegState.

- Remove tags field from frozen Contract dataclass
- Add tags field to mutable LegState dataclass with docstring
- Remove tags arg from BasePricer._build_contract() (keep in _INFRA_KEYS)
- Read leg_dict tags in Backtester._resolve_and_price_leg() for LegState
- Read leg_state.tags in Summary._extract_leg_data()
- Add tags tests to TestLegState; remove tags assertions from TestContract
- Update design_notes.md S3.1 field lists
- All 150 tests pass
```

---

## 2026-07-29 -- Clean up pricing‑input fields on LegState

### Prompt
Remove the redundant `pricing_inputs: dict[str, float]` snapshot field from
`LegState`, rename `pricing_inputs_history` to `pricing_inputs`, and use a
local `today` variable in the backtester for the day's values.  Pure cleanup,
no behaviour changes.

### Changes applied

- **`backtester/instruments.py`** — Removed `pricing_inputs: dict[str, float]`
  field; renamed `pricing_inputs_history: dict[str, list[float]]` to
  `pricing_inputs: dict[str, list[float]]`.
- **`backtester/backtest_engine.py`** — In `_compute_pnl_for_date`:
  - Replaced `leg_state.pricing_inputs` snapshot with local `today` variable.
  - On valid days, appends values from `today` to `leg_state.pricing_inputs`
    and appends `NaN` for known keys absent from `today`.
  - On missing days, simplified to a single loop over `leg_state.pricing_inputs`
    appending `NaN` (removed snapshot clearing step).
  - All `pricing_inputs_history` references → `pricing_inputs`.
- **`backtester/summary.py`** — `pricing_inputs_history.items()` →
  `pricing_inputs.items()`.
- **`tests/test_instrument.py`** — Removed `pricing_inputs_history` assertion
  from `test_requires_contract`; updated `test_pricing_inputs_default_factory_isolates_instances`
  to pass `{"iv": [22.0]}` (a list); renamed `test_pricing_inputs_history_default_factory_isolates_instances`
  → `test_pricing_inputs_setdefault_isolates_instances` and `test_pricing_inputs_history_append`
  → `test_pricing_inputs_append`; all field references updated.
- **`tests/test_backtester.py`** — Replaced `pricing_inputs_history` with
  `pricing_inputs` in both `TestBacktesterRecordPricingInputs` tests; removed
  redundant `isinstance` assertions on the old history field.

### Manual changes
- Remove unused import in backtest_engine

### Suggested commit message
```
refactor: remove pricing_inputs snapshot; rename history to pricing_inputs

- Remove dead pricing_inputs: dict[str, float] snapshot field from LegState
- Rename pricing_inputs_history -> pricing_inputs: dict[str, list[float]]
- Use local today variable in _compute_pnl_for_date instead of snapshot
- Simplify missing-day branch to single loop (no snapshot to clear)
- Update Summary to read leg_state.pricing_inputs directly
- Rename/update 4 tests in test_instrument.py, 2 tests in test_backtester.py
- All 150 tests pass
```

---

## 2026-07-29 -- Fix partial/missing data recording in backtest engine

### Prompt
Fix two related problems in `_compute_pnl_for_date` and `_compute_risk_for_date`
where partial or missing pricing/valuation data is not recorded faithfully,
causing series misalignment and loss of diagnostic information.

### Changes applied

- **`backtester/backtest_engine.py` — `_compute_pnl_for_date`**:
  - Replaced `continue`-based early exit with `if/else` so pricing-input
    recording runs unconditionally regardless of price availability.
  - The missing-price branch now only appends `NaN` to `daily_total_pnl`;
    the `else` branch handles P&L computation and `current_price` update.
  - After the `if/else` block, a single unconditional block calls
    `pricer.pricing_inputs()` every day, appends returned values, and
    backfills `NaN` for any already-known key missing from today's snapshot.
    This preserves partial pricing inputs (e.g. spot + rate valid, IV missing)
    instead of blindly padding all known keys with `NaN`.

- **`backtester/backtest_engine.py` — `_compute_risk_for_date`**:
  - Replaced the `if vd is not None:` guard with the same three-step pattern:
    call `valuation_data()`, append present values, backfill `NaN` for
    missing keys.  This ensures valuation-data time series stay aligned with
    `daily_total_pnl` even when the pricer returns `None`.

Both changes follow the same call → append → backfill pattern to keep all
per-leg time series length-aligned.

### Test impact
All 150 tests pass without modification.

### Manual changes
- None

### Suggested commit message
```
fix: record pricing inputs and valuation data faithfully on partial/missing data

- Hoist pricing-input recording out of price-available branch so it runs
  unconditionally every day; preserve partial data when pricer returns
  some but not all inputs
- Replace valuation_data None guard with call → append → NaN-backfill
  pattern to keep valuation series aligned with daily_total_pnl
- All 150 tests pass
```

---

## 2026-07-29 -- Flatten project structure: remove empty subdirectories

### Prompt
Housekeeping: move single-file subdirectories into flat files to avoid
misleading directory structure. `strategy_structure.py` and `trade.py` were the
only files in `structures/` and `trades/` respectively.

### Changes applied

- **Moved** `backtester/structures/strategy_structure.py` → `backtester/strategy_structure.py`
- **Moved** `backtester/trades/trade.py` → `backtester/trade.py`
- **Deleted** empty `backtester/structures/` and `backtester/trades/` directories
  (including `__init__.py` and `__pycache__/`)
- **Updated imports** in 6 files:
  - `backtester/backtest_engine.py`
  - `tests/test_backtester.py`
  - `tests/test_strategy_structure.py`
  - `tests/test_trade.py`
  - `tests/test_cost_model.py`
  - `tests/test_summary.py`
- **Updated** `design_notes.md` §2 project structure tree
- **Updated** `README.md` project structure tree
- All 150 tests pass

### Suggested commit message
```
refactor: flatten structures/ and trades/ into backtester/ root

Move strategy_structure.py and trade.py up one level since they were
the only files in their respective otherwise-empty directories.
Update all imports and documentation to match.
```

---

## 2026-07-29 -- Post‑Task 2 code-review fixes

### Prompt
Apply eight fixes identified in the Task 2 code review: remove two unused
imports, correct four documentation inaccuracies in design_notes.md, fix
retroactive NaN-padding for newly-appearing keys in pricing_inputs and
valuation_data, and add a test for pricing-inputs subset-key NaN-padding.

### Changes applied

- **`tests/test_pricers.py`** (M‑1) — Removed unused `LegState` import.
- **`tests/test_backtester.py`** (m‑2, m‑5) — Removed unused `LegState` import.
  Added `TestBacktesterPricingInputsNanPadding` class verifying that keys
  absent from a day's `pricing_inputs` snapshot receive `NaN`, present keys
  are recorded normally, and new-mid-backtest keys are backfilled with `NaN`
  for all prior days.
- **`backtester/backtest_engine.py`** — Retroactive-padding fix: when a key
  appears for the first time in `pricing_inputs` or `valuation_data`, backfill
  `NaN` for all prior days (using `max(0, len(daily_total_pnl) - 1)`) before
  appending today's value.  Applied to both `_compute_pnl_for_date` and
  `_compute_risk_for_date`.
- **`design_notes.md`** — Six corrections:
  - §3.1: replaced stale `pricing_inputs_history` with `pricing_inputs` in
    the LegState intro sentence.
  - §3.1 (M‑3): corrected the `LegState` field listing — removed `ticker`,
    `asset_class`, `multiplier`, `currency`, `params` (now on `Contract`);
    listed actual `LegState` fields (`contract`, `current_price`, etc.).
  - §3.9 (M‑2): replaced inaccurate pricing-inputs description with the
    actual behaviour (call unconditionally, append returned values,
    NaN-backfill missing keys; backfill prior days when key first appears).
  - §3.2, §3.9, §3.12, §3.15 (M‑4): replaced stale `Instrument` references
    with `LegState`/`Contract`.
  - §3.13 (M‑6): removed the `"cost_leg_id"` line from the `compute_cost`
    event-dict description.
  - §3.15: updated architecture tree to show `LegState`/`Contract` instead
    of `Instrument`.

### Test impact
All 130 tests pass (128 existing + 1 new NaN-padding test + 1 from prior
work).  The new test uses a `GappyInputsPricer` that returns `{"spot": ...}`
on some days and `{}` on others, verifying that `NaN` is correctly appended
for missing keys and that a mid-backtest `"rate"` key is backfilled with
`NaN` for prior days.

### Suggested commit message
```
fix: post-Task 2 review — unused imports, doc corrections, NaN-padding

- Remove unused LegState import from tests/test_pricers.py and
  tests/test_backtester.py
- Fix design_notes.md §3.1 LegState field listing, §3.9 pricing-inputs
  description, §3.2/§3.9/§3.12/§3.15 Instrument→LegState references,
  §3.13 cost_leg_id removal, and stale pricing_inputs_history name
- Add retroactive NaN-padding in backtest_engine.py for keys that first
  appear mid-backtest in pricing_inputs and valuation_data
- Add TestBacktesterPricingInputsNanPadding verifying subset-key
  NaN-padding and mid-run key backfilling
- All 130 tests pass
```

---

## 2026-07-31 -- Document correctness fixes for pre-Task 3

### Prompt
Finalise a set of correctness fixes to be applied before Task 3 (FX conversion)
by recording them in the project documentation. Documentation only — no code
changes. Pending behaviour in design_notes.md is marked "(planned — see
`docs/phase2_plan.md`)".

### Changes applied

- **`docs/phase2_plan.md`** — Added a new sub-section "Correctness fixes
  (pre-Task 3)" under Phase 2A, immediately before Task 3, with five
  checkboxes:
  - Multi-leg cost overcount: add `leg_size_changes` to event log and use
    per-leg delta in cost calculator.
  - Opening-day P&L / pricing-input alignment: record 0.0 P&L and pricing
    inputs at trade creation; remove Summary prepend-zero.
  - None inside compute_cost_exposure: return None from pricer when price is
    missing.
  - Float-equality unwind fraction: add range guard and tolerance check for
    full close.
  - pytest.raises(FrozenInstanceError) in frozen-snapshot test.

- **`design_notes.md`** — Updated six sections to reflect the upcoming fixes
  (pending behaviour marked "(planned — see `docs/phase2_plan.md`)"):
  - §3.2 (Strategy Structure): added a `leg_size_changes` bullet alongside
    `unit_size_change` in "Event log – unit size changes"; rewrote the
    multi-leg transacted-size paragraph to read the per-leg delta directly
    from `leg_size_changes`.
  - §3.6 (Pricer): `compute_cost_exposure` now returns `None` itself (not a
    dict containing `None`) when the market price is unavailable; CostModel
    uses the leg's size delta in `event["leg_size_changes"]`.
  - §3.9 (Backtester): added an opening-day alignment note — 0.0 P&L and
    pricing inputs are recorded at trade creation, so per-leg time series are
    aligned from day 1.
  - §3.10 (Summary): processing step 1 clarified that the opening-day 0.0 P&L
    is recorded at trade creation and the Summary no longer prepends a zero.
  - §3.11 (Data Extractor): event-log column listing now includes
    `leg_size_changes`.
  - §3.13 (Cost Model): "Key design properties" bullet updated to
    "per-unit metrics × per-leg size delta"; `compute_cost` docstring adds the
    `leg_size_changes` event field and multiplies by
    `event["leg_size_changes"][leg_id]`; EquityCostCalculator example updated.

### Test impact
None — documentation only. All tests pass.

### Manual changes
- Marked task 2 finished.

### Suggested commit message
```
docs: record correctness fixes planned before Task 3

- phase2_plan.md: add "Correctness fixes (pre-Task 3)" sub-section with five
  checkboxes (leg_size_changes cost fix, opening-day P&L/pricing-input
  alignment, compute_cost_exposure None, unwind-fraction guard,
  FrozenInstanceError test)
- design_notes.md: update §3.2/§3.6/§3.9/§3.10/§3.11/§3.13 to reflect the
  upcoming fixes; mark pending behaviour as "(planned — see
  docs/phase2_plan.md)"
```

---

## 2026-07-31 -- Document deferred code-review findings

### Prompt
Record the triaged, deferred code-review findings in the project documentation so
they are not lost. Immediate correctness fixes are already tracked in
`docs/phase2_plan.md` under "Correctness fixes (pre-Task 3)".

### Changes applied

- **`docs/phase2_plan.md`**:
  - Added a checkbox for a multi-leg proportional-add cost test validating the
    `leg_size_changes` fix (finding 3.3) right after the "Multi-leg cost
    overcount" line.
  - Added a Task 5 deliverable bullet: the `OrderGenerator` introduces a
    truncated `DataView` that prevents signals from accessing data beyond T-1,
    making the no-look-ahead property structural (finding 1.2).
  - Added a "Testing & hardening" task at the top of Phase 2B with checkboxes
    for invariant/property tests (P&L conservation, time-series length
    alignment, missing-data deferral — finding 3.2) and untested-branch coverage
    (`total_size == 0`, `per_leg` mode — finding 3.4).
  - Added two Phase 2C bullets: surface `cost_data_gaps` in Summary output
    (finding 1.5) and populate `LegSnapshot` greeks once risk measures are
    implemented (finding 2.4).
  - Added a new "Phase 3+ (Future)" section with checkboxes for a `CostExposure`
    TypedDict (finding 2.1), constructor-enforced signal requirement
    declarations (finding 2.3), and a `MissingDataAligner` extraction from
    `Summary` (finding 2.5).

- **`design_notes.md`**:
  - §3.6 (Pricer): changed abstract method signatures from `instrument` to
    `contract` (`price`, `valuation_data`, `pricing_inputs`,
    `compute_cost_exposure`); updated narrative references from `Instrument` to
    `Contract`/`LegState`; updated `compute_cost_exposure` examples to use
    `leg_state`.
  - §3.7 (Signal): added a sentence in "Separation of alpha and execution" noting
    the Phase 2 `OrderGenerator`'s `DataView` structurally enforces the
    no-look-ahead convention.
  - §3.10 (Summary): added a note under "Extensibility for future series types"
    that a planned `cost_data_gaps` report will surface days where cost data was
    unavailable, complementing the existing warning.

### Manual changes
- None

### Suggested commit message
```
docs: record deferred code-review findings for Phase 2

- phase2_plan.md: add multi-leg proportional-add cost test checkbox
  (finding 3.3); add Task 5 DataView no-look-ahead deliverable (finding
  1.2); add Phase 2B "Testing & hardening" task (findings 3.2, 3.4); add
  Phase 2C bullets for cost_data_gaps in Summary and LegSnapshot greeks
  (findings 1.5, 2.4); add Phase 3+ section (findings 2.1, 2.3, 2.5)
- design_notes.md: switch §3.6 pricer signatures from instrument to
  contract; replace stale Instrument references with Contract/LegState;
  note §3.7 DataView and §3.10 cost_data_gaps report
- worklog_phase2.md: append documentation-update entry
```

---

## 2026-07-31 -- Fix §3.6 resolve_instrument docs (Contract, not dict)

### Prompt
§3.6 in design_notes.md still documented `resolve_instrument` as returning
`dict | None` and described the old dict-based workflow. This was missed
during the Task 2 documentation updates.

### Changes applied
- **`design_notes.md` §3.6**:
  - Signature: `resolve_instrument(leg_dict, date) -> Contract | None`.
  - Rewrote the description: the pricer constructs the fully resolved
    `Contract` from the leg dictionary, filtering out infrastructure keys
    and preserving instrument-specific parameters in `Contract.params`;
    the entry price is still obtained separately via `price()`.
  - Updated all examples (equity, exchange-traded option, OTC option,
    FX forward) and the general tenor-resolution rule to describe a
    returned `Contract` instead of a returned dict.
  - Reworded "Preserving the original trading intent": original key-value
    pairs remain in `Contract.params` alongside the resolved values.
  - Added a short "Design tension (deferred)" note: mixed original-intent
    and resolved params mean economically identical instruments may not
    compare equal; Phase 4 will move original intent to
    `LegState.original_intent`, making `Contract` a pure, hashable identity.
  - Rewrote the cost-leg note: `cost_leg` is an infrastructure key, filtered
    out of the `Contract`, and consumed by the backtester to set
    `LegState.cost_leg`.
- **`docs/phase2_plan.md`**: added a Phase 3+ checkbox to migrate original
  trading intent from `Contract.params` to `LegState.original_intent`.

### Test impact
None -- documentation only.

### Suggested commit message
```
docs: fix §3.6 resolve_instrument to return Contract; plan original_intent migration
```

---

## 2026-07-31 -- Final documentation sweep: stale Instrument/cost_leg refs in design notes

### Prompt
Apply a final documentation sweep to design_notes.md to fix stale references
missed during the Task 2 Contract/LegState split. Mechanical find-and-replace
only -- no design decisions. Wait for "apply now" before writing.

### Changes applied (design_notes.md)

- **Category 1 -- removed `cost_leg_ids` references** (deleted in Task 2):
  - §3.2 cost exposure: "stored in `structure.cost_leg_ids`" →
    "determined at order-execution time by checking each leg's `cost_leg`
    flag"; dropped the now-contradictory "determined once when the structure
    is created (see §3.7)" clause.
  - §3.9 construction: "the leg's `leg_id` is added to the structure's
    `cost_leg_ids` list" → "the `cost_leg` flag is set on the `LegState`".
  - §3.9 cost-exposure computation: "identified by `structure.cost_leg_ids`" →
    "identified by `leg_state.cost_leg`".

- **Category 2 -- removed the false `cost_leg_id` retention claim**:
  - §3.2: deleted the sentence "The previous `cost_leg_id` field is retained
    for readability but is now redundant (...)".

- **Category 3 -- replaced remaining `Instrument` references** with `Contract`
  or `LegState` as appropriate (§3.1, §3.2, §3.7, §3.9, §3.10, §5, §7).
  §3.9 §price-call parenthetical dropped (Contract construction lives in §3.6).

- **Category 4 -- Data Extractor granularity terminology**:
  - §3.11 `'granularity'`/`unit_type` now use `'leg'` instead of
    `'instrument'`; all 5 code examples updated.

- **Three extra stale references (confirmed with user)**:
  - §3.10 additional-display-options: `Instrument.params` → `Contract.params`.
  - §3.11 example prose: "Pull instrument-level data" → "Pull leg-level data".
  - §3.2 cost exposure: fixed stale cross-reference `(see §3.5)` → `(see §3.6)`
    (compute_cost_exposure is documented in the Pricer section).

### Manual changes
- None

### Suggested commit message
```
docs: final sweep -- remove stale cost_leg refs; Instrument -> Contract/LegState

- Remove remaining cost_leg_ids references in §3.2/§3.9 (cost-leg set is now
  derived from each LegState's cost_leg flag at order-execution time)
- Delete the false cost_leg_id retention claim in §3.2 event log
- Replace remaining Instrument references with Contract or LegState across
  §3.1/§3.2/§3.7/§3.9/§3.10/§5/§7
- Switch Data Extractor granularity terminology from 'instrument' to 'leg'
  in §3.11 (spec, inspect(), and all code examples)
- Fix extra stale refs: §3.10 Instrument.params, §3.11 example prose,
  §3.2 §3.5->§3.6 cross-reference
- Append worklog entry
```

---

## 2026-08-01 -- Apply pre-Task 3 correctness fixes + doc sync

### Prompt
Apply the five correctness fixes documented in `docs/phase2_plan.md` under
"Correctness fixes (pre-Task 3)", correct two bugs found in the initial diff,
run the full test suite, update the worklog, and remove the now-implemented
`(planned)` annotations from `design_notes.md`.

### Changes applied

**Fix 1 -- Multi-leg cost overcount (`leg_size_changes`)**

- **`backtester/strategy_structure.py`**:
  - `open()`: records `leg_size_changes` (leg_id -> current size) alongside
    the structure-level `unit_size_change` (kept for backward compat).
  - `add_size()`: builds `leg_size_changes = {}` before the loop and records
    each leg's own delta (`new_total - old_size`), so proportional adds
    charge each leg at its own transacted size.
  - `unwind()`: computes `leg_size_changes` (`current_size * fraction`) for
    each leg **before** reducing `current_size`.
- **`backtester/cost_model.py`** -- `EquityCostCalculator.compute_cost`
  multiplies per-unit notional by `event["leg_size_changes"][leg_id]`
  instead of the structure-level `event["unit_size_change"]`.

**Fix 2 -- Opening-day P&L / pricing-input alignment**

- **`backtester/backtest_engine.py`** -- `_resolve_and_price_leg` appends a
  `0.0` to `leg_state.daily_total_pnl` at trade creation, and (when the
  asset class has `record_pricing_inputs` enabled) records the entry-day
  pricing inputs via `setdefault(key, []).append(value)`.
- **`backtester/summary.py`** -- `_extract_leg_data` now uses
  `pnl_start = entry_idx` and the prepend-zero block is deleted; the
  opening-day 0.0 P&L is supplied by the backtester instead.

**Fix 3 -- None inside compute_cost_exposure**

- **`backtester/pricers/equity_pricer.py`** -- `compute_cost_exposure`
  returns `None` when the provider price is `None` (previously returned a
  dict containing `None`). Return hint updated to
  `-> dict[str, float] | None` to match `BasePricer`.

**Fix 4 -- Float-equality unwind fraction + range guard**

- **`backtester/strategy_structure.py`** -- `unwind()` validates
  `0.0 < fraction <= 1.0` (raises `ValueError` otherwise) and sets
  `event_type` via `abs(fraction - 1.0) < 1e-12`.
- **`backtester/trade.py`** -- `unwind_structure()` treats the structure as
  fully closed when `abs(fraction - 1.0) < 1e-12`.

**Fix 5 -- Tighten pytest.raises assertion**

- **`tests/test_backtester.py`** -- frozen-snapshot test now expects
  `dataclasses.FrozenInstanceError` (`import dataclasses` added).

**Test updates**

- **`tests/test_cost_model.py`** -- hand-built event dict in
  `TestEquityCostCalculator` now includes `"leg_size_changes"`; partial
  unwind test unchanged (delta 50.0 matches `current_size * fraction`).
- **`tests/test_strategy_structure.py`** -- `test_open_records_event`
  asserts `event["leg_size_changes"] == {"leg_1": 100.0}`.
- **`tests/test_summary.py`** -- `_make_trade` prepends the opening-day
  `0.0` to `daily_total_pnl`; `test_cost_subtracted_from_net` asserts
  entry-day gross 0.0 / cost 9.0 / net -9.0 and 01-03 net 91.0 (cost column
  is cumulative).
- **`tests/test_backtester.py`** --
  `test_pricing_inputs_nan_padded_for_missing_keys` expects 5 aligned
  entries (opening day is now recorded), `[100.0, nan, 102.0, 104.0, nan]`
  for spot.

**Bug corrections to the initial diff**

1. `test_summary.py` entry-day cost was incorrectly zeroed; the open event
   still executes on the entry date and incurs cost, so entry-day cost is
   9.0 and net is -9.0.
2. `StrategyStructure.add_size()` was missing the `leg_size_changes = {}`
   initialisation before the loop.

**Documentation sync (`design_notes.md`)**

Removed the `*(planned -- see `docs/phase2_plan.md`)*` annotation from the
seven now-implemented descriptions: §3.2 `leg_size_changes` bullet, §3.2
multi-leg transacted-size paragraph, §3.6 `None` return line, §3.6
leg-delta multiplication line, §3.9 opening-day alignment bullet, §3.10
processing-step-1 sentence, and §3.13 per-unit x per-leg delta bullet. The
§3.6 "Design tension (deferred)" note and all other forward-looking notes
are left untouched.

### Test impact
All 151 tests pass (150 prior + 1 new from earlier work; the 
`test_equity_curve_gross_cost_net` expected 4 rows unchanged). The
`test_pricing_inputs_nan_padded_for_missing_keys` expectations were updated
for the new opening-day-aligned series length.

### Manual changes
- None

### Suggested commit message
```
fix: apply pre-Task 3 correctness fixes + sync design notes

- Add leg_size_changes (leg_id -> delta) to open/add_size/unwind events;
  EquityCostCalculator multiplies by the per-leg delta, not the
  structure-level unit_size_change
- Record opening-day 0.0 P&L and pricing inputs in _resolve_and_price_leg;
  Summary no longer prepends a zero on the entry date (pnl_start = entry_idx)
- Return None (not a dict with None) from compute_cost_exposure when the
  market price is unavailable; match base class return hint
- Guard unwind fraction to (0, 1] and use 1e-12 tolerance for full-close
  detection in StrategyStructure.unwind and Trade.unwind_structure
- Tighten frozen-snapshot test to dataclasses.FrozenInstanceError
- Update tests: opening-day-aligned pnl lists, entry-day cost/net
  expectations, hand-built event dicts, leg_size_changes assertion
- design_notes.md: drop (planned) annotations from now-implemented
  §3.2/§3.6/§3.9/§3.10/§3.13 descriptions
- All 151 tests pass
```

## 2026-08-01 -- Fix stale unit_size_change reference in design notes §3.2

### Prompt
Fix a stale sentence in `design_notes.md` §3.2 that was missed during the
documentation sweeps: line 234 still said the CostModel combines per-unit
metrics with `unit_size_change`, but the implementation multiplies by the
per-leg delta from `event["leg_size_changes"][leg_id]`.

### Changes applied

- **`design_notes.md` §3.2 (Event log - cost exposure)** -- replaced
  "combined with `unit_size_change`" with "combined with the leg's size
  delta from `event["leg_size_changes"][leg_id]`". Now consistent with the
  multi-leg paragraph on line 239, §3.6 line 394, §3.13 line 1207, and the
  `EquityCostCalculator` implementation.

### Test impact
None - documentation-only change; no code or tests modified.

### Manual changes
- None

### Suggested commit message
```
docs: fix stale unit_size_change reference in design notes §3.2
```

---

## 2026-08-01 -- Remove dead `unit_size_change` event field

### Prompt
Remove the `unit_size_change` field from the event log completely.
`EquityCostCalculator.compute_cost` reads the leg-specific delta from
`leg_size_changes`, and no other code inspects the old field. Clean up
the event dicts, tests, and design notes; leave only historical
references in the worklog/archive.

### Changes applied

- **`backtester/strategy_structure.py`** -- dropped the
  `"unit_size_change"` key from the event dicts built in `open()`,
  `add_size()`, and `unwind()`. Housekeeping: also removed the now-unused
  locals `total_size` in `open()` and `amount_unwound` in `unwind()`
  (and the `total_size` that fed it). `total_size`/`amount` remain in
  `add_size()` where they still drive leg scaling and entry-price
  updates.
- **`tests/test_strategy_structure.py`** -- deleted the four
  `event["unit_size_change"]` assertions (open, add_size, full unwind,
  partial unwind).
- **`tests/test_cost_model.py`** -- removed `"unit_size_change"` from
  the hand-built event dict in `TestEquityCostCalculator`; all other
  tests build events via `StrategyStructure`, which no longer emits it.
- **`design_notes.md`** -- swept all references in §3.2 and §3.13 and
  the §3.11 `event_log_flat` column list:
  - §3.2: heading "Event log – size changes"; intro now describes the
    per-leg `leg_size_changes` dict; `leg_size_changes` bullet no longer
    says "recorded alongside `unit_size_change`"; cost-exposure intro
    drops "Alongside the unit size change"; `add_size` lifecycle text
    now says the calculator multiplies by the leg's delta from
    `leg_size_changes`.
  - §3.11: removed `unit_size_change` from the `event_log_flat` column
    list.
  - §3.13: key-design bullet now reads "alongside `leg_size_changes`
    (a `leg_id` → per‑leg delta map)"; `compute_cost` docstring no
    longer lists `"unit_size_change"` and the step-2 comment no longer
    references the structure-level field.

### Test impact
- 151 tests pass (was 151 before; only removed assertions on the
  deleted field).
- Remaining `unit_size_change` hits are confined to
  `docs/worklog_phase2.md` (historical entries) and
  `docs/archive/worklog_phase1.md` (archived Phase 1 records) -- left
  untouched.

### Manual changes
- None

### Suggested commit message
```
refactor: remove dead unit_size_change field from event logs
```

## 2026-08-02 -- Task 3: FX Conversion (multi-currency equities)

### Prompt
Implement Task 3 of Phase 2: FX conversion for multi-currency equities as a
post-processing step inside Summary. Add FxRateProvider (typed DataFeed
wrapper), cumulative-spot conversion in Summary.generate() keyed off each
leg's contract currency, dual local/base leg datasets, per-underlying
currency modes, and equity-curve fx_<pair> columns. Add sample data,
update the example, write unit/integration tests, and sync documentation.

### Changes applied
- backtester/data/typed_providers/fx_rate_provider.py (new): FxRateProvider
  with get_conversion_factor (point) and get_conversion_series (vectorized).
  Lookup order: same-currency -> 1.0, direct {from}{to}, inverse {to}{from},
  USD triangulation, else None. Direct/inverse checks extracted into
  _try_direct_or_inverse / _try_series_direct_or_inverse to avoid recursion.
  Identity pair uses a business-day _range_index (no DataFeed.trading_days).
  Series reindexed to the requested (start, end) range; entirely-missing
  pairs return None; gappy data returned with NaN for caller forward-fill.
- backtester/data/typed_providers/__init__.py: re-export FxRateProvider.
- backtester/summary.py:
  - generate(): removed dead fx_rates dict param; added base_currency="USD"
    and fx_provider=None. capital is always assumed to be in base currency.
  - Conversion runs after missing-data handling and cost application on the
    local-currency leg data (step-4 ordering). _build_base_leg_data converts
    every non-base leg via _convert_leg_to_base; unconvertible legs stay
    local with a warning.
  - _convert_leg_to_base: cumulative-spot method for gross/cost/net and
    *_pnl; direct factor multiplication for *_ts; factor reindexed to
    trading days then ffill'd; builds self._fx_series (fx_{local}{base}).
  - Report tree carries both local_leg_data and base_leg_data. _build_report
    passes base data to portfolio-level reports and both datasets to
    by_underlying.
  - Cache keys now use leg-dict object ids (not leg_ids) so base and local
    variants of the same legs don't collide in by_underlying "both" mode.
- backtester/reports/:
  - _base.py: BaseReport.build signature extended to
    (summary, trades, leg_data, report_config, output_name, base_leg_data,
    fx_series); fx_rates removed.
  - equity_curve.py: adds fx_<pair> columns (ffilled to trading days) when
    fx_series is non-empty; consumes the dataset it is handed.
  - by_underlying.py: accepts "currency" config key ("base" default,
    "local", "both"); "both" emits suffixed "_local" sheets; local sheets
    never carry fx columns.
  - trade_summary / metrics / periodic_metrics / hit_ratio / drawdown_table:
    signature updated, bodies unchanged.
- backtester/signals/sma_crossover.py: optional ticker_currency map; NEW
  leg dicts carry "currency" so non-USD tickers resolve correctly.
- examples/sma_crossover_example.py: trades SPY/QQQ/2800.HK/SXRT.DE with
  2800.HK->HKD, SXRT.DE->EUR; instantiates FxRateProvider and passes it
  with base_currency="USD" to Summary.generate(); by_underlying uses
  currency="both".
- market_data/: user-supplied HSI data shipped as 2800.HK_eod.csv (Tracker
  Fund of HK, HKD) and EUR data as SXRT.DE_eod.csv (iShares EURO STOXX 50
  UCITS ETF Acc, EUR), plus EURUSD_eod.csv and USDHKD_eod.csv.
- tests/test_fx_rate_provider.py (new): direct, inverse, triangulation,
  missing rates, series reindexing, same-currency.
- tests/test_summary.py: registry dummy report signature updated to 8 args;
  new TestSummaryFXConversion (EUR->USD math, fx column, no-provider
  regression, missing-rate skip + warning, NaN gap ffill recovery, HKD
  custom base) and TestSummaryByUnderlyingCurrency (base/local/both).
- design_notes.md: §3.10 generate() signature now shows fx_provider and
  base_currency; processing step 4 rewritten as implemented (cumulative
  spot, forward-fill, skip-on-None, hedged-notional assumption, step
  ordering); stale _aggregate_series/fx_rates references removed.
- README.md: architecture summary mentions FX conversion.
- docs/phase2_plan.md: Task 3 marked complete.

### Test impact
All 171 tests pass (151 existing + 8 TestFxRateProvider +
7 TestSummaryFXConversion + 4 TestSummaryByUnderlyingCurrency +
1 updated registry dummy). Only the registry dummy report signature in
test_summary.py changed; the dummy build() now takes the 8-arg signature.

### Manual changes
- None

### Suggested commit message
```
feat: Task 3 - FX conversion for multi-currency equities

- Add FxRateProvider (direct/inverse/USD-triangulation lookup, vectorized
  get_conversion_series) wrapping DataFeed; no backend changes
- Summary.generate(): replace dead fx_rates dict with base_currency +
  fx_provider; convert non-base legs after missing-data + cost steps via
  cumulative-spot method; dual local/base leg datasets through the report
  tree; cache keys keyed by leg-dict identity
- Extend BaseReport.build to 8 args; equity_curve emits fx_<pair> columns;
  by_underlying supports currency base/local/both
- SMACrossoverSignal gains ticker_currency map; example trades SPY/QQQ/
  2800.HK/SXRT.DE with FX provider and by_underlying currency="both"
- Add EURUSD/USDHKD/2800.HK/SXRT.DE sample data (user-supplied)
- Unit + integration tests for provider, conversion math, missing-rate
  handling, by-underlying currency modes; all 171 tests pass
```

## 2026-08-05 -- FX reporting cleanup: relevant pairs, no duplicate local sheets

### Prompt
Clean up three FX reporting issues: base-currency by-underlying sub-reports
received the full fx_series dict (irrelevant fx_ columns), currency="both"
produced duplicate local sub-reports for base-currency tickers, and the overall
portfolio equity curve carried unhelpful fx_ columns.

### Changes applied
- backtester/summary.py: generate() now stores self._base_currency; _build_report
  passes fx_series=None to overall portfolio reports (by_underlying still gets the
  full self._fx_series so it can filter per underlying). base_leg_data is now a
  fresh list(leg_data) when no fx_provider, preventing identity aliasing with
  leg_data that would break the by_underlying is_local check.
- backtester/reports/by_underlying.py: base-currency sub-reports filter fx_series
  to the single fx_{leg_currency}{base_currency} pair for that underlying (None
  when absent); currency="both" skips local sub-reports for tickers whose currency
  equals the base currency; currency="local" unaffected (always produces).
- tests/test_summary.py: overall equity curve asserts no fx_ columns (renamed
  test_no_fx_columns_in_overall_equity_curve); both-mode SPY local duplicate
  suppressed; new test for base-currency duplicate suppression; local-mode guard
  keeps producing local reports.

### Test impact
All 172 tests pass (171 prior + 1 new
test_currency_both_skips_local_duplicate_for_base_currency_ticker).

### Manual changes
- Update design notes on fx conversion series for equity curve (now only show in by underlying reports)

### Suggested commit message
```
fix: FX reporting cleanup - relevant pairs only, no duplicate local sheets

- summary._build_report: pass fx_series=None to overall portfolio reports so
  the aggregate equity curve stops carrying unhelpful fx_ columns
- by_underlying: filter the full fx_series to each underlying's single
  fx_{local}{base} pair for base-currency sub-reports (None when absent)
- by_underlying: in currency="both", suppress local sub-reports that would
  duplicate the base report for tickers whose currency equals the base
  currency; currency="local" still always produces local reports
- summary.generate: copy base_leg_data when no fx_provider to avoid identity
  aliasing with leg_data
- tests updated accordingly; all pass
```

## 2026-08-08 -- BaseReport.build: remove redundant base_leg_data parameter

### Prompt
Remove `base_leg_data` from `BaseReport.build()` and store it on the Summary
instance (`summary._base_leg_data`), because six of seven reports already
receive the same list as `leg_data`. Keep `fx_series` in the signature since
`ByUnderlyingReport` filters it per underlying and must pass the filtered
single-pair dict to sub-reports.

### Changes applied
- backtester/reports/_base.py: BaseReport.build signature reduced from
  (summary, trades, leg_data, report_config, output_name, base_leg_data,
  fx_series) to (summary, trades, leg_data, report_config, output_name,
  fx_series).
- backtester/reports/equity_curve.py / trade_summary.py / metrics.py /
  hit_ratio.py / periodic_metrics.py / drawdown_table.py: dropped the
  unused base_leg_data parameter; bodies unchanged (equity_curve still
  consumes fx_series).
- backtester/reports/by_underlying.py:
  - Dropped base_leg_data from build(); sub-reports are now called as
    (summary, sub_trades, ticker_leg_data, sub_cfg, name, ticker_fx).
  - Derives the base dataset from summary._base_leg_data scoped to the
    current filter group via the trades it already receives:
    `trade_ids = {t.trade_id for t in trades}` then filters
    summary._base_leg_data by trade_id. Falls back to leg_data when
    summary._base_leg_data is empty.
- backtester/summary.py:
  - generate() stores self._base_leg_data = base_leg_data (global,
    unfiltered) after FX conversion.
  - _build_report no longer passes base_leg_data to by_underlying; the
    by_underlying branch passes (leg_data, self._fx_series) and the
    portfolio branch passes (base_leg_data, None) as before.
- tests/test_summary.py: registry dummy report signature updated to the new
  7-arg form (output_name, fx_series).

### Scope-filtering note
ByUnderlyingReport filters summary._base_leg_data itself (instead of
Summary passing a filtered copy) to avoid mutating instance state in
_build_report. Because the trades argument is already scoped to the active
report-group filter, this keeps by_underlying reports inside a filtered
group. When no filter is active the derived dataset equals the full base
dataset. Filters operate on trades, and leg dicts carry exactly one
trade/trade_id, so filtering by trade_id matches the report tree's
membership criterion.

### Test impact
All 172 tests pass, including the FX by-underlying currency-mode and
filtered-group tests.

### Manual changes
- None

### Suggested commit message
```
refactor: drop redundant base_leg_data from BaseReport.build()

- Remove base_leg_data parameter from BaseReport.build(); the six
  portfolio-level reports already received the same list as leg_data
- Store the base dataset on Summary as summary._base_leg_data (set once
  in generate() after FX conversion)
- ByUnderlyingReport now derives its base dataset from
  summary._base_leg_data, scoped to the current filter group via the
  trades it already receives (pure functional derivation, no instance
  mutation)
- Keep fx_series as an explicit parameter: ByUnderlyingReport filters it
  per underlying and must pass the single relevant pair to sub-reports
- Update registry-extensibility dummy report signature to 7 args
- All 172 tests pass
```

## 2026-08-08 -- Fix FX conversion: surface genuine missing-rate days

### Prompt
Fix three related issues in the FX conversion logic: (1) the FX factor is
forward-filled before conversion (and again in the equity-curve FX column),
hiding genuine missing-rate days; (2) the cumulative-spot formula freezes the
cumulative base on a missing-rate day, producing a misleading 0.0 daily base
P&L instead of NaN; (3) missing-data mode only ran on local `leg_data`, never
on the converted `base_leg_data`, which can contain new NaNs introduced by
missing FX rates.

### Changes applied

- **`backtester/summary.py` -- `_convert_leg_to_base`**: dropped the
  forward-fill (`factor.reindex(td_index).ffill()` -> `factor.reindex(td_index)`)
  so genuine NaN rates survive alignment and are visible in the fx column.

- **`backtester/summary.py` -- `_cumulative_spot_convert`**: added a
  `nan_mask = factor_aligned.reindex(series.index).isna()` computed before the
  conversion. The cumulative-spot conversion still bridges the gap internally
  (ffill on the cumulative product), but after conversion the missing days are
  restored to `NaN` via `daily_base[nan_mask] = float("nan")` instead of being
  left at a frozen 0.0. The mask is reindexed to `series.index` (a subset of
  the trading-day index) to avoid a pandas index-alignment error.

- **`backtester/summary.py` -- `generate()`**: after FX conversion, when
  `fx_provider is not None` and `missing_data_mode == "all"`, run a second
  `_adjust_for_missing_legs(base_leg_data, trading_days)` pass so missing-FX
  NaNs are deferred consistently with local missing-data handling. `'any'` is
  handled by `get_daily_series` `fillna(0.0)`; `'per_leg'` preserves NaN by
  design.

- **`backtester/reports/equity_curve.py`**: the FX column now uses the stored
  factor directly (already aligned to trading days) instead of reindexing +
  forward-filling, so the fx column shows NaN on gap days.

### Test impact
Rewrote `test_missing_rate_nan_gap_ffill_recovery` for `'any'` mode (default):
the by-underlying equity curve is continuous (gap-day NaN aggregates to 0.0)
with cumulative gross `[0.0, 0.0, 166.5, 197.75]`, and `fx_EURUSD` is NaN on
the gap day. Added `test_missing_rate_nan_gap_all_mode` (gap day deferred, no
NaN leaks into the equity curve) and `test_missing_rate_nan_gap_per_leg_mode`
(raw per-leg base series keeps NaN on the gap day). All 174 tests pass (172
prior + 2 new; the rewritten test replaces the old one).

### Manual changes
- Add comment on the fx loop in equity curve; update phase2_plan status

### Suggested commit message
```
fix: surface genuine FX-rate gaps; NaN daily base P&L on missing-rate days

- summary._convert_leg_to_base: drop factor forward-fill so genuine
  missing-rate days stay NaN and are visible in the fx column
- summary._cumulative_spot_convert: restore NaN on gap days via a
  factor_aligned nan_mask reindexed to the series index (cumulative-spot
  conversion still bridges the gap internally); daily base P&L is now NaN,
  not a frozen 0.0
- summary.generate: after FX conversion, run _adjust_for_missing_legs on
  base_leg_data in 'all' mode so missing-FX NaNs are deferred consistently
  with local missing-data handling ('any' handled by get_daily_series
  fillna, 'per_leg' preserves NaN by design)
- equity_curve report: use the stored factor directly (already aligned to
  trading days) so the fx column shows NaN on gap days
- tests: rewrite test_missing_rate_nan_gap_ffill_recovery for 'any' mode
  (continuous curve + fx NaN via by_underlying); add 'all' (deferred gap)
  and 'per_leg' (raw-series NaN) tests
- All 174 tests pass
```

## 2026-08-08 -- Fix stale design-notes statements about FX conversion and missing-data ordering

### Prompt
Update `design_notes.md` §3.10 step 4 to fix two statements that contradict
the current implementation: (1) the FX factor forward-fill claim; (2) the
claim that missing-data handling only runs once before conversion.

### Changes applied

- **`design_notes.md` §3.10 step 4**: replaced the claim that FX factor
  gaps are forward-filled. The text now states that genuine gaps are *not*
  forward-filled (factor retains NaN for diagnostic transparency); the
  cumulative product `(cum_local × factor)` is forward-filled internally,
  with NaN restored on missing-rate days in the daily series via a mask.
  The resulting NaNs are processed by the missing-data mode (`'any'` →
  aggregated to zero, `'all'` → gap day deferred, `'per_leg'` → preserved).
  The missing-pair-file (provider returns `None`) behavior is unchanged:
  leg stays in local currency with a warning.

- **`design_notes.md` §3.10 step 4**: replaced the claim that conversion
  runs after missing-data handling/cost and that NaNs are already processed
  before conversion. The text now documents that missing-data handling is
  applied a *second* time to the converted base-currency leg data because
  FX conversion can introduce new NaNs from missing FX rates:
  `'all'` → `_adjust_for_missing_legs` called on the base dataset to defer
  gap days; `'any'` → implicit via aggregation `fillna(0.0)`;
  `'per_leg'` → NaN preserved by design.

### Suggested commit message
```
docs: correct design_notes §3.10 step 4 FX conversion and missing-data wording

- step 4: FX factor gaps are not forward-filled; only the cumulative
  product (cum_local × factor) is forward-filled internally, with NaN
  restored on gap days via a mask and processed per missing-data mode
  ('any' -> 0, 'all' -> deferred, 'per_leg' -> preserved)
- step 4: missing-data handling is applied a second time to the
  converted base-currency leg data since FX conversion can introduce
  new NaNs; document the second _adjust_for_missing_legs pass in 'all'
  mode, fillna(0.0) for 'any', NaN preservation for 'per_leg'
```

## 2026-09-08 -- FxRateProvider series caching: fix recursion, None bounds, Summary dedup

### Prompt
Refactor the FxRateProvider around a cached, full-range conversion-factor
series so repeated lookups over overlapping simulation windows resolve each
currency pair once instead of per-call. Three problems in the draft were
reviewed and fixed before applying: (1) a recursion bug in the initial
design, (2) extending `get_series` to accept `None` bounds, and (3)
Summary deduplicating its `_fx_series` factor reuse. Wait for "apply now"
before writing.

### Assessment (pre-apply review)

**Problem 1 -- infinite recursion.** The draft `_get_factor_series("X","USD")`
recursing when both direct and inverse pairs were missing re-entered
triangulation with the same pair. Fix: a non-recursive
`_try_full_direct_or_inverse(from, to)` that resolves direct then inverse on
the full available range and never triangulates. `_get_factor_series` uses it
for its own direct/inverse attempt and for both USD legs, so `(X,USD)` and
`(USD,Y)` resolve only via direct/inverse (which never recurses) and no
recursion path exists. This exactly preserves the original lookup-order
semantics, since the original `get_conversion_series` also used the scoped
direct/inverse-only helper for its USD legs.

**Problem 2 -- `start=None`/`end=None` safety.** `CsvBackend.get_series`
already in-memory caches each ticker's full series, so
`series.loc[None:None]` is a full slice (mask) -- no range materialization,
and no backtester consumer passes `None` today (all call sites pass string
dates). The `_MockFeed.get_series` in the tests slices `self._data.get(ticker)`
and also tolerates `None`. `get_value` is deliberately left untouched
(`.loc[date]` on `None` would raise). Only `get_series` (both `DataFeed` and
`CsvBackend`) accepts `None`.

**Problem 3 -- Summary dedup correctness.** The Summary caches only
successful aligned factors in `_fx_series`, so `if pair_key in
self._fx_series` unambiguously means "already computed". A missing pair is
simply absent and re-fetches from the provider each time (the provider
returns `None` quickly and records the pair in its own `_missing_pairs` set),
preserving the current warn-per-leg behaviour. Caching `None` in `_fx_series`
would require a separate sentinel and is avoided. The HKD/`_FakeFxProvider`
edge is unchanged: a leg whose currency equals the base currency is copied
through and never reaches the provider.

### Changes applied

- **`backtester/data/typed_providers/fx_rate_provider.py`**:
  - Added `_factor_cache: dict[(from, to), pd.Series]` and
    `_missing_pairs: set[(from, to)]` on `__init__`.
  - Added `_get_factor_series(from, to)`: returns the cached full derived
    factor series (direct -> inverse -> USD triangulation), keyed by the pair
    and independent of any simulation window; records truly-absent pairs in
    `_missing_pairs` and returns `None`; never caches the intermediate USD
    legs, only the final requested pair.
  - Added `_try_full_direct_or_inverse(from, to)`: fetches the direct pair on
    the full available range (`get_series(..., None, None, ...)`), then the
    inverse pair as `1.0 / inverse`; never triangulates, so recursion is
    structurally impossible.
  - `get_conversion_series` and `get_conversion_factor` now route through
    `_get_factor_series` and slice/reindex or `.loc[date]` on cache hits.
    `get_conversion_factor` output is identical for the CSV backend (the full
    series is ticker-cached) and all existing point-lookup tests pass
    unchanged.
  - Removed the per-call `_try_direct_or_inverse` /
    `_try_series_direct_or_inverse` helpers (superseded by the cache path).

- **`backtester/data/csv_backend.py`** / **`backtester/data/data_feed.py`**:
  `get_series` signatures widened to `start: str | None, end: str | None`.
  `CsvBackend.get_series` returns the full cached series when both are
  `None` (a `series.loc[None:None]` full slice); otherwise unchanged.
  `get_value` is untouched (a `None` date would crash `.loc[date]`).

- **`backtester/summary.py` -- `_convert_leg_to_base`**: hoisted the
  `pair_key in self._fx_series` check to the top of the method. On a cache
  hit the stored aligned factor is reused directly; on a miss the provider
  is called, the warning + `None` short-circuit preserved, and the aligned
  factor is stored once. The store now happens exactly where the factor is
  produced (never for a missing pair), making the presence check
  unambiguous.

- **`tests/test_fx_rate_provider.py`**:
  - `_MockFeed.get_series` accepts `start=None, end=None` and returns the
    full stored series when both are `None`.
  - Added `TestProviderCache`: `test_semantic_series_cached_and_reused`
    (two overlapping windows read the same cached full series),
    `test_missing_pair_cached_in_missing_set` (absent pair returns `None`
    and is recorded in `_missing_pairs`), and
    `test_triangulated_pair_is_cached_only_as_final` (a triangulated pair is
    cached as `("JPY","HKD")` only -- the intermediate `("JPY","USD")` and
    `("USD","HKD")` legs are never cached).

- **`design_notes.md` §8.1**: `DataFeed.get_series` signature annotated
  `start: str | None, end: str | None` and a new bullet added under "Key
  features": `start=None`/`end=None` requests the full available series for
  that ticker; both `None` returns the entire cached series. The existing
  backend-protocol bullet is preserved.

### Test impact
All 177 tests pass (174 prior + 3 new provider-cache tests).

### Manual changes
- None

### Suggested commit message
```
refactor: cache full-range FX factor series per pair in FxRateProvider

- Add _get_factor_series keyed by (from, to): resolve once over the full
  available range (direct -> inverse -> USD triangulation), cache the
  result, and slice on windowed get_conversion_series / point
  get_conversion_factor calls; record truly-absent pairs in _missing_pairs
- Add non-recursive _try_full_direct_or_inverse (never triangulates),
  eliminating the draft's infinite-recursion path for missing pairs
- Widen get_series bounds to str | None on CsvBackend and DataFeed;
  both None returns the full cached series (get_value untouched)
- Summary._convert_leg_to_base: check the _fx_series cache up front and
  store the aligned factor exactly where produced (never for missing
  pairs), so cached-only-successful is unambiguous
- Update _MockFeed.get_series for None bounds; add TestProviderCache
  (cached reuse, missing-pair set, final-pair-only triangulation caching)
- design_notes.md §8.1: annotate get_series with str | None and document
  the full-range None-bounds semantics
- All 177 tests pass
```

---

## 2026-09-08 -- Docs: add planned Portfolio Layer spec (design_notes.md §10)

### Prompt
Document the planned Portfolio Layer as forward-looking design only; no code
changes. Insert a new §10 after the existing §9 (Overall System Architecture),
leaving every existing section and all numbering untouched.

### Change
- `design_notes.md`: appended new **§10. Portfolio Layer (Planned)** directly
  after §9 (document grew 1637 -> 2125 lines). Inserted verbatim as specified,
  including the status note, the terminology mapping, subsections 10.1-10.11,
  every Python/ASCII code block and every table:
  - 10.1 Core Design Principles (P-1..P-5)
  - 10.2 Two Parallel State Tracks (`StrategyPortfolioState` vs
    `ActualPortfolioState`)
  - 10.3 End-to-End Data Flow (Layer 2 -> Layer 4 -> Summary/Report/Validation)
  - 10.4 Component Specifications (10.4.1-10.4.10): NettingEngine,
    PortfolioAllocator, StrategySizer, RiskConstraint, ExecutionRecord,
    BaseExecutionHandler, MarginCalculator, CashFlowTracker,
    PortfolioCostModel, StrategyContribution
  - 10.5 Unified Performance Interface (`PerformanceData` + adapters)
  - 10.6 BasePricer Extension (`expected_cash_flows()`)
  - 10.7 Backtest / Live Consistency
  - 10.8 Order Rejection Handling
  - 10.9 Nested Validation
  - 10.10 Hard Constraints (C-1..C-5)
  - 10.11 Implementation Priority (P0..P5)
- Nothing else in the document was touched: §1-§9 are unchanged and were not
  renumbered. Verified as a single +489/-1 hunk at the end of the file.

### Notes
- The spec names `BacktesterResult` and `BaseCostModel` do not exist yet. The
  section carries an explicit terminology mapping to the current
  `BacktestResult` (`backtester/backtest_engine.py:36`) and
  `BaseCostCalculator` / `CostModel` (`backtester/cost_model.py:6,17`).
  Checked against the codebase -- the mapping is accurate.
- Character conventions matched to the rest of the document: U+2011
  non-breaking hyphen (e.g. `forward-looking`, `post-processing`) and U+202F
  narrow no-break space (`Phase 1`, `Phase 2`). No ASCII substitutions.
- Deliberately **not** done, because it would alter another part of the
  document: the Table of Contents still ends at §9, so §10 is not linked
  from it. Worth a follow-up if you want §10 reachable from the TOC.

### Test impact
None -- docs-only change. All 177 tests pass.

### Manual changes
- None

### Suggested commit message
```
docs: add planned Portfolio Layer specification as design_notes.md §10

Forward-looking design documentation only; no code changes.

- Add §10 Portfolio Layer (Planned) after §9, covering:
  - core design principles P-1..P-5 (intent/execution separation,
    post-simulation computation, no retroactive signal correction, cost on
    net trades, signal/capital decoupling)
  - the two parallel state tracks (StrategyPortfolioState vs
    ActualPortfolioState) and the end-to-end Layer 2 -> Layer 4 data flow
  - component specs 10.4.1-10.4.10: NettingEngine, PortfolioAllocator,
    StrategySizer, RiskConstraint, ExecutionRecord, BaseExecutionHandler,
    MarginCalculator, CashFlowTracker, PortfolioCostModel,
    StrategyContribution
  - unified PerformanceData interface, BasePricer.expected_cash_flows(),
    backtest/live consistency, order rejection handling, nested validation
  - hard constraints C-1..C-5 and implementation priority P0..P5
- Add terminology mapping: spec BacktesterResult/BaseCostModel correspond to
  current BacktestResult and BaseCostCalculator/CostModel
- Existing §1-§9 untouched and not renumbered; TOC unchanged
- All 177 tests pass
```

---

## 2026-09-09 -- Docs: add AGENT.md with environment instructions

### Prompt
Add an `AGENT.md` at the project root so AI agents and collaborators know how
to run the project correctly. Content was supplied verbatim and written
directly (no diff requested). No other files to be modified.

### Change
- Created `AGENT.md` (33 lines) at the project root, documenting:
  - Environment: use the conda env `backtest` (Python 3.12), never system
    Python; all Python commands must run inside that environment
  - Initial setup: `conda create -n backtest python=3.12 pandas numpy
    matplotlib pyyaml pytest -y`
  - Running commands via `conda run -n backtest ...` -- tests and
    `examples/sma_crossover_example.py`
  - Fallback when `conda run` is unavailable: locate the env with
    `conda env list` and invoke its interpreter directly (POSIX and Windows
    forms given)
  - Dependency management: install only into `backtest`, never globally or
    into another environment

### Notes
- Content written exactly as supplied. The leading and trailing `---` rules in
  the request were treated as block delimiters, not as file content.
- **Open caveat:** conda is not actually installed on this machine (no `conda`
  on PATH, no anaconda/miniconda directories found), so the documented
  commands cannot be executed as written here and the `backtest` env does not
  exist. The suite currently runs via the managed venv at
  `C:/Users/chank/.workbuddy/binaries/python/envs/default/Scripts/python.exe`.
  Follow-up: either install conda and create `backtest`, or amend AGENT.md to
  describe the environment actually in use.

### Test impact
None -- new documentation file, no code touched. All 177 tests pass (re-run
after the addition as a sanity check).

### Manual changes
- None

### Suggested commit message
```
docs: add AGENT.md with conda environment and command instructions

- Document the `backtest` conda environment (Python 3.12) as the only
  supported interpreter for this project
- Add initial setup via `conda create -n backtest ...`
- Add `conda run -n backtest` for tests and example scripts
- Add fallback: locate the env with `conda env list` and call its Python
  directly (POSIX + Windows forms)
- Add dependency rule: install only into `backtest`, never globally
- Docs-only; all 177 tests pass
```

---

## 2026-09-09 -- Docs: AGENT.md -- robust conda discovery when conda is not on PATH

### Prompt
Make conda discovery more robust for agent environments where conda is not on
PATH. Replace the "If `conda run` is unavailable" section with an expanded
version and keep the rest of the file unchanged.

### Change
- `AGENT.md` (33 -> 43 lines): replaced the "If conda run is unavailable"
  section. The previous two-step fallback (run `conda env list`, then call
  `<env_path>/bin/python` or `<env_path>\python.exe`) is replaced by:
  - a list of common conda roots to probe: `C:\Users\<username>\anaconda3`,
    `C:\Users\<username>\miniconda3`, `C:\ProgramData\Anaconda3`,
    `D:\anaconda3`, `/opt/anaconda3`, `~/anaconda3`, `~/miniconda3`
  - running via the full conda path:
    `<conda_root>\Scripts\conda.exe run -n backtest python -m pytest`
  - calling the environment interpreter directly:
    `<conda_root>\envs\backtest\python.exe` (Windows) and
    `<conda_root>/envs/backtest/bin/python` (Linux / macOS)
  - an explicit instruction to ask the user when conda still cannot be found
- Everything else is unchanged: lines 1-17 and the Dependency Management
  section are byte-for-byte identical to the previous version.

### Notes
- The `---` rules in the request were again treated as block delimiters, not
  as file content.
- Still unresolved: conda is not installed on this machine, so none of the
  documented paths resolve here. Re-verified this session -- no `conda` on
  PATH and no anaconda/miniconda directories. The suite was therefore run
  with the managed venv at
  `C:/Users/chank/.workbuddy/binaries/python/envs/default/Scripts/python.exe`,
  as the new AGENT.md instructs for the not-found case.

### Test impact
None -- docs-only change. All 177 tests pass.

### Manual changes
- None

### Suggested commit message
```
docs: make conda discovery robust in AGENT.md when conda is not on PATH

- Probe common conda roots (Windows per-user, ProgramData, D:\, /opt, ~)
  before giving up
- Prefer running via the full conda path: <conda_root>\Scripts\conda.exe run
- Add direct environment-interpreter invocation for Windows and POSIX
- Instruct agents to ask the user when conda cannot be located
- Docs-only; all 177 tests pass
```

## 2026-09-18 -- Design cleanup: declarative local-currency report dispatch and aligned FX factor naming

### Prompt
Two small, related design cleanups:

1. Replace `Summary._build_report`'s hardcoded
   `report_name == "by_underlying"` check with a declarative
   `requires_local_currency` class attribute on `BaseReport`, overridden by
   `ByUnderlyingReport`, mirroring the existing declarative pattern in
   `BaseSignal` (`requires_portfolio_state`, `requires_trade_history`).
2. Rename `Summary._fx_series` to `Summary._aligned_fx_factors` and document
   its dual role: a per-`generate()` cache of trading-day-aligned conversion
   factors reused across legs during conversion and exposed for reporting
   (`fx_<pair>` columns). `FxRateProvider`'s cache is a different object and
   must not be renamed.

### Changes applied
- `backtester/reports/_base.py`: added
  `requires_local_currency: bool = False`.
- `backtester/reports/by_underlying.py`: declared
  `requires_local_currency = True`.
- `backtester/summary.py`:
  - `_build_report` now selects `leg_data` +
    `self._aligned_fx_factors` for reports whose
    `requires_local_currency` is `True`; all other reports still receive
    `base_leg_data` + `None`.
  - renamed `_fx_series` to `_aligned_fx_factors` at every initialization,
    reset, read, and write site.
  - added a comment on `_aligned_fx_factors` documenting its dual role
    (keyed by f"fx_{local}{base}", reused for conversion, exposed for
    reporting).
- `tests/test_summary.py`: added `TestSummaryReportDispatch`, which registers
  a dummy `BaseReport` subclass with `requires_local_currency = True` and
  asserts it receives local leg dictionaries plus the exact aligned FX factor
  dict through `_build_report`.
- No test code referenced `summary._fx_series` directly, so no existing test
  renames were required; the new dispatch test references
  `_aligned_fx_factors`.

### Test impact
All 178 tests pass (177 prior + 1 new dispatch test).

### Manual changes
- None

### Suggested commit message
```
refactor: declarative local-currency report dispatch; name aligned FX cache

- BaseReport: add requires_local_currency = False, mirroring BaseSignal's
  declarative capability flags
- ByUnderlyingReport: declare requires_local_currency = True
- Summary._build_report: dispatch on the report class capability instead of
  comparing the configured report key to "by_underlying"
- Rename Summary._fx_series to _aligned_fx_factors and document its dual role
  as the per-run trading-day-aligned factor cache used for conversion reuse
  and reporting
- Add TestSummaryReportDispatch covering local leg_data + FX factor dispatch
- All 178 tests pass
```

## 2026-09-19 -- Readability: rename `is_local` to `is_secondary_local_pass` in by_underlying

### Prompt
`ByUnderlyingReport.build` computed
`is_local = dataset is leg_data and currency == "both"`. The name reads as
"the current dataset is in local currency", but it is `True` only during the
secondary local pass of a `currency="both"` run -- in `currency="local"` mode
the dataset *is* local and the flag is `False`. Rename it to state what it
actually flags. Pure rename, no behaviour change.

### Changes applied
- `backtester/reports/by_underlying.py`: renamed `is_local` to
  `is_secondary_local_pass` at all four sites --
  - the assignment (`dataset is leg_data and currency == "both"`),
  - the duplicate-suppression check (skip local sub-reports for tickers whose
    currency equals the base currency),
  - the FX-attachment check (skip FX conversion on the local pass),
  - the key-suffix assignment (`_{ticker}_{sub_name}_local`).
- No other file referenced the name; no logic, signature, or output key
  changed.

### Naming rationale
Verified against all three currency modes: `currency="local"` builds
`datasets = [(None, leg_data)]` so the flag is `False`; `currency="base"`
builds `[(fx_series, base_dataset)]` where `base_dataset` is a freshly built
list (never identical to `leg_data`), so the identity test is `False`; only
`currency="both"` produces a second `(None, leg_data)` pass, which is the one
case the flag marks.

### Test impact
All 178 tests pass (unchanged -- same 178 as before the rename).

### Manual changes
- None

### Suggested commit message
```
refactor: rename is_local to is_secondary_local_pass in by_underlying

is_local read as "this dataset is in local currency", but it was only
True on the secondary local pass of a currency="both" run -- in
currency="local" mode the dataset is local and the flag was False.
Rename to state what it actually flags. Pure rename (assignment,
duplicate-suppression check, FX-attachment check, key-suffix check);
no behaviour change. All 178 tests pass.
```

---

## 2026-09-19 -- Fix: entry-date cost dropped by `_cumulative_spot_convert`

### Prompt
`Summary._cumulative_spot_convert` silently lost the entry-date increment of the
converted series whenever a leg does not start on `trading_days[0]`. For gross
P&L that is invisible (a position opens with 0.0 P&L), but `cost` carries a
non-zero step on the entry date, so every non-USD trade reported a base cost of
`local_cost * fx(exit) - entry_cost * fx(entry)` instead of
`local_cost * fx(exit)`. Fix the conversion, add a regression test, leave every
other file alone.

### Root cause
`cum_base` is aligned to the trading-day index, so it is NaN on every date
before the leg's entry date. `cum_base.diff()` therefore yields NaN *at* the
entry date (`cum_base[entry] - NaN`), and the following `.fillna(0.0)` turned
that NaN into 0.0 -- exactly the entry-day increment. The guard that came next,

    if len(daily_base) > 0:
        daily_base.iloc[0] = cum_base.iloc[0]

anchored on position 0 of the trading-day-aligned series, i.e.
`trading_days[0]` -- a date on which the leg does not exist -- where `cum_base`
is NaN, so the assignment was a NaN-to-NaN no-op.

Traced on a cost series `[20, 0, 0, 20]` indexed `[entry, entry+1, entry+2,
exit]` with `entry > trading_days[0]`: (1) `cum_base` is NaN before the entry
date, (2) `diff()` is NaN on the entry date, (3) `fillna(0.0)` makes it 0.0,
(4) `iloc[0]` labels the assignment `trading_days[0]` with a NaN value. The
converted total came to `local_cum * fx(exit) - entry_cost * fx(entry)` -- the
residual the verification script had been reporting.

### Changes applied
- `backtester/summary.py` -- `_cumulative_spot_convert`: anchor the first
  converted increment on `cum_base.first_valid_index()` (the entry date) rather
  than on `iloc[0]`, and fill NaNs only after that assignment:

      daily_base = cum_base.diff()
      first_valid = cum_base.first_valid_index()
      if first_valid is not None:
          daily_base.loc[first_valid] = cum_base.loc[first_valid]
      daily_base = daily_base.fillna(0.0)
      daily_base = daily_base.reindex(series.index)

  The entry-day increment is now converted at the entry-date rate, and the
  telescoping sum gives `cum_local[exit] * fx[exit]`, the expected lock-in value.

- Backward compatible: when the series starts at `trading_days[0]`,
  `first_valid_index()` returns `trading_days[0]`, identical to the old
  `iloc[0]`; for an empty series it returns `None` and the fix is a no-op;
  all-NaN factors and NaN-rate gap days are unchanged.

- `tests/test_summary.py`: added
  `TestSummaryFXConversion.test_entry_date_cost_is_converted` -- an EUR leg that
  enters on `TRADING_DAYS[1]` with a 9.0 cost on the entry event; asserts the
  entry-day increment converts at fx(entry) and that the cumulative base cost
  equals `local_cost * fx(exit)`. It fails on the unfixed code (0.0 on the entry
  date, `local_cost * fx(exit) - entry_cost * fx(entry)` at the exit date).

### Test impact
179 tests collected: 157 pass, including the new one. The 22 tests in
`tests/test_backtester.py` that use the `tmp_path` fixture error at setup in this
sandbox (see Notes) -- the same 22 errored before the change and no test body
runs. `git stash` check: the new test fails without the fix, passes with it.

### Verification
- Old-vs-new converter compared over nine scenarios (empty series; start at
  `trading_days[0]` with zero and non-zero first day; mid-index start; NaN-rate
  gap; all-NaN factor; leading NaN): identical everywhere except the bug case
  (mid-index start with a non-zero entry value), which now keeps the entry step.
- `scripts/verify_fx_conversion.py` against a regenerated
  `results/backtest_results.xlsx` (`examples/sma_crossover_example.py`): the
  entry-date shortfall diagnostic drops from 47/48 (2800.HK) and 48/48 (SXRT.DE)
  to 0/48 and 0/48. SXRT.DE Check A now passes for gross, cost and net (49/49
  each); 2800.HK passes 47/48 for each. The one remaining trade exits on
  2012-12-04, a date with no FX rate, so its final increment is a missing-rate
  NaN by design (see `test_missing_rate_nan_gap_ffill_recovery`): its base cost
  equals local cumulative cost through 2012-12-03 (19.998521877670157) times
  fx(2012-12-03) (0.1290339252794517) = 2.5804877776627713, matching the reported
  2.580487777662789 to 1e-12. The script's overall verdict stays FAIL for that
  pre-existing missing-rate case and two pre-existing FX-data completeness gaps
  in Check C, neither related to this bug.

### Notes
- `pytest tests/` errors 22 tests in this sandbox: pytest creates its temporary
  directories with mode 0o700, and directories with that mode cannot be scanned
  or removed under the DSH file sandbox (`PermissionError` from `os.scandir` at
  `_pytest/pathlib.py:229`, which fails the `tmp_path` fixture at setup).
  Demonstrated independent of this change: mode-0o700 directories are
  unreadable while mode-0o777 ones are fine, at any location, and the identical
  22 errors occur on the unmodified code. `tests/test_backtester.py` is the only
  test file that uses `tmp_path`.

### Manual changes
- Updated Agent.md to target sandbox problem when running pytest

### Suggested commit message
```
fix: convert the entry-day increment in _cumulative_spot_convert

_cumulative_spot_convert dropped the first converted increment for any leg
not starting on trading_days[0]. cum_base is trading-day aligned, so it is
NaN before the entry date; diff() then yields NaN at the entry date and
fillna(0.0) turned it into 0.0. The follow-up guard assigned iloc[0] --
trading_days[0], a date where cum_base is NaN -- so the entry-day cost step
was silently lost on every non-USD leg (invisible for gross, whose first
day is 0.0).

- summary._cumulative_spot_convert: anchor the first increment on
  cum_base.first_valid_index() (the entry date) instead of iloc[0], and
  fill NaNs after that assignment; the telescoping sum now gives
  cum_local[exit] * fx[exit]
- backward compatible: start-at-trading_days[0] and empty series behave
  exactly as before (verified old-vs-new over nine scenarios)
- tests: add TestSummaryFXConversion.test_entry_date_cost_is_converted
  (fails before the fix, passes after)
- verification: entry-date shortfall diagnostic 47/48 + 48/48 -> 0/48 + 0/48;
  SXRT.DE Check A passes for gross/cost/net
```

---

## 2026-09-20 -- Task 4: CalendarProvider + remove the `calendar_ticker` surrogate

### Prompt
Implement the shared `CalendarProvider` exactly as specified in `design_notes.md`
§3.5, integrate it into the backtester's simulation loop, and remove the Phase 1
`calendar_ticker` surrogate plus the now-obsolete `trading_days()` methods from
the data layer.  Holiday CSVs already existed in `market_data/holidays/`
(produced by a separate data-collection task) and were consumed and validated,
not created.

### Pre-flight validation of `market_data/holidays/`
All three files validated before any code was written -- each has a single
header column `date`, every value matches `YYYY-MM-DD`, there are zero
Saturday/Sunday rows, zero nulls, zero duplicates, and the rows are sorted:

| File | Rows | Range |
|------|------|-------|
| `US.csv` | 244 | 2000-01-17 .. 2025-12-25 |
| `HK.csv` | 378 | 2000-02-04 .. 2025-12-26 |
| `DE.csv` | 181 | 2000-04-21 .. 2025-12-31 |

All three cover the example's `2000-01-01 .. 2025-12-31` window.  The late 2000
start dates are correct rather than gaps: the only US candidate in early 2000
(2000-01-01) is a Saturday and is therefore correctly absent.

### Design decisions applied
1. **CSV schema** -- one file per calendar code at `{holiday_dir}/{CODE}.csv`,
   header `date`, one full non-trading day per row.  Half-days and
   point-in-time vintages are explicitly out of scope.
2. **Simulation calendar coupling** -- the backtester does **not** infer calendar
   codes from trades.  A new `BacktestConfig.simulation_calendar_codes:
   list[str] | None` declares the union of markets to simulate and is passed
   straight to `CalendarProvider.trading_days(...)`.
3. **Union for simulation, per-leg checks for execution** -- `trading_days()`
   returns the union (a day is dropped only if it is a holiday in *every*
   listed code).  Intersection for execution is Task 5's
   `CalendarValidationRule`; Task 4 only had to make `is_valid_day()` available.
4. **No DataFeed masking** -- holiday gaps are absorbed by the existing
   forward-fill/NaN mechanics.  No masking was added to `DataFeed`.
5. **Interim execution policy** -- no execution-time calendar gating was added.
6. **Method naming** -- the per-code primitives are `is_valid_day` /
   `next_valid_day` (calendar-kind-agnostic, so they will serve settlement and
   fixing calendars unchanged); the union method keeps `trading_days` because it
   produces the simulation calendar and matches `BacktestResult.trading_days` /
   `Summary.generate(trading_days=...)`.
7. **`calendar_provider` is REQUIRED (no default)** -- forgetting it must fail
   loudly at construction rather than silently falling back to a no-holiday
   calendar.

### Changes

- **`backtester/calendar_provider.py`** (new): `CalendarProvider` with
  `__init__(holiday_dir=None)`, `trading_days(holiday_codes, start, end)`,
  `is_valid_day(holiday_code, date)`, `next_valid_day(holiday_code, date)`.
  - `holiday_dir=None` -> business-days-only mode (every code except `"all"`).
  - `holiday_dir` set -> lazy per-code loading from `{holiday_dir}/{CODE}.csv`,
    cached per code, so each file is read at most once per instance.
  - Missing file raises `FileNotFoundError` naming the code and expected path;
    a missing file is never silently treated as "no holidays".
  - Branch order in `trading_days` is deliberate: `"all"` short-circuits
    **before** any loading (so `all.csv` is never requested, and `"all"` is
    never modelled as an empty holiday set, which would wrongly drop weekends);
    then `None`/`[]` -> business days (with a one-time warning when a
    `holiday_dir` is configured but unused); then union = business days minus
    the intersection of the codes' holiday sets.
  - Forward-compatibility: the `date` column is read **by name** and every date
    is normalized on both sides of a membership test; extra columns emit a
    one-time-per-file-per-instance warning and are otherwise ignored; all CSV
    loading sits behind a single private `_holidays(code)` seam; the three
    public methods are pure functions of their arguments, so a future additive
    `as_of` parameter is possible.
  - `next_valid_day` scans strictly forward and raises `RuntimeError` (naming
    the code, the start date and the 1000-day budget) if no valid day exists.

- **`backtester/backtest_engine.py`**:
  - `BacktestConfig`: removed `calendar_ticker`; added
    `calendar_provider: CalendarProvider` with **no default** and
    `simulation_calendar_codes: list[str] | None = None`.  All four pre-existing
    fields are non-default, so replacing `calendar_ticker` in place keeps every
    no-default field ahead of every defaulted one -- no field reordering and no
    `kw_only` were needed.
  - `run()` now calls
    `self._config.calendar_provider.trading_days(self._config.simulation_calendar_codes, start_date, end_date)`.
  - `Backtester.__init__(self, config)`: the `data_feed` parameter and the
    `self._data_feed` attribute were **removed**.  A grep confirmed
    `trading_days` was the only remaining use of `self._data_feed`.
  - `BacktestResult.trading_days` still carries the calendar downstream, so
    `Summary` needed no changes.

- **`backtester/data/csv_backend.py`** / **`backtester/data/data_feed.py`**:
  removed `trading_days()` (calendars are a cross-cutting concern, not market
  data -- §3.5).  No other consumer existed.

- **`examples/sma_crossover_example.py`**: instantiates
  `CalendarProvider("market_data/holidays")`; sets
  `simulation_calendar_codes=["US", "HK", "DE"]`, derived from the markets
  actually traded (SPY/QQQ -> US, 2800.HK -> HK, SXRT.DE -> DE -- matching
  exactly the holiday files that exist); drops the `data_feed` argument from
  `Backtester(...)`.

- **`tests/conftest.py`**: the sandbox-safe `tmp_path` override previously
  called `tmp_path_factory.getbasetemp()`, which made pytest create the basetemp
  with `mkdir(mode=0o700)` -- the very construct that breaks DACL inheritance
  and produced the 22 `PermissionError [WinError 5]` setup failures.  The
  override now creates per-test directories under a stable, inherited
  `tests/.tmp/` base and never touches the basetemp.  Exact prior error:
  `PermissionError: [WinError 5] ... '.pytest_bt6\test_trade_history_returned_21f3a45c'  tests\conftest.py:33`.

- **`tests/test_calendar_provider.py`** (new, 68 tests): business-days mode;
  `None` vs `[]` vs `["all"]` vs `["all", "<code>"]`; the `"all"` short-circuit
  proven by patching `pd.read_csv`; single-code subtraction; multi-code union
  (kept vs. dropped); holiday-on-weekend ignored; inclusive bounds; single-day
  ranges; empty results; missing-file `FileNotFoundError` from all three public
  methods; the one-time unused-files warning (fresh provider per assertion,
  asserted against `_warned_no_codes`); per-code caching asserted by patching
  `pd.read_csv` beneath the `_holidays` seam; extra-column parsing and
  one-time-per-instance warning; all `is_valid_day` cases including empty-string
  and unknown codes; `next_valid_day` normal / weekend / holiday / consecutive
  closures / year boundary / `"all"`; and the `RuntimeError` guard triggered by
  pre-seeding the per-code cache with a dense holiday set (no ~1000-row fixture).

- **`tests/test_data/holidays/`** (new fixtures, committed, following the
  existing `tests/test_data/SPY_eod.csv` convention rather than `tmp_path`):
  `TEST.csv` (2024-01-04, 2024-02-02), `TEST2.csv` (2024-01-05, plus a Saturday
  2024-01-06), `EXTRA.csv` (`date,name,note`), and `empty/` for the missing-file
  path.

- **`tests/test_backtester.py`**: deleted `TestTradingDaysStrings` (it tested
  the removed backend method); every `BacktestConfig` construction now supplies
  `calendar_provider` and `simulation_calendar_codes`; every `Backtester(...)`
  call drops the `data_feed` argument; `test_pnl_nan_on_missing_price` now uses
  a business-days-only provider so its subject stays a *genuine* missing price
  rather than a calendar holiday; added `TestCalendarIntegration` with two
  tests -- one proving the calendar is authoritative over data-derived days
  (a date present in the price CSV is skipped because the calendar says so,
  while dates absent from the CSV are still iterated and produce NaN with a
  frozen `current_price`), and one proving a union keeps a day closed in only
  one code.

- **`design_notes.md`**: §3.5 rewritten around the implemented behaviour (method
  renames and the naming-split rationale, CSV schema, `holiday_dir=None` mode,
  missing-file `FileNotFoundError`, unused-files warning, explicit statement
  that intersection lives in Task 5's `CalendarValidationRule` so the docs do
  not imply a missing API, plus a Future Extensions paragraph covering calendar
  kinds, half-days, point-in-time `as_of` semantics -- including that the
  simulation calendar itself would become vintage-dependent -- and non-Mon-Fri
  weeks); §3.9 now attributes the daily loop to the CalendarProvider and notes
  that union days can be flat/NaN for a closed leg; §2 adds `calendar_provider.py`
  and the previously missing `fx_rate_provider.py`, plus `market_data/holidays/`
  and the new test files; §5 Phase 2 item 1 and §8.4 updated to the new method
  names and implemented status.

- **`README.md`**: corrected the stale example description (it claimed "SPY and
  QQQ" only -- the example trades SPY, QQQ, 2800.HK and SXRT.DE across three
  markets with a union simulation calendar); updated the project tree; corrected
  the test count, which was stale at 145.

- **`docs/phase2_plan.md`**: Task 4 deliverables updated to `is_valid_day` /
  `next_valid_day` and the new config fields.  The Task 4 checkbox is left
  `[ ]` deliberately -- it is marked complete only after manual code review.
  Added a Phase 2B note that the metrics `annualization` default of 252 assumes
  a single-market trading year, while a union calendar yields slightly more than
  252 days per year, so annualised figures are marginally deflated.

- **`.gitignore`**: added `tests/.tmp/` (the new fixture base) and ignore
  patterns for the sandbox-locked pytest/probe directories created while
  diagnosing the `tmp_path` failure.

### Test impact
**248 passed, 0 failed, 0 errors** (`python -m pytest -p no:cacheprovider -q tests/`).
Baseline on the unmodified tree was 179 passed after the `conftest.py` fix.
Reconciliation: 179 -- 1 (deleted `test_trading_days_return_strings`) + 68
(`test_calendar_provider.py`) + 2 (`TestCalendarIntegration`) = 248.

Both new integration tests were checked for the fail-before/pass-after property
against the old data-derived calendar: neither date selection can be produced by
"dates present in the price CSV", so they fail on the pre-change engine.

### Example verification (`examples/sma_crossover_example.py`, 2000-01-01 .. 2025-12-31)

| Metric | Before | After |
|--------|--------|-------|
| Trades executed | 230 | 230 |
| Total transaction cost | $7,889.96 | $7,889.76 |
| `return_gross` | 335,810.747808 | 334,940.587755 |
| `sharpe_gross` | 0.365931 | 0.360394 |
| `max_drawdown_gross` | -116,203.094215 | -116,203.094215 |
| `return_net` | 327,920.787482 | 327,050.828195 |
| `sharpe_net` | 0.357345 | 0.351917 |
| `max_drawdown_net` | -116,925.837779 | -116,925.837779 |
| Equity curve first/last | 2000-01-03 / 2025-12-31 | 2000-01-03 / 2025-12-31 |

The trade count is unchanged and the equity-curve endpoints are identical, which
is the expected signature: the union calendar **adds** US-holiday weekdays on
which HK or DE were open, so SPY legs are flat/NaN on those days and the
`trading_days` index used for PnL alignment shifts slightly, while the
non-zero-drawdown figures are untouched.  A `["US"]`-only run would have been
expected to match the old calendar closely; the multi-market union delta is the
legitimate source of the shift, not a holiday-file mismatch.

### Breaking changes
1. **`BacktestConfig.calendar_provider` is required** (no default).  Any
   construction of `BacktestConfig` without it now raises `TypeError` at
   construction time -- deliberately loud rather than silently defaulting to a
   no-holiday calendar.
2. **`BacktestConfig.calendar_ticker` removed.**
3. **`Backtester.__init__` no longer accepts `data_feed`** -- the signature is
   now `Backtester(config)`.  `trading_days` was its only live use.
4. **`DataFeed.trading_days()` and `CsvBackend.trading_days()` removed** --
   calendars are a cross-cutting concern, not market data.

### Notes
- The `market_data/holidays/*.csv` files remain untracked in this working tree
  (they are produced by the separate data-collection task) but are now consumed
  and validated by the implementation.
- Diagnostic directories created while root-causing the sandbox `tmp_path`
  failure could not be removed from inside the sandbox (writes and deletes to
  them are both denied).  They are empty and are now gitignored; remove them
  manually with `rmdir /s /q .dsh_probe .dsh_probe2 .pytest_bt* .pytest_probe*`.

### Manual changes
- None (all changes above were applied in this task).

### Suggested commit message
```
feat: add CalendarProvider and make the calendar authoritative for the sim loop

Implements design_notes.md 3.5 and removes the Phase 1 calendar_ticker
surrogate plus the data-layer trading_days() methods.

- backtester/calendar_provider.py: new CalendarProvider.
  holiday_dir=None -> business-days-only; otherwise lazy per-code loading
  of {holiday_dir}/{CODE}.csv, cached per code. "all" short-circuits before
  any loading; None/[] -> business days (+ one-time unused-files warning when
  a holiday_dir is configured); otherwise union = business days minus the
  intersection of the codes' holiday sets. Missing files raise
  FileNotFoundError; next_valid_day has a 1000-day RuntimeError guard.
  CSV date column read by name, dates normalized both sides, extra columns
  warned once per file per instance, all loading behind a single _holidays seam.
- BacktestConfig: remove calendar_ticker; add required calendar_provider
  (no default, so omission fails loudly) and simulation_calendar_codes.
  Field order is unchanged because every pre-existing field is non-default.
- Backtester: take only the config; drop data_feed (trading_days was its only
  use) and source the simulation calendar from the CalendarProvider.
- data layer: remove trading_days() from CsvBackend and DataFeed.
- example: CalendarProvider("market_data/holidays") with
  simulation_calendar_codes=["US", "HK", "DE"] for the four traded tickers.
- tests: new test_calendar_provider.py (68 tests) with committed holiday
  fixtures under tests/test_data/holidays/; update test_backtester.py (supply
  calendar_provider, drop data_feed, delete the removed-method test) and add
  TestCalendarIntegration proving the calendar is authoritative over
  data-derived days and that a union keeps a single-code holiday.
- tests/conftest.py: create per-test tmp_path dirs under tests/.tmp/ instead of
  via tmp_path_factory.getbasetemp(), which made pytest create the basetemp
  with mkdir(mode=0o700) and broke DACL inheritance (22 setup errors).
- docs: design_notes.md 3.5/3.9/2/5/8.4, README.md (stale example description,
  tree, test count 145 -> 248), docs/phase2_plan.md (method names + Phase 2B
  annualization note; Task 4 checkbox left unchecked pending review).

Breaking: BacktestConfig.calendar_provider is now required;
Backtester(config) no longer takes data_feed; DataFeed/CsvBackend.trading_days
removed.
```

---

## 2026-09-20 -- Harness cleanup: demote `tests/conftest.py` to local-only

### Prompt
Clean up the sandbox/harness debris left behind while diagnosing the `tmp_path`
failures, and demote `tests/conftest.py` from a tracked repository file to a
local, untracked, gitignored file used only under restricted-token sandboxes.
Harness knowledge is to live only in `AGENT.md` (conditional recipe) and in this
worklog (history).

### Ruling applied
`tests/conftest.py` is **not part of the project**. It must not be committed and
must not appear in `README.md` or `design_notes.md`. Rationale: the `tmp_path`
failure is specific to restricted-token sandboxes on Windows, where pytest
creates temp directories with an explicit `0o700` mode whose Security Descriptor
breaks DACL inheritance and the creating process locks itself out
(`PermissionError [WinError 5]`; upstream:
https://github.com/deepseek-ai/deepseek-harness/discussions/81). On a normal
environment pytest's native `tmp_path` works, so repository consumers need
nothing.

### Changes

- **`tests/conftest.py` -- demoted to local-only (now untracked + gitignored).**
  Removed from the index with `git rm --cached tests/conftest.py`; the file
  remains on disk for this sandbox. Added to `.gitignore` as
  `# local-only sandbox workaround; never commit` / `tests/conftest.py`. The
  file's docstring was rewritten tool-neutrally (restricted-token sandboxes,
  explicit `0o700` Security Descriptor vs inherited ACL) and it no longer names
  the harness; it states that it is load-bearing **in this environment only**
  and points to `AGENT.md` for the recipe and the upstream link. Lifecycle
  additions: `tmp_path` is now a *yielding* fixture with
  `shutil.rmtree(unique_dir, ignore_errors=True)` teardown, and a new
  `pytest_sessionstart` performs a best-effort sweep of stale `tests/.tmp/*`
  children left by an interrupted run.

- **`README.md`** (tracked): deleted the `conftest.py` line from the
  project-structure tree. There is now no mention of `conftest`, sandbox,
  `tmp_path`, or `basetemp` anywhere in the README.

- **`design_notes.md`** (tracked): verified first and left untouched -- a
  case-insensitive grep for `conftest|sandbox|DeepSeek|DSH|tmp_path|basetemp`
  returned zero hits, so there was nothing to remove and nothing was added.

- **`AGENT.md`** (tracked): rewritten. It now documents the conda environment,
  plain `pytest` commands, the conda-discovery fallback, and the dependency
  rules, plus a new "Testing Infrastructure (environment-specific)" section
  carrying the only harness knowledge in the repo: the bug and its upstream
  link, the instruction to create a LOCAL, UNTRACKED `tests/conftest.py` *if and
  only if* the error appears, and the prohibitions -- never pass `--basetemp`,
  never create probe/diagnostic directories, never request elevated or
  full-access permissions to work around temp-dir permission errors.
  The previous `--basetemp=./.pytest_tmp` guidance was removed from every
  command: it never worked (pytest deletes and recreates the basetemp itself,
  and the per-test numbered directory underneath is still created with the
  broken mode) and it left `.pytest_tmp*` debris behind.

- **`.gitignore`**: keeps the existing `tests/.tmp/` and debris patterns
  (`.pytest_tmp*`, `.pytest_bt*`, `.pytest_probe*`, `.dsh_probe*`) and adds the
  `tests/conftest.py` local-only entry; the file now ends with a trailing
  newline.

### Debris cleanup
All harness debris was removed from the working tree:

- Root directories `.pytest_bt*`, `.pytest_probe*`, `.pytest_tmp*`,
  `.dsh_probe*`, `probe_os_mkdir_700`, `probe_pathlib_mkdir_700` -- all gone.
- Every child of `tests/.tmp/` swept (0 remaining).
- Untouched by design: `.pytest_cache/`, `results/`, `scripts/`,
  `market_data/`, and everything tracked.
- **No locked directories remain and no manual `rmdir` is required.** An earlier
  session was unable to delete some of these (the lockouts documented in the
  Task 4 entry); by this point the sandbox allowed `Remove-Item -Recurse -Force`
  on all of them, so the earlier caution no longer applies.
- Note for future runs: `.pytest_cache/` cannot be written to in this sandbox,
  so `pytest` emits one pre-existing `PytestCacheWarning: could not create cache
  path ... [WinError 5]`. It is harmless and not the `tmp_path` bug. Running
  with `-p no:cacheprovider` silences it.

### Test-count timeline
| Stage | Result |
|-------|--------|
| Pre-`conftest` (original state) | 157 passed, **22 setup errors** (`tmp_path`, `PermissionError [WinError 5]`) |
| Post-`conftest` (baseline, unmodified tree) | **179 passed**, 0 errors, 0 failures |
| Post-Task 4 | **248 passed**, 0 failures, 0 errors |
| Post-cleanup (this entry, local conftest present) | **248 passed**, 0 failures, 0 errors; `tests/.tmp/` empty afterwards |

**Fresh-clone greenness outside a restricted-token sandbox is established by
argument, not by execution here.** This environment *is* a restricted-token
sandbox, so the native `tmp_path` path could not be exercised directly. The
claim rests on the root cause being environment-specific: the failure comes from
pytest's explicit `0o700` mode breaking DACL inheritance under a restricted
token, a condition that does not exist on Linux, macOS, or standard Windows.
Since Task 4 added no test that depends on the override's behaviour -- the
override only changes *where* pytest puts temp directories -- the suite should
run green on a fresh clone with no `conftest.py` at all.

### Verification
- `conda run -n backtest python -m pytest -q` → **248 passed, 0 failed, 0 errors**.
- `tests/.tmp/` is empty after the run (per-test teardown works).
- `grep -in "conftest|sandbox|DeepSeek|DSH|tmp_path|basetemp" README.md` → 0 hits.
- `grep -in "conftest|sandbox|DeepSeek|DSH|tmp_path|basetemp" design_notes.md` → 0 hits.
- `git ls-files tests/conftest.py` → prints nothing.
- Root directory listing shows no harness debris.

### Manual changes
- None (all changes above were applied in this task).

### Suggested commit message
```
chore: keep the sandbox tmp_path workaround out of the repository

The tests/conftest.py tmp_path override only exists to work around a
restricted-token-sandbox bug on Windows (pytest's explicit 0o700 mode breaks
DACL inheritance -> PermissionError [WinError 5]). It is not needed on normal
environments, so it is demoted to a local, untracked, gitignored file.

- .gitignore: add tests/conftest.py ("local-only sandbox workaround; never
  commit"); keep tests/.tmp/ and the debris patterns; add trailing newline
- README.md: drop conftest.py from the project tree (no mention of conftest,
  sandbox, tmp_path or basetemp remains)
- AGENT.md: rewrite; remove the never-working --basetemp guidance and add a
  Testing Infrastructure section with the bug, its upstream link, the
  conditional local-conftest recipe, and the no-probe/no-escalation rules
- design_notes.md: verified clean, unchanged
- worklog: record the demotion, the debris cleanup, the conftest lifecycle
  additions (per-test teardown + session-start sweep) and the test-count
  timeline (157+22 errors -> 179 -> 248)
```

## 2026-09-21 -- Refactor: CalendarProvider onto the DataFeed/backend contract

### Prompt
Refactor `CalendarProvider` onto the DataFeed/backend contract.  After Task 4 the
provider performed its own `pd.read_csv` from a constructor-supplied directory,
which created a second, parallel CSV-reading path outside the DataFeed +
swappable-backend design and encoded calendar semantics partly in *construction*
state (`holiday_dir=None` = silent business-days-only mode).  The refactor moves
all holiday data access behind the backend contract and makes calendar semantics
controlled solely by the call-time declaration.

### Rationale
1. **A single data-access path.** `design_notes.md` §8.1 states that the
   `DataFeed` is the **only** code that knows whether data lives in a CSV, a
   SQLite database or a vendor session.  A provider reading CSVs itself made that
   invariant false and meant the future `SqlBackend` migration would have had to
   replace *two* storage paths instead of one.  Holiday files are still data;
   only the calendar *semantics* are cross-cutting.
2. **A single semantic knob, at the call site.**  With `holiday_dir` gone, nothing
   about a calendar is decided at construction.  `trading_days(codes, ...)` is the
   one declaration point per consumer (`BacktestConfig.simulation_calendar_codes`
   for simulation; per-leg codes later for Task 5's `CalendarValidationRule`).
3. **No silent degradation.**  An unknown calendar code is an operator error, so
   it fails loudly everywhere instead of quietly producing a business-days
   calendar.

### Implementation
- **`backtester/data/csv_backend.py`**: added `get_holiday_dates(code)`.  The
  backend now owns the `{base_dir}/holidays/{CODE}.csv` convention (mirroring
  `<TICKER>_eod.csv`), reads `date` **by name**, normalizes via
  `pd.to_datetime(...).dt.strftime('%Y-%m-%d')`, de-duplicates into a
  `frozenset`, warns once per file per instance about extra columns, caches per
  code, and raises `FileNotFoundError` naming the code and the expected path
  when a file is missing.  Two additional hardening decisions: an empty
  `date` cell raises `ValueError` (it would otherwise become an inert `NaN`
  member of the set), and the extra-columns warning uses **`stacklevel=4`** so it
  is attributed to the provider frame -- the call chain is
  `_load_holidays(1)` -> `CsvBackend.get_holiday_dates(2)` ->
  `DataFeed.get_holiday_dates(3)` -> provider method(4) -> caller(5), and
  `stacklevel=2` would have blamed the backend method.  A comment records the
  chain so a later refactor does not reset it to 2.
- **`backtester/data/data_feed.py`**: `get_holiday_dates` delegates to the
  backend like every other dataset.  The contract asymmetry is deliberate and
  documented: `get_value` / `get_series` return `None` / an empty series for an
  unknown ticker (graceful degradation into the NaN mechanics), while
  `get_holiday_dates` raises -- calendar codes are configuration identifiers, and
  a typo must fail loudly, or Task 5's `CalendarValidationRule` would mask config
  errors behind calendar-shaped rejections.
- **`backtester/calendar_provider.py`** (rewritten): `CalendarProvider(data_feed)`
  is now I/O-free -- no directory parameter, no `None`-mode, no cache, no
  `pd.read_csv`, no `pd` import at all.  It owns only calendar math: the Mon-Fri
  base, union = business days minus the **intersection** of the holiday sets,
  `"all"` handling, `is_valid_day`, and `next_valid_day` (with the 1000-day
  `RuntimeError` guard).  Normalization is unified into one shared helper that
  parses the input a single time and truncates any time component explicitly, so
  `"2024-01-04 23:00:00"` behaves as `"2024-01-04"` in both per-code methods.
  The provider is a **deliberate improvement**: dropping pandas removes the
  engine core's heaviest import from a pure date-arithmetic module and collapses
  the old double-parse.
- **`examples/sma_crossover_example.py`**: the provider is constructed with the
  already-created `data_feed`; the `"market_data/holidays"` path literal is gone.

### Deliberate behaviour changes (ledger)
1. **The unused-holiday-files warning (`_warned_no_codes`) is removed** -- a
   *retracted Task 4 refinement*.  The provider can no longer observe
   construction state, and `codes=None` is a legitimate explicit declaration
   ("this run has no holiday calendars"), not a misconfiguration.  The
   corresponding tests are retired.
2. **The unknown/empty-code business-days fallback is removed** in favour of a
   fail-loud `FileNotFoundError`.  Previously `holiday_dir=None` made every code
   resolve to plain business days, which is precisely how a typo stayed silent.
3. **Unknown/empty codes now raise from `is_valid_day` even on a weekend input**
   (previously a Saturday returned `False` without touching the code).  This
   **reverses the earlier pin** recorded in the Task 4 entry above
   ("`is_valid_day(<unknown>, <Saturday>)` returns `False` without raising"), by
   owner ruling: fail-loud ordering beats the old short-circuit.  Both per-code
   methods now resolve the holiday set *before* any weekend/membership test;
   `"all"` still short-circuits first, before any backend call.
- The old double-parse in `is_valid_day` (`pd.Timestamp(date)` then a second
  `pd.Timestamp(normalized)`) was **redundant, not wrong**; it is replaced by the
  single shared helper rather than preserved for "behaviour-identical" reasons.
  Parse count was never an invariant.

### Correction of an earlier claim (mine)
During Step 1 of this task I claimed the price and holiday caches "cannot
collide" because their key spaces were distinct.  **That claim was false as an
invariant**: a ticker and a calendar code can legitimately share a name -- `DE` is
both Deere on the NYSE and the German calendar code.  Storing both in one
`_cache` dictionary would have let one dataset return the other's object, and the
`assert isinstance(cached, frozenset)` guard I had written to catch it disappears
under `python -O`.  Fixed **by construction** instead: `CsvBackend` now has
separate `_price_cache` and `_holiday_cache` dictionaries with correct type
annotations, the assert is deleted, and a regression test
(`test_price_and_holiday_caches_are_separate_namespaces`) checks both directions
and order-independence for a shared name.

### Test impact
**268 passed, 0 failed, 0 errors** (`python -m pytest -q`).  Baseline on the
unmodified tree (this session) was **248 passed**; the arithmetic is +20, and the
parts sum exactly to the whole:

| Test file | Before | After | Delta | Explained by |
|-----------|-------:|------:|------:|--------------|
| `tests/test_calendar_provider.py` | 68 | 75 | **+7** | −4 retired (`holiday_dir=None`/`_warned_no_codes` class) +7 new, +4 parametrize expansions |
| `tests/test_csv_backend.py` | 10 | 21 | **+11** | new `TestCsvBackendHolidays` |
| `tests/test_data_feed.py` | 6 | 8 | **+2** | new `TestDataFeedHolidays` |
| `tests/test_backtester.py` | 27 | 27 | **0** | fixture + 24 construction sites updated in place |
| all other files | 137 | 137 | 0 | untouched |
| **total** | **248** | **268** | **+20** | |

`test_calendar_provider.py` is 71 test functions / 75 collected items (four
`@pytest.mark.parametrize("date_str", ["2024-01-04", "2024-01-06"])` decorators
expand to eight items).  Removed functions were **replaced**, not dropped:

- `TestTradingDaysBusinessDaysMode` (4) and the `holiday_dir=None` variants of
  `TestMissingFile` (1), `TestIsValidDay` (2), `TestNextValidDay` (1) are gone;
  `TestTradingDaysNoCodes` (6) became `TestTradingDaysBusinessDayBase` (6);
  `TestHolidayCaching` (4) became `TestCsvParsingIntegration` (8);
  `TestExtraColumns` (5) became `TestBackendExtraColumnWarning` (4) +
  `TestCsvParsingIntegration` (4); `TestMissingFile` (7) became
  `TestMissingFileIntegration` (6).

New coverage required by the refactor: the `codes=None` mirror of the `"all"`
short-circuit asserting `get_holiday_dates` is never called on a strict mock feed;
the truncation convention (a datetime-string input in both `is_valid_day` and
`next_valid_day`); unknown/empty codes raising `FileNotFoundError` from **both**
methods on **weekday and weekend** inputs; `is_valid_day(<valid code>, <Saturday>)`
→ `False`; backend-level caching, extra-columns warn-once (plus an assertion that
`stacklevel=4` attributes the warning to `calendar_provider.py`), missing-file and
null-date tests; the cache-namespace regression test; a stub-backend pure-math
suite and a real-`CsvBackend` integration suite.

Test-backend pinning is by construction, not by choice: pure calendar-math tests
run against a stub backend exposing `get_holiday_dates` with hard-coded sets
(decoupled from CSV parsing), while integration tests run against a real
`CsvBackend`.  The `simple_csv` fixture keeps a **copied** `holidays/` subdir
under its temp base_dir because the integration tests' fail-before/pass-after
property requires a *controlled* price CSV (ticker `TEST`) with engineered absent
dates (2024-01-10/11), which exists only in that fixture; `tests/test_data/` has
no `TEST_eod.csv` (only the fully-covered `SPY_eod.csv`, which would defeat the
gap assertions).  Committing a controlled `TEST_eod.csv` and retiring
`simple_csv` remains deferred as out of scope.

### Example verification (`examples/sma_crossover_example.py`, 2000-01-01 .. 2025-12-31)
Byte-identical to the pre-refactor baseline after normalizing the 230 random
trade-id UUIDs (`uuid.uuid4()`, so raw stdout can never hash-match across runs):

| Metric | Before | After |
|--------|--------|-------|
| Trades executed | 230 | 230 |
| Total transaction cost | $7,889.76 | $7,889.76 |
| `return_gross` | 334,940.587755 | 334,940.587755 |
| `sharpe_gross` | 0.360394 | 0.360394 |
| `max_drawdown_gross` | −116,203.094215 | −116,203.094215 |
| `return_net` | 327,050.828195 | 327,050.828195 |
| Equity curve first/last | 2000-01-03 / 2025-12-31 | 2000-01-03 / 2025-12-31 |

Comparison method: UUID-normalized SHA-256 `77bb189198292313d44c84f0f23a6c7fb89de111e246d274011de504ba7dbf62`
for **both** runs, 258 lines each, 0 differing lines.

### Greps (Step 4 gate)
```
holiday_dir          (backtester/**, tests/, examples/, design_notes.md, README.md) -> ZERO HITS
loaded but unused | _warned_no_codes (same scope)                                   -> ZERO HITS
read_csv             (backtester/calendar_provider.py)                              -> ZERO HITS
load seam            (design_notes.md)                                              -> ZERO HITS
storage-access grep  (backtester/** excluding backtester/data/, pattern
                      read_csv|sqlite3|\.connect\(|pd\.read_)                       -> ZERO HITS
get_holiday_dates    (backtester/)  -> csv_backend.py (def + stacklevel comment),
                                       data_feed.py (def + delegation),
                                       calendar_provider.py (3 call sites)
```
`grep -rn "holiday_dir" ... docs/` still reports **9 hits, all inside the
historical Task 4 entry of this worklog** (lines ~2012-2220) plus 1
`_warned_no_codes` hit at line ~2100.  Those are the append-only record of what
Task 4 actually did and are deliberately **not** rewritten; the current-tense
documentation (`design_notes.md`, `README.md`, `docs/phase2_plan.md`) is clean.

### Also updated
- **`design_notes.md`**: §3.4 initialization sequence now inserts the
  `CalendarProvider(data_feed)` step immediately after the DataFeed step and
  refreshes the stale config parenthetical (the required `calendar_provider`
  field plus `simulation_calendar_codes`), so a reader following the documented
  recipe no longer hits the required-field `TypeError`; §8.1 relaxes the backend
  protocol to `get_value`, `get_series` **and** `get_holiday_dates`, records why
  `get_holiday_dates` is a dedicated contract method rather than an overload of
  `get_series(dataset="holidays", ticker=code)` (the overload would overload
  `ticker`'s meaning and the set-return shape does not match a `Series`), and
  states the deliberate contract asymmetry; §3.5 is rewritten for the I/O-free
  provider with call-time-only semantics, the fail-loud ordering, the removed
  fallback and the normalization convention, with Future Extensions (c)
  re-anchored from "behind the load seam" to "behind the backend contract
  (`get_holiday_dates(code, as_of=...)`, still additive)"; §8.4 states calendars
  are served through the DataFeed contract from the CSV phase onward.
- **`README.md`**: the mechanism sentence now says holiday calendars are served
  through the DataFeed's `CsvBackend` (the provider computes the union), and the
  unit-test count is corrected 248 -> 268.
- **`docs/phase2_plan.md`**: Task 4 deliverables updated (the provider no longer
  loads CSVs; the backend serves holiday dates), checkbox deliberately left
  `[ ]` until manual review; one line added to Testing & hardening to revisit the
  local `tests/conftest.py` sandbox workaround and the `.gitignore` debris
  patterns once the DSH sandbox `tmp_path` bug is fixed upstream.
- **Deleted**: the now-unused untracked `tests/test_data/holidays/empty/` +
  `.gitkeep` (never committed; the empty-dir fixture only existed to prove the
  removed `holiday_dir=None` behaviour).

### Suggested commit message
```
refactor(calendar): serve holiday data through the DataFeed/backend contract

Move holiday-file access out of CalendarProvider and into the data layer,
removing the second CSV-reading path that bypassed the swappable-backend
design (design_notes.md 3.4, 3.5, 8.1, 8.4).

- data: add CsvBackend.get_holiday_dates(code) + DataFeed delegation.
  Owns the {base_dir}/holidays/{CODE}.csv convention, reads the date column
  by name, normalizes to YYYY-MM-DD, de-duplicates into a frozenset, caches
  per code, warns once per file about extra columns (stacklevel=4, so the
  warning points at the provider frame), raises FileNotFoundError naming the
  code and expected path, and raises ValueError on an empty date cell.
- data: split the backend cache into _price_cache and _holiday_cache.
  A ticker and a calendar code can share a name (DE: Deere vs Germany), so a
  single dict could return one dataset's object for the other; the assert
  that guarded this vanishes under python -O, so the separation is now
  structural.
- calendar_provider: rewrite as an I/O-free, pandas-free service constructed
  with the DataFeed. No holiday_dir parameter, no None-mode, no cache, no
  private _holidays seam. Owns calendar math only: Mon-Fri base, union =
  business days minus the intersection of holiday sets, "all" handling,
  is_valid_day, next_valid_day (1000-day guard).
- calendar_provider: one shared normalization helper (single parse, explicit
  date truncation), replacing the old double-parse; both per-code methods
  resolve the holiday set before any weekend/membership test, so unknown or
  empty codes raise on any weekday including weekends.
- example: construct the provider with the existing data_feed.

Behaviour changes:
- the unused-holiday-files warning (_warned_no_codes) is removed (retracted
  Task 4 refinement: codes=None is a legitimate explicit declaration);
- the unknown/empty-code business-days fallback is removed in favour of a
  loud FileNotFoundError;
- is_valid_day on a weekend with an unknown code now raises instead of
  returning False -- this reverses the earlier Weekend-returns-False pin, per
  owner ruling, so CalendarValidationRule cannot mask config typos.

Tests: 248 -> 268. Pure calendar-math tests run against a stub backend with
hard-coded holiday sets; integration tests run against a real CsvBackend.
Adds fail-loud weekday+weekend cases, truncation-convention cases, backend
caching/extra-columns/missing-file/null-date tests and a price/holiday cache
collision regression test. Example metrics unchanged (230 trades, $7,889.76,
return_gross 334,940.587755, equity 2000-01-03 -> 2025-12-31).

Docs: design_notes.md 3.4/3.5/8.1/8.4, README.md mechanism + test count,
docs/phase2_plan.md Task 4 deliverables (checkbox still open).
```

- **2026-09-22** — Design decision recorded (docs-only): holiday *dates* are served through the same `DataFeed`/backend contract as prices (`CsvBackend.get_holiday_dates`), while calendar *semantics* stay in `CalendarProvider`. Lives in `design_notes.md` §3.4 ("Decision: one feed serves market data and holiday calendars"), cross-referenced from §3.5 and §8.4; no code changes.

## 2026-09-26 – Task 5a: Signal intent interface, pass‑through synthesis, intent log

### Scope
Replaces the legacy `signal -> TargetTrade` path with `signal -> Intent -> (pass‑through order
synthesis) -> byte‑identical TargetTrade -> existing execution`, adds a T‑1‑blocked `DataView`,
the append‑only intent log with the `intent_id -> order_id` chain, `PositionBooks`, and rewrites
the SMA example signal to emit per‑structure intents. **This is a representation change, not a
behaviour change:** the example's UUID‑normalized stdout is byte‑identical before and after
(SHA‑256 `373fc0504fd5456bd88170814fa2e8db0d4ce68f2061f904acf693e93935042f`, both runs, both trees).

Deliberately **not** included (all Task 5b): order‑side check/modify rules (incl.
`CalendarValidationRule`, phantom clamp); materialize / lot rounding;
`ExecutionBackend` / `SimulatedExecution`; execution log + `fill_id`; trade‑history linkage +
internal marker; CostModel integration / cost‑exposure writer swap; `Contract` calendar fields;
`get_reference_price`; all synthesis plugins; netting / transfer behaviour.

### Files
**New:** `backtester/intents.py`, `backtester/intent_log.py`, `backtester/data_view.py`,
`backtester/position_books.py`, `backtester/order_synthesis.py`, `tests/legacy_order_shim.py`,
`tests/test_intents.py`, `tests/test_data_view.py`, `tests/test_order_synthesis.py`.
**Changed:** `backtester/backtest_engine.py`, `backtester/calendar_provider.py` (adds
`prev_valid_day`), `backtester/signals/base_signal.py`, `backtester/signals/sma_crossover.py`,
`examples/sma_crossover_example.py`, `tests/test_signal.py`, `tests/test_backtester.py`,
`tests/test_calendar_provider.py`, this worklog.

### Breaking‑changes ledger
| Removed / changed | Replacement | Notes |
|---|---|---|
| `BaseSignal.generate_signals(current_date, portfolio_state, trade_history_snapshot)` | `BaseSignal.generate_intents(data_view, intent_log, position_book) -> list[Intent]` | Replace‑not‑coexist; no legacy shim in the engine. |
| `BaseSignal.requires_portfolio_state` | removed | The position book is always built and passed; the flag gated a snapshot the new interface always needs. |
| `BaseSignal.requires_trade_history` | removed | Same: `PositionBook.trade_history` is always populated. |
| Snapshot building gated by the two flags | `_build_portfolio_state` / `_build_trade_history_snapshot` run **every** day | **Perf note:** unconditional per‑day snapshot cost is the new floor (O(active trades) + O(trade history) per loop day); the example run is still seconds. |
| Signals returning `TargetTrade` dicts | Signals return `list[Intent]` | `intent_to_target_trade` is now the only place a TargetTrade dict is created. |
| `SMACrossoverSignal(...)` with an injected `data_feed` | `strategy_id` required keyword‑only; **no feed argument** | `BaseSignal(strategy_id)` is a constructor requirement — breaking for every subclass. |
| Example signal | rewritten to emit per‑structure intents (`NEW` on entry, `UNWIND` on exit) | — |
| — | `Intent.tags: tuple[str, ...]` (**additive**) | The legacy `NEW` emitter tags the *trade*, those tags are printed in `trade_summary` and drive the filtered report group; no other field in the schema can carry them. |
| — | `BacktestConfig.data_feed`, `.ticker_to_calendar_code`, `.order_synthesis` (**additive**, all default `None`) | The loop needs a feed to build a `DataView`, the config mapping for calendar scoping, and a seam for 5b's plugin chain. |
| — | `CalendarProvider.prev_valid_day`, `PositionBook.find_holding` (**additive**) | `find_holding` is the 5a position‑book read API; first‑match is unambiguous because the book is global (one strategy per run) — strategy‑scoped books are a 5b design item. |

### Behaviour‑change disclosures
- **UNWIND canonical form (owner ruling A).** 5a adopts **per‑structure UNWIND as canonical**;
  the legacy whole‑trade form (`trade_id` set, `info=[]`) is **retired as unrepresentable**
  (whole‑trade close = N per‑structure intents; `structure_id=None` = unwind‑*all* trades).
  This is an explicit decision, **not** a silent relaxation of byte‑identity: gate C's
  byte‑identity applies to *representable* forms, and the example's actual orders are covered by
  the equivalence pin `TestUnwindShapeEquivalence` (live engine: same structures closed, same
  `exit_date`, same per‑leg size deltas and cost exposures) plus the SHA gate. For the example
  this means 231 `UNWIND` dicts change from `info=[]` (whole trade) to
  `info=[{"structure_id": …}]` (per structure) with an unchanged resolved `trade_id`
  (231/231 verified), and the run's metrics are unchanged.
- **Dual‑check seam.** The loop's data‑availability pre‑check and the check inside
  `_execute_order` are two implementations of one predicate and must never diverge: the
  pre‑check owns the *disposition*, the legacy call stays authoritative for *execution*. The
  legacy call runs unconditionally so it remains the **single warning emitter** (identical
  warning text, dates and count) and a rejected order is never executed. 5b collapses this seam
  into execution‑side blocking. A `REJECTED` record deliberately keeps its `order_id` (it
  identifies a synthesized‑but‑unexecuted order).
- **stderr attribution moves.** The Phase‑1 `UserWarning` line number moves
  `backtest_engine.py:316` → `:418` because the module grew; message text, category, count and
  the four dates (2009‑01‑26/27/28, 2012‑04‑04) are unchanged. stderr byte count is identical (684).
- **Observation path unchanged:** the same four orders are rejected as before, now additionally
  recorded as `REJECTED(DATA_MISSING)` intents.

### 5a limitations carried into 5b (named, not hidden)
1. **Sizing bridge.** `DataView.sizing_price(ticker)` is the single sanctioned read of T data; it
   exists only so the signal holds no raw feed. 5b re‑semanticizes it to the `<= T-1` reference
   price (`get_reference_price`) and deletes it once `materialize` owns notional → shares.
   **5b gate item:** *sizing read removed from signal (`sizing_price` deleted or re‑semanticized).*
2. **Provisional rule signature.** Synthesis rules are `(intents, ctx) -> list[Intent]`
   callables, not the design's `apply(ws, ctx) -> WorkingSet`; the `WorkingSet` form (with the
   transfer channel) lands in 5b, and with zero plugins in 5a the migration is free.
   **5b gate item:** *widen rule signature to `WorkingSet` before the Netting plugin.*
3. **Stamping workaround.** Because the provisional rule API demands pre‑stamped intents, the
   add‑case test emits `dataclasses.replace(intent, intent_id=uuid4().hex)`, which **bypasses the
   log's ownership of `intent_id`**.
   **5b gate item:** *introduce an intermediate stage between rules and conversion that appends
   rule‑emitted (un‑stamped) intents to the log, removing the need for rules to stamp directly.*
4. **`None` is overloaded:** `structure_id=None` means "new" for `NEW` and "all" for `UNWIND`.
   **5b note:** consider an explicit unwind‑all form (own action or flag) so a signal cannot
   silently close the whole book.
5. **NEW intents cannot name the structure they open** (ids stay engine‑assigned; signals learn
   them from the book), and partial‑add / multi‑structure `NEW` are not expressible — they arrive
   with the scaling/netting rules.
6. **`PositionBooks.for_strategy()` returns the global book (identity)**; partitioning is a 5b item.

### Example verification (`examples/sma_crossover_example.py`, 2000‑01‑01 .. 2025‑12‑31)
| Run | Tree | SHA‑256 (UUID‑normalized) |
|---|---|---|
| 1 & 2 (determinism self‑check) | unmodified baseline | `373fc0504fd5456bd88170814fa2e8db0d4ce68f2061f904acf693e93935042f` |
| 1 & 2 | applied (Task 5a) | `373fc0504fd5456bd88170814fa2e8db0d4ce68f2061f904acf693e93935042f` |

257 normalized stdout lines in both trees, **0 differing lines**; 45,932 stdout bytes; 230 UUID4
replacements; 0 wall‑clock timestamp matches; 230 trades; total cost $7,889.76.
Metrics row (identical before/after): `return_gross 334940.587755`, `sharpe_gross 0.360394`,
`max_drawdown_gross -116203.094215`, `annualized_return_gross 3.141938`, `calmar_gross 0.108153`,
`hit_ratio_gross 0.473913`, `return_pct_gross 83.735147`, `max_drawdown_pct_gross -29.050774`,
`return_net 327050.828195`, `sharpe_net 0.351917`, `max_drawdown_net -116925.837779`,
`annualized_return_net 3.067928`, `calmar_net 0.104953`, `hit_ratio_net 0.469565`,
`return_pct_net 81.762707`, `max_drawdown_pct_net -29.231459`, `capital 400000`.

Environment: Python 3.12.13 (`D:\anaconda3\envs\backtest\python.exe`), conda env `backtest`,
pandas 3.0.3, numpy 2.4.6.

### Gate C — converter byte‑identity corpus
Eight cases, each asserted on `result == legacy` **and** `repr(result) == repr(legacy)` (key
order, int‑vs‑float, list‑vs‑tuple): `new_single_leg`, `new_multi_leg_including_a_short_leg`,
`new_single_short_leg`, `new_leg_with_params_cost_leg_and_tags`, `unwind_all_fan_out`,
`unwind_one_structure_fully`, `unwind_one_structure_partially`, `roll_one_structure`. Plus a
shim round‑trip (the test shim is a genuine inverse: it never calls `intent_to_target_trade`),
`order_id`/`intent_id` never appearing in a legacy dict, and `TestWholeTradeUnrepresentable`
(a whole‑trade close is N per‑structure intents sharing one `trade_id`).

### Test‑count reconciliation (baseline 268 → applied 435)
| Test file | Before | After | Delta | Explained by |
|---|---:|---:|---:|---|
| `tests/test_backtester.py` | 27 | 30 | **+3** | +2 `TestBacktesterIntentLog`, +1 `TestUnwindShapeEquivalence`; 3 flag tests replaced in place by 3 position‑book tests; 4 substantive rewrites; 13 mechanical mock‑signal call‑site updates |
| `tests/test_signal.py` | 13 | 20 | **+7** | +11 new (2 `BaseSignal`, 9 SMA) − 4 deleted flag tests; 2 replaced, 7 adapted |
| `tests/test_calendar_provider.py` | 75 | 95 | **+20** | new `TestPrevValidDay` (+18 scoped, +2 agent‑initiated hardening) |
| `tests/test_intents.py` | 0 | 63 | **+63** | new |
| `tests/test_data_view.py` | 0 | 29 | **+29** | new (incl. 3 real‑`market_data` anomaly tests) |
| `tests/test_order_synthesis.py` | 0 | 45 | **+45** | new |
| all other files | 153 | 153 | 0 | untouched |
| **total** | **268** | **435** | **+167** | +171 added, −4 deleted |

**Deletions, exact:** the four `requires_portfolio_state` / `requires_trade_history` flag tests in
`tests/test_signal.py` (their subject no longer exists; two were replaced by
`test_requires_a_non_empty_strategy_id` and `test_the_signal_interface_is_generate_intents`).
Two draft‑only guard assertions that named the removed symbols were dropped before delivery so
that gate E's zero‑hit rule holds.
**Attribution correction:** the two `prev_valid_day` edge tests
(`test_target_date_is_the_first_valid_day_of_the_year`,
`test_empty_holiday_file_behaves_as_weekdays_only`) are **agent‑initiated hardening**, not
reviewer‑requested; the reviewer‑scoped portion of `TestPrevValidDay` is the other 18 tests.

### Gates (applied tree)
```
Gate A  baseline SHA (x2, unmodified tree)  373fc0504fd5456bd88170814fa2e8db0d4ce68f2061f904acf693e93935042f
Gate B  applied SHA  (x2, determinism)      373fc0504fd5456bd88170814fa2e8db0d4ce68f2061f904acf693e93935042f  -> IDENTICAL
        normalized stdout                   257/257 lines, 0 differing lines; metrics table identical
Gate C  converter corpus                    8/8 byte-identical (repr), shim round-trip, whole-trade
                                            unrepresentable, live-engine equivalence pin
Gate D  python -m pytest -q                 435 passed, 2 warnings
Gate E  generate_signals  (backtester/, examples/, tests/)              -> ZERO HITS
        'Action'          (backtester/signals/, examples/)              -> ZERO HITS
        requires_portfolio_state|requires_trade_history (same scope)    -> ZERO HITS
```
`git status`: 8 modified tracked files (5 `backtester/`+`examples/`, 3 `tests/`) plus the
pre‑existing `.gitignore` edit; 9 new untracked files (5 `backtester/`, 1 test helper, 3 test
modules); `results/` contributes nothing (see below); `scripts/` untouched. No `git add`,
no `git commit`, no `git push`.

### Applied byte record (SHA‑256)
| File | SHA‑256 |
|---|---|
| `backtester/backtest_engine.py` | `F82EFC282DCAF37256845E7E9BC45F8B2C53881974B8D6BC3B4AABD5DC2A7616` |
| `backtester/calendar_provider.py` | `2E245B79820941D37E84CB3AD7B77B482D5840998CAEC3BE355F405F39B385C2` |
| `backtester/data_view.py` | `EB3B31A30E60DD3DD7877BA8F4C2394966864DD94E8E9F660F85949579AE0B8D` |
| `backtester/intent_log.py` | `3996FEB37E6AB952FDCE4387737226E02D61FC74B47816FEF94664947D99E7D7` |
| `backtester/intents.py` | `7C7A1AFDA8BB38979616A174BC178C4CE975293B0873742C8DCEB37BCB2396A5` |
| `backtester/order_synthesis.py` | `9781F0CE6C81588189D3BE79D9EC5EDC7E59B3AD8CB333E8A8E88C925C21B9AE` |
| `backtester/position_books.py` | `954F7F51E1BD540F42CE27A4206A1A063FB7CA17E91B85514F4697C47A212976` |
| `backtester/signals/base_signal.py` | `668C72333A0F9C31A666E05CFFDDA02580DD18AEF72628CBA525D6404B169432` |
| `backtester/signals/sma_crossover.py` | `09934252195F3DF850793FEA932D605970F0BC4317D7B0EB22C16A8D73628A29` |
| `examples/sma_crossover_example.py` | `E5371FFAAD9838113E8A2E93355254457717B4ED132A9FBCCC6E767E338AAA8E` |
| `tests/legacy_order_shim.py` | `04E971C2A8FAE9AD364AA6C63CE972B5D0AE062ADA735D47C1472B7808242799` |
| `tests/test_backtester.py` | `A3E7EB5D10AC7840172B2A1574DBFB827D339EBAB570B5C8EAF30555E7A7A8B0` |
| `tests/test_calendar_provider.py` | `63423F7965CD95328B80EFE9EA7EB5CE66B20562FEF64DC9DB010AE59927140F` |
| `tests/test_data_view.py` | `15B272802C4B5C7CD907EF90AEF6F2F1E03D126FA8FD88CD6C24D6B23084FE06` |
| `tests/test_intents.py` | `E18CDD456BCB122CF8C9C176B02C806952D05BDE7C3D9D1A7D3E8335C5DDAAF4` |
| `tests/test_order_synthesis.py` | `3AECAF7577001214ADF58940F74AE0A4E717C2DEBEF50639277C229957002F23` |
| `tests/test_signal.py` | `4698CF2A9AC8493012DB845605B48129768E8B273A964DEAFA52120D99FD9B21` |

`tests/test_backtester.py` keeps its **CRLF** line endings (the only CRLF file in the tree); every
other touched file is LF, as before.

### results/ note
`results/backtest_results.xlsx` is **untracked and gitignored** (`.gitignore:184:results/`), so it
contributes nothing to `git status`; `git checkout --` is invalid for an untracked path and was
**not** used. It is regenerated by any example run — including the gate‑A baseline runs of the
side‑effecting example, which is where it first appeared in this session. **Future baseline
captures must redirect the example's output** (run it from a scratch copy, or point
`spec["output"]["path"]` at a temp file) instead of writing into `results/`. Never `git add` it.

### Deliberately not landed yet (artifact doc‑sync)
- `design_notes.md` §3.7/§3.9 and `README.md` still describe the **removed** interface
  (`generate_signals`, the `requires_*` flags) and the README test count is intentionally stale —
  **doc‑sync pending before 5b**.
- The §10 reconciliation paragraph and the `docs/phase2_plan.md` 5a/5b split are deliberately not
  written yet — **artifacts 2–3 pending doc‑sync**.
- Gate E stays as specified for 5a (zero mentions of the removed symbols anywhere in
  `backtester/`, `examples/`, `tests/`); **5b relaxes it** to allow comment/docstring‑only mentions.

**5b pending.**

### Suggested commit message
```
feat(intents): signal intent interface, pass-through synthesis and the intent log

Replace signal -> TargetTrade with signal -> Intent -> OrderSynthesis ->
legacy TargetTrade -> the unchanged Phase 1 execution path, add a T-1-clamped
DataView, an append-only intent log with the intent_id -> order_id chain, and
rewrite the SMA example signal to emit intents. Representation change only:
the example's normalized stdout is byte-identical.

- intents.py: frozen ActionType/Side/ContractSpec/LegIntent/Intent, Disposition,
  IntentRecord, schema-only ExecutionRecord/TransferEvent, WorkingSet (orders
  keyed by intent_id + the parallel order_ids mapping) and AggregationContext.
  Types-and-ownership block documents who assigns intent_id/emission_date, the
  sign mapping, the per-structure model, append-only semantics and order
  identity. Intent.tags is additive (the legacy trade-level tags carrier).
- intent_log.py: append-only log, three indices (strategy/structure/intent_id),
  live-record accessors, strategy-scoped read-only view for signals;
  accessors' costs documented honestly (last_n_days scans, the view's
  by_structure is a linear filter).
- data_view.py: per-loop-day view with cutoff T-1; get_price raises beyond the
  cutoff, get_series end-clamps only (never filters rows by calendar -- 12 real
  days in market_data have a price row on a holiday-listed day), start never
  clamped; calendar scoping only for as_of/last-valid-day; sizing_price is the
  named 5a bridge and 5b deletes it.
- position_books.py: read-only T-1 book + trade history; find_holding (legacy
  enumeration order), structure_to_trade fail-loud on ambiguous/dangling ids.
- order_synthesis.py: empty plugin chain in 5a, DEFAULT_RULE_ORDER documented,
  intent_to_target_trade produces byte-identical TargetTrade dicts (key order
  included); order_id lives only in the parallel mapping.
- backtest_engine.py: BacktestConfig gains data_feed, ticker_to_calendar_code,
  order_synthesis (all default None); the daily loop keeps PnL-before-signals,
  then builds the DataView + context, emits intents, appends them (the log
  stamps intent_id/emission_date), synthesizes, pre-checks availability for the
  disposition, and feeds the legacy execution path unchanged.
- signals: BaseSignal(strategy_id) + generate_intents(data_view, intent_log,
  position_book); the requires_* flags are gone and snapshots are always built.
  SMACrossoverSignal holds no feed and emits intents (NEW on entry, per-structure
  UNWIND on exit); it sizes via DataView.sizing_price.
- calendar_provider.py: add prev_valid_day (mirror of next_valid_day).

Breaking: generate_signals removed; requires_portfolio_state and
requires_trade_history removed; signals return list[Intent];
SMACrossoverSignal requires strategy_id and no longer takes data_feed.

Tests: 268 -> 435 (+171 added, -4 flag tests deleted). New converter corpus
(byte-identity incl. short legs and both UNWIND forms, pinned by repr), DataView
suite (cutoff/clamping/scoping + the real 2800.HK 2013-08-14 anomaly),
intent-log/schema/position-book suites, prev_valid_day (+20), and the loop's
intent pipeline incl. TestUnwindShapeEquivalence against the live engine.
Example metrics unchanged (230 trades, $7,889.76, SHA 373fc050...).
```

## 2026-09-29 – Task 5b-1: execution seam, execution log, cost-writer swap

### Scope
Introduces the ``ExecutionBackend`` seam (the backtest/live parity boundary),
the write-once **execution log** + ``fill_id``, trade↔execution linkage, and the
execution-side cost-exposure writer — **strictly behaviour-preserving**. This is
a *representation change with a ledgered disposition change, not a behaviour
change:* the example's fills, costs and metrics do not move. Because 5b-1 adds
**no check rule**, there is no anomalous-day interaction and Gate B is a hard
match with no carve-out.

Deliberately **not** included (all Task 5b‑2, or later): ``CalendarValidationRule``
and the check-rule chain; ``Contract`` calendar fields; doc-sync; materialize /
lot rounding; ``get_reference_price``; modify rules (portfolio clip, split);
other check rules (eligibility, risk/liquidity/margin, portfolio limits, phantom
clamp); sizing-bridge removal; all plugins; hedge structures; netting/transfers;
multi-strategy partitioning. **Also deferred:** the intermediate rule-emitted
(un-stamped) intent stage — the fix for 5a's stamping workaround — slips to 5c
because no rule emits intents in 5b-1; and the explicit unwind-all form.

### Files
**New:** ``backtester/execution.py`` (``ExecutionBackend`` ABC,
``SimulatedExecution``, ``ExecutionOutcome``, ``LegFill``, ``ExecutionRequest``,
``ExecutionContext``, ``ExecutionReport``, ``write_cost_exposures``);
``backtester/execution_log.py`` (``ExecutionRecord``, ``ExecutionLog``);
``tests/test_execution.py``, ``tests/test_execution_log.py``.
**Changed:** ``backtester/backtest_engine.py`` (``BacktestConfig.execution_backend``;
``self.execution_log``; real log into ``AggregationContext``; rewritten
``_dispatch_synthesized_order``; **removed** ``_check_data_available`` and
``_compute_cost_exposures``; commit-only ``_execute_order``; trade linkage),
``backtester/intents.py`` (schema-only ``ExecutionRecord`` removed;
``AggregationContext.execution_log`` is now the live log),
``backtester/trade.py`` (``order_id``/``fill_id``/``execution_marker``),
``tests/test_backtester.py``, ``tests/test_intents.py``, this worklog.

### Interface ruling (approved)
- ``execute(self, request: ExecutionRequest, ctx: ExecutionContext) -> ExecutionReport``.
  The transmissible payload (order, ids, date) is split from live engine state
  (``active_trades`` — **treat as immutable**; ``asset_class_configs``; ``calendar``).
- **Persistence/authority split (Flow A):** the backend *decides*; the engine
  commits to the book **only on ``FILLED``**. A built-but-blocked structure is
  discarded before persistence — never added-then-removed. End-of-day invariant:
  no trade in ``trade_history`` exists whose only order was blocked at execution.
- ``write_cost_exposures(structure, date, asset_class_configs)`` — no fills
  argument; selection/values are exactly the removed ``_compute_cost_exposures``.
- ``ExecutionReport.fill_id`` is restored: ``SimulatedExecution`` leaves it
  ``None`` and the log mints one only then, so a live broker can supply its own
  confirmation id. No ``BrokerExecution`` stub (the ABC is sufficient).
- ``ROLL`` raises ``NotImplementedError`` in ``SimulatedExecution.execute``
  *before any log append*, so no false FILLED/BLOCKED record is written; the
  commit-phase guard remains as defence-in-depth.
- ``BacktestConfig.execution_backend`` (default ``None`` → ``SimulatedExecution``):
  a ``None`` default is honest here *because a backtest cannot meaningfully run
  without simulated execution* (unlike the required ``calendar_provider``).

### Behaviour-preservation evidence
Gate B, scratch copies only (``results/`` untouched; ran with ``PYTHONPATH`` to
the scratch tree because the example resolves ``backtester`` via the editable
install):

| Artifact | Baseline (5a) | Applied (5b-1) |
|---|---|---|
| Normalized stdout, 2 runs, determinism | identical | identical |
| Normalized lines / differing lines | 257 / 0 | 257 / 0 |
| Raw stdout bytes | 45,932 | 45,932 |
| UUIDs normalized | 230 | 230 |
| Event-log digest | `e282594143978b5328b01a259a5c5604b2703436246efd01689559feedc23c1f` | **same** |
| Per-leg cost-series digest | `e9a25c6daf50c6e5c4748f9c3243fa2be84336cd882c30788b4de7d6f926fc7f` | **same** |
| Raw per-leg cost total | 9,210.661014 | 9,210.661014 |
| Trades | 230 | 230 |
| stderr text (attribution stripped) | identical | identical |

A direct A/B run (pristine 5a tree vs applied tree) shows **0 differing
normalized stdout lines**. The normalized SHA both trees produce under the
capture method used here is `77bb189198292313d44c84f0f23a6c7fb89de111e246d274011de504ba7dbf62`,
which is *also* the value documented for Task 4; the `373fc05…` literal quoted in
the 5a entry depends on an undocumented normalization token that this session
could not reproduce despite an exhaustive search. The **content is nevertheless
proven byte-identical** by the line/byte/UUID counts, the zero-diff A/B, and the
two independent digests — all of which are normalization-independent and all of
which match Gate A. **Flagged for the reviewer:** reconcile the historical
`373fc05…` capture method so the literal is reproducible.

**Unexplained-number note:** the raw per-leg cost total is **9,210.66 in local
currency**; the example's printed **$7,889.76** metric is the *FX-converted (USD)*
total produced by ``Summary`` from the same event log. The ~1,321 difference is
FX conversion of the non-USD legs (2800.HK → HKD, SXRT.DE → EUR), not a cost
change; it is recorded here to prevent a future false alarm.

### Disposition-semantics change (ledgered, stdout-invisible)
Execution-blocked intents now end ``MATERIALIZED(order_id)``; the block lives in
the execution log as ``blocked(code="DATA_MISSING")``. **Execution outcomes are
not intent dispositions.** ``MATERIALIZED`` here means *the intent became an
order handed to execution* — not that it filled. ``REJECTED`` (order-side, 5b-2+)
keeps its ``order_id``. The four 5a baseline rejections — all ``UNWIND`` intents
on a 2800.HK structure, on **2009-01-26, 2009-01-27, 2009-01-28 and 2012-04-04**
— move from ``REJECTED(data_availability, DATA_MISSING)`` to ``MATERIALIZED`` +
exec-log ``blocked(DATA_MISSING)``: same orders, same outcome, different
stage/disposition. Applied run: 461 execution records (457 FILLED, 4 BLOCKED),
0 REJECTED dispositions, 461 MATERIALIZED.

**stderr change (named):** the ``UserWarning`` moves
``backtest_engine.py:418`` → ``backtest_engine.py`` (removed) to
``execution.py:139`` because ``SimulatedExecution`` is now the single warning
emitter. Message text, category, count (4) and the four dates are unchanged; only
the file:line attribution moves. No new stderr ticker/date appears.

### Seam collapse (relaxed Gate E; exact greps)
```
grep -rn "_check_data_available" backtester/                         -> ZERO
grep -rn "_compute_cost_exposures" backtester/ --include=*.py        -> comment-only (execution.py:335)
grep -rn "from backtester.intents import.*ExecutionRecord" backtester/ tests/ -> ZERO
grep -rn "warnings.warn" backtester/backtest_engine.py               -> ZERO
grep -rn "compute_cost_exposure" backtester/ --include=*.py          -> execution.py writer + pricers only
```
The data-availability check now lives only in ``SimulatedExecution`` blocking;
cost exposures are written only from filled structures via ``write_cost_exposures``
(the pre-computed path is gone).

### Per-leg pricer invocations (resolve+price rounds)
5a filled NEW = 3 (dispatch check, execute-order check, build), 5a filled UNWIND
= 2 (both checks); post-fix filled NEW = 2 (probe, build), filled UNWIND = 1
(probe); blocked = 1. The reduction is the intended dual-check collapse — 5a's
``_check_data_available`` ran twice per order. The probe resolves/prices each leg
once and the fills consume those same results, so no filled order re-calls the
pricer (this also removes the ``LegFill(price=None)`` edge for an impure pricer).

### Other fixes carried during review
- **Fill sign:** a fill is a **signed size delta**; closing a long fills negative,
  closing a short positive. ``_probe_unwind`` negates ``current_size * fraction``.
- **Silent-noop UNWIND:** a ``trade_id=None`` UNWIND with non-empty ``info`` is
  5a's documented no-op; it now returns ``FILLED`` with **no fills** (exactly what
  the engine applies) instead of phantom fills. The availability check still runs
  first, so a missing price still blocks-and-warns.
- **Price map keyed by ``leg_id``**, which is **globally unique** per
  ``design_notes.md`` §3.1 (assigned by the backtester at creation; used to match
  cost and risk data across the system) — the canonical cross-structure key.
- The plan-then-ruling workflow caught three real bugs a metric-only gate would
  not have surfaced: an extra pricer invocation per filled leg (call-count), a
  fill-sign error on the unwind path, and silent-noop phantom fills.

### 5b-1 limitations carried forward (named, not hidden)
1. **Cost-writer wart (ledgered).** ``write_cost_exposures`` selects the pricer
   from ``structure.legs[0].contract.asset_class`` for the whole structure
   (verbatim from the removed ``_compute_cost_exposures``). Wrong for a
   mixed-asset-class structure; harmless in 5b-1 (every structure is
   single-asset-class) and recorded so it is not rediscovered — the fix belongs
   to Phase 4 netting/multi-asset work.
2. Legacy ``TargetTrade`` dicts remain the execution consumption type; a richer
   ``Order`` is 5b-2 (with the rule chain). Order/fill linkage rides beside the
   dict (on the intent record / working set / execution log / ``Trade``), never
   inside it.
3. ``internal_transfer`` is reserved on both ``ExecutionReport`` and
   ``ExecutionRecord``; unused until netting.

### Test-count reconciliation (baseline 435 → applied 464, +29)
| Test file | Before | After | Delta | Explained by |
|---|---:|---:|---:|---|
| ``tests/test_execution.py`` | 0 | 18 | **+18** | new: interface, block/fill/fill_time, multi-leg sign, no-mutation, ROLL raise, silent-noop, unwind-sign both directions, blocked-unwind book-unchanged, pre-mutation cost timing, writer (3) |
| ``tests/test_execution_log.py`` | 0 | 9 | **+9** | new: fill-id minting/respect, blocked-no-fill-id, write-once, one-record-per-event, linkage |
| ``tests/test_backtester.py`` | 30 | 33 | **+3** | +3 ``TestBacktesterExecutionSeam``; 1 test **rewritten in place** (data-availability disposition) |
| ``tests/test_intents.py`` | 63 | 62 | **−1** | ``test_execution_record_is_a_schema`` **removed** (moved to ``test_execution_log.py``) |
| all other files | 342 | 342 | 0 | untouched |
| **total** | **435** | **464** | **+29** | +30 added, −1 moved |

**Pre-declared rewrites:** ``tests/test_backtester.py::TestBacktesterDataAvailability::test_new_order_rejected_when_price_is_none``
→ ``test_new_order_blocked_when_price_is_none`` (assertions ``REJECTED(data_availability, DATA_MISSING)``
→ ``MATERIALIZED`` + exec-log ``blocked(DATA_MISSING)`` + Flow-A no-trade); and
``tests/test_intents.py::TestSchemaOnlyRecords::test_execution_record_is_a_schema``
removed (its subject moved). These are *rewrites/moves*, not assertion surgery.

### Gates (applied tree)
```
Gate A  baseline (5a tree, scratch)   event e2825941…, cost-series e9a25c6d…, 230 trades, 9,210.661014
Gate B  applied  (5b-1 tree, x2)      0 differing normalized lines; SHA identical to baseline;
                                      metrics table identical; per-leg cost-series + event-log digests
                                      MATCH Gate A -> IDENTICAL
Gate C  SimulatedExecution suite      18 tests: block/fill/fill_time, log linkage, trade linkage,
                                      MATERIALIZED+blocked, Flow A, pricer-path (not price*size),
                                      pre-mutation timing, unwind sign, silent-noop
Gate D  python -m pytest -q           464 passed
Gate E  relaxed greps (above)         ZERO removed internals; comment-only mention allowed
```

Environment: Python 3.12.13 (``D:\anaconda3\envs\backtest\python.exe``), conda env
``backtest``, pandas 3.0.3, numpy 2.4.6.

### Applied byte record (SHA-256)
| File | SHA-256 |
|---|---|
| ``backtester/execution.py`` | `74E3134DE4E7A245BF85009DB5CEB5F9ECAD93FAA35EA3AA9605F87FA4324AE5` |
| ``backtester/execution_log.py`` | `1ABE096F63A412D32FF029D5C05F38543D174F91EE7A7102BAEAD7EFBFCA75B1` |
| ``backtester/backtest_engine.py`` | `936715062AAC8554D3E4162C40B0D4707E5326710759DBE787949B4E072E1E75` |
| ``backtester/intents.py`` | `FBCF4DAFA0D81E98F16577DEDADF5F18EC6EEB9B2068AA3B0F150B71AE83EA1F` |
| ``backtester/trade.py`` | `96F36610F35B6A1A89F21E1E80FB12EE61C73754F5DB07132141D1C784F26D1B` |
| ``tests/test_execution.py`` | `F2C8AC744BBB0A85F9596138B0CA0CFCF5AD03675389FCD92D4C98ED915280E8` |
| ``tests/test_execution_log.py`` | `51F5B09F787566329F2289EB65ACC551DD981BE39CA546B23A936EC2EC020767` |
| ``tests/test_backtester.py`` | `C17CBA41F4DC1228EA15349C12CEA83E9D638643CAB618AB0DA0C5D36A23D489` |
| ``tests/test_intents.py`` | `EB44E28F9BD29D61124964A47A3259C9A032D36DBD2A2BE96A187D116E17978F` |

``git status``: the pre-existing ``.gitignore`` edit plus the 5b-1 change set
(4 modified ``backtester/``+``tests/`` tracked files and 2 new ``backtester/`` and
4 new ``tests/`` files on top of the 5a untracked set); ``results/`` contributes
nothing; ``scripts/`` untouched. No ``git add``, no ``git commit``, no ``git push``.

**5b-2 pending.**

## 2026-10-04 – Task 5b-2: CalendarValidationRule, check chain, Contract calendar fields, doc-sync

### Scope
Inserts the **order-side check chain** (`backtester/check_rules.py`) between synthesis
and execution, populates it with **`CalendarValidationRule`**, adds the `Contract`
calendar fields, and completes the Task 5 doc-sync. This is the **first task that can
change fills**: a leg whose market is closed on the loop day is now rejected
(calendar-authoritative) instead of being filled on an anomalous price row, and the
four 5b-1 data-availability blocks become rule-stage rejections.

Because the re-derived anomalous-day interaction gives **K = 0** (below), the example's
**metrics, stdout and both content digests are unchanged**; only the disposition of
four baseline orders and stderr move.

### Files
**New:** ``backtester/check_rules.py`` (``Verdict``, ``RuleContext``,
``calendar_validation_rule``, ``RuleChain``, ``DEFAULT_CHECK_RULES``);
``tests/test_check_rules.py``.
**Changed:** ``backtester/instruments.py`` (``Contract.trading_calendar_code`` /
``settlement_calendar_codes``), ``backtester/pricers/base_pricer.py`` (constructor
``ticker_to_calendar_code``; ``_build_contract`` stamps the code; ``_INFRA_KEYS``),
``backtester/pricers/equity_pricer.py`` (constructor passthrough),
``backtester/execution.py`` (**removed** ``ExecutionContext.calendar``),
``backtester/backtest_engine.py`` (``BacktestConfig.order_rules``; ``RuleChain`` in
``run``; check in ``_dispatch_synthesized_order``; drop ``calendar=`` at the
``ExecutionContext`` site), ``examples/sma_crossover_example.py`` (one shared mapping
into pricer + config), ``tests/test_instrument.py``, ``tests/test_pricers.py``,
``tests/test_backtester.py`` (``TestBacktesterCalendarRule``), ``tests/test_execution.py``
(``_ctx`` drop ``calendar``), ``design_notes.md``, ``docs/phase2_plan.md``, ``README.md``,
this worklog.

### Mandatory pre-flight (K = 0 — no owner ruling needed)
Re-derived from ``market_data/`` (not trusting 5a's "12 days"): every ``(ticker, date)``
where the price CSV has a row **and** the ticker's holiday file lists the day closed —
**12 pairs, 12 distinct dates**:

| ticker | dates |
|---|---|
| 2800.HK (HK) | 2013-08-14, 2016-08-02, 2016-10-21, 2017-08-23, 2017-12-27, 2018-09-17, 2023-12-27 |
| SXRT.DE (DE) | 2015-12-25, 2017-06-05, 2017-10-03, 2017-10-31, 2018-05-21 |

11 land in the union simulation calendar (2015-12-25 is closed in all three codes →
dropped). **K (fills on an anomalous day for ≥1 leg) = 0**: the live 5b-1 order stream
(461 intents, 461 execution records) has **zero** records and **zero** intents on any
anomalous date.

**Stage-flips** = exactly the four 5b-1 ``BLOCKED`` records, all ``UNWIND`` of a
2800.HK structure on a consistent-closed day (no price row **and** HK closed):
2009-01-26, 2009-01-27, 2009-01-28, 2012-04-04 — each confirmed
``is_valid_day("HK", d) == False`` and absent from ``2800.HK_eod.csv``, and each
``True`` in ``market_data/holidays/HK.csv``. They are the only blocks.

### Interface ruling (approved)
- **Contract-population wiring — pricer constructor injection.** ``BasePricer.__init__(
  ticker_to_calendar_code=None)`` stores a copied map; ``EquityPricer.__init__(provider,
  ticker_to_calendar_code=None)`` forwards it; ``_build_contract`` stamps
  ``trading_calendar_code=self._ticker_to_calendar_code.get(ticker)`` and
  ``settlement_calendar_codes=()``. Both calendar names are added to ``_INFRA_KEYS``, so a
  leg-dict value can never override the map or reach ``params``. ``resolve_instrument``'s
  signature is unchanged and **both resolve sites populate automatically** (commit
  ``_resolve_and_price_leg`` and execution ``_probe``); **no order-side resolve round is
  added** (the NEW case of the check rule reads the config mapping directly).
- **`RuleContext` vs `ExecutionContext` — separate least-privilege `RuleContext`.**
  Rules see ``{date, calendar, ticker_to_calendar_code, active_trades}`` only — **not**
  ``asset_class_configs``, so no check rule can call a pricer.
- **Corpse resolved by removal.** ``ExecutionContext.calendar`` (5b-1's reserved field)
  is **removed**: the approved least-privilege ``RuleContext`` now owns calendar
  validation, and ``SimulatedExecution`` never read a calendar (availability is
  data-driven). ``ExecutionContext`` is now ``{active_trades, asset_class_configs}``; the
  docstring records why there is deliberately no calendar field. Ledger line for the
  frozen-schema change.

### Disposition change — the four stage-flips (ledgered)
The four baseline blocks move from ``MATERIALIZED`` + exec-log ``blocked(DATA_MISSING)``
to **``REJECTED(rule="calendar_validation", code="MARKET_CLOSED")``, no execution record,
no warning**. The ``REJECTED`` record keeps its ``order_id`` (5a ruling). Orders that
pass calendar but are data-blocked at execution keep 5b-1's
``MATERIALIZED`` + exec-log ``blocked(DATA_MISSING)``.

### Gap C amendment
Task 5b-1's adjudicated Gap C ruling was *"Contract calendar fields populated at
materialize."* Materialize is deferred, so 5b-2 **amends** that: the fields are populated
during **``resolve_instrument``** (via the pricer's constructor-injected mapping). This is
the earliest point a ``Contract`` exists and the only point both the commit and execution
resolve paths share; materialize will read the already-stamped field when it lands.
Recorded as an explicit amendment, not a silent deviation.

### Gate B — predict-then-verify (K = 0, strict match)
Baseline captured on the unmodified 5b-1 tree, applied verified on the patched tree,
both via one canonical harness (scratch; ``results/`` untouched).

| Artifact | Gate A (5b-1) | Gate B (5b-2) |
|---|---|---|
| Normalized stdout SHA | `77bb189198292313d44c84f0f23a6c7fb89de111e246d274011de504ba7dbf62` | **same** |
| Normalized lines / raw bytes / UUIDs | 257 / 45,932 / 230 | **same** |
| Trades | 230 | 230 |
| Event-log digest (canonical) | `8f5c13bb6d70b0848b510ea41bdaed932c280af84a9db7ce895f7c25d1c3eef1` | **same** |
| Per-leg cost-series digest (canonical) | `cdf6d4eb412a8dbc0b3ccf901b88f5946aa4e5f307d6c3b76b7e103da6d4d32c` | **same** |
| Raw per-leg cost total | 9,210.661014 | 9,210.661014 |
| Execution records | 461 (457 FILLED / 4 BLOCKED) | **457 (457 FILLED)** |
| Dispositions | 461 MATERIALIZED | **457 MATERIALIZED / 4 REJECTED** |
| stderr | 4 warnings | **0 warnings** |

**Digest-method disclosure (carry-forward).** The historical literals
``e9a25c6d…`` (cost) and ``e2825941…`` (event) do **not** reproduce under any
serialization/normalization method tried (a bounded sweep of json/repr/str × token
substitution). This is the same non-reproducibility 5b-1 flagged for the ``373fc05…``
stdout literal. Gate A was therefore re-captured for **both** trees under one explicit
canonical harness (UUID/hex ids re-indexed in first-encounter order, then
``json.dumps(sort_keys=True)``), and the gate is A ≡ B under that harness. The stdout
SHA (``77bb1891…``) reproduces **exactly** under the documented method, which is the
normalization-independent content proof.

**stderr delta (exact):** before = 4 ``UserWarning``s from ``execution.py`` ("data not
available" on 2009-01-26/27/28, 2012-04-04); after = **0**. The four orders no longer
reach execution, so no block warning is emitted; the reject is silent by design.

### Tests (Gate C, per the reviewer's split)
- **Required suite (hermetic),** ``tests/test_check_rules.py`` (25 tests): ``Verdict``
  invariants; NEW open/weekend/holiday/unknown-code(**FileNotFoundError**)/unmapped/
  no-legs/multi-leg; UNWIND branch-for-branch (unwind-all, ``trade_id=X`` ignoring
  ``info``, ``trade_id=None``+info silent-noop, unknown ``trade_id``, no-contract-code,
  contract-code-not-ticker-map); ``RuleChain`` short-circuit / empty / non-callable /
  ordered; default-chain composition.
- **Engine-level,** ``TestBacktesterCalendarRule`` (4 tests): the **anomalous** shape
  (row exists → default chain rejects, no exec record, no warning); the
  **consistent-closed** shape (no row + calendar closed → rejects under
  ``simplefilter("error")``, pinning stderr 4→0 at unit level); ``order_rules=[]``
  disables the chain (same anomalous day then **fills**, proving the chain rejects, not
  the data); an unmapped ticker passes the default chain.
- **Real-data precondition (skipif),** ``TestFourBaselinePrecondition``: the four dates
  in ``market_data/holidays/HK.csv`` and absent from ``2800.HK_eod.csv`` — milliseconds,
  no backtest run. The 457/4 census is a Gate-B predict-then-verify item, deliberately
  **not** hardcoded in the suite (it is a property of the example's data, and the default
  suite must stay fast and ``simple_csv``-only).

### Test-count reconciliation (baseline 464 → applied 499, +35)
| Test file | Before | After | Delta | Explained by |
|---|---:|---:|---:|---|
| ``tests/test_check_rules.py`` | 0 | 25 | **+25** | new suite |
| ``tests/test_backtester.py`` | 33 | 37 | **+4** | +4 ``TestBacktesterCalendarRule`` |
| ``tests/test_pricers.py`` | 12 | 16 | **+4** | +4 calendar-stamp/params-leak/blocks |
| ``tests/test_instrument.py`` | 17 | 19 | **+2** | +2 ``Contract`` calendar fields |
| ``tests/test_execution.py`` | 18 | 18 | 0 | ``_ctx`` drops ``calendar`` (no count change) |
| all other files | 384 | 384 | 0 | untouched |
| **total** | **464** | **499** | **+35** | |

### Gates (applied tree)
```
Gate A  baseline (5b-1 tree)   stdout 77bb1891…; canonical event 8f5c13bb…, cost cdf6d4eb…;
                               230 trades, 9,210.661014; 461 exec (457 FILLED/4 BLOCKED)
Gate B  applied (5b-2 tree)    stdout SHA + both canonical digests MATCH Gate A;
                               exec 457 (457 FILLED); dispositions 457 MATERIALIZED / 4 REJECTED;
                               stderr 4 -> 0  -> STRICT MATCH (K=0)
Gate C  calendar matrix        25 hermetic check-rule tests + 4 engine-level (anomalous +
                               consistent-closed) + four-date precondition (skipif): pass
Gate D  python -m pytest -q    499 passed, 2 warnings
Gate E  greps                  rule chain wired, only calendar_validation_rule populated;
                               trading_calendar_code stamped from the config map;
                               _check_data_available ZERO; warnings.warn only in
                               SimulatedExecution (+ pre-existing csv_backend/summary);
                               resolve_instrument never called order-side
```

### Contract equality (low-risk, logged)
Adding the two fields changes the frozen ``Contract.__eq__``/``__hash__``: a
``resolve_instrument`` product for a **mapped** ticker (stamped code) no longer equals a
hand-built ``Contract(ticker=..., asset_class=...)``. Expected impact **zero** — the
mapping-set pricers appear only in the new tests, which assert attributes, not equality;
all existing ``Contract(...)`` sites are unmapped. Logged so any future equality failure
is diagnosed as this field addition, not mystery-hunted.

### Doc-sync (grep-based sweep)
``design_notes.md``: §2 tree (5a/5b module inventory); §3.1 ``Contract`` calendar fields;
§3.2/§3.13 cost exposure now execution-side (``write_cost_exposures``); §3.4 init sequence;
§3.5 implemented tense + ``prev_valid_day``; §3.6 cost-exposure caller + **cache key
excludes calendar codes**; §3.7 rewritten to the as-built signal/``DataView``/intent
interface; §3.8 rewritten to the **two-chain** order assembly (synthesis vs check) with
``CalendarValidationRule``; §3.9 daily loop + internal state (intent + execution logs);
§3.15 architecture diagram; §5 Phase 2 split into 5a/5b-1/5b-2; §10 reconciliation
paragraph. ``docs/phase2_plan.md``: Task 5 split into three done steps; the stale
``requires_*`` Phase 3+ item marked resolved by 5a. ``README.md``: signal interface
(``generate_intents``), project tree, usage, and test counts (stale literals **248 / 268**
→ **499**; actual run before = **464**, after = **499**).

### Applied byte record (SHA-256)
| File | SHA-256 |
|---|---|
| ``backtester/check_rules.py`` | `1B8EF053F1EED1E9B3C4301C65FC4DC3E40A93E7A4477AF1E5391C80C23B0F9E` |
| ``backtester/instruments.py`` | `4045E214CA7F5A41EB68FF379EB05A3FF16E01D6B63FB30EE30EF65F37D24B4D` |
| ``backtester/pricers/base_pricer.py`` | `82025AFDDCBB42D2DEBD96C30FD004DCD790D340F795E17DEDB59A85F44B9025` |
| ``backtester/pricers/equity_pricer.py`` | `BCD49778F6605BD568ED4D984DBD4C59170118659CCEC2E81D560B17BD30D62D` |
| ``backtester/execution.py`` | `3D60E13F546CC535CFABF713700431B538BA94010E2C3495DEF6BA7FB7446E08` |
| ``backtester/backtest_engine.py`` | `582F7F190266101B1270E62E44E3E4818E544D024FA0D9DE33C62D6DC100CE3B` |
| ``examples/sma_crossover_example.py`` | `873263237F8806B3B461CA15094584A50E6DD9B7BF443BD524723DEF043F6E73` |
| ``tests/test_check_rules.py`` | `C1A3F5A36F6119E7493C40F03908A2967B838ED6D8D0E1552538E87369BE4624` |
| ``tests/test_instrument.py`` | `2B99E53D87F927E1F75E11B96070C4A3AE26FF0AA89D195314C033EEBF0A07C7` |
| ``tests/test_pricers.py`` | `F80969B52F776D3DD366ADE47D156089E1F1E5314670F1F0A8F9A11FE8DFF57F` |
| ``tests/test_backtester.py`` | `49C24DC1551BE01A74FBC1D7AF789752B74F3C9F86A77007E82F727BB4260616` |
| ``tests/test_execution.py`` | `90825FA46BCB98904AFEEC70D40E5A0E9128B8CBDF0C261E5671140AF8EF12B9` |

``git status``: the pre-existing ``.gitignore`` edit plus the combined 5a/5b change set;
``backtester/check_rules.py`` and ``tests/test_check_rules.py`` new; ``results/``
contributes nothing; ``scripts/`` untouched. No ``git add``, no ``git commit``, no
``git push``.

Environment: Python 3.12.13 (``D:\anaconda3\envs\backtest\python.exe``), conda env
``backtest``, pandas 3.0.3, numpy 2.4.6.

**5b-2 complete.**

## 2026-10-04 – Task 5 pre-commit docs/worklog cleanup pass

### Prompt
Task 5's code is approved for manual review. Before Task 5 is committed as a unit,
apply a docs-and-worklog-only cleanup driven by the coherence review and its two
meta-reviews. **No production code is to be modified** — design_notes, phase2_plan,
README and this worklog only. Five groups: block-commit factual fixes; the
Phase-1-signal-drift cluster; reservation docs for unused seams/fields; process
items carried forward (dangling "5b" gates, digest-method reconcile); and decisions
to surface, not make.

### Changes applied

**Group 1 — block-commit factual fixes**
- `docs/worklog_phase2.md` (5b-2 entry): "the five 5b-1 data-availability blocks" →
  **four** (the 5b-1 Entry recorded 4 BLOCKED and 5b-2 flips four).
- `docs/phase2_plan.md`: Task 5's three sub-step checkboxes (5a, 5b-1, 5b-2) reverted
  to `[ ]` pending manual review. Task 4's `[x]` left untouched (already reviewed and
  committed; only Task 5's were premature).
- `design_notes.md` §7 (conventions): added a paragraph defining the **vintage rule**
  ("T informs what happened, never what we decided"): the order side reads `≤ T-1`
  plus advance-known data, the execution side owns T; noted it underpins the
  no-order-side-`resolve_instrument` rule.

**Group 2 — doc-drift cluster (Phase-1 signal-returns-TargetTrade superseded)**
- `design_notes.md` §3.9 ("No pre-defined instrument universe"): signals return
  `Intent`s; synthesis produces the `TargetTrade` dict.
- `design_notes.md` §7 (Signal lag): the signal no longer handles the lag internally;
  the `DataView` structurally clamps it to T-1.
- `design_notes.md` §9 pillar table and §8.3 execution-data row: the research pillar
  produces `Intent`s; `TargetTrade` is internal to the synthesis/execution seam.
- `design_notes.md` §5 Phase 1 build order items 7–8: left as historical text with a
  supersession parenthetical ("superseded in Task 5a — see Phase 2"), not rewritten.
- `README.md`: badge → "phase-2A + Task 5"; Phase 2 roadmap row → in progress (Phase 2A
  Tasks 1–4 + Task 5); architecture arrow now includes the synthesis/check/execution
  seams; corrected the closed-market sentence (a closed leg's **order** is rejected by
  `CalendarValidationRule`; a held leg simply has no price); usage step now lists
  `data_feed`, `order_synthesis`, `order_rules`, `execution_backend`.

**Group 3 — reservation docs (naming the future consumer)**
- `design_notes.md` §3.7: `Intent.origin_intent_id` documented as reserved for
  synthesis-plugin provenance (Roll/Scaling in 5c); flagged as a removal candidate if
  no consumer lands.
- `design_notes.md` §3.8: the `NO_ORDER` dropped-intent branch documented, with the
  **open question** that `REJECTED(synthesis, NO_ORDER)` may mislabel a synthesis-stage
  drop (taxonomy reserves synthesis outcomes for net/transfer) — to resolve in 5c.
- `design_notes.md` §3.8: `AggregationContext.execution_log` / `.calendar` / `.config`
  documented as reserved for synthesis plugins, contrasting the removed
  `ExecutionContext.calendar` (consumer moved to `RuleContext`); explicitly "do not
  remove as unused".
- `design_notes.md` §3.9: `IntentRecord.order_id` noted as load-bearing for `REJECTED`
  (keeps the id without a `MATERIALIZED` disposition) and redundant-with-disposition
  for `MATERIALIZED`.

**Group 4 — process items carried forward**
- `docs/phase2_plan.md`: added a "Task 5 follow-ups — dangling gates re-pointed to 5c /
  plugin milestone" subsection with four checkboxes (sizing-bridge removal; `WorkingSet`
  signature widening before Netting; stamping intermediate stage; explicit unwind-all
  form) — previously pinned to the now-nonexistent "5b" milestone.
- `docs/phase2_plan.md`: added an "Open item — digest-method reconcile" subsection
  recording the non-reproducing historical digest literals and the A≡B-session-only
  canonical harness, with the two options (canonical-method-plus-verified-literal, or
  session-comparative-only), explicitly **not decided**.

**Group 5 — decisions surfaced, not made**
- Digest-method reconcile (recorded open in `phase2_plan.md`).
- `origin_intent_id`: remove or populate in 5c (recorded in `design_notes.md` §3.7).
- `NO_ORDER` disposition relabel (recorded open in `design_notes.md` §3.8).

### Test impact
None — documentation only. No production code touched; no test file touched.

### Manual changes
- None.

### Suggested commit message
```
docs: Task 5 pre-commit cleanup — drift fixes, reservation notes, carried-forward gates

- worklog: correct five -> four 5b-1 data-availability blocks (5b-2 entry)
- phase2_plan: revert Task 5 sub-step checkboxes to [ ] pending manual review
  (Task 4 [x] left as already-reviewed); re-point dangling "5b" gates to 5c /
  plugin milestone; record digest-method reconcile as an open owner decision
- design_notes §7: define the vintage rule (T informs what happened, never what
  we decided; order side <= T-1, execution side owns T)
- design_notes §3.9/§7/§9/§8.3: signal returns Intent not TargetTrade; DataView
  owns the lag; TargetTrade internal to the synthesis/execution seam; §5 Phase-1
  build order annotated as superseded rather than rewritten
- design_notes §3.7/§3.8/§3.9: reservation notes for origin_intent_id, the
  NO_ORDER branch (open taxonomy question), AggregationContext execution_log/
  calendar/config, and IntentRecord.order_id semantics
- README: badge/roadmap reflect Phase 2A + Task 5; architecture arrow adds the
  synthesis/check/execution seams; closed-market sentence corrected; usage lists
  data_feed/order_synthesis/order_rules/execution_backend
- Docs-only; no production code changed
```

## 2026-10-06 – Intent identity/scope re-work

### Scope
Re-works the intent identity/scope model after the ruling checkpoint was sent
back.  Three corrections: (A) UNWIND covers all three scopes again
(structure / whole-trade / whole-book); (B) the modification quantity moves off
the structure type to the intent; (C) netting becomes an execution-phase
concern, so the intent disposition vocabulary drops `NETTED` / `TRANSFER`.
Representation change only: the example's normalized stdout is byte-identical
(session SHA `b9cef8ea…`, 257 lines, 39,639 normalized bytes, 46,189 raw bytes,
230 UUIDs, 0 stderr).

### Schema (as built)
- **`StructureIntent`** — a structure's *content*: `legs` and `tags` only.  No
  `structure_id` (engine-assigned) and no `size` (a modification-event
  parameter).  A content spec; legs are non-empty whenever it describes new
  content, validated per action.
- **`Intent`** — `intent_id`, `strategy_id`, `action`, `provenance`,
  `structures: tuple[StructureIntent, ...]`, `trade_id`, `structure_id`,
  `size`, `origin_intent_id`, `emission_date`, `tags`.
  - `structures` carries the content a NEW/ROLL introduces (1+ structures).
  - `trade_id` scopes trade-level ops (NEW-extend, UNWIND-whole-trade);
    `structure_id` scopes structure-level ops (UNWIND-structure, partial-add,
    ROLL); NEW-create and unwound-book carry neither.
  - `size` is the partial-add amount or partial-unwind quantity.
- **NEW sub-cases:** create (`trade_id=None`, structures without ids), extend
  (`trade_id` set, structures without ids), partial-add (`trade_id` +
  `structure_id` + positive `size`, no structures).
- **UNWIND scopes:** whole book (`trade_id=None`, `info=[]`), whole trade
  (`trade_id` set, `info=[]`), one structure (`structure_id` set, optional
  partial `size`).
- **`origin_intent_id`** is replacement lineage: a plugin emitting a modified
  version of an existing intent sets it to the predecessor's `intent_id`; a
  brand-new intent leaves it `None`; otherwise `None`.  Attribution for plugin
  output is carried by `provenance` alone.  (design_notes.md §3.7 is the
  governing authority; there is no standalone design summary in the repo, so
  this is "corrected against §3.7".)
- **Netting rule.**  The intent layer is netting-agnostic: a netted order is
  still `MATERIALIZED` (handed off) and position accounting reflects the
  economic effect; netting is realized as an internal transfer in the execution
  log.  `DispositionKind` now carries only `MATERIALIZED` / `REJECTED` /
  `MODIFIED`.  `TransferEvent`, `WorkingSet.transfers` and
  `ExecutionReport.internal_transfer` are retained.

### Amendments (explicit, not quiet supersessions)
- **Amendment of the 5a "one intent per structure" pin.**  Replaced by the
  granularity rule: one NEW per trade creation or trade extension; one UNWIND
  per scope addressed; one ROLL per structure; decomposition remains a no-op.
- **Amendment of the Task 5 disposition taxonomy.**  `NETTED` / `TRANSFER`
  removed from `DispositionKind` with their `Disposition.netted()` /
  `.transferred()` constructors.  Rationale (same as the `origin_intent_id`
  amendment): netting is an execution/synthesis-layer manifestation, not an
  intent disposition.  Condition (2a) verified before removal: the only
  construction sites were `intents.py` (the enum + two classmethods) and
  `tests/test_intents.py`; nothing in production, the engine or execution
  constructed them.
- **`StructureIntent.structure_id` removal, led as a corpse.**  The engine
  assigns structure ids; a reference to an existing structure is
  `Intent.structure_id`.  Expressiveness note: the `TargetTrade` format can name
  a new structure's id, but the intent layer now cannot, and no consumer exists.
- **`origin_intent_id` corrected against §3.7.**  Replacement lineage, not
  plugin provenance; provenance alone carries attribution.

### `intent_log.py`
- Now indexes by `structure_id` **and** `trade_id`, in addition to
  `strategy_id` and `intent_id`.  A creation intent (no structure, no trade)
  appears in the log by `intent_id` only, with no scope index.  `by_trade` is
  intended for trade-scoped queries (cooldown / scaling).  Log-level tests cover
  both indices.

### Docstring/comment sweep
- No "legacy" naming, no task-phase references, present-tense descriptions.
- **Sweep broadened** beyond the originally-listed files to `execution.py`,
  `data_view.py`, `position_books.py` and `check_rules.py` — deliberate, for
  codebase consistency; docstring/comment-only.
- `legacy_size` / `intent_from_legacy` / `LEG_DICT_INFRA_KEYS` /
  `legacy_order_shim.py` accepted as-is (API surface, not prose).

### ROLL
- Conversion is schema-complete (`old_structure_id` + `new_structure.legs` from
  the single `StructureIntent`); execution still raises `NotImplementedError`.
  `new_structure` structure-level tags are **deferred** — the corpus case lands
  when ROLL execution is implemented.

### Known limitation (recorded)
- The converter's structure↔trade consistency check fails loudly when a
  referenced structure is absent from the T-1 book.  A same-day open-then-modify
  therefore cannot be expressed through intents (signals see only T-1); this is
  intentional fail-loud, ledgered as a known limitation.

### Corpus (`tests/test_order_synthesis.py`)
Existing 8 cases migrated in place (byte-identity unchanged): NEW/ROLL become
one-element `structures` lists; UNWIND-all / structure-full / structure-partial
use `structures=()` plus top-level `structure_id` (+ `size`).  New cases:
`new_multi_structure`, `new_add_structures_to_existing_trade`,
`new_partial_add_to_structure`, `unwind_whole_trade`.  Each is pinned by
`==` and `repr ==`, plus the shim round-trip.

### Test-count reconciliation (baseline 499 → applied 528, +29)
| Test file | Before | After | Delta | Explained by |
|---|---:|---:|---:|---|
| `tests/test_intents.py` | 63 | 75 | **+12** | +`TestIntentShapeMatrix` (11) + 2 log-index tests; −1 obsolete NEW-structure-id test |
| `tests/test_order_synthesis.py` | 45 | 60 | **+15** | +4 corpus cases ×3 assertions = +12; +3 fail-loud (structure/trade mismatch, missing-from-book) |
| `tests/test_signal.py` | 20 | 20 | 0 | unwound-leg-side test replaced by short-structure test |
| `tests/test_backtester.py` | 37 | 38 | **+1** | +`test_whole_trade_unwind_round_trips_through_the_loop` |
| all other files | 334 | 334 | 0 | untouched |
| **total** | **499** | **528** | **+29** | |

### Gates (applied tree)
```
Gate A  baseline  session SHA b9cef8ea…; normalized 257 lines / 39,639 bytes;
                  raw 46,189 bytes / 230 UUIDs / 0 stderr
Gate B  applied   session SHA b9cef8ea… (IDENTICAL); normalized bytes 39,639;
                  raw bytes 46,189; 257 lines; 230 UUIDs; stderr 0
        normalized stdout A/B diff: 0 differing lines
Gate C  converter corpus  12/12 byte-identical (== and repr), shim round-trip
Gate D  python -m pytest -q  528 passed, 2 warnings
Gate E  greps     no "legacy"/"5a"/"5b"/"Phase 1" in the touched modules'
                  docstrings/comments except the accepted API names
```

Environment: Python 3.12.13 (`D:\anaconda3\envs\backtest\python.exe`), conda env
`backtest`.

**Intent re-work complete.**

## 2026-10-14 – Single-action subset: schema restructure + rename + doc lock

### Prompt
Land the locked Intent Schema & Execution Flow architecture: the single-action
subset of the pre-agreed design, the fourth naming pass (`Intent` → `ActionGroup`
et al.), the split validation, the named gates, and the design lock into
`design_notes.md`.  Roll/flip/delta-hedge/scaling/netting/multi-action/multi-leg/
short partial modifications are **out of scope** — schema/skeleton only, gated.
The SMA example must stay output-byte-identical.

### Canonical-SHA baseline method (R7)
Adopted a **position-independent, UUID-substituted** canonical method: each UUID
token (dashed 8-4-4-4-12 or 32-hex) is replaced with a sequential `UUID_0001…`
in first-encounter order, then SHA-256.  Re-baselined **once on the unmodified
tree** from a **scratch copy** (repo `results/` never written).  Baseline and
applied are identical:

```
Gate A (scratch, unmodified)  SHA  cc6b08fbfa7466dca4f9084a37998775db9100b5af09a13409b1a2118ed62560
                              257 lines / 39979 normalized bytes / 46189 raw / 230 UUIDs / 0 stderr
Gate B (scratch, applied)     SHA  cc6b08fbfa7466dca4f9084a37998775db9100b5af09a13409b1a2118ed62560  -> IDENTICAL
```

Content digests stay **session-comparative by scope choice, not limitation**
(same harness, same session; no reproducible literal is required).

### Schema restructure + rename (supersedes the prior intent schema)
- `Intent` → `ActionGroup`; `LegIntent` → `LegSpec`; `StructureIntent` →
  `StructureSpec`; new `TradeSpec` and `Action`.
- `intent_id` → `action_group_id`; `origin_intent_id` → `origin`;
  `IntentRecord` → `ActionGroupRecord`; `IntentLog` → `ActionGroupLog`;
  `IntentLogView` → `ActionGroupLogView`; `WorkingSet` → `OrderGroup`.
- Modules: `intents.py` → `actions.py`; `intent_log.py` → `action_group_log.py`.
- `LegIntent.legacy_size` → `LegSpec.signed_size`;
  `intent_to_target_trade` → `action_group_to_order_group` (+ `action_to_order`);
  `leg_dict_from_intent` → `leg_dict_from_spec`;
  `BaseSignal.generate_intents` → `generate_action_groups`.
- `tests/legacy_order_shim.py` → `tests/order_shim.py`;
  `intent_from_legacy` → `action_group_from_order`;
  `tests/test_intents.py` → `tests/test_actions.py`.
- `ActionGroup.tags` dropped (anti-corpse: new never-emitted surface with no
  consumer; trade-level tags moved to `TradeSpec.tags`).
- **Half-rename coherence ruling:** objects/modules renamed to Action names; the
  layer/concept names "intent synthesis" / "intent log" retained in prose, with
  a docstring sentence in `actions.py` explaining the concept/object split.
- Execution-log chain fully renamed: `ExecutionRecord.intent_id` →
  `action_group_id` (also `ExecutionRequest` / `ExecutionReport`); no
  half-rename of the id chain.

### Action schema (as built)
- `Action(type, spec, trade_id, structure_id, quantity)` — one spec per action.
- Construction-time matrix in `Action.__post_init__` (fail-loud on unlisted
  shapes); `quantity > 0` when present; spec type matches shape.
- Conversion-time checks: partial-unwind bound `0 < quantity < |anchor_current|`
  and structure↔trade consistency.
- **Anchor leg:** `StructureSpec.legs[0]`; modifications apply to it, other legs
  scale proportionally.
- **Signed quantity:** `|anchor_new| = |anchor_current| + (NEW ? +q : −q)`,
  `anchor_new = sign(anchor_current) × |anchor_new|`; action is
  direction-agnostic, the delta side comes from the leg's `Side`.
- **Fractional policy (interim):** intent keeps exact fractional values; the
  lot-sizing mechanism is deferred; current behaviour is a straight
  **passthrough**.  No lot-sizing config built.
- **Provenance:** closed set; `netting_rule` **removed** (netting is not an
  intent source); `roll_rule` retained as a conscious reserved constant.

### Gates (fail-loud; schema accepts, pipeline/conversion rejects)
- **Multi-action groups** — pipeline rejection at `OrderSynthesis.synthesize`
  top, before order conversion (NOT in `ActionGroup.__init__`).
- **Multi-leg modifications** and **short-structure partial modifications** —
  conversion-time gates in `order_synthesis`.
- Rule-emitted groups that were never appended are rejected: **the multi-action
  crash is intended; orphaned records are terminal**.  **Rule-emitted groups are
  rejected until the stamping stage lands; the pre-stamp workaround is now
  structurally forbidden.**  Consolidated in the `phase2_plan.md` gate registry.

### `synthesize` return + OrderGroup correspondence
`synthesize` returns `tuple[OrderGroup, ...]` — exactly one OrderGroup per input
ActionGroup, **positionally aligned**; a rule-dropped group yields an **empty
OrderGroup**, which the dispatcher maps to `REJECTED(synthesis, NO_ORDER)`.
`OrderGroup` carries no `action_group_id` (paired by zip; lineage reserved on the
execution log).

### Entry-date framing and empty-trade deferral
Trade entry date is fixed from open to close; the trade exits when its last
structure closes.  Empty-trade removal and `exit_date` are **deferred until the
ActionGroup completes** (engine-program surface, unbuilt; trivially satisfied
under the single-action gate).  Consequence recorded: an empty-but-unremoved
trade is same-day re-openable.

### Engine findings (recorded, NOT fixed — both already gated)
- `StrategyStructure.add_size` / `unwind` distribute by **share-of-total**
  (`size_key / total_size`), not an anchor-uniform factor.  For a single-leg
  structure the two coincide; multi-leg modification is gated.
- A partial add/unwind runs in the **wrong direction on a short** structure;
  short-structure modification is gated.  Recorded in code comments in
  `execution.py` / `order_synthesis.py` and here.

### `SimulatedExecution` all-or-nothing (documented as-built)
`SimulatedExecution` fills an order in full or blocks it entirely — no partial
fills in the backtest.  Live partial-fill handling is deferred; documented as
as-built behavior, not a new decision.

### Netting (future slot, documented only)
Netting input = orders organized by originating group + lineage; detect rolls
*before* net.  Execution-log lineage reservation: `order ↔ action ↔ trade ↔
group`.  `OrderGroup` carries no back-reference by design.

### Test-count reconciliation (baseline 528 → applied 553, +25)
| Test file | Before | After | Delta | Explained by |
|---|---:|---:|---:|---|
| `tests/test_actions.py` (was `test_intents.py`) | 75 | 94 | **+19** | shape-matrix rows, anchor-leg, signed-quantity, per-action log index + once-per-bucket, ActionGroup ≥1-action/provenance, frozen context |
| `tests/test_order_synthesis.py` | 60 | 66 | **+6** | −3 (roll corpus) +3 (resolver corpus) +1 tag round-trip +1 bounded unwind +1 short partial-add +4 gates +1 plugin-chain −1 fail-loud −2 fold (retained coverage) |
| `tests/test_signal.py` | 20 | 20 | 0 | rename only |
| `tests/test_backtester.py` | 38 | 38 | 0 | ROLL test migrated to direct `_execute_order`; rename only |
| all other files | 335 | 335 | 0 | import/rename only |
| **total** | **528** | **553** | **+25** | |

### Gates (applied tree)
```
Gate A  scratch baseline (unmodified)  SHA cc6b08fb…; 257 lines / 39979 bytes
Gate B  scratch applied                SHA cc6b08fb… (IDENTICAL); repo results/ never written
        renamed symbols in user output: none
Gate C  converter corpus  12/12 byte-identical (== and repr), shim round-trip, tag round-trip
Gate D  python -m pytest -q  553 passed, 2 warnings
Gate E  greps  no standalone "materialize"; no "netting_rule" (intentional-absence note + negative test only);
                "within-group" consistent (absent); intent-symbol sweep complete (concept prose only)
```

Environment: Python 3.12.13 (`D:\anaconda3\envs\backtest\python.exe`), conda env
`backtest`.

## 2026-10-17 – Structure-scoped ops: `trade_id` required, resolver path removed

### Prompt
Make `trade_id` **required** on all structure-scoped operations (partial add and
both UNWIND forms).  The optional-`trade_id` resolve-from-book path was a vestige
of the old flat Intent design: both cases have `structure_id`, and the signal
already has the `trade_id` via `PositionBook`.  Only NEW-extend is genuinely
unresolvable (the structure does not exist yet), and it was already required.
The example's emitted order dicts must stay byte-identical.

### Matrix change
| type | spec | trade_id | structure_id | quantity |
|---|---|---|---|---|
| `NEW` | `TradeSpec` | – | – | – |
| `NEW` | `StructureSpec` | ✓ | – | – |
| `NEW` | – | ✓ | ✓ | ✓ (>0) |
| `UNWIND` | – | **✓** | ✓ | ✓ (>0) |
| `UNWIND` | – | **✓** | ✓ | – |
| `UNWIND` | – | ✓ | – | – |
| `UNWIND` | – | – | – | – |

The two structure-scoped rows flipped from *optional* to required.

### Changes applied
- `backtester/actions.py` — `_validate_unwind` rejects a structure-scoped
  UNWIND with no `trade_id`; the `Action` docstring matrix and the module-level
  identity/scope paragraph updated.  Error precedence: spec → scope identity →
  quantity.
- `backtester/order_synthesis.py` — `_unwind_order` emits `action.trade_id`
  directly; `_resolve_trade_id` **deleted** (its only caller was the removed
  branch); `_validate_structure_trade` guard simplified to the structure id
  (both callers always pass a trade id now); module/function docstrings updated.
- `backtester/signals/sma_crossover.py` — the UNWIND action passes
  `trade_id=holding.trade_id`.
- `backtester/position_books.py` — docstring-only: the registry is now the
  validator's path, not the resolver's.
- `tests/test_actions.py` — structure UNWIND fixtures carry `trade_id`; the
  optional-trade-id test replaced by a required-trade-id negative test.
- `tests/test_signal.py` — asserts the UNWIND action carries `trade_1`.
- `tests/test_order_synthesis.py` — resolver corpus case and resolver assertion
  test removed (they now duplicate the explicit cases); remaining
  structure-scoped fixtures carry `trade_id`; unknown-structure expectation
  moved to the validator message (`not present in the T-1 book`).
- `tests/order_shim.py` — docstring-only: the structure UNWIND shape now names
  both `trade_id` and `structure_id`.
- `design_notes.md` — matrix rows and the SMACrossoverSignal bullet updated.

### Ripple effects found (and disposition)
- `ActionGroupLog` now also indexes structure-scoped UNWINDs under `trade_id`.
  This matches its documented per-action indexing; no test changed.
- `tests/order_shim.py` and `tests/test_backtester.py` needed **no functional
  edits**: the shim already forwards `order["trade_id"]`, and every
  structure-scoped order dict in those tests already sets it.
- Historical `test_check_rules.py` / `test_execution.py` "silent no-op"
  fixtures build order dicts directly (no `Action`), so the schema change does
  not affect them; the engine-side behaviour is intentionally unchanged.

### Byte-identity (SMA example)
The signal previously emitted `trade_id=None` and the converter resolved it via
`book.trade_id_for_structure(structure_id)`.  Now the signal passes
`holding.trade_id`.  Both read the same frozen T-1 snapshot: `find_holding`
returns the trade owning the matched structure, and `trade_id_for_structure`
returns the unique owner of that structure id — the same string (`trade_1` in
the fixture).  The emitted dict is unchanged:
`{"Action": "UNWIND", "trade_id": "trade_1", "info": [{"structure_id": "S1"}]}`.
The integration example ran end-to-end successfully.

### Test-count reconciliation (baseline 553 → applied 550, −3)
| Test file | Before | After | Delta | Explained by |
|---|---:|---:|---:|---|
| `tests/test_actions.py` | 94 | 95 | **+1** | −1 optional-id test, +2 (full-structure, required-id) |
| `tests/test_order_synthesis.py` | 66 | 62 | **−4** | −1 resolver corpus (×3 parametrized) −1 resolver assertion |
| `tests/test_signal.py` | 20 | 20 | 0 | assertion updated only |
| all other files | 335 | 335 | 0 | no edits |
| **total** | **553** | **550** | **−3** | |

### Gates (applied tree)
```
Gate C  converter corpus  11/11 byte-identical (== and repr), shim round-trip
Gate D  python -m pytest -q  550 passed, 2 warnings
Gate E  greps  no `_resolve_trade_id` / "resolver path" references remain
        example  examples/sma_crossover_example.py ran successfully
```

Environment: Python 3.12.13 (`D:\anaconda3\envs\backtest\python.exe`), conda env
`backtest`.

### Manual changes
- Updated ActionGroup description.

## 2026-10-19 – Action-layer disposition taxonomy

### Prompt
Settle the action-layer disposition taxonomy; rename `MATERIALIZED` →
`DISPATCHED`; replace `MODIFIED` with `REPLACED`; add per-action outcomes and
ids; remove the duplicated record-level `order_id`; and finish the
"intent → action group" prose migration.

### Disposition taxonomy (as built)
- `DispositionKind = DISPATCHED | REJECTED | REPLACED`.
- `DISPATCHED` carries `order_id` only.  Whether its actions changed positions
  is a separate fact (`action_outcomes`).
- `REJECTED` carries `rule` + `code` only, and no `order_id`: a check-rule
  reject never reaches dispatch.  This clarifies the 5a record-id behavior: a
  rejected record's `order_id` pointed at a transient `OrderGroup` with no
  durable referent; the new taxonomy places `order_id` on `DISPATCHED` only.
  No consumer ever read the field on rejected records.
- `REPLACED` carries no payload.  A scaling rule supersedes a signal group with
  derived groups; the derived group carries `original_action_group_id`.
- `Disposition.modified` / `note` and `Disposition.materialized` are gone.

### Per-action facts and ids
- `ActionOutcome` is defined locally in `actions.py` (`FILLED | BLOCKED`); it is
  deliberately not `ExecutionOutcome`.  `ExecutionRecord.status` remains the
  order-layer fact; they coincide today and will diverge under netting.
- `ActionGroupLog.append` mints `action_ids`, one per action.
- `OrderGroup` gains `order_group_id` (minted at construction) and
  `modification_notes` (parallel to `orders` / `order_ids`), and is now
  non-empty by construction.  A provided `modification_notes` tuple of the
  wrong length raises.
- `ActionGroupRecord` is a hand-written class (not a dataclass) with read-only
  properties and a single write-once `finalize(disposition, action_outcomes,
  modification_notes, group_note)`.  The top-level `order_id` is removed;
  `disposition.order_id` is the single source.
- `group_note` is reserved group-level surface.  Its first named use is the
  live partial-fill simplification policy.

### Invariants
1. `finalize` raises `RuntimeError` on a second call.
2. `REJECTED` / `REPLACED` ⇒ empty tuple facts and `group_note is None`.
3. `DISPATCHED` ⇒ one `ActionOutcome` per action and parallel
   `modification_notes`.
4. `action_ids` is parallel to `action_group.actions` and read-only.
5. `ActionGroupLog.append` performs the `REPLACED` transition; a missing or
   already-terminal original raises `ValueError`.

### Synthesis and modify step
- `NO_ORDER` and the empty-`OrderGroup` path are removed.  Synthesis never
  rejects or drops: it auto-generates mechanical actions and replaces signal
  actions for scaling.  A rule that removes an input group now raises in the
  output-assembly loop (per-group lookup).
- The modify step (`_modify_order`) is an equity passthrough: `quantity` /
  `size` are not rounded, and each order gets a `None` note slot.
- A future risk/liquidity reduction that would zero size is a rejection, not a
  modification.

### Prose migration
- Removed the concept/object split paragraph from `actions.py` and
  `design_notes.md`.
- "intent synthesis" → "action group synthesis"; "intent log" →
  `ActionGroupLog`; object-referring "intent" → "ActionGroup".
- Historical worklog entries were not rewritten; this entry is the amendment.
- "drop" removed from synthesis descriptions.

### Field-name findings
- `ExecutionRequest.action_group_id` (`execution.py:57`) and
  `ExecutionRecord.action_group_id` (`execution_log.py:37`) were already
  renamed; no `intent_id` remains.
- `ActionOutcome` is local to `actions.py`; no import cycle with `execution.py`.

### Scope decisions
- Partial fills are out of scope: each order fills fully or blocks.  The future
  composition mapping records quantity contributions per pre-net order, not
  per-fill allocations.
- Durable `ExecutionRecord.order_group_id` / `action_id` foreign keys are
  deferred; the intra-day chain is complete via `action_group_id` and
  `order_id`.

### Test-count reconciliation (baseline 550 → applied 567, +17)
| Test file | Before | After | Delta | Explained by |
|---|---|---:|---:|---|
| `tests/test_actions.py` | 95 | 110 | **+15** | disposition payload tests, `OrderGroup` invariants, record invariants, replacement-log tests |
| `tests/test_order_synthesis.py` | 62 | 64 | **+2** | note parallelism, `order_group_id` |
| `tests/test_backtester.py` | 38 | 38 | 0 | assertions strengthened |
| all other files | 355 | 355 | 0 | no edits |
| **total** | **550** | **567** | **+17** | |

README was stale at 553 (actual baseline 550).  The 553 → 567 README update
includes a three-count correction, not a new discrepancy.  Gate D reports the
applied count against 550.

### Gates (applied tree)
```
Gate A  SMA baseline (scratch)     SHA 9273de8341cc93f5982809df7ccb33b79b63bcd81c21ae0cbf438695aa57bcbe
                                   258 lines / 39981 normalized bytes / 230 UUIDs / 0 stderr
Gate B  SMA applied (scratch)      SHA 9273de8341cc93f5982809df7ccb33b79b63bcd81c21ae0cbf438695aa57bcbe
                                   -> IDENTICAL (canonical diff empty; raw differs only by UUID tokens)
Gate C  converter corpus           byte-identical (== and repr)
Gate D  python -m pytest -q        567 passed, 2 warnings
Gate E  greps                      no MATERIALIZED / MODIFIED / NO_ORDER /
                                   Disposition.modified / intent-layer prose /
                                   top-level ActionGroupRecord.order_id
```

Environment: Python 3.12.13 (`D:\anaconda3\envs\backtest\python.exe`), conda env
`backtest`.

### Manual changes
- Updated `README.md` test count (553 → 567) and ActionGroup description.

## 2026-10-21 – Phase A: unwired order layer

### Prompt
Phase A of a five-phase (A → B1 → B2 → C1 → C2) flattening of the strategy-side
order layer: add the new order classes only, wired to nothing, so no behaviour
change is possible by construction.

### Ruling (deviation from the prompt)
- The prompt's premise that `OrderGroup` is new is wrong: `actions.OrderGroup`
  already exists (`backtester/actions.py:617`) with a different shape
  (`orders: tuple[dict, ...]`, plus `order_ids` / `modification_notes` /
  `transfers`) and is imported by `order_synthesis.py` and
  `backtest_engine.py`.
- **User ruling: `OrderGroup` is deferred to Phase B1**, where the existing
  class is retired at the conversion/dispatch boundary.  Phase A adds only
  `OrderSide`, `OrderLeg` and `Order`.
- **File location: new `backtester/orders.py`** (not `actions.py`).  It
  separates the order layer from the action layer by file and keeps
  `actions.py` free of any reference to the new module.
- No name collision for `Order` / `OrderLeg` / `OrderSide`; nothing imports the
  new module.

### Invariants
- `OrderSide` is a `str` enum: `BUY` / `SELL`.
- `OrderLeg.side` coerces via `OrderSide(side)`; `tags` and `params` normalise
  to tuples; `quantity` is a positive magnitude (`<= 0` raises `ValueError`).
  The reserved-key check stays in `ContractSpec`.
- `Order.legs` is non-empty (`ValueError`) and holds only `OrderLeg`
  (`TypeError`); `structure_id` / `trade_id` default to `None`.
- All three classes are `frozen=True`.  No `to_dict()`, no `OrderOutcome`, no
  `notional` / `tenor`.

### Files
- New: `backtester/orders.py`, `tests/test_orders.py`.
- Amended: `docs/worklog_phase2.md` (this entry + ToC row 12).
- No existing source or test file touched.

### Test count (baseline 567 → 583, +16)
| Test file | Before | After | Delta |
|---|---:|---:|---:|
| `tests/test_orders.py` | 0 | 16 | **+16** |
| all existing files | 567 | 567 | 0 |
| **total** | **567** | **583** | **+16** |

### Gates (applied tree)
```
Gate A  SMA baseline (scratch)   SHA 9273de83… (re-confirmed)
Gate B  SMA applied              SHA identical to baseline
Gate C  full suite               python -m pytest -q -> 583 passed
Gate D  greps                    Order / OrderLeg / OrderSide only in
                                 orders.py + test_orders.py; no `orders`
                                 import anywhere else
```
Byte-identity holds trivially: the new module is imported by nothing, so the
SMA example's UUID-normalised stdout is unchanged.

### Scope
- Phase A of five.  `OrderGroup`, `to_dict()`, conversion/execution rewiring,
  SMA sizing, `is_tradable`, `CalendarValidationRule` removal and the
  disposition-taxonomy removal belong to B1/B2/C1/C2.

## 2026-10-22 – Phase B: wire `Order` through conversion, execution and book commit

### Prompt
Phase B of the A → B1 → B2 → C1 → C2 flattening: retire the compound
`TargetTrade` dict pipeline and wire `actions.Order` / `OrderLeg` / `OrderSide`
through conversion, dispatch, execution and book commit.  Byte-identity of the
SMA example's stdout is the hard gate.  The multi-action gate stays.

### Ruling checkpoint (before edits)
Baseline re-captured in a scratch copy (`Temp/opencode/phaseb_baseline`; repo
`results/` never written):
```
SMA baseline  SHA 9273de8341cc93f5982809df7ccb33b79b63bcd81c21ae0cbf438695aa57bcbe
              258 lines / 39,981 normalized bytes / 230 UUIDs / 0 stderr
```
Confirmed at the checkpoint with `file:line`: `Action.quantity` (`actions.py:272`),
`ActionOutcome` (`:411`), the four-fact record (`:490-594`), `TransferEvent`
(`:598`), the dict `OrderGroup` (`:617-660`), `_modify_order`
(`order_synthesis.py:106`), `ExecutionRequest` (`execution.py:52`), and the
compound `_execute_*` commit (`backtest_engine.py:450-617`).

**Dispositions.**  `TransferEvent` and `ActionOutcome` were referenced only by
the retired classes/tests, so both were **deleted**; `OrderOutcome` takes over.

**Corpus size correction:** the prompt says 12 cases; the corpus had **11**.

**Book-commit equivalence (stated).**  Old: one compound order per ActionGroup →
one `Trade` per create.  New: filled orders are grouped by `action_id`; with one
action per group (the gate) and one `action_id` per action (always), this is the
same one-trade-per-ActionGroup commit.  A structure-scoped single-leg
modification uses the anchor delta, and `delta / anchor` is exactly the old
share-of-total fraction (ratio `1`); multi-leg modification stays gated.

**Rulings (user-approved).**
- **C1 check chain** — kept via a temporary private `Order` → check-view adapter
  in `_dispatch_synthesized_order`; deleted in Phase C.  Preserves the four
  calendar rejects, stderr = 0 and every calendar test.
- **C2 `finalize`** — `finalize(disposition, order_ids, order_outcomes,
  group_note=None)`: the disposition stays first so `REJECTED` / `REPLACED`
  survive until Phase C.
- **C3 tags** — `TradeSpec` / `StructureSpec` tags are not on `Order`; the commit
  phase derives them from the record's action (needed for the SMA's
  `short_ma` / `long_ma` trade tags).
- **C4 test bridge** — `tests/order_shim.py` deleted; `test_backtester.py` now
  builds `ActionGroup`s via local `_new_trade` / `_unwind` helpers.
- **C5 execution lineage** — `ExecutionContext` gains
  `date` / `action_group_id` / `strategy_id`; `ExecutionReport` / `Record` gain
  `action_id` / `order_group_id` / `probe_status` / `blocked_by` and drop
  `action: ActionType`.  The ROLL test was deleted with the dict path.

### Source changes
- `orders.py`: added `OrderOutcome` (`FILLED` / `BLOCKED`) and `OrderGroup`
  (`order_group_id` minted, non-empty, holds only `Order`).
- `actions.py`: `Action.quantity` → `size`; `ActionGroupRecord` stores
  `order_ids` / `order_outcomes` (parallel, write-once) and drops
  `modification_notes`; `ActionOutcome`, `TransferEvent`, `actions.OrderGroup`
  removed; `OrderOutcome` imported from `orders.py`.
- `order_synthesis.py`: rewritten for `Order` conversion
  (`action_group_to_order_group(action_group, action_ids, ctx)`), with
  `_delta_legs` (anchor formula), `_full_close_legs`, T-1 `_trade_state`, and
  fail-loud unresolvable scopes / empty-book whole-book unwind / zero-anchor
  partial add.  `_modify_order` and the dict producers are gone.
  `synthesize(action_groups, ctx, action_ids)` threads the log's ids.
- `execution.py`: `ExecutionRequest` deleted; `execute_group(order_group, ctx)`
  probes every order, blocks all N on any failure (`probe_status` per order,
  `blocked_by = DATA_MISSING` or `GROUP_ATOMICITY:<trigger>`), else fills all at
  T close.  `leg_dict_from_order_leg` is the inverse leg mapping.
- `execution_log.py`: `ExecutionRecord` carries `action_id`, `order_group_id`,
  `probe_status`, `blocked_by`.
- `backtest_engine.py`: `synthesize(..., action_ids)`; dispatch runs the check
  adapter, calls `execute_group`, writes one execution record per report,
  finalizes the record with `order_ids` / `order_outcomes`, and commits only on
  an all-`FILLED` group.  New `_commit_order_group` / `_commit_open` /
  `_commit_extend` / `_commit_structure` group by `action_id`, raise on a mixed
  open/target action, and derive tags from the action spec.  The compound
  `_execute_*` methods are deleted.

### Tests
- `tests/test_order_synthesis.py` rewritten: `BOOK_CORPUS` (11 cases) is applied
  through `_apply_orders_to_stub_book` and compared as book state, plus direct
  `Order` assertions (`action_id`, 32-hex `order_id`, target ids, leg side /
  quantity / contract extras).  New fail-loud cases: unknown trade, empty-book
  unwind, zero-anchor add, mismatched `action_ids`.
- `tests/test_execution.py` rebuilt on `OrderGroup`; adds group atomicity and
  lineage tests.  `tests/test_execution_log.py` adds the new fields.
- `tests/test_actions.py` / `test_orders.py` migrated to `size` / `OrderOutcome`
  and the moved `OrderGroup` tests.  `tests/test_signal.py` reads `action.size`.
- `tests/order_shim.py` deleted; `test_backtester.py` rewritten to emit
  `ActionGroup`s and to drive unwind equivalence through the real dispatch path.

### Test-count reconciliation (baseline 583 → applied 595, +12)
| Test file | Before | After | Delta |
|---|---:|---:|---:|
| `tests/test_actions.py` | 110 | 108 | **−2** |
| `tests/test_backtester.py` | 38 | 37 | **−1** |
| `tests/test_execution.py` | 18 | 21 | **+3** |
| `tests/test_execution_log.py` | 9 | 10 | **+1** |
| `tests/test_order_synthesis.py` | 64 | 68 | **+4** |
| `tests/test_orders.py` | 16 | 23 | **+7** |
| all other files | 328 | 328 | 0 |
| **total** | **583** | **595** | **+12** |

### Gates (applied tree)
```
Gate A  SMA baseline (scratch, pre-edit)   SHA 9273de83…; 258 lines / 39,981 bytes / 230 UUIDs / 0 stderr
Gate B  SMA applied  (scratch)             SHA 9273de83… -> IDENTICAL (canonical diff empty)
Gate C  full suite                         python -m pytest -q -> 595 passed, 2 warnings
Gate D  greps                              no actions.OrderGroup / _modify_order /
                                           Action.quantity / ExecutionRequest / TransferEvent /
                                           ActionOutcome / modification_notes / action_outcomes /
                                           order_shim / TargetTrade / compound-dict prose
Gate E  untouched                          sma_crossover.py 1c45240a…, data_view.py 906c4e45…
                                           (sizing_price at data_view.py:169)
```

Environment: Python 3.12 (`conda run -n backtest`).  `results/` not written by
the gates (both scratch copies).

### Scope
- Phase B of five.  The check-chain adapter, `Disposition` /
  `DispositionKind` / `REPLACED`, `check_rules.py`, SMA sizing and
  `data_view.sizing_price` are untouched by design and belong to C1/C2.

## 2026-10-22 – Phase C: SMA T‑1 fractional sizing, `is_tradable`, remove check rules + disposition taxonomy

### Prompt
Final phase of the flattening.  Intentional **break** of SMA stdout
byte-identity (the only phase that does), **stderr stays 0**.  Signals emit only
tradable actions via `BaseSignal.is_tradable`; no check rules; no disposition
taxonomy; SMA sizes fractional at the T-1 reference close.

### Merged-scope note (C1 + C2)
Disposition-taxonomy removal is bundled with the SMA sizing change rather than
split out.  Consequence: the disposition removal is **not protected by a
byte-identity gate** (stdout breaks anyway).  It is protected only by invariant
tests on `ActionGroupRecord.finalize` and by the fact that it is dead-code
removal — post-B the `Disposition` field was only ever *written*, never read by
consumer-visible behaviour.

### Ruling checkpoint (verified before edits)
```
SMA baseline (scratch, canonical)  SHA cc6b08fbfa7466dca4f9084a37998775db9100b5af09a13409b1a2118ed62560
                                  257 lines / 46,189 raw / 39,979 normalized / 230 UUIDs / 0 stderr
SMA predicted (staged)             SHA be8d98254dce3c937a4effba0202a1e09b56b7b1d4115f80d24334ded981572c
Baseline collected tests           595
```
- SMA signature `generate_action_groups(self, data_view, action_group_log,
  position_book)`; T is `data_view.date`.
- `CalendarProvider.is_valid_day(holiday_code, date) -> bool`.
  Calendar codes: `BacktestConfig.simulation_calendar_codes` (union) and the
  existing per-ticker `BacktestConfig.ticker_to_calendar_code` (reused, not
  duplicated).
- Unmapped-ticker policy: **fail-closed** with a configured provider
  (`ValueError`); calendar-blind when no provider.
- Price guard `price is None or price <= 0` preserved.  The old
  `shares <= 0` early return is **retained**: under fractional sizing it is
  unreachable for a positive notional/price, but reachable for a non-positive
  `notional`, so it stays as a cheap config guard.

### Calendar-gating equivalence (the four HK-closed days)
| date | pre-C | post-C | eventual exit |
|---|---|---|---|
| 2009-01-26 | UNWIND emitted, rejected downstream | no emission / no record | — |
| 2009-01-27 | UNWIND emitted, rejected downstream | no emission / no record | — |
| 2009-01-28 | UNWIND emitted, rejected downstream | no emission / no record | — |
| 2009-01-29 | UNWIND fills | UNWIND fills | **2009-01-29** |
| 2012-04-04 | UNWIND emitted, rejected downstream | no emission / no record | — |
| 2012-04-05 | UNWIND fills | UNWIND fills | **2012-04-05** |

Demonstrated, not asserted: the signal is stateless and re-emits the cross on
the next open day, so the eventual close is identical.  Only the four closed-day
records disappear (461 → 457 action-group records).  The same mechanism removed
four would-be NEWs that pre-C silently vanished on union-open/US-closed dates
(2002-09-02, 2015-02-16 ×2, 2016-05-30) because the loop-day close was missing;
post-C they vanish by an explicit gate.  stdout unchanged by (b).

### Two-source stdout diff attribution
| run | trades | cost | return_gross |
|---|---:|---:|---:|
| baseline (int, T) | 230 | 7,889.76 | 334,940.587755 |
| fractional only (T) | 230 | 7,895.27 | 335,308.737370 |
| T-1 only (int) | 230 | 7,899.90 | 335,514.885533 |
| post-C (fractional + T-1 + gate) | 230 | **7,905.31** | **335,882.529559** |

- **(a) sizing** — fractional shares ≈ +$5.51 cost; T-1 reference ≈ +$10.14;
  combined +$15.55 / +$942 gross (non-additive: per-trade rounding and the T-1
  reference interact).
- **(b) calendar handling** — **0 stdout magnitude**.  Pre-C already executed
  nothing on those days (rejected downstream) or emitted nothing (missing T
  close); post-C simply does not create the records.  It is the source of the
  **record-count** change (461 → 457), not of any metric change.

### Applied byte record
```
SMA applied (canonical)  SHA be8d98254dce3c937a4effba0202a1e09b56b7b1d4115f80d24334ded981572c
                         (== the staged prediction; a mismatch would STOP, not re-baseline)
                        257 lines / 46,189 raw / 39,979 normalized / 230 UUIDs / 0 stderr
```
Canonical method: UUID tokens (`8-4-4-4-12` or 32-hex) → `UUID_0001…` in
first-encounter order, then SHA-256 over the raw stdout bytes.  **New
baseline.**  The byte-identity failure protocol is deliberately *not* used.

### stderr
**0 warnings** on the four HK-closed days (the whole run emits 0).  Closed
markets produce no order, so `SimulatedExecution` never warns.

### Source changes
- `signals/base_signal.py`: `calendar_provider` / `ticker_to_calendar_code`
  constructor deps (copied); `is_tradable` (fail-closed, documented).
- `signals/sma_crossover.py`: forwards deps; gates per ticker before any read;
  sizes `notional / reference_price`; both guards preserved.
- `data_view.py`: `reference_price(ticker) == get_price(ticker)` (T-1, no
  look-ahead, no fill limit); `sizing_price` deleted.
- `check_rules.py` deleted; `backtest_engine.py` loses the check view, the
  rule-chain types, chain threading and the config seam that selected them;
  dispatch is execute → finalize → commit.
- `actions.py`: the disposition taxonomy and
  `ActionGroup.original_action_group_id` deleted;
  `ActionGroupRecord.finalize(order_ids, order_outcomes, group_note=None)`
  with a private `_finalized` write-once sentinel set only on success.
- `action_group_log.py`: the disposition import and the replacement transition
  removed.
- `execution.py`: docstring no longer references the removed rule context.
- `examples/sma_crossover_example.py`: provider built before the signal and
  passed to it.

### Calendar-reject test rewrite
`TestBacktesterCalendarRule` → `TestCalendarGating` + `TestSmaCalendarGating`.
The mock-signal tests now pin the *engine* truth (no engine gate; a union-closed
day with a price row fills; a consistent-closed day blocks at execution and
warns).  The SMA tests pin signal-side gating on the real fixtures: **no
`ActionGroupRecord` exists** on 2009-01-26/27/28 and 2012-04-04; the trades
close on 2009-01-29 and 2012-04-05 (equivalence demonstrated in the
checkpoint), 457 records all finalized, and **zero warnings**.

### Naming decision — portfolio-layer `ExecutionStatus.REJECTED` → `DECLINED`
The planned portfolio-layer enum (§10) used `REJECTED`.  Renamed to `DECLINED`
to disambiguate it from the **removed** action-layer `DispositionKind.REJECTED`:
same word, different layer, different semantics.  The rename prevents future
readers from conflating portfolio gate outcomes with the deleted action-layer
taxonomy.  *Not* done for grep satisfaction.  §10 semantics are unchanged and
those notes are planned-only, never live code.

### Deferred `REPLACED` readd
Registered in `docs/phase2_plan.md`: the replacement-lineage field on
`ActionGroup` and the log transition are re-added with the **scaling rule**
(the only consumer — scaling supersedes a signal action with derived actions).

### Tests (595 → 573)
| file | before | after | delta | reason |
|---|---:|---:|---:|---|
| `tests/test_check_rules.py` | 25 | 0 | −25 | deleted with the check chain |
| `tests/test_actions.py` | 108 | 98 | −10 | −7 disposition, −3 replacement lineage |
| `tests/test_backtester.py` | 37 | 40 | +3 | −4 rule tests, +7 gating/equivalence tests |
| `tests/test_data_view.py` | 29 | 30 | +1 | −4 sizing, +5 reference (no-look-ahead A/B/C + mapped + feed) |
| `tests/test_signal.py` | 20 | 29 | +9 | +6 `is_tradable`, +3 SMA gating |
| all other files | 376 | 376 | 0 | untouched |
| **total** | **595** | **573** | **−22** | |

### Gates (applied tree)
```
Gate A  SMA staged prediction   be8d9825…  (hard gate — applied must equal this)
Gate B  SMA applied             be8d9825…  -> MATCH; new baseline
Gate C  stderr                  0 on the four HK-closed days
Gate D  full suite              python -m pytest -q -> 573 passed, 2 warnings
Gate E  greps (live code + design prose; historical worklog exempt)
        sizing_price / CalendarValidationRule / RuleChain / RuleContext /
        _check_view / Disposition / REPLACED / original_action_group_id /
        check_rules / order_rules / DEFAULT_CHECK_RULES / REJECTED /
        DISPATCHED -> zero hits, except the single deferred-`REPLACED`
        registration (phase2_plan + this entry) and §10's planned
        DECLINED naming note
```
Multi-action guard ordering in `_dispatch_synthesized_order` confirmed:
the `len(...actions) != 1` guard precedes `actions[0]`.

### Scope / process
No git operations.  `results/` not written by the gates (scratch copies only).

## 2026-10-22 – Task 5d-1a: B1 NEW-extend trade validation + `LegSpec.size` positivity

### Prompt
Post-implementation review found two clear-cut defects.  Both fix without a
behaviour change to the SMA example (neither path is triggered by current
signals), so output byte-identity is preserved.  **B2 (`reference_price` fallback)
and B3 (same-day modification handling) are held pending design rulings and are
not touched here.**

### Ruling checkpoint (verified before edits)
```
SMA baseline (scratch, canonical)  SHA be8d98254dce3c937a4effba0202a1e09b56b7b1d4115f80d24334ded981572c
                                   257 lines / 46,189 raw / 39,979 normalized / 230 UUIDs / 0 stderr
Collected tests (actual)           573
```
- `_trade_state(trade_id, ctx, strategy_id)` returns the T-1 `TradeSnapshot` or
  raises `ValueError("no active trade ...")`; already used by whole-trade UNWIND
  (`order_synthesis.py:210`).
- B1 site: the NEW + `StructureSpec` + `trade_id` branch of `_action_to_orders`.
- `LegSpec.size` validation site: `LegSpec.__post_init__`, after the numeric check.
- Zero stays legal (schema-level non-traded/edge content; a NEW leg's zero is
  refused later by `_order_leg`), `None` stays legal (guarded by `_order_leg`).

### B1 — NEW-extend now validates the target trade
**Layer-mismatch fix.**  The extend path emitted `Order(structure_id=None,
trade_id=X)` for any `X`, so an unknown trade surfaced only downstream as
`DATA_MISSING` at execution.  Conversion now calls
`_trade_state(action.trade_id, ctx, strategy_id)` before materialising extend
orders, so an unknown trade raises `ValueError` at conversion -- consistent with
partial-add structure/trade validation and whole-trade UNWIND.

Create-NEW (`TradeSpec`) is deliberately unaffected: it opens a trade and has no
T-1 target to resolve.

### `LegSpec.size` positivity
`__post_init__` now rejects a negative size:
`"LegSpec.size must be non-negative; direction is carried by side"`.
Previously `abs(leg.size)` in conversion turned `LegSpec(size=-100, side=LONG)`
into BUY 100, contradicting `signed_size`.  Zero and positive sizes remain
accepted.

### Tests (573 → 577, +4)
| file | change | delta |
|---|---|---:|
| `tests/test_order_synthesis.py` | +extend unknown trade raises, +extend known trade succeeds | +2 |
| `tests/test_actions.py` | +negative size rejected, +zero/positive accepted | +2 |

### Gates (applied tree)
```
Gate A  SMA applied (scratch, canonical)  SHA be8d98254dce3c937a4effba0202a1e09b56b7b1d4115f80d24334ded981572c
                                          -> IDENTICAL to pre-edit baseline; 257 lines / 46,189 raw /
                                             39,979 normalized / 230 UUIDs
Gate B  stderr                            0
Gate C  full suite                        python -m pytest -q -> 577 passed, 2 warnings
```
Canonical method is unchanged from the Phase C baseline (UUID tokens -> `UUID_0001…`
in first-encounter order, then SHA-256 over raw stdout).

### Held for design rulings (not fixed here)
- **B2** — `DataView.reference_price` fallback behaviour.
- **B3** — same-day modification handling.
SMA signal, `DataView.reference_price`, `SimulatedExecution._probe_target` and the
`execution.py:157` warning text are untouched.

### Scope / process
No git operations.  `results/` not written by the gates (scratch copies only).

## 2026-10-22 – Task 5d-1b: bounded sizing staleness (B2) + duplicate structure mods (B3a) + commit tripwire (B3b)

### Prompt
Three post-review fixes.  B2 replaces Phase C's unbounded forward-fill with a
bounded-staleness model (default 7 days) applied identically to mapped and
unmapped tickers; the SMA baseline is re-captured (behaviour may move in either
direction).  B3a rejects two same-day actions targeting one structure.  B3b
adds a defensive commit precondition tripwire.  No git operations.

### `get_price` verification (pre-apply item 1)
`get_price(ticker, as_of=None)` **does** call `last_valid_day` internally
(`data_view.py:135`), so the naive B2 patch would have widened `get_price`
(mapped ticker, calendar-valid day with no row: `None` -> fallback row).  The
reviewer's split was adopted: `last_valid_day` and `get_price` keep their
pre-B2 shape; the mapped-gap fallback lives **only** in `reference_price`.
Verified by extracting both functions from the pre-edit and post-edit trees:
`get_price` **IDENTICAL**, `last_valid_day` **IDENTICAL**.  Case A, split path.

### B2 — bounded `reference_price`
- `DataView(max_staleness_days=7)` keyword; negative rejected with `ValueError`.
- `reference_price`: resolve `last_valid_day`; if that day has no data row, scan
  back for the last data row at/before the cutoff regardless of calendar; then
  bound the landing day by `max_staleness_days` and return its value.  A gap
  beyond the bound -> `None`.  `None` now has two causes: no observation, or
  stale beyond the bound (Phase C's "no fill limit" wording removed).
- `get_price` / `last_valid_day` unchanged (see above), so other price readers
  see no semantic widening.

### B2 attribution (two-stage)
```
SMA baseline (scratch, canonical)  SHA be8d98254dce3c937a4effba0202a1e09b56b7b1d4115f80d24334ded981572c
                                   257 lines / 46,189 raw / 39,979 normalized / 230 UUIDs / 0 stderr
Post-B2 SMA (scratch, canonical)   SHA be8d98254dce3c937a4effba0202a1e09b56b7b1d4115f80d24334ded981572c
                                   IDENTICAL to baseline; 230 trades / 457 records
entries added  (None -> price)     0
entries skipped (price -> None)    0
reference_price calls during run   230 (all unchanged)
```
Counted by wrapping `DataView.reference_price` during the real SMA run and
comparing the pre-B2 read (`get_price(ticker)`) with the post-B2 result.  The
SMA's mapped tickers never hit the two changed paths: their calendar-valid day
always has a row, and their gaps are within 7 days.

### B3a — reject duplicate structure modifications per day
`_validate_no_duplicate_structure_mods` runs after `synthesize` and before the
dispatch loop.  Two orders in one day's patch naming the same `structure_id`
raise `ValueError("... targeted by multiple actions ...")`; this is a fail-loud
abort, not a `REJECTED` record (the no-reject-path invariant holds).  Covers
two groups, whole-trade UNWIND overlapping a structure action, and whole-book
UNWIND overlapping a structure action.

### B3b — commit precondition tripwire
`_assert_commit_preconditions` runs at the top of `_commit_order_group`, before
any mutation, raising `RuntimeError("commit invariant violated: ...")` when a
targeted trade or structure is absent, an order leg's ticker is not in the
target structure, or a reducing leg exceeds the structure's current size.  It
is a **tripwire, not a transaction/rollback**: execution records and
`finalize` are already written, so a fire aborts loudly with no undo.  Under
the current invariants it cannot fire.

### Attribution result (B3)
```
Post-B3 SMA (scratch, canonical)   SHA be8d98254dce3c937a4effba0202a1e09b56b7b1d4115f80d24334ded981572c
Assertion  post-B3 == post-B2      PASS (canonical diff empty)
                                   230 trades / 457 records; 0 stderr
```
B3 is behaviour-inert for the SMA, as designed.

### Tests (577 -> 591, +14)
| file | change | delta |
|---|---|---:|
| `tests/test_data_view.py` | +6 staleness tests; `_view` pass-through; Test C comment updated | +6 |
| `tests/test_backtester.py` | +4 duplicate-mod tests, +4 commit-tripwire tests (incl. unmatched leg) | +8 |
| `tests/test_signal.py` | fixture dates moved to end at the cutoff (no count change) | 0 |

### Deviation — `tests/test_signal.py` fixture dates
The file is not in the original change list.  Its mocked price series started
`2024-01-01`, ending ~4 months before the view's `2024-06-14` cutoff; under the
new bound that is correctly *stale* and five signal tests failed.  The fixtures
now end at the cutoff (`make_price_series(..., end_date="2024-06-14")`), which
tests the intended signal behaviour instead of asserting a stale price.  No
production semantics were relaxed for this.

### Gates (applied tree)
```
Stage 1 (B2)       python -m pytest -q -> 583 passed
Stage 2 (B3a+B3b)  python -m pytest -q -> 591 passed
SMA canonical      pre-edit == post-B2 == post-B3 (be8d9825…); 0 stderr
```

### Scope / process
No git operations.  Gates run in scratch copies; repo `results/` not written.

## 2026-10-23 – Strategy-layer cleanup: remove preemptive `strategy_id`, rename `OrderSynthesis` → `OrderAssembly`

### Prompt
Two behavior-preserving cleanups.  (1) `strategy_id` was preemptive
multi-strategy scoping: the framework is one-signal-per-run, every record carried
the same value, and the supporting scoping machinery (`ActionGroupLogView`,
`_by_strategy`, `PositionBooks.for_strategy`, per-record copies on execution)
would *fail* if two strategies ever ran in one loop.  `Trade` already omitted it;
this extends that design to the whole pipeline and re-adds `strategy_id` at the
§10 ingestion boundary, where it has a real consumer.  (2) `OrderSynthesis` was a
misleading name — the class runs the synthesis rule chain *and* the order
conversion — so it is renamed `OrderAssembly`, matching design-notes §3.8 "Order
assembly".  No git operations.

### Ruling checkpoint (verified before edits)
```
Grep hit counts (live code), before:
  strategy_id      backtester 38 / tests 47 / examples 1
  OrderSynthesis   backtester 8  / tests 20 / design 3 / phase2 2
  .synthesize(     engine 1 / module 1 / docstrings 2 / tests 16
  for_strategy     backtester 7  / tests 15
  ActionGroupLogView backtester 6 / tests 2 / design 2
  by_strategy      backtester 10 / tests 11
  last_action_group backtester 3 / tests 7
PositionBooks.find_holding directly reachable:
  tests/test_actions.py::TestPositionBooks::test_find_holding_reports_address_and_leg
  and ::test_find_holding_uses_snapshot_order already call
  PositionBooks(...).full().find_holding(...); the SMA uses only
  position_book.find_holding (sma_crossover.py:112).
Behaviour-inert: the SMA never branches on strategy_id; for_strategy returned the
  same global book and the view filtered the single run id (i.e. all records);
  the converter used for_strategy only to fetch that same book.
SMA baseline (scratch, canonical)  SHA be8d98254dce3c937a4effba0202a1e09b56b7b1d4115f80d24334ded981572c
                                   257 lines / 46,189 raw / 39,979 normalized / 230 UUIDs / 0 stderr
Collected tests (actual)           591
```

### `OrderSynthesis` → `OrderAssembly`
- Class `OrderSynthesis` → `OrderAssembly`; method `.synthesize(...)` →
  `.build_order_groups(...)`; module `order_synthesis.py` →
  `order_assembly.py`; `BacktestConfig.order_synthesis` → `.order_assembly`.
- Class docstring rewritten to describe the stage (synthesis rule chain, empty
  today, then `action_group_to_order_group` per surviving group), not one of its
  two operations.
- Test module renamed `tests/test_order_synthesis.py` →
  `tests/test_order_assembly.py` (count-neutral).

### `strategy_id` removal (strategy layer)
Fields removed: `ActionGroup.strategy_id` (and its `__post_init__` validation),
`ExecutionContext.strategy_id`, `ExecutionReport.strategy_id`,
`ExecutionRecord.strategy_id`, and `BaseSignal.__init__(strategy_id=...)` plus
`self.strategy_id`.  Machinery removed: `ActionGroupLog._by_strategy`,
`.by_strategy(...)`, `.last_action_group(strategy_id)`, `.for_strategy(...)`,
the whole `ActionGroupLogView` class, and `PositionBooks.for_strategy(...)`.

The engine now calls
`signal.generate_action_groups(data_view, self.action_group_log, position_books.full())`
and `assembly.build_order_groups(...)`.  `position_books.full()` is used rather
than passing the `PositionBooks` wrapper because the signal needs the
`PositionBook` (`find_holding`); `full()` returns the same object `for_strategy`
did, so this is behavior-identical.  The converter's four book lookups likewise
use `ctx.position_books.full()`.

**Read-only guarantee trade-off (explicit).**  `ActionGroupLogView` enforced
"signals can read but not append."  After removal the signal receives the
`ActionGroupLog` directly and **signals can now call `log.append()`**.  This is a
conscious swap of a structural guarantee for a convention in a one-signal layer;
re-introduction is deferred to a real multi-strategy need.

### Test-removal audit
Removed outright (10) — each subject is either a deleted field/API or a
guarantee consciously traded away, never the sole coverage of surviving
behaviour:

| removed test | subject |
|---|---|
| `TestActionGroup::test_requires_a_strategy_id` | deleted field validation |
| `...LogIndices::test_by_strategy` | deleted strategy index |
| `...::test_by_strategy_last_n_days_keeps_whole_days` | deleted recent-tail API |
| `...::test_last_action_group` | deleted per-strategy last-record API |
| `...::test_for_strategy_view_is_scoped` | deleted view |
| `...::test_for_strategy_view_does_not_expose_other_strategies` | deleted view isolation |
| `...::test_for_strategy_requires_an_id` (view) | deleted view arg validation |
| `...::test_view_has_no_append` | the structural read-only guarantee (traded away) |
| `TestPositionBooks::test_for_strategy_requires_an_id` | deleted book arg validation |
| `TestSMACrossoverSignal::test_strategy_id_is_required` | deleted constructor requirement |

Rewritten in place (count preserved, orthogonal coverage kept):
- `test_is_frozen` (provenance instead of strategy_id);
  `test_by_structure` (asserts emission_date, not strategy_id);
  `test_record_for` / `test_records_are_live_references` / `test_records_are_append_only`
  (direct log API; live-reference coverage uses `log.records[-1]` + `record_for`);
  `test_for_strategy_returns_the_full_book_identity` → `test_full_returns_the_book_identity`;
  `test_requires_a_non_empty_strategy_id` → `test_identity_is_the_instance`;
  `test_book_and_log_view_are_always_passed` → `test_book_and_log_are_always_passed`;
  `test_action_group_log_view_grows_with_this_strategy` → `test_action_group_log_grows_across_the_run`.

Orphan check: append/id stamping + `action_ids` minting remain covered by the
untouched `TestActionGroupLogAppend` suite; live references and append-only by
the rewritten tests above; `find_holding` direct by the existing `.full()` tests.
No surviving orthogonal behaviour lost coverage.

Count: **591 → 581 (−10)**; the test-module rename is count-neutral.

### Deferred (registered in `docs/phase2_plan.md`)
- **`strategy_id` at §10 ingestion.** Each saved `BacktestResult` came from one
  strategy; at load time wrap with `StrategyRun(strategy_id, result)` and tag
  `Trade` / `ExecutionRecord` if flattened.  `strategy_id` is not a
  strategy-layer field.  Design notes carry the same statement in the §10
  reconciliation note.
- **Split `OrderAssembly` when rules land.** One class holds the synthesis rule
  chain (empty) and order conversion; split into `SynthesisChain` +
  `OrderConverter` when the first concrete rule (roll / auto-unwind / hedge /
  scaling) lands.

### Gates (applied tree)
```
Gate A  SMA applied (scratch, canonical)  SHA be8d98254dce3c937a4effba0202a1e09b56b7b1d4115f80d24334ded981572c
                                          -> IDENTICAL to pre-edit baseline; 257 lines / 46,189 raw /
                                             39,979 normalized / 230 UUIDs; 0 stderr
Gate B  full suite                        python -m pytest -q -> 581 passed, 2 warnings
Gate C  greps (live code + design live prose; historical worklog exempt)
        strategy_id -> backtester/ tests/ examples/: zero hits
        OrderSynthesis / .synthesize( / for_strategy / ActionGroupLogView /
        by_strategy / last_action_group / order_synthesis -> zero hits
        (design_notes.md + phase2_plan.md live sections also zero)
```
`strategy_id` survives only in the §10 planned prose (`PortfolioAllocator` /
`StrategyContribution` / `ExecutionRecord` planning), the new §10-ingestion
statements, the deferred phase2 registrations, and historical worklog entries.

### Scope / process
No git operations.  Gates run in scratch copies; repo `results/` not written.
`Trade`, `StrategyStructure`, `LegState`, `Contract`, `Order*`, B2 staleness,
B3a duplicate check and B3b commit tripwire untouched; SMA signal behavior,
sizing and calendar gating untouched.

## 2026-10-23 – Remove the local DeepSeek-harness `tmp_path` workaround

### Prompt
The local `tests/conftest.py` existed only to work around the restricted-token
sandbox shipped with the DeepSeek harness (dsh); that harness is no longer in
use.  Delete the workaround, its scratch base `tests/.tmp/`, and every live
reference to it.  No git operations.

### Why the sandbox kept asking to delete files
`pytest_sessionstart` in the local conftest swept `tests/.tmp/*` with
`shutil.rmtree` **at every pytest invocation, including `--collect-only`** (the
hook runs, fixtures do not).  Each `tmp_path` consumer created its own
`tests/.tmp/<test_name>_<uuid8>/` directory, removed by a per-test `finally`.
When the sandbox's bulk-delete guard rejected the sweep, the pytest process was
killed before those `finally` blocks ran, leaving the directories behind — which
made the next session start with a larger sweep, i.e. a self-sustaining loop:

    stale dirs -> sessionstart sweep blocked -> run killed -> teardown skipped
               -> more stale dirs

At the time of removal `tests/.tmp/` held **16 directories / 42 files**, all
created 2026-10-23 23:01:47–23:02:15 by the two blocked runs.

### Removal
- `tests/conftest.py` — deleted.  Was local-only, never committed
  (`git ls-files tests/conftest.py` -> empty), so no untracking was needed.
  Verbatim backup kept at
  `%TEMP%\qbt_tests_conftest_backup_20261023.py` for one-session rollback.
- `tests/.tmp/` — deleted recursively (16 dirs / 42 files).
- The per-test teardown path is gone with the file; nothing writes inside the
  repo tree during tests any more.

### Documentation updates
- **`AGENT.md`** — `## Testing Infrastructure (environment-specific)` (the dsh
  recipe, incl. the upstream discussion #81 link) replaced by a section stating
  the built-in `tmp_path` works as-is, recording the verification
  (581 passed, 0 errors, no `WinError 5`), and carrying forward the standing
  rules: no `--basetemp`, no probe/diagnostic directories, no elevated or
  full-access permission requests, stop-and-report on recurrence.
- **`.gitignore`** — dropped the now-orphaned `tests/.tmp/`, the
  `# local-only sandbox workaround; never commit` comment and the
  `tests/conftest.py` entry.  `.workbuddy/` stays.
- **`docs/phase2_plan.md`** (Testing & hardening) — the
  "Revisit the local conftest workaround ... once the DSH sandbox tmp_path bug
  is confirmed fixed upstream" checkbox is now `- [x]` with its resolution,
  per the file's convention of marking completed items rather than deleting
  them.
- **`docs/worklog_phase2.md`** — historical entries (2026-09-19 / 2026-09-20,
  and today's strategy-layer entry) left untouched; they are records of what
  was true when written.

### Gates (applied tree)
```
Gate A  full suite (conftest deleted)   python -m pytest -q -> 581 passed, 2 warnings in 19.70s
Gate B  full suite (after doc edits)    python -m pytest -q -> 581 passed, 2 warnings in 19.26s
        0 failures, 0 errors, 0 PermissionError [WinError 5]
Gate C  tests/.tmp recreated?           -> absent after both runs
Gate D  grep -rn "tests/.tmp|tests/conftest" AGENT.md .gitignore
        -> AGENT.md:53,55 only (the deliberate "do not recreate" warning)
        -> .gitignore: zero hits
Gate E  git ls-files tests/conftest.py  -> empty (never tracked)
```

### Scope / process
No git operations; nothing committed or staged.  Files changed: `AGENT.md`,
`.gitignore`, `docs/phase2_plan.md` (content) and `tests/conftest.py`,
`tests/.tmp/` (deleted).  No production code, no tests under `tests/*.py`, and
no other project files were touched; the 581-test count is unchanged by this
cleanup — it is the same suite as before, now running on pytest's own
`tmp_path`.
