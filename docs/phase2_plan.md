# Phase 2 Plan

**Status:** Working on Phase 2A  
**Start date:** 2026-07-25 
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
- [x] **Multi‑leg cost overcount:** add `leg_size_changes` to event log and use per‑leg delta in cost calculator.
- [x] Add multi‑leg proportional‑add cost test to validate the `leg_size_changes` fix (finding 3.3).
- [x] **Opening‑day P&L / pricing‑input alignment:** record 0.0 P&L and pricing inputs at trade creation; remove Summary prepend‑zero.
- [x] **None inside compute_cost_exposure:** return None from pricer when price is missing.
- [x] **Float‑equality unwind fraction:** add range guard and tolerance check for full close.
- [x] **pytest.raises(FrozenInstanceError) in frozen‑snapshot test.**

### Task 3: FX Conversion (Multi‑Currency Equities)
- [x] **Goal:** Enable backtesting non‑USD equities and consolidate P&L into a base currency.
- **Deliverables:**
  - `FxRateProvider` wrapping `DataFeed` for spot rates.
  - Cumulative‑spot conversion logic in `Summary.generate()` (via `fx_provider` + `base_currency`).
  - Converted P&L, component PnL, and risk series; equity curve gains `fx_<pair>` column.
  - All aggregated reports work with mixed‑currency legs.
- **Dependencies:** Task 2 (legs carry `currency` from `Contract`)

### Task 4: CalendarProvider
- [x] **Goal:** Shared holiday calendar service.
- **Deliverables:**
  - `CalendarProvider` class: I/O‑free calendar math — `trading_days()` (union simulation calendar), `is_valid_day()`, `next_valid_day()` (calendar‑kind‑agnostic per‑code primitives) — constructed with the shared `DataFeed`. Semantics are call‑time only; there is no directory parameter and no "no‑holidays" mode, and an unknown calendar code fails loudly.
  - `CsvBackend.get_holiday_dates(code)` + `DataFeed.get_holiday_dates(code)`: holiday dates per calendar code from `{base_dir}/holidays/{CODE}.csv`, `date` column read by name, normalized to `YYYY-MM-DD`, de‑duplicated into an immutable `frozenset`, cached per code in a namespace separate from price series, with a loud `FileNotFoundError` for a missing code and a `ValueError` for an empty date cell.
  - `BacktestConfig.calendar_provider` (required, no default) + `simulation_calendar_codes`; `calendar_ticker` removed.
  - Data‑layer `trading_days()` removed from `CsvBackend` / `DataFeed` (calendars are cross‑cutting, not market data).
- **Dependencies:** None

### Task 5: Order pipeline — action-group interface, execution seam

Task 5 was delivered in three steps. The as‑built pipeline is
`signal → ActionGroup → (order assembly) → OrderGroup → execution seam → book`,
with an append‑only **action‑group log** and a write‑once **execution log**. The
order assembly is a single **synthesis chain** that transforms action groups
(`rule(action_groups, ctx)`); the engine has no check stage.  The order‑id
fan‑out is handled by `ActionGroupRecord` (`action_ids` → `order_ids`).

> **Naming note.** The schema was renamed in the single‑action‑subset task:
> `Intent`→`ActionGroup`, `LegIntent`→`LegSpec`, `StructureIntent`→`StructureSpec`,
> `WorkingSet`→`OrderGroup`, `IntentLog`→`ActionGroupLog`, modules
> `intents.py`→`actions.py` and `intent_log.py`→`action_group_log.py`. The
> pipeline stage is now **action group synthesis** and its log is the
> `ActionGroupLog`; the old names survive only in historical records.

- [ ] **Task 5a (done): Signal action-group interface, pass‑through synthesis, action-group log.**
  - `BaseSignal.generate_action_groups(data_view, action_group_log, position_book) -> list[ActionGroup]`; no `strategy_id` (identity is the signal instance; §10 ingestion re‑adds it); the `requires_portfolio_state` / `requires_trade_history` flags and `generate_signals()` are removed.
  - `ActionGroup` schema (`ContractSpec`, `LegSpec`, `StructureSpec`, `TradeSpec`, `Action`, `Side`, `OrderGroup`, `AggregationContext`), the append‑only `ActionGroupLog`, the T-1-clamped `DataView`, and `PositionBooks`.
  - `OrderAssembly` producing `OrderGroup`s of `Order` objects; each order carries its own `order_id` / `action_id`.
  - Notional‑to‑shares happens in the signal via `DataView.reference_price` (the T-1 reference close) with fractional sizes.  Moving sizing into synthesis remains future work.
