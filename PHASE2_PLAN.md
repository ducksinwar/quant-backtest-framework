# Phase 2 Plan

**Status:** Planning  
**Start date:** TBD  
**Target:** Complete core backtester enhancements (Phase 2A), then build validation pipeline (Phase 2B). Risk bridge deferred to Phase 2C (future).

---

## Phase 2A – Core Infrastructure & Abstractions

### Task 1: Summary Refactoring – Pluggable MetricCalculator & BaseReport Registries
- [ ] **Goal:** Replace hard‑coded metric functions and report builders with a registry pattern (like CostModel). Summary becomes a thin data coordinator.
- **Deliverables:**
  - `BaseMetricCalculator` ABC + registry (wrapping existing pure functions).
  - `BaseReport` ABC + registry (each standard report becomes a class).
  - Summary retains only data orchestration and caching helpers.
  - All existing tests pass with identical output.
- **Dependencies:** None

### Task 2: Contract / LegState Split + Remove Redundant `cost_leg_id`
- [ ] **Goal:** Separate static contract definition from mutable position state. Clean up legacy `cost_leg_id` field while touching those modules.
- **Deliverables:**
  - `Contract` (frozen dataclass): ticker, asset_class, multiplier, currency, tags, params.
  - `LegState` (mutable dataclass): holds a `Contract` reference, leg_id, current_price, current_size, entry_price, P&L/risk time series, pricing_inputs.
  - Pricers accept `Contract`, never `LegState`. `compute_cost_exposure` fetches market price from its provider, not from state.
  - `resolve_instrument` returns a `Contract`.
  - Backtester builds and mutates `LegState` objects; `_check_data_available` uses lightweight `Contract`.
  - **Remove `cost_leg_id`** from event log; delete `_cost_leg_id_from_exposures` helper; update tests.
  - `StrategyStructure`, `Trade`, `Snapshots`, `Summary`, `CostModel` updated mechanically.
  - **`Instrument` class removed.**
- **Dependencies:** Task 1 (to avoid merge conflicts in Summary)

### Task 3: FX Conversion (Multi‑Currency Equities)
- [ ] **Goal:** Enable backtesting non‑USD equities and consolidate P&L into a base currency.
- **Deliverables:**
  - `FxRateProvider` wrapping `DataFeed` for spot rates.
  - Cumulative‑spot conversion logic in `Summary.generate()` (already has `fx_rates` parameter).
  - Converted P&L, component PnL, and risk series; equity curve gains `fx_<pair>` column.
  - All aggregated reports work with mixed‑currency legs.
- **Dependencies:** Task 2 (legs carry `currency` from `Contract`)

### Task 4: CalendarProvider
- [ ] **Goal:** Shared holiday calendar service.
- **Deliverables:**
  - `CalendarProvider` class: loads holiday CSVs per calendar code.
  - Methods: `trading_days()` (union), `is_trading_day()`, `next_trading_day()`.
- **Dependencies:** None

### Task 5: OrderGenerator & Signal Intent Interface
- [ ] **Goal:** Separate mechanical order rules from alpha signals.
- **Deliverables:**
  - `AlphaIntent` dict (BUY, SELL, CLOSE with ticker, notional).
  - `OrderRule` ABC and `OrderGenerator` chain (first rule: `CalendarValidationRule`).
  - `BaseSignal` gains optional `generate_intents()`; `SMACrossoverSignal` updated.
  - `Backtester` uses new pipeline when `OrderGenerator` present; legacy `generate_signals()` still works.
  - Notional‑to‑shares conversion moves into `OrderGenerator`.
- **Dependencies:** Tasks 2, 3, 4

---

## Phase 2B – Validation Pipeline

### Task 6: FoldGenerator
- [ ] **Goal:** Produce purged, embargoed walk‑forward fold tuples.
- **Deliverables:**
  - `FoldGenerator` using `CalendarProvider` for business‑day shifting.
  - Returns `(train_start, train_end, val_start, val_end)`.
- **Dependencies:** Task 4

### Task 7: Walk‑Forward Runner & Nested Parameter Selection
- [ ] **Goal:** Full walk‑forward CV with grid search on training windows; aggregated OOS `BacktestResult`.
- **Deliverables:**
  - `WalkForwardRunner` accepting `FoldGenerator`, parameter grid, base config, metric name.
  - Grid search on training window; best parameters selected; validation run.
  - Aggregated OOS `BacktestResult` returned.
- **Dependencies:** Task 6 + full core stack

### Task 8: Summary Verification on Aggregated OOS
- [ ] **Goal:** Confirm `Summary` handles concatenated trade histories from multiple folds.
- **Dependencies:** Task 7

---

## Phase 2C (Future) – Risk Bridge
- Enable trivial delta risk measures for equities.
- Implement `RiskReport` using the new `BaseReport` interface.
- Demonstrates connection to the Risk pillar without new asset classes.