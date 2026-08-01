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