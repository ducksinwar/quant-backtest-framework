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