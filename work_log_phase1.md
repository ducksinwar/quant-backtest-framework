# Phase 1 Work Log

**Start:** 2026‑06‑14 &nbsp;|&nbsp; **End:** 2026‑06‑17 &nbsp;|&nbsp; **Final review:** PASS &nbsp;|&nbsp; **Tests:** 141/141

## Table of Contents

| Step | Date | Topic | Section |
|------|------|-------|---------|
| 1 | 06‑14 | Foundation: Instrument, DataFeed, CsvBackend, EquityPriceProvider | [§ Foundation](#2026-06-14--foundation-classes-instrument-datafeed-csvbackend-equitypriceprovider) |
| 2 | 06‑15 | Pricers: BasePricer + EquityPricer | [§ Pricers](#2026-06-15--pricers-basepricer--equitypricer) |
| 3 | 06‑15 | StrategyStructure + Trade | [§ Structures & Trades](#2026-06-15--strategystructure-and-trade) |
| 4 | 06‑15 | CostModel, BaseSignal, SMACrossoverSignal | [§ Costs & Signals](#2026-06-15--costmodel-basesignal-smacrossoversignal) |
| 5 | 06‑16 | Backtester, Snapshots, trading_days | [§ Backtester](#2026-06-16--backtester-snapshots-and-datafeedtrading_days) |
| 6 | 06‑16 | Fix look‑ahead bias, data check, loop reorder | [§ Loop fix](#2026-06-16--fix-look-ahead-bias-data-availability-check-and-loop-reorder) |
| 7 | 06‑16 | Fix `_compute_risk_for_date` valuation storage | [§ Risk fix](#2026-06-16--fix-_compute_risk_for_date-valuation-data-storage) |
| 8 | 06‑16 | Summary class (all standard reports) | [§ Summary](#2026-06-16--summary-class) |
| 9 | 06‑16 | End‑to‑end example script | [§ Example](#2026-06-16--end-to-end-example-script) |
| 10 | 06‑17 | Code review fixes: Instrument + DataFeed | [§ Review fixes](#2026-06-17--code-review-fixes-instrument-and-datafeed) |
| 11 | 06‑17 | Design notes refactored (cost‑exposure flow) | [§ Design refactor](#2026-06-17--design-notes-refactored-asset-agnostic-cost-exposure-flow) |
| 12 | 06‑17 | Cost‑exposure implementation (all modules) | [§ Cost impl](#2026-06-17--cost-exposure-refactoring-implementation) |
| 13 | 06‑17 | Fix Summary cost alignment | [§ Cost fix](#2026-06-17--fix-summary-cost-alignment-date-indexed-gross-pnl) |
| 14 | 06‑17 | **Final end‑to‑end code review** | [§ Final review](#2026-06-17--final-phase1-endtoend-code-review) |

---

## 2026-06-14 – Foundation classes (Instrument, DataFeed, CsvBackend, EquityPriceProvider)

### Prompt
Please read the file `design_notes.md` at the project root.  
We are implementing Phase 1 of the framework, starting with the foundation.

**Task: Build the Instrument dataclass, DataFeed, CsvBackend, and EquityPriceProvider.**  
Write unit tests for each. All code must follow the specifications in the design notes exactly.

Details:

1. **Instrument** (`backtester/instruments/instrument.py`)  
   - A dataclass. Fields: `ticker`, `asset_class`, `multiplier` (default 1.0), `currency` (default "USD"), `tags` (optional list[str]), `leg_id` (str), `params` (dict).  
   - Also add these list attributes, all initialized to empty lists: `daily_total_pnl`, `current_price` (float, 0.0), `current_size` (float, 0.0), `entry_price` (float, 0.0).  
   - Add empty lists for valuation data series, component PnL series, and an empty dict for `pricing_inputs`.  
   - No methods beyond `__init__`.

2. **CsvBackend** (`backtester/data/csv_backend.py`)  
   - Reads a CSV file with columns `date` and `close` (like `market_data/spy_eod.csv`).  
   - Provide `get_value(dataset: str, date: str, ticker: str = None) -> float | None`. For `dataset="eod_prices"`, return the close for that date. Return `None` if date not found.  
   - Provide `get_series(dataset, start, end, ticker=None) -> pd.Series` (optional, but stub it).  
   - Use pandas, index by date.

3. **DataFeed** (`backtester/data/data_feed.py`)  
   - A concrete class that takes a backend in the constructor.  
   - Implement `get_value` and `get_series` that delegate to the backend.

4. **EquityPriceProvider** (`backtester/data/typed_providers/equity_price_provider.py`)  
   - Wraps `DataFeed`. Exposes `get_price(ticker: str, date: str) -> float | None`.

Write pytest tests for each class in the `tests/` folder. Use the provided `spy_eod.csv` for testing.

After writing all files, run `pytest` from the project root and confirm everything passes. Only proceed once tests pass.

### Agent output summary
Source files:
- backtester/instruments/instrument.py — Instrument dataclass with all specified fields, P&L tracking, valuation/componenent series dicts, and pricing_inputs
- backtester/data/csv_backend.py — CsvBackend that reads CSV files with date/close columns, lazily caches them, returns None for missing dates/tickers
- backtester/data/data_feed.py — DataFeed that delegates get_value/get_series to the backend
- backtester/data/typed_providers/equity_price_provider.py — EquityPriceProvider wrapping the DataFeed with a get_price(ticker, date) method
- pyproject.toml — minimal build config so the package is importable
Tests (34 across 4 files):
- tests/test_instrument.py — 13 tests covering defaults, custom values, field mutations, dict/list isolation between instances
- tests/test_csv_backend.py — 10 tests for value/series retrieval, missing dates, missing tickers, unknown datasets, caching, known exact price
- tests/test_data_feed.py — 6 tests verifying delegation, None returns, empty series for unknown datasets
- tests/test_equity_price_provider.py — 5 tests for price retrieval, missing date/ticker, known value, HK ticker

### Manual changes
- None

### Key configuration fix
- Corrected `opencode.json` to use DeepSeek provider with proper model mapping (see `~/.config/opencode/opencode.json` for the working config)

### Commit
`git commit -m "Add Instrument, DataFeed, CsvBackend, EquityPriceProvider"`

## 2026-06-15 – Pricers (BasePricer + EquityPricer)

### Prompt
Please read the file `design_notes.md` again, focusing on Section 3.5 (Pricer).  
We are continuing Phase 1 of the framework. The previous session created Instrument, DataFeed, CsvBackend, and EquityPriceProvider.

**Task: Build the BasePricer abstract class and the EquityPricer concrete implementation.**  
Write unit tests for both. All code must follow the specifications in the design notes exactly.

Details:

1. **BasePricer** (`backtester/pricers/base_pricer.py`)  
   - An abstract class with four abstract methods:
     - `price(instrument, date: str) -> float | None`
     - `valuation_data(instrument, date: str, measures: list[str]) -> dict[str, float] | None`
     - `resolve_instrument(leg_dict: dict, date: str) -> dict | None`
     - `pricing_inputs(instrument, date: str) -> dict[str, float] | None`
   - Use Python's `abc` module (ABC, abstractmethod).

2. **EquityPricer** (`backtester/pricers/equity_pricer.py`)  
   - Inherits from `BasePricer`.
   - Constructor takes an `EquityPriceProvider` instance (already built in `backtester/data/typed_providers/equity_price_provider.py`).
   - Implements:
     - `price(instrument, date)` – calls `self.provider.get_price(instrument.ticker, date)` and returns the result.
     - `valuation_data(instrument, date, measures)` – returns an empty dict (equities have no decomposition).
     - `resolve_instrument(leg_dict, date)` – returns the leg dict unchanged (equities need no extra parameters).
     - `pricing_inputs(instrument, date)` – returns an empty dict.
   - The pricer does NOT need caching in Phase 1 (equity prices are simple lookups).

3. **Unit tests**  
   - Create `tests/test_pricers.py`.
   - Test `EquityPricer` with a mock `EquityPriceProvider`:
     - Verify `price()` returns the value from the provider.
     - Verify `valuation_data()` returns an empty dict.
     - Verify `resolve_instrument()` passes through the leg dict.
     - Verify `pricing_inputs()` returns an empty dict.
   - Test that `BasePricer` cannot be instantiated directly (abstract class).

Use the existing project structure. After writing all files, run `pytest` from the project root and confirm everything passes. Only proceed once tests pass.

### Agent output summary
Source files:
- backtester/pricers/base_pricer.py — BasePricer(ABC) with four @abstractmethods: price, valuation_data, resolve_instrument, pricing_inputs
- backtester/pricers/equity_pricer.py — EquityPricer(BasePricer) that takes an EquityPriceProvider, delegates price() to provider.get_price(), returns empty dicts for valuation_data/pricing_inputs, and passes through resolve_instrument unchanged
Tests (10 new in tests/test_pricers.py):
- TestBasePricer: verifies abstract class cannot be instantiated (2 tests)
- TestEquityPricer: verifies price delegation, None propagation, empty dict returns, leg dict pass-through, and isinstance check against BasePricer (8 tests)

### Manual changes
- None

### Commit
`git commit -m "Add BasePricer and EquityPricer"`

## 2026-06-15 – StrategyStructure and Trade

### Prompt
Please read `design_notes.md` again, focusing on Section 3.2 (StrategyStructure) and Section 3.3 (Trade).  
We are continuing Phase 1 of the framework. The existing codebase includes Instrument, DataFeed, CsvBackend, EquityPriceProvider, BasePricer, and EquityPricer.

**Task: Build the StrategyStructure and Trade classes.**  
Write unit tests for both. Follow the design notes exactly.

Details:

1. **StrategyStructure** (`backtester/structures/strategy_structure.py`)  
   - Holds a fixed list of `Instrument` legs (in Phase 1 always one leg).  
   - Has an event log (list of dicts) that records lifecycle events: `open`, `partial add`, `partial unwind`, `roll`, `full close`.  
   - Each event stores: `event_type`, `date`, `unit_size_change`, `cost_exposure`, `cost_leg_id`, `cost_free`.  
   - Lifecycle methods: `open(date)`, `add_size(date, amount)`, `unwind(date, fraction=1.0)`, `roll(new_structure, date)`.  
   - `get_cost_exposure()` returns the risk metric(s) for cost quoting.  
   - Include a `structure_id` field, `original_entry_date`, and optional `tags`.

2. **Trade** (`backtester/trades/trade.py`)  
   - Internal state: `trade_id`, `active_structures`, `structure_history`, `tags`, `entry_date`, `exit_date`.  
   - Lifecycle methods: `add_structure`, `add_to_structure`, `unwind_structure`, `roll_structure`.  
   - In Phase 1, every trade contains exactly one structure with one leg.

3. **Unit tests**  
   - Create `tests/test_strategy_structure.py` and `tests/test_trade.py`.  
   - Test event log population, full/partial unwind, entry/exit date tracking, size scaling, and weighted-average entry price updates.

### Agent output summary
Source files:
- backtester/structures/strategy_structure.py — StrategyStructure with event log, lifecycle methods (open, add_size, unwind, roll), get_cost_exposure, leg size scaling
- backtester/structures/__init__.py — package init
- backtester/trades/trade.py — Trade class with active_structures/structure_history two-list pattern, lifecycle methods, weighted-average entry price on add_to_structure

Tests (34 new across 2 files):
- tests/test_strategy_structure.py — 17 tests: open event, original_entry_date, add_size event and scaling, full/partial unwind events and size reduction, get_cost_exposure, roll NotImplementedError, tags, multi-event log sequence
- tests/test_trade.py — 17 tests: entry_date, active/history lists, open event delegation, exit_date on full unwind, partial unwind keeps active/doesn't set exit, multiple structures exit_date logic, add_to_structure size scaling and weighted entry price, roll delegation, tags, initial None state

### Manual changes
- None

### Commit
`git commit -m "Add StrategyStructure and Trade"`

## 2026-06-15 – CostModel, BaseSignal, SMACrossoverSignal

### Prompt
Please read `design_notes.md` again, focusing on Section 3.11 (Cost Model) and Section 3.6 (Signal).  
We are continuing Phase 1. The codebase already contains Instrument, DataFeed, CsvBackend, EquityPriceProvider, BasePricer, EquityPricer, StrategyStructure, and Trade.

**Task: Build the FixedCostModel, BaseSignal abstract class, and SMACrossoverSignal example signal.**  
Write unit tests for all three. Follow the design notes exactly.

Details:

1. **CostModel (abstract) and FixedCostModel** (`backtester/cost_model.py`)  
   - An abstract `CostModel` class with a method: `compute_costs(trades: list[Trade]) -> dict[str, pd.Series]`  
   - `FixedCostModel` inherits from `CostModel`. Constructor takes a dictionary of basis‑point fees per asset class (e.g., `{'equity': 2.0}`).  
   - Implementation: walk every trade, every structure, every event log entry. For each cost‑bearing event (not cost‑free), compute cost as `notional * bps / 10000`. Return a dictionary mapping `leg_id` → `pd.Series` of daily costs.

2. **BaseSignal** (`backtester/signals/base_signal.py`)  
   - An abstract class with class attributes `requires_portfolio_state: bool = False`, `requires_trade_history: bool = False`.  
   - Abstract method `generate_signals(current_date, portfolio_state=None, trade_history_snapshot=None) -> list[dict]`.

3. **SMACrossoverSignal** (`backtester/signals/sma_crossover.py`)  
   - Inherits from `BaseSignal`. Constructor takes `short_window`, `long_window`, `ticker`, `size`, and a `DataFeed`.  
   - `requires_portfolio_state = True`. Stateless: reads PortfolioState snapshot to check position, uses DataFeed for SMA computation.

4. **Unit tests**  
   - `tests/test_cost_model.py` and `tests/test_signal.py`.  
   - Test FixedCostModel with mock structures/events, verify per-leg Series output.  
   - Test SMACrossoverSignal with mocked DataFeed and mock PortfolioState snapshots.

### Agent output summary
Source files:
- backtester/cost_model.py — CostModel(ABC) with abstract compute_costs; FixedCostModel walks trade.structure_history, extracts cost_exposure/total_notional from event_log, applies bps/10000 per asset class, returns dict[leg_id -> pd.Series]
- backtester/signals/base_signal.py — BaseSignal(ABC) with class attributes requires_portfolio_state/requires_trade_history and abstract generate_signals method
- backtester/signals/sma_crossover.py — SMACrossoverSignal with DataFeed, SMA computation, portfolio state inspection via mock dataclass snapshot traversal

Tests (22 new across 2 files):
- tests/test_cost_model.py — 9 tests: abstract instantiation, single trade cost, multiple events, different asset classes, unknown asset class (zero bps), partial unwind, empty trades, missing/empty leg_id skip, same-day cost aggregation
- tests/test_signal.py — 13 tests: BaseSignal abstract/partial instantiation, default flags, flag override; SMACrossoverSignal NEW/UNWIND/empty orders, insufficient data, not enough points, different ticker in portfolio, requires_flags

Bug fixes during testing:
- FixedCostModel: changed `leg_id is None` check to `not leg_id` to also skip empty string leg_ids
- SMACrossoverSignal tests: adjusted price series to properly produce short>long (rising) and short<long (falling) SMA relationships

### Manual changes
- None

### Commit
`git commit -m "Add CostModel, BaseSignal, and SMACrossoverSignal"`

## 2026-06-16 – Backtester, Snapshots, and DataFeed.trading_days

### Prompt
Please read `design_notes.md` again, focusing on Section 3.7 (Backtester) and the PortfolioState / TradeRecord descriptions in Section 3.6.  
We are continuing Phase 1. All other modules are built.

**Task: Build the Backtester and the snapshot dataclasses it needs.**  
Write unit tests. Follow the design notes exactly.

Details:

1. **Snapshot dataclasses** (new file `backtester/snapshots.py`) — LegSnapshot, StructureSnapshot, TradeSnapshot, PortfolioState, TradeRecord (all frozen dataclasses).
2. **Backtester** (`backtester/backtest_engine.py`) — BacktestConfig + AssetClassConfig dataclasses, Backtester with daily loop: PnL computation, snapshot building, order execution (NEW, UNWIND; ROLL stubbed).
3. **Unit tests** — tests/test_backtester.py covering snapshots, open/close cycle, PnL accumulation, missing price NaN, portfolio state/trade history snapshot passing, unknown asset class error, ROLL NotImplementedError.

### Agent output summary
Source files:
- backtester/snapshots.py — 5 frozen dataclasses: LegSnapshot, StructureSnapshot, TradeSnapshot, PortfolioState, TradeRecord
- backtester/backtest_engine.py — BacktestConfig, AssetClassConfig, Backtester with full daily loop: compute PnL (with NaN on missing), build PortfolioState/TradeHistorySnapshot (conditional on signal flags), execute NEW (new trade + add-to-existing), UNWIND (full/partial), data availability check, instrument resolution and UUID leg_id assignment, ROLL (NotImplementedError)
- backtester/data/csv_backend.py — added trading_days(ticker, start, end) method
- backtester/data/data_feed.py — added trading_days(ticker, start, end) delegation method

Tests (15 new in tests/test_backtester.py):
- TestSnapshots (4): frozen immutability, PortfolioState construction, TradeRecord open/closed flags
- TestBacktesterBasic (3): open-and-close cycle, empty history, entry/exit_date verification
- TestBacktesterPnl (3): PnL accumulation, multiplier-aware PnL, NaN on missing price (current_price preserved)
- TestBacktesterPortfolioState (3): PortfolioState passed when flag True, TradeHistorySnapshot passed, None when flags False
- TestBacktesterUnknownAssetClass (1): raises ValueError
- TestBacktesterRoll (1): raises NotImplementedError

Bug fixes during testing:
- Added numpy import to test file for np.isnan usage
- Backtester._execute_unwind: added support for trade_id=None (closes all active trades, Phase 1 convenience)
- CsvBackend.trading_days: correctly filters by start/end and returns sorted list

### Manual changes
- None

## 2026-06-16 – Fix look-ahead bias, data availability check, and loop reorder

### Prompt
Please fix the daily loop in `backtester/backtest_engine.py` and the `trading_days` method in `backtester/data/csv_backend.py` to match `design_notes.md` §3.7 exactly.  
The current implementation has a look‑ahead bias, missing fields, and a date‑format mismatch.

### Agent output summary
Changes made:

1. **Reordered `run()` daily loop** (removed look-ahead bias):
   - Old: PnL for next_day computed after executing orders, snapshots built from already-advanced prices.
   - New: For each trading day T: (a) build snapshots from current T-1 state, (b) compute PnL for T (advances prices), (c) call signal with T-1 snapshots, (d) execute orders, (e) compute risk for T (post-trade).
   - Removed the early `_compute_pnl_for_date(first_date)` call before the loop.

2. **Explicit `entry_date`/`exit_date` setting** in `_execute_new_trade` and `_execute_unwind` — set `trade.entry_date = date` and `trade.exit_date = date` directly rather than relying solely on delegated methods.

3. **Added `_check_data_available(order, date)`** — for NEW orders, resolves each leg and checks `pricer.price()` is non‑None; for UNWIND, checks all instruments in affected trade. Raises `ValueError` for unknown asset classes (per spec). Orders that fail are rejected with a warning.

4. **Added `_compute_risk_for_date(T)` stub** — iterates active trades, calls `pricer.valuation_data()` when `risk_measures` is non‑empty, stores results on `Instrument.component_pnl_series`.

5. **Fixed `trading_days` in `csv_backend.py`** — added explicit `str(d)` conversion in return list to guarantee string dates.

6. **New tests** (4 added, 19 total in backtester suite):
   - `TestBacktesterDataAvailability`: NEW order rejected when price is None (warns), UNWIND proceeds when price available.
   - `TestBacktesterSnapshotSemantics`: verifies snapshots contain T-1 state (positions visible after open).
   - `TestTradingDaysStrings`: verifies trading_days returns `str` instances.

### Manual changes
- None
## 2026-06-16 – Fix _compute_risk_for_date valuation data storage

### Prompt
Fix the `_compute_risk_for_date` method in `backtester/backtest_engine.py`.  
It currently references a non‑existent `leg.component_pnl_series` dictionary, which will crash when risk measures are enabled.  
Replace with per‑measure list attributes on Instrument (e.g. `delta_ts`, `gamma_ts`) following design notes §3.1 and §3.7.

### Agent output summary
- `backtester/backtest_engine.py:112-120`: replaced `leg.component_pnl_series.setdefault(key, []).append(val)` with dynamic attribute creation pattern using `f"{key}_ts"` as attribute name, `getattr`/`setattr` for lazy initialization per §3.1 valuation data storage.

### Manual changes
- Update trade_days return format

### Commit
`git commit -m "Add Backtester, AssetClassConfig/BacktestConfig, snapshots, and daily loop"`

## 2026-06-16 – Summary class

### Prompt
Build the Summary class per design_notes.md §3.8. Constructor takes a spec dict with `reports`, `missing_data_mode`, and optional `output`. Primary method `generate(trade_history, cost_model, fx_rates=None)` extracts leg P&L, applies costs, handles missing data, and produces standard reports.

### Agent output summary
Source files:
- backtester/summary.py — Summary class with full report generation pipeline: leg data extraction with cost alignment, missing-data modes (any/all/per_leg), report tree traversal with nested groups and filter composition (AND of parent+root+group filters), standard report builders (equity_curve, trade_summary, metrics, hit_ratio, drawdown_table, by_underlying), and file output (excel/csv/parquet).

Reports implemented:
- equity_curve: daily portfolio-level cumulative gross/cost/net with include filtering
- trade_summary: per-trade rows with identifiers, tags, gross/cost/net/local PnL
- metrics: Sharpe, max drawdown, annualized return, Calmar, hit ratio (gross/net versions, include-filtered)
- hit_ratio: positive-day proportion grouped by year or month
- drawdown_table: top N underwater periods with dates, depth, underwater days
- by_underlying: per-ticker sub-reports (equity_curve, metrics, drawdown_table, hit_ratio)

Tests (15 new in tests/test_summary.py):
- TestSummaryEquityCurve (2): gross/cost/net columns, include subset filtering
- TestSummaryTradeSummary (2): basic identifiers + tags, PnL aggregation
- TestSummaryMissingDataModes (2): any treats NaN as zero, all produces NaN days
- TestSummaryFiltering (2): group filter lambda, root filter applies to all reports
- TestSummaryMetrics (2): all metrics generated, include subset
- TestSummaryHitRatio (1): yearly hit ratio
- TestSummaryDrawdownTable (1): top N drawdown periods
- TestSummaryByUnderlying (1): per-ticker equity curves
- TestSummaryEmpty (1): empty trade_history returns {}
- TestSummaryNoOutputReturnsDict (1): dict return when no output config

Bug fixes during testing:
- _compute_hit_ratio: fixed .str accessor crash with integer indices; uses pd.to_datetime conversion with fallback
- _build_by_underlying: fixed sub-report dispatch to use build_all flag when include is empty
- CsvBackend.trading_days: reverted strftime() call to str() since index is already string-typed

### Manual changes
- None

### Commit
`git commit -m "Add Summary class with standard reports and group filtering"`

## 2026-06-16 – End-to-end example script

### Prompt
Create `examples/sma_crossover_example.py` that wires together all Phase 1 modules: CsvBackend → DataFeed → EquityPriceProvider → EquityPricer → SMACrossoverSignal → Backtester → FixedCostModel → Summary. Runs SMA crossover (50/200) on SPY from 2020-01-01 to 2022-12-31, prints metrics/equity curve/trade summary, and writes CSV output.

### Agent output summary
- examples/sma_crossover_example.py — full Phase 1 integration: loads SPY_eod.csv, creates all components, runs backtest (2 trades generated), computes costs ($0.08 total across both trades), generates equity curve + metrics + trade summary reports, prints to console, and writes CSV files to results/ folder (fallback from Excel since openpyxl not installed).

Console output shows:
- 2 trades: first lost ~$7,062 (entered 2020-01-02, exited 2020-04-01), second gained ~$12,637 (entered 2020-07-07, exited 2022-03-17)
- Net gross profit: ~$5,575
- Equity curve has NaN tail due to missing data days after final signal execution
- Results written as CSV: equity_curve.csv, metrics.csv, trade_summary.csv

### Manual changes
- None

## 2026-06-17 – Code review fixes: Instrument and DataFeed

### Prompt
Act as a code reviewer. Read `design_notes.md` (§3.1, §3.4, §8.1) and review the backtester package. Fix confirmed issues in Instrument and DataFeed.

### Review findings
- **Instrument** (`instrument.py`): `valuation_data_series` and `component_pnl_series` dicts were dead fields — design notes specify per-measure list attributes (e.g. `delta_ts`) created dynamically by the backtester, not a catch-all dict. Removed both.
- **DataFeed** (`data_feed.py`): `get_value()` and `get_series()` lacked `**params` forwarding, contrary to §3.4/§8.1 spec showing `get_value(self, dataset, date, ticker=None, **params)`. Added `**params` to both methods.
- **CsvBackend** (`csv_backend.py`): Added `**params` to `get_value` and `get_series` for signature compatibility with DataFeed delegation.
- **Tests** (`test_instrument.py`): Removed two test methods referencing deleted fields, removed stale assertions from `test_default_values`.

### Other findings (not yet fixed)
- **CRITICAL**: `summary.py:43-49` — Cost alignment broken. Gross PnL Series uses integer RangeIndex while cost Series has date-string index, so `net == gross` in all reports.
- **MINOR**: `backtest_engine.py` — `record_pricing_inputs` flag never checked; temp-object hack in `_check_data_available`; `LegSnapshot` doesn't populate `component_pnls`/`risk_measures` from leg.

### Manual changes
- None

### Commit
`git commit -m "Fix Instrument dead fields and add **params forwarding to DataFeed/CsvBackend"`

## 2026-06-17 – Design notes refactored: asset-agnostic cost-exposure flow

### Prompt
Refactor the cost-exposure flow in `design_notes.md` so that the core framework (StrategyStructure, Trade, Backtester) is completely agnostic to any asset class. Adding a new instrument type should require only asset-specific classes (pricer, AssetPnlCalculator, cost calculator) with zero changes to the framework core.

### Changes applied to design_notes.md
**10-point update across §3.1, §3.2, §3.3, §3.5, §3.7, §3.11:**

1. **§3.1** — Added `"cost_leg"` to common/infrastructure keys that are never placed in `Instrument.params`.
2. **§3.2** — StrategyStructure becomes a **pure event recorder**. `get_cost_exposure()` removed. Lifecycle methods now accept `cost_exposures: dict[str, dict] | None = None`. Event log key becomes `"cost_exposures"` (nested, per leg) storing **per-unit** metrics. `cost_leg_ids` attribute added. Old `cost_leg_id` field retained for readability.
3. **§3.3** — Trade's `add_structure`, `add_to_structure`, `unwind_structure`, `roll_structure` all accept optional `cost_exposures` parameter and forward it to StrategyStructure. Documented that the backtester must compute exposure before calling `unwind_structure` (pre-unwind sizes needed).
4. **§3.5** — New abstract method `compute_cost_exposure(instrument, date) -> dict[str, float] | None` on `BasePricer`. Returns **per-unit** metrics (e.g. `notional_per_unit`, `vega_per_contract`). No default implementation. Called only at order-execution time. Pricer cache shared between this and `valuation_data`.
5. **§3.5** — `resolve_instrument` may add `"cost_leg": true` to each leg dict; backtester uses this for `cost_leg_ids`.
6. **§3.7** — Backtester's `_resolve_and_price_leg` now filters `"cost_leg"`, `"structure_id"`, `"leg_id"` from params.
7. **§3.7** — Instrument construction now includes `cost_leg_ids` population from resolved leg dicts.
8. **§3.7** — New subsection: Cost-exposure computation during order execution. Backtester calls `pricer.compute_cost_exposure` for each cost-bearing leg before size changes, collects into `{leg_id: per_unit_dict}`, passes through Trade to structure. If exposure returns `None`, leg treated as cost-free for that event with a warning.
9. **§3.11** — Complete rewrite. Introduces `BaseCostCalculator` abstract class with `compute_cost(leg_id, event, data_feed=None) -> float`. `CostModel` holds a registry `{asset_class: BaseCostCalculator}`. `EquityCostCalculator` replaces `FixedCostModel`. New asset classes add calculators with zero core changes.
10. **Partial events and multi-leg support** woven throughout — per-unit metrics × unit_size_change ensures correct partial-unwind charging; straddle entries contain two cost_exposures entries; swap far-leg-only uses single entry.

### Key design principles achieved
- **Zero core changes for new asset classes** — only pricer + cost calculator needed.
- **Correct partial unwinds** — per-unit metrics prevent overcharging.
- **Framework never interprets cost metrics** — purely moves data from pricer to event log to calculator.
- **Pricer cache sharing** — `compute_cost_exposure` reuses greeks from `valuation_data`, zero redundant computation.
- **Backward compatible** — `EquityCostCalculator` provides same fixed-bps behavior as old `FixedCostModel`.

### Manual changes
- None

### Commit
`docs: refactor cost-exposure flow to be fully asset-agnostic`

## 2026-06-17 – Cost-exposure refactoring implementation

### Prompt
Implement the full cost-exposure refactoring across the backtester package to match the updated `design_notes.md`. Keep `daily_total_pnl` as `list[float]` (rejected the `pd.Series` migration). Defer the Summary cost-alignment fix to next session.

### Changes applied

**Pricers:**
- `base_pricer.py` — Added abstract method `compute_cost_exposure(instrument, date) -> dict[str, float] | None` (5th abstract method).
- `equity_pricer.py` — Implemented `compute_cost_exposure` returning `{"notional_per_unit": instrument.current_price}`.

**StrategyStructure:**
- Removed `get_cost_exposure()` entirely.
- Added `cost_leg_ids` attribute (list of leg IDs) to `__init__`.
- `open()`, `add_size()`, `unwind()` now accept `cost_exposures: dict[str, dict] | None = None`.
- Event log key changed from `"cost_exposure"` (singular, flat) to `"cost_exposures"` (plural, nested by leg_id).
- `cost_leg_id` derived from `cost_exposures` key set rather than hard-coded `legs[0]`.

**Trade:**
- `add_structure()`, `add_to_structure()`, `unwind_structure()`, `roll_structure()` all accept optional `cost_exposures` parameter and forward to StrategyStructure lifecycle methods.

**CostModel:**
- New `BaseCostCalculator(ABC)` with `compute_cost(leg_id, event, data_feed=None) -> float`.
- `CostModel` is now a concrete class with `__init__(self, calculators, data_feed=None)`.
- `compute_costs` iterates `event["cost_exposures"]` keys, dispatches to per-asset-class calculator.
- New `EquityCostCalculator(BaseCostCalculator)` — reads `event["cost_exposures"][leg_id]["notional_per_unit"] * event["unit_size_change"] * bps / 10000`.
- Removed `FixedCostModel`.
- Leg lookup by `leg_id` for multi-leg structures.

**Backtester:**
- Module-level `_INFRA_KEYS` constant: `{"ticker", "size", "multiplier", "currency", "asset_class", "tags", "structure_id", "leg_id", "cost_leg"}`.
- `_resolve_and_price_leg` now returns `tuple[Instrument | None, dict | None]` (instrument + resolved dict for cost_leg inspection).
- `_build_structure_from_info` now calls `_collect_cost_leg_ids()` to populate `structure.cost_leg_ids`.
- `_collect_cost_leg_ids` — if `"cost_leg": true` in any resolved dict, collects those leg_ids; single-leg default if none marked.
- New `_compute_cost_exposures(structure, date) -> dict[str, dict]` — iterates `structure.cost_leg_ids`, calls `pricer.compute_cost_exposure(leg, date)`. Warns on `None` return, skips leg.
- `_execute_new_trade` — computes `cost_exposures` for each structure, passes to `trade.add_structure()`.
- `_execute_add_to_existing` — both new-structure and partial-add paths compute `cost_exposures` before calling Trade.
- `_execute_unwind` — all three paths (full-all, full-specific, partial) compute `cost_exposures` BEFORE size reduction.
- `_compute_pnl_for_date` — added `record_pricing_inputs` block calling `pricer.pricing_inputs()` and appending to leg's dict time series. NaN appended on missing-price days.
- `_check_data_available` — replaced `type("_Temp")` hack with proper `Instrument()` using `_INFRA_KEYS` filtering.

**Example:**
- `sma_crossover_example.py` — replaced `FixedCostModel(fees={...})` with `CostModel(calculators={"equity": EquityCostCalculator(bps=2.0)})`.

**Tests:**
- `test_pricers.py` — added `test_compute_cost_exposure_returns_notional_per_unit`.
- `test_strategy_structure.py` — full rewrite for new signatures and `cost_exposures` keys; removed `test_get_cost_exposure_returns_notional`; added `test_cost_leg_ids` tests.
- `test_cost_model.py` — full rewrite: `TestBaseCostCalculator`, `TestEquityCostCalculator`, `TestCostModel` (8 tests).
- `test_summary.py` — updated imports and `_make_trade` to use new CostModel API and `cost_leg_ids`.
- `test_backtester.py` — added `TestBacktesterCostExposure` (3 tests: NEW, cost_leg_ids, UNWIND) and `TestBacktesterRecordPricingInputs` (2 tests); fixed `GappyPricer` mock.
- `test_trade.py` — unchanged (existing tests pass with default `cost_exposures=None`).
- `test_instrument.py` — unchanged.

All 140 tests pass.

### Deferred
- Summary cost alignment (`summary.py:43-49` — index mismatch). Fix in next session.
- `valuation_data` fetch during PnL step (Phase 1 never enables decomposition).

### Manual changes
- None

### Commit
`feat: implement asset-agnostic cost-exposure flow across all core modules`

## 2026-06-17 – Fix Summary cost alignment (date-indexed gross PnL)

### Prompt
The Summary had a critical bug where `_extract_leg_data` built gross PnL as `pd.Series(leg.daily_total_pnl)` with an integer RangeIndex, while the CostModel returns date-string-indexed cost Series. The alignment check `date_str in RangeIndex` never matched, so costs were silently dropped and `net == gross` in all reports.

### Changes applied

**Backtester:**
- `backtest_engine.py` — `trading_days` is now stored as `self.trading_days: list[str] = []` (initialized in `__init__`, assigned at start of `run()`). This exposes the full trading calendar for downstream consumers.

**Summary:**
- `summary.py` — `generate()` now accepts optional `trading_days: list[str] | None = None`.
- `_extract_leg_data` — when `trading_days` is provided, constructs `pd.Series(pnl_list, index=trading_days[:len(pnl_list)], dtype=float)`, giving the gross PnL a date-string index.
- Cost alignment simplified: `cost_series.reindex(gross.index, fill_value=0.0)` replaces the old broken loop (`for i, (idx, c) in enumerate(cost_series.items()): if idx in gross.index: ...`).
- When `trading_days` is `None` (backward-compatible), falls back to integer-indexed Series as before.

**Example:**
- `sma_crossover_example.py` — passes `trading_days=bt.trading_days` to `summary.generate()`.

**Tests:**
- `test_summary.py` — added `test_cost_subtracted_from_net`: verifies that when `cost_exposures` are present in event log, the cost column is non-zero and `net = gross - cost`. Confirms the alignment fix works end-to-end.
- Updated existing equity-curve test to pass `trading_days` and assert date index.

All 141 tests pass.

### Manual changes
- None

### Commit
`fix: align Summary gross PnL with cost series via date-indexed trading_days`

## 2026-06-17 – Final Phase 1 End‑to‑End Code Review

### Prompt
Act as a senior quant developer performing a final, end‑to‑end code review of Phase 1. Review **every module** against the current `design_notes.md` and check 12 specific items: Instrument fields, DataFeed/CsvBackend params, Pricers abstract methods, StrategyStructure cost_exposures, Trade cost forwarding, CostModel registry, Backtester daily loop order/_INFRA_KEYS/cost_leg_ids/cost exposure timing/record_pricing_inputs/entry_exit_dates, Summary cost alignment, Snapshots frozen, Signals unchanged, Example script correctness, and Tests.

### Review findings (all PASS)

| # | Check | Module(s) | Result |
|---|-------|-----------|--------|
| 1 | All fields present, dead `valuation_data_series`/`component_pnl_series` removed, `pricing_inputs` correctly init'd, `daily_total_pnl` is `list[float]` | Instrument | PASS |
| 2 | `**params` pass through in `get_value`/`get_series`; `trading_days` returns date strings | DataFeed, CsvBackend | PASS |
| 3 | `BasePricer` has 5 abstract methods (`price`, `valuation_data`, `resolve_instrument`, `pricing_inputs`, `compute_cost_exposure`); `EquityPricer.compute_cost_exposure` returns `{"notional_per_unit": instrument.current_price}` | BasePricer, EquityPricer | PASS |
| 4 | `get_cost_exposure()` removed; `cost_leg_ids` present; lifecycle methods accept/store `cost_exposures`; event log key is `"cost_exposures"` (plural) | StrategyStructure | PASS |
| 5 | All lifecycle methods (`add_structure`, `add_to_structure`, `unwind_structure`, `roll_structure`) accept and forward `cost_exposures` | Trade | PASS |
| 6 | `FixedCostModel` fully removed; `BaseCostCalculator` (abstract), `EquityCostCalculator`, `CostModel` with registry pattern; `compute_costs` produces date-indexed per-leg Series correctly | CostModel | PASS |
| 7a | Daily loop order: snapshot(T-1) → PnL(T-1→T) → orders → risk(T) correct | Backtester | PASS |
| 7b | `_INFRA_KEYS` includes `"cost_leg"`, `"structure_id"`, `"leg_id"`; used to filter params in `_resolve_and_price_leg` and `_check_data_available` | Backtester | PASS |
| 7c | `cost_leg_ids` populated via `_collect_cost_leg_ids` in `_build_structure_from_info` | Backtester | PASS |
| 7d | `_compute_cost_exposures` called before every Trade lifecycle call (NEW, partial-add, unwind all variants) | Backtester | PASS |
| 7e | For unwind, cost exposure computed **before** `structure.unwind()` reduces sizes | Backtester | PASS |
| 7f | `record_pricing_inputs` checked correctly; pricing inputs stored on valid days, NaN padded on missing | Backtester | PASS |
| 7g | `entry_date` set on `_execute_new_trade`/`Trade.add_structure`; `exit_date` set on all unwind paths when last structure closes | Backtester | PASS |
| 8 | Cost alignment: `cost_series.reindex(gross.index, fill_value=0.0)` fixes index mismatch; `net = gross - cost_aligned`; all standard reports reflect net P&L | Summary | PASS |
| 9 | All 5 snapshot classes frozen (`@dataclass(frozen=True)`); no live references; immutability tested | Snapshots | PASS |
| 10 | `BaseSignal` interface unchanged; `SMACrossoverSignal` passes all 9 tests | Signals | PASS |
| 11 | Uses `EquityCostCalculator` + `CostModel(calculators={...})`; passes `trading_days=bt.trading_days`; runs without errors | Example | PASS |
| 12 | 141 tests pass (0 failures, 1 expected warning); cost-exposure flow tested at unit and integration level | Tests | PASS |

### Minor gaps (non-blocking)
- No test for the warning path when `compute_cost_exposure()` returns `None` (`backtest_engine.py:290-293`).
- No explicit integration test verifying cost exposure computed before sizes change in partial unwind (unit tests cover mechanics independently).
- `design_notes.md:1263` and `README.md:105` still mention old `FixedCostModel` name (historical references only).

### Verdict
**No deviations, regressions, or blocking issues found.** The codebase matches `design_notes.md` on all 12 review points. Phase 1 is complete and production-ready.

### Manual changes
- None

## 2026-06-19 – Design note clarifications, add_to_structure fix, and additional test coverage

### Prompt
Read design_notes.md and codebase. Three-part task:
1. Clarify multi-leg cost exposure in design notes and fix bug in Trade.add_to_structure.
2. Review test coverage and add unit tests for untested Phase 1 behaviors.
3. Update work log.

### Changes applied

**Design notes (design_notes.md):**
- §3.2: Added paragraph after cost_exposures description explaining that for multi-leg structures, the transacted size of each leg is derived from total `unit_size_change` and the leg's fixed proportion.
- §3.2 Lifecycle methods: Updated `add_size` description to include entry-price weighted-average update.
- §3.3 Lifecycle methods: Updated `add_to_structure` description to reflect thin-passthrough role.

**Bug fix – `add_to_structure` sizing ownership (strategy_structure.py + trade.py):**
- **Problem:** `Trade.add_to_structure` computed leg size updates and entry prices but failed to assign `leg.current_size = new_total`. Entry price used old size in both numerator and denominator, yielding correct entry price by coincidence, but `leg.current_size` was never updated.
- **Fix:** Moved all leg‑size scaling and entry‑price weighted‑average computation into `StrategyStructure.add_size`. `Trade.add_to_structure` reduced to a thin passthrough: `structure.add_size(date, additional_size, cost_exposures)`. The structure now owns its legs' mutations end-to-end.
- `add_size` uses `old_size` in the entry‑price weighted‑average formula to preserve correctness before size is updated.

**Test updates:**
- `test_add_size_scales_legs` — enhanced to set `entry_price`/`current_price` on the leg before calling `add_size`, then asserts `entry_price == 443.33…` (verifying weighted‑average formula moved into `add_size` correctly).

**New tests (4 added):**
1. `test_original_entry_date_unchanged_by_add_unwind` (test_strategy_structure.py) — verifies `original_entry_date` is preserved after `add_size` and `unwind`.
2. `test_order_rejection_emits_warning` (test_backtester.py) — mock pricer returns `None`; asserts `pytest.warns(UserWarning)` with matching message.
3. `test_trade_history_snapshot_reflects_open_and_closed` (test_backtester.py) — runs backtest with open-then-close; verifies `TradeRecord` with `is_open=False` and `exit_date` set appears after close.
4. Enhanced `test_snapshot_contains_t_minus_1_prices` — added assertion that snapshot `current_price` equals T‑1 close price (100.0), confirming snapshot is built before PnL update.

### Test results
144/144 passed (0 failures, 1 expected warning).

### Suggested commit message
```
fix: move sizing/entry-price logic into StrategyStructure.add_size; clarify design notes; add 4 tests
```

## 2026-06-20 – Fix Summary PnL/cost date alignment

### Problem
`_extract_leg_data` aligned leg PnL using `trading_days[:len(pnl_list)]`, assigning PnL values to the first N simulation days regardless of when the trade was actually alive. This caused costs to appear on wrong dates for trades that opened or closed mid-simulation.

### Root cause
The backtester records PnL as follows: on the entry day, the trade is created after PnL computation (no PnL entry appended). The first PnL entry corresponds to the trading day immediately after `entry_date`. The last PnL entry corresponds to `exit_date` itself (the leg is still in `active_trades` when `_compute_pnl_for_date` runs on exit day). Therefore the correct date slice is `trading_days[entry_idx+1 : exit_idx+1]`.

### Changes applied

**`backtester/summary.py` — `_extract_leg_data`:**
- Replaced `trading_days[:len(pnl_list)]` alignment with proper entry/exit date logic:
  - `entry_idx = trading_days.index(trade.entry_date or "")`
  - `pnl_start = entry_idx + 1`
  - `pnl_end = trading_days.index(trade.exit_date)` (inclusive) or `len(trading_days) - 1`
  - PnL dates = `trading_days[pnl_start:pnl_end + 1]`
- Prepend `entry_date` with PnL=0 so that entry-day costs align (costs happen at entry, not at first PnL date).
- Fallback to old behavior when PnL length doesn't match the computed date range (legacy test data).

**`tests/test_summary.py`:**
- `test_equity_curve_gross_cost_net`: PnL reduced from 4 → 3 entries (matching actual backtester output), updated expected dates.
- `test_cost_subtracted_from_net`: PnL reduced from 3 → 2 entries, updated assertions for entry-date prepended zero with cost subtraction.

### Test results
144/144 passed (0 failures, 1 expected warning).

### Manual changes
- None

### Suggested commit message
```
fix: align Summary PnL dates with actual trade entry/exit dates
```

## 2026-06-26 – BacktestResult, aggregation fix, design note updates

### Prompt
1. Create a `BacktestResult` frozen dataclass packaging trade_history, trading_days, active_trades, and last_processed_date.
2. Modify `Backtester.run()` to return `BacktestResult` instead of a plain list.
3. Update the example script and all tests to unpack `BacktestResult`.
4. Fix `_aggregate_series` to correctly handle non‑overlapping trade lifetimes by reindexing each leg's series to the full `trading_days` index before aggregation.
5. Update design notes for BacktestResult, continuation runs, immutability, and FX deferral.

### Changes applied

**`backtester/backtest_engine.py`:**
- Added `BacktestResult` frozen dataclass with fields: `trade_history: Tuple[Trade, ...]`, `trading_days: Tuple[str, ...]`, `active_trades: Tuple[Trade, ...]`, `last_processed_date: str`.
- `Backtester.run()` now returns `BacktestResult`. Early return when no trading days returns empty tuples.

**`examples/sma_crossover_example.py`:**
- Updated to unpack `result = bt.run()`, then `result.trade_history` and `result.trading_days`.

**`tests/test_backtester.py`:**
- Added `BacktestResult` import.
- All 13 occurrences of `history = bt.run()` replaced with `result = bt.run()` + `history = list(result.trade_history)` — preserving existing assertions on the list form.

**`backtester/summary.py` — `_aggregate_series`:**
- Now stores `trading_days` in `self._trading_days` from `generate()`.
- For `'any'` and `'all'` modes: reindexes each leg's series to the full `trading_days` index with `fill_value=0.0`. This zero-fills dates where the leg was not alive (before entry / after exit), and converts genuine missing-data NaN to 0.0.
- For `'all'` mode: builds a per-leg NaN mask only on dates where the leg WAS alive AND had NaN. Reindexes the mask to `trading_days` with `fill_value=False`, so non-alive dates are never masked. Combines masks via logical OR and applies to the aggregate.
- `'per_leg'` mode unchanged.
- `fx_rates` parameter retained in signature for future use.

**`design_notes.md`:**
- §3.7: Described `BacktestResult` as the formal return type, listing all four fields.
- §3.7 "Future extension – incremental backtesting": Updated to reference `BacktestResult` for continuation runs; noted that `Summary` consumes `BacktestResult` unchanged.
- §3.7: Added immutability paragraph — `BacktestResult` uses tuples now; Phase 2 will add recursive freeze.
- §3.10 step 4: Added note that FX conversion is deferred to Phase 2; all Phase 1 legs are USD.

### Test results
144/144 passed (0 failures, 1 expected warning).

### Manual changes
- vectorized a nan_mask computation for self._missing_mode == "all"

### End‑to‑end verification
Example runs correctly — equity curve shows proper date-indexed data, costs appear on correct dates, Sharpe ratio and max drawdown computed correctly.

### Suggested commit message
```
feat: add BacktestResult dataclass, fix aggregation for non-overlapping trades
```

## 2026-06-26 – Manual fixes for summary

### Manual changes
- rewrite _build_equity_curve in a cleaner way
- removing missing_mode dependency for _build_trade_summary

## 2026-06-26 – trade_summary enhancements and design‑note updates

### Prompt
1. Add `underlying` and `holding_days` columns to the `trade_summary` report.
2. Update design notes: resolution preservation rule, `trade_breakdown` spec, OMS integration paragraph, and `trade_summary` table row.

### Changes applied

**`backtester/summary.py` — `_build_trade_summary`:**
- Added `underlying` column: comma‑separated sorted unique tickers across all legs of the trade.
- Added `holding_days` column: trading days from `entry_date` to `exit_date` inclusive (or last trading day if trade still open), using `self._trading_days`. Falls back to 0 when `trading_days` is not available.
- Both columns controlled by the existing `include` mechanism (None = show all).

**`design_notes.md`:**
- §3.8 trade_summary table row: replaced `'local_pnl'`/`'usd_pnl'` with `'underlying'` and `'holding_days'`.
- §3.5 `resolve_instrument`: added "Preserving the original trading intent" paragraph requiring pricers to keep original key‑value pairs alongside resolved ones.
- §3.8: added full `trade_breakdown` (Phase 2+) subsection specifying the five level hierarchy (leg → structure → lot → underlying → trade), currency handling, and display options.
- §9: added OMS and trade lifecycle integration paragraph describing continuity from backtest to production.

### Test results
144/144 passed (0 failures, 1 expected warning).

### Suggested commit message
```
feat: add underlying/holding_days to trade_summary; update design notes for Phase 2+
```

## 2026-06-26 – trade_summary: mandatory identifiers, column ordering

### Changes applied

**`backtester/summary.py` — `_build_trade_summary`:**
- Made `trade_id`, `entry_date`, `exit_date` mandatory — always present regardless of `include`.
- Reordered output columns to: trade_id, entry_date, exit_date, holding_days, tags, underlying, gross_pnl, cost, net_pnl.
- Removed the `local_pnl` block entirely.
- `holding_days`, `tags`, `underlying`, `gross_pnl`, `cost`, `net_pnl` remain controlled by the `include` setting.

### Test results
144/144 passed (0 failures, 1 expected warning).

### Suggested commit message
```
refactor: make trade_id/entry/exit mandatory in trade_summary; reorder columns
```

## 2026-06-27 – Design note corrections: component P&L and equity‑curve risk

### Changes applied

**`design_notes.md`:**
- §3.8 `trade_breakdown` Trade bullet: clarified that component P&L is always net (no gross component P&L), and both risk measures and component P&L are gated by `include`.
- §3.8 equity‑curve table: added new paragraph describing portfolio‑level risk and component P&L in Phase 2, including the correct underlying‑level netting method for gross measures. Corrected "net and gross component P&L" to "net component P&L".

### Suggested commit message
```
docs: clarify component P&L is net-only; add portfolio-level risk note to equity_curve
```