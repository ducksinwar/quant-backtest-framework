# Quantitative Backtest Framework – Design Notes

## 1. Overview
This project is a rigorous, production‑grade backtesting and validation framework for systematic trading strategies.  
It is designed to:
- Simulate multi‑asset, multi‑leg strategies with proper transaction cost accounting.
- Enforce out‑of‑sample testing through purged walk‑forward cross‑validation.
- Correct for multiple testing bias using Deflated Sharpe Ratio (DSR).
- Serve as both a personal trading research tool and a portfolio piece demonstrating industry best practices.

## 2. Project structure (planned)
backtester/
data/
market_data.py # MarketData class (CSV loader)
instruments/
instrument.py # Instrument dataclass (ticker, asset_class, multiplier)
pricers/
equity_pricer.py # EquityPricer (uses MarketData to price equities)
signals/
base_signal.py # BaseSignal abstract class
sma_crossover.py # Example signal: SMA crossover with lag
trades/
trade.py # Trade class (entry/exit, cost separation, P&L)
backtest_engine.py # Backtester daily loop
summary.py # Summary statistics (Sharpe, max drawdown, win rate)
examples/
sma_crossover_example.py # End‑to‑end example using SMA signal
tests/
test_trade.py # Unit tests
design_notes.md # This file


## 3. Core classes and their responsibilities

### 3.1 Instrument
- A dataclass with fields: `ticker` (str), `asset_class` (str), `multiplier` (float, default 1.0).
- For simple equities, multiplier = 1. For futures/options it can be used to scale P&L.

### 3.2 MarketData
- Loads a CSV of daily close prices (columns: date, close) from a file path.
- Provides a method `get_price(ticker, date)` that returns the close price.
- Uses pandas internally; index by date; raises KeyError for missing dates.

### 3.3 Pricer (base + EquityPricer)
- Each asset class will have its own pricer. The first concrete pricer is `EquityPricer`.
- `EquityPricer` is initialized with a `MarketData` instance.
- Method `price(instrument, date)` returns the instrument’s price on that date (instrument.ticker, market_data.get_price).
- For equities, price = close * multiplier.

### 3.4 Trade
Represents a single directional trade (long or short) with entry/exit information.
- Fields: instrument, entry_date, exit_date (optional, None while open), entry_price, exit_price (optional), size (number of contracts/shares, positive for long, negative for short), cost_bps (transaction cost in basis points, e.g., 1.0 = 1 bps).
- Methods:
  - `realized_pnl()`: if closed, (exit_price - entry_price) * size * multiplier – cost. Returns gross P&L before cost, and cost separately. So returns tuple (gross_pnl, cost).
  - `unrealized_pnl(current_price)`: (current_price - entry_price) * size * multiplier (no cost).
  - `close_trade(exit_date, exit_price)`: sets exit fields, calculates realized P&L.
- Cost is calculated as `abs(entry_price * size * multiplier) * cost_bps / 10000 + abs(exit_price * size * multiplier) * cost_bps / 10000` (applied at both entry and exit).
- P&L is always stored separately before cost and cost amount for later analysis.

### 3.5 Signal (abstract and example)
- **BaseSignal** is an abstract class with a method:
  `generate_signals(current_date, market_data) -> list[TargetTrade]`
- **TargetTrade** dataclass: instrument, action (BUY, SELL, CLOSE), size, trade_id_to_close (for CLOSE action).
- The signal is stateless; it only uses market data available *before* or at `current_date`. The signal output should be lagged by one day: for a strategy using today’s close to decide tomorrow’s trades, the signal called on day T returns orders that will be executed on day T+1 close.
- **SMACrossoverSignal** (example): parameters `short_window` (e.g., 50) and `long_window` (e.g., 200). On each call, it computes the SMA for both windows using data up to `current_date`, and if short SMA > long SMA (crossover up), generates a BUY order for 1 unit; if short SMA < long SMA (crossover down), generates a SELL order to close the existing position. It also tracks whether a position is open via a simple state (can be a boolean stored in the signal instance).

### 3.6 Backtester
- Orchestrates the daily loop.
- Initialized with MarketData, a list of instruments, a Signal, start_date, end_date, initial_cash (optional, not needed for trade list generation), and a Pricer map.
- Loop over each trading day (as determined by MarketData’s dates):
  1. **Mark‑to‑market**: for each open trade, compute unrealized P&L using current close price (for later analysis, though not strictly necessary for closed‑trade P&L).
  2. **Get signal**: `orders = signal.generate_signals(current_date, market_data)`. Note: signal generation uses data up to `current_date` but the execution price will be the *next* day’s close (to avoid look‑ahead). So we record the orders and execute on the next iteration. Implementation detail: the backtester can have a “pending orders” list. On day T, we execute orders generated on day T‑1 at the day T close.
  3. **Process pending orders**: For each pending order:
     - If BUY: create a new Trade with entry_price = today’s close, size from order, entry_date = today, cost_bps from config.
     - If SELL (without trade_id): treat as opening a short trade.
     - If CLOSE with trade_id: close the referenced trade at today’s close.
  4. **Generate new pending orders**: After processing pending, call signal for the *next* day’s orders, storing them as pending for tomorrow.
  5. **Move to next day**.