- [ ] **Task 5b‑1 (done): Execution seam, execution log, cost‑writer swap.**
  - `ExecutionBackend` / `SimulatedExecution` (the backtest/live parity boundary) and `ExecutionReport`; the write‑once `ExecutionLog` + `fill_id`; trade↔execution linkage.
  - The data‑availability pre‑check collapses into `SimulatedExecution` blocking (the single warning emitter); a blocked group has `order_outcomes == (BLOCKED,)`, an execution‑log `blocked(DATA_MISSING)`, and is never committed (Flow A).
  - `write_cost_exposures` moves the cost‑exposure computation to the execution side (filled structures only).
- [x] **Task 5b‑2 (landed, then superseded by Phase C): Contract calendar fields.**
  - The order‑side validation stage (its rule types, the short‑circuit chain and
    the config seam that selected them) was **removed**.  Calendar gating is
    signal‑side (`BaseSignal.is_tradable`); there is no engine rejection path
    and no action‑layer disposition taxonomy.
  - `Contract.trading_calendar_code` / `settlement_calendar_codes` remain,
    populated during `resolve_instrument` from the pricer‑constructor‑injected
    `ticker_to_calendar_code` mapping.
- **Dependencies:** Tasks 2, 3, 4
- **Remaining (future):** lot rounding; the synthesis plugins (roll/auto‑unwind/hedge/scaling) and the out‑of‑band netting module; **deferred `REPLACED` re‑add** — the replacement‑lineage field on `ActionGroup` and the log transition are registered against the **scaling rule**, which is their only consumer (scaling supersedes a signal's action with derived actions); portfolio‑layer checks (eligibility, risk/liquidity/margin, portfolio limits) belong to §10, not the strategy layer; `ROLL` execution.  Equity uses adjusted data and conversion carries fractional sizes unchanged (no rounding).

#### Consolidated gate registry

The single‑action‑subset task lands the schema/skeleton and **gates** every
shape outside its realized scope. Each gate is **fail‑loud** and **named**; the
schema accepts the shape and the pipeline or conversion rejects it. This is the
one registry; individual gates are not restated elsewhere.

| Gate | Kind | Placement | Behavior | Concrete trigger |
|---|---|---|---|---|
| **Multi-action ActionGroups** | pipeline | `OrderAssembly.build_order_groups`, **before** order conversion | reject groups with >1 Action until the engine program lands | `test_multi_action_group_is_rejected_before_conversion` |
| **Multi-leg modifications** | conversion | `order_assembly` gate, needs the book's legs | reject a partial add/unwind on a structure with >1 leg | `test_multi_leg_partial_add_is_rejected` |
| **Short-structure partial modifications** | conversion | `order_assembly` gate, needs signed anchor size | reject a partial add/unwind on a short structure | `test_short_structure_partial_add_is_rejected`, `…_unwind_is_rejected` |
| **Stamping intermediate stage** | engine-program | between synthesis rules and order conversion | rule-emitted groups are rejected until the stamping stage appends un‑stamped groups to the log; the pre‑stamp workaround is structurally forbidden | `test_a_rule_may_not_emit_a_group_never_appended` |
| **Order-id fan-out** | schema/pipeline | `ActionGroupRecord` (per-action `action_ids`, per-order `order_ids` / `order_outcomes`) ↔ `OrderGroup` (`order_group_id`, N `Order`s with their own ids) | Each action and each order has its own id; the record carries parallel facts written once by `finalize`. | — |
| **T-1 sizing** | landed | `DataView.reference_price` | T-1 reference price, fractional sizing; no look-ahead. | `test_returns_the_t_minus_1_close_when_t_is_present` |
| **Replacement lineage (`REPLACED` re‑add)** | engine-program | `ActionGroup` + `ActionGroupLog` | register with the **scaling rule**: scaling sets the predecessor pointer and the log performs the transition; no other consumer exists today. | — |
| **Netting module** | future slot | between order conversion and execution (order-in → order-out, documented only) | detect rolls *before* net; netting input = orders organized by originating group + lineage | — |
| **Underlying-identity field** | schema | `Contract.params` → resolved identity | move original-intent params off `Contract.params` so `Contract` is a pure hashable identity (Phase 4 risk aggregation / multi-leg netting prerequisite) | — |

#### Deferred registrations (from the strategy-layer `strategy_id` cleanup)

- [ ] **`strategy_id` at §10 ingestion.** Each saved `BacktestResult` came from one strategy; at load time, wrap with `StrategyRun(strategy_id, result)` and tag `Trade` / `ExecutionRecord` if flattened. `strategy_id` is not a strategy-layer field.
- [ ] **Split `OrderAssembly` when rules land.** Currently one class holding both the synthesis rule chain (empty) and order conversion. Split into `SynthesisChain` + `OrderConverter` when the first concrete rule (roll / auto-unwind / hedge / scaling) lands.

#### Explicit unwind-all form (future)

- [ ] **Explicit unwind‑all form** — give the unwind‑all fan‑out its own action/flag so a `structure_id=None` UNWIND cannot silently close the whole book.

#### Resolved — digest-method reconcile (R7)

The historical content‑digest literals (`e9a25c6d…` cost, `e2825941…` event) did
**not** reproduce under any serialization/normalization method tried, while the
stdout SHA did. **Closed by the single‑action‑subset task:** the stdout gate
adopts one **canonical, position‑independent, UUID‑substituted** method — each
dashed/hex UUID token is replaced with a sequential `UUID_0001…` in
first‑encounter order, then SHA‑256 — and was **re‑baselined once on the
pre‑change tree** (`cc6b08fbfa7466dca4f9084a37998775db9100b5af09a13409b1a2118ed62560`).
Content digests stay **session‑comparative** by scope choice (same harness, same
session), not because a reproducible literal is impossible.

---

## Phase 2B – Validation Pipeline

> **Note (annualization under union calendars):** the metrics `annualization` default of **252** assumes a single‑market trading year. The simulation calendar is now the *union* of the configured markets, which yields slightly **more** than 252 days per year (e.g. US + HK + DE), so annualised figures are marginally deflated relative to a true 252‑day year. Revisit whether `annualization` should stay 252, become a per‑run computed value, or be exposed explicitly in `SummarySpec` when the validation pipeline lands.

### Testing & hardening
- [ ] Add invariant/property tests for P&L conservation, time‑series length alignment, and missing‑data deferral (finding 3.2).
- [ ] Fill coverage gaps for untested branches (e.g., `total_size == 0` fallback, `per_leg` missing‑data mode) (finding 3.4).
- [x] Revisit the local `tests/conftest.py` sandbox workaround and the `.gitignore` debris patterns once the DSH sandbox `tmp_path` bug is confirmed fixed upstream. **Done 2026-10-23:** the DeepSeek harness is no longer in use; `tests/conftest.py` and its `tests/.tmp/` scratch base were deleted, the matching `.gitignore` entries were dropped, and the suite runs green on pytest's built-in `tmp_path` (581 passed, 0 errors, no `WinError 5`).

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
- [x] ~~Replace `requires_portfolio_state` / `requires_trade_history` class attributes with constructor‑enforced declarations or properties (finding 2.3).~~ **Resolved in Task 5a**: both flags were removed; the loop always builds the T‑1 position book and trade history, and `BaseSignal` has no `strategy_id` (the one‑signal‑per‑run framework re‑adds it at §10 ingestion).
- [ ] Extract a `MissingDataAligner` class from `Summary` if the class grows beyond its current scope (finding 2.5).
- [ ] Migrate original trading intent (tenor, delta, etc.) from `Contract.params` to `LegState.original_intent` so that `Contract` becomes a pure, hashable instrument identity (prerequisite for Phase 4 risk aggregation and multi‑leg netting).