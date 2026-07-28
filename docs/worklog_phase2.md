# Phase 2 Work Log

**Start:** 2026‑06‑18 &nbsp;|&nbsp; **End:** — &nbsp;|&nbsp; **Status:** In progress

## Table of Contents

| Step | Date | Topic | Section |
|------|------|-------|---------|
| 1 | 06‑18 | Design notes: CalendarProvider + OrderGenerator + Phase 2 plan | [§ Design notes](#2026-06-18--design-notes-calendarprovider-ordergenerator-phase2-plan) |
| 2 | 07‑25 | Documentation restructuring: archive Phase 1, rename + move docs | [§ Docs restructure](#2026-07-25--documentation-restructuring-archive-phase1-rename--move-docs) |

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
