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
- [List any fixes you made, e.g., "Fixed type hint in Instrument.currency" or "None"]

### Key configuration fix
- Corrected `opencode.json` to use DeepSeek provider with proper model mapping (see `~/.config/opencode/opencode.json` for the working config)

### Commit
`git commit -m "Add Instrument, DataFeed, CsvBackend, EquityPriceProvider"`