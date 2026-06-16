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