- Collect all closed trades in a list. At the end, return the list of closed Trade objects.

### 3.7 Summary
- Function `summary_statistics(trades: list[Trade], annualization=252) -> dict`:
  - Computes total gross P&L, total costs, net P&L.
  - Daily returns from net P&L (if multiple trades on a day, aggregate). If no cash, compute daily equity curve by accumulating net P&L.
  - Sharpe ratio: mean(daily_returns) / std(daily_returns) * sqrt(annualization).
  - Max drawdown, win rate (percentage of trades with positive net P&L).
  - Return a dictionary with these metrics.

## 4. Validation framework (to be built after core backtester)

### 4.1 Walk‑forward cross‑validation
- Split the full historical period into multiple folds, each with a training window and a subsequent validation window.
- Use a `FoldGenerator` that:
  - Takes start_date, end_date, train_length (e.g., 2 years), validation_length (e.g., 6 months), step_size (e.g., 6 months), purge_length (equal to the maximum lookback window used by the strategy, e.g., 50 days), embargo_length (1 day to simulate realistic execution delay).
  - Yields (train_start, train_end, val_start, val_end) for each fold.
- Purging: Ensure that no data from the validation period leaks into the training set via lookback. So train_end must be at least `purge_length` before val_start.
- Embargo: Add a gap of `embargo_length` after train_end before val_start to avoid trading on information that wasn’t available.

### 4.2 Nested parameter selection (within each training window)
- For a strategy with a parameter grid (e.g., short_window, long_window), we want to select the best parameters without overfitting the validation period.
- Inside each training window, we further split the training data into sub‑training (e.g., first 80% of train period) and sub‑validation (last 20%).
- For each parameter combination:
  - Run the backtester on sub‑training to warm up the signal and compute the state, then continue the backtest into the sub‑validation period.
  - Compute the Sharpe ratio on the sub‑validation trades only.
- Select the parameter set that gives the highest sub‑validation Sharpe.
- Then run that best parameter set on the *full validation period* for that fold, collecting out‑of‑sample trades.

### 4.3 Multiple testing correction across strategies
- Over time, we will test many distinct strategies (different asset classes, signal ideas).
- Each strategy will produce an aggregated out‑of‑sample Sharpe (from all its walk‑forward folds).
- To decide if the best‑performing strategy is genuine, we use the **Deflated Sharpe Ratio (DSR)**.
- Maintain a “Strategy Graveyard” log per independent trading universe (e.g., “US Equities”, “FX”). Each entry contains the aggregated OOS Sharpe and sample size.
- After adding a new strategy, compute the DSR for the current champion strategy, using the total number of strategies in that graveyard as the multiple testing count (N).
- DSR threshold: if DSR > 0.95, consider the strategy significant. If not, do not trade it.
- Reset the graveyard only when moving to a completely independent asset class with no overlap in return history.

### 4.4 Deployment
- Once a strategy passes DSR, we deploy it with parameters re‑estimated on all available data (the entire historical dataset, using the same nested selection procedure).
- This provides the best estimate of parameters for live trading.
- Live performance should be monitored, and periodic refitting (e.g., monthly) can follow the same walk‑forward logic.

## 5. Implementation plan (Phases)

### Phase 1: Core skeleton (minimal end‑to‑end)
Build the following in order, each tested before moving on:
1. MarketData, Instrument, EquityPricer.
2. Trade class with cost separation and P&L.
3. BaseSignal abstract class and SMACrossoverSignal (with lag, using simple boolean state).
4. Backtester with daily loop as described, including pending order queue.
5. Summary module.
6. Example script (`examples/sma_crossover_example.py`) that:
   - Loads a CSV of SPY daily data (date, close) from a local file.
   - Creates MarketData, Signal with short_window=50, long_window=200.
   - Runs Backtester from 2020-01-01 to 2022-12-31.
   - Prints summary statistics.
7. Unit tests for Trade and MarketData using pytest.

### Phase 2: Validation
1. Implement FoldGenerator with purge/embargo.
2. Implement nested parameter selection: walk‑forward loop that, per fold, does grid search using a sub‑training/sub‑validation split within the train window, then evaluates best params on validation.
3. Extend summary to aggregate out‑of‑sample trades across folds.

### Phase 3: Statistical rigor
1. Implement Deflated Sharpe Ratio calculation.
2. Build a simple Strategy Graveyard (JSON file).
3. Add a top‑level script that compares multiple strategies and reports DSR.

## 6. Technology stack
- Python 3.12
- pandas, numpy, matplotlib, pyyaml, pytest
- All code will be written in a modular, docstring‑documented style.

## 7. Important conventions
- Signal output is always lagged by one day.
- Transaction costs are separated from gross P&L in Trade.
- Backtester does not handle portfolio sizing; it simply executes one unit per signal (for now).
- All prices are assumed to be adjusted close prices (dividends and splits handled in the CSV).
- Use consistent date formats (YYYY-MM-DD).