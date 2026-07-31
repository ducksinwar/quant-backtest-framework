# Phase 2 Plan

**Status:** Planning  
**Start date:** TBD  
**Target:** Complete core backtester enhancements (Phase 2A), then build validation pipeline (Phase 2B). Risk bridge deferred to Phase 2C (future).

---

## Phase 2A – Core Infrastructure & Abstractions

### Task 1: Summary Refactoring – Pluggable MetricCalculator & BaseReport Registries
- [x] **Goal:** Replace hard‑coded metric functions and report builders with a registry pattern (like CostModel). Summary becomes a thin data coordinator.
- **Deliverables:**
  - `BaseMetricCalculator` ABC + registry (wrapping existing pure functions).
  - `BaseReport` ABC + registry (each standard report becomes a class).
  - Summary retains only data orchestration and caching helpers.
  - All existing tests pass with identical output.
- **Dependencies:** None

### Task 2: Contract / LegState Split + Remove Redundant `cost_leg_id`
- [x] **Goal:** Separate static contract definition from mutable position state. Clean up legacy `cost_leg_id` field while touching those modules.
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

### Correctness fixes (pre‑Task 3)
- [ ] **Multi‑leg cost overcount:** add `leg_size_changes` to event log and use per‑leg delta in cost calculator.
- [ ] Add multi‑leg proportional‑add cost test to validate the `leg_size_changes` fix (finding 3.3).
- [ ] **Opening‑day P&L / pricing‑input alignment:** record 0.0 P&L and pricing inputs at trade creation; remove Summary prepend‑zero.
- [ ] **None inside compute_cost_exposure:** return None from pricer when price is missing.
- [ ] **Float‑equality unwind fraction:** add range guard and tolerance check for full close.
- [ ] **pytest.raises(FrozenInstanceError) in frozen‑snapshot test.**

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
   - `OrderGenerator` introduces a truncated `DataView` that prevents signals from accessing data beyond T‑1, making the no‑look‑ahead property structural rather than conventional (finding 1.2).
- **Dependencies:** Tasks 2, 3, 4

---

## Phase 2B – Validation Pipeline

### Testing & hardening
- [ ] Add invariant/property tests for P&L conservation, time‑series length alignment, and missing‑data deferral (finding 3.2).
- [ ] Fill coverage gaps for untested branches (e.g., `total_size == 0` fallback, `per_leg` missing‑data mode) (finding 3.4).

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
- A lightweight, immutable `RiskPosition` dataclass holds only what the risk engine needs: instrument identity (ticker, asset_class, multiplier, currency), net position size, current price, and per‑unit greeks (delta, gamma, etc.).
- The backtester produces a daily time series of `RiskPosition` objects by netting all `LegState` objects per ticker and fetching greeks from the pricer. For the current equity‑only scope, netting is per ticker. When options or futures are added, the netting key expands to include contract‑specific parameters (strike, expiry) so distinct instruments on the same underlying are not incorrectly aggregated.
- The same `RiskPosition` class is produced by the live position system from its blotter, so the risk engine consumes both historical simulations and live positions through a single interface.
- The risk engine never imports `LegState` or other backtester internals — it depends only on `RiskPosition`.
- Gross trade/leg detail (for margin, funding, and settlement) is a separate concern and is not part of `RiskPosition`; the backtester's event log and trade history already contain sufficient detail for those calculations if needed later.
- This design ensures the backtester and live system are aligned on risk analytics while keeping each pillar independent.
- Surface `cost_data_gaps` in Summary output so that missing‑cost days are visible to the user (finding 1.5).
- Populate `LegSnapshot` greeks once risk measures are implemented (finding 2.4).

## Phase 3+ (Future)
- [ ] Introduce a `CostExposure` TypedDict for type safety in the cost‑exposure path (finding 2.1).
- [ ] Replace `requires_portfolio_state` / `requires_trade_history` class attributes with constructor‑enforced declarations or properties (finding 2.3).
- [ ] Extract a `MissingDataAligner` class from `Summary` if the class grows beyond its current scope (finding 2.5).
- [ ] Migrate original trading intent (tenor, delta, etc.) from `Contract.params` to `LegState.original_intent` so that `Contract` becomes a pure, hashable instrument identity (prerequisite for Phase 4 risk aggregation and multi‑leg netting).