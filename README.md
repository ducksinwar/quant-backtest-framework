# Quant Backtest Framework

A rigorous, production‑grade backtesting and validation engine for systematic trading strategies.

![Python](https://img.shields.io/badge/python-3.12-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Phase](https://img.shields.io/badge/phase-2A%20%2B%20Task%205-blue)

## Motivation

I built this framework because I believe systematic trading deserves honest research.  
With five years as a head of quant at a hedge fund, I know what separates a backtest that looks good on paper from one that survives live trading. This project is built to that production‑grade standard: every strategy must survive **purged walk‑forward cross‑validation** and a **deflated Sharpe ratio reality check** before it ever touches live capital.

## Key Features

- **Event‑driven daily loop** with one‑day‑lagged signal execution – no look‑ahead bias.  
- **Stateless signals** – signals derive positional awareness from immutable portfolio snapshots, making them fully reproducible and trivially extendable.  
- **Swappable data backends** – a `DataFeed` fronts a pluggable backend (CSV today); adding SQL or multi‑source data later requires no strategy‑code changes.  
- **Abstract pricer layer** – equities today, with clean interfaces ready for options / futures / FX.  
- **Transaction cost separation** – costs are computed post‑simulation from a structure‑level event log; change cost assumptions without re‑running the backtest.  
- **Standard performance reports** – equity curve, trade summary, scalar metrics, periodic metrics, hit ratio, drawdown table, and per‑underlying breakdowns, with optional capital‑based percentage figures.  
- **Modular, well‑documented code** with 573 unit tests – easy to extend with new instruments or signals.

## Architecture

The framework is built around a daily event loop:

**Data → Pricer → Signal → ActionGroup → (synthesis chain) → OrderGroup → Execution seam → Backtester/Book → Summary & Cost Model**

- **DataFeed** abstracts all data access (CSV today, SQL tomorrow).  
- **Pricers** value instruments via an immutable `Contract` and supply greeks for P&L decomposition.  
- **Signals** are stateless, emit `ActionGroup` objects (not orders), read market data only through a T-1-clamped `DataView`, and suppress emission on a closed market (`is_tradable`); the loop then runs the synthesis chain and the execution seam.  
- **Backtester** computes daily P&L, executes orders, and records all lifecycle events.  
- **CostModel** turns those events into a per‑leg cost series; the **Summary** is a thin data coordinator that dispatches report generation through a pluggable `BaseReport` registry, with individual metrics computed by reusable `BaseMetricCalculator` classes.  
- **FX conversion** – a post‑processing step inside `Summary` (`FxRateProvider` wraps the `DataFeed`), consolidating multi‑currency legs into a configurable base currency via cumulative‑spot conversion; portfolio reports, equity‑curve `fx_<pair>` columns, and per‑underlying local/base/dual output are all supported.  

Everything is fully decoupled – you can swap a pricer, change the cost model, or add a new report without touching the backtester loop.

A complete class‑level specification is maintained in [design_notes.md](design_notes.md).

## Project Structure
```markdown
backtester/
    data/
        data_feed.py            # DataFeed with swappable backends
        csv_backend.py          # CSV backend implementation
        typed_providers/        # Equity price + FX rate providers (Vol/rate/forward curve: future)
    instruments.py              # Contract and LegState
    strategy_structure.py       # Atomic leg grouping with event log
    pricers/
        base_pricer.py          # Abstract BasePricer
        equity_pricer.py        # EquityPricer (Phase 1)
    signals/
        base_signal.py          # BaseSignal abstract class
        sma_crossover.py        # SMA crossover example
    trade.py                    # Trade class
    snapshots.py                # Frozen snapshot dataclasses
    actions.py                  # Action schema (LegSpec/StructureSpec/TradeSpec/Action/ActionGroup)
    orders.py                   # Order schema (Order/OrderLeg/OrderSide/OrderGroup/OrderOutcome)
    action_group_log.py         # Append‑only action-group log
    data_view.py                # T‑1‑clamped market‑data view handed to signals
    position_books.py           # Read‑only T‑1 position book
    order_synthesis.py          # ActionGroup → order synthesis chain
    execution.py                # Execution seam (ExecutionBackend / SimulatedExecution)
    execution_log.py            # Write‑once execution log
    backtest_engine.py          # Daily loop orchestrator
    calendar_provider.py        # Trading‑day calendars (union simulation calendar)
    summary.py                  # Thin data coordinator
    cost_model.py               # Transaction cost computation
    metrics_registry.py         # Pluggable BaseMetricCalculator registry
    reports/
        __init__.py             # REPORTS dict + re‑exports
        _base.py                # BaseReport ABC
        equity_curve.py         # EquityCurveReport
        trade_summary.py        # TradeSummaryReport
        metrics.py              # MetricsReport
        periodic_metrics.py     # PeriodicMetricsReport
        hit_ratio.py            # HitRatioReport
        drawdown_table.py       # DrawdownTableReport
        by_underlying.py        # ByUnderlyingReport
examples/
    sma_crossover_example.py    # End‑to‑end example
market_data/
    <TICKER>_eod.csv            # Daily adjusted closes (date, close)
    holidays/<CODE>.csv         # Holiday calendars (header `date`, YYYY-MM-DD rows)
tests/
    test_calendar_provider.py   # CalendarProvider unit tests
    test_data/holidays/         # Committed holiday fixtures
design_notes.md                 # Full architectural specification
```
## Installation

1. Clone the repository:
```bash
git clone git@github.com:ducksinwar/quant-backtest-framework.git
cd quant-backtest-framework
```
2. Create and activate the conda environment:
```bash
conda create -n backtest python=3.12 pandas numpy matplotlib pyyaml pytest -y
conda activate backtest
```
3. Run the tests to verify everything works:
```bash
pytest
```
## Quick Start
```bash
conda activate backtest
python examples/sma_crossover_example.py
```
The script backtests a 20/50‑day SMA crossover on four tickers across three markets – SPY and QQQ (US), 2800.HK (Hong Kong) and SXRT.DE (Germany) – each notional‑sized and FX‑converted to USD, and prints the equity curve, metrics, and trade summary.  
The simulation calendar is the **union** of the US, HK and DE calendars (holiday calendars are served through the `DataFeed`'s `CsvBackend`, which reads `market_data/holidays/{CODE}.csv`; the `CalendarProvider` computes the union), so a day that is a holiday in only one market is still simulated. The signal gates emission per instrument with `BaseSignal.is_tradable`, so nothing is emitted for a ticker whose market is closed that day (no reject record, no warning); a held leg simply carries no price that day, so its P&L is `NaN` while `current_price` is held at the last valid mark.  
*Replace or add CSVs in `market_data/` (named `<TICKER>_eod.csv`, columns `date`, `close`) to test on different data.*

If you don’t have a `market_data/` folder yet, create one and place your CSV inside – the folder is gitignored so your data stays local.

## Usage

1. Place a CSV of daily adjusted prices (columns: `date`, `close`) in `market_data/`.  
2. Create a signal class that inherits from `BaseSignal` (pass a `strategy_id`) and implements `generate_action_groups()`.  
3. Instantiate the components:
   - `DataFeed` with a `CsvBackend`
   - `EquityPriceProvider` wrapping the feed
   - `EquityPricer` (pass the optional `ticker_to_calendar_code` mapping to enable calendar validation)
   - `CalendarProvider` (over the same feed)
   - Your `Signal` (with a `strategy_id`)
   - `Backtester` config with the signal, asset class config, calendar provider, and optional `ticker_to_calendar_code`; the order-pipeline seams are all optional and default sensibly — `data_feed` (the daily T-1 `DataView`'s source), `order_synthesis` (`None` → empty synthesis chain), and `execution_backend` (`None` → `SimulatedExecution`)
   - `CostModel(calculators={"equity": EquityCostCalculator(bps=2.0)})`
4. Run `backtester.run()` and pass the resulting `trade_history` to `Summary` for reports.

See `examples/sma_crossover_example.py` for a complete, working template.

## What Sets This Apart

- **Honest validation by design** – the architecture is built around out‑of‑sample testing; purged, embargoed walk‑forward folds and a deflated Sharpe ratio reality check are the next milestones (see Roadmap).  
- **Stateless, reviewable signals** – every signal call receives a frozen snapshot of the portfolio; no hidden state means you can resume a backtest at any point and always get the same result.  
- **Production‑ready separation** – costs and risk attribution are post‑processing steps, so you can change assumptions instantly without re‑running the backtester (FX conversion follows the same pattern in Phase 2).  
- **Data independence** – swapping CSV for a full SQL database with point‑in‑time data requires changing a single backend object; the rest of the code never knows the difference.

## Roadmap

| Phase | Description | Status |
|-------|-------------|--------|
| 1 | Core skeleton – daily loop, equities, SMA example, summary reports, cost model | ✅ Complete |
| 2 | Purged walk‑forward cross‑validation with nested parameter selection | 🟡 In progress – Phase 2A (Tasks 1–4) + Task 5 (order pipeline) implemented |
| 3 | Deflated Sharpe Ratio, Strategy Graveyard, multiple testing correction | ⬜ Planned |
| 4 | Multi‑leg trades, options, partial unwinds, advanced pricers | ⬜ Planned |

## Design Notes

The full design specification – every class, its methods, and the validation methodology – is in [design_notes.md](design_notes.md).  
If you’re evaluating this project as a hiring manager, that file will give you a detailed view of the system’s depth and my approach to rigorous quant research.

## Testing
```bash
pytest
```
573 unit tests cover `Contract`/`LegState`, `DataFeed`, `Pricers`, `Trade`, `StrategyStructure`, `CostModel`, `Backtester`, `CalendarProvider`, `Summary`, `Signals`, the action/synthesis pipeline, and the execution seam.

## Contributing

This is primarily a personal research tool, but pull requests are welcome. Please open an issue first to discuss what you’d like to change.

## License

MIT – see the `LICENSE` file for details.

## Author

Terry Chan – systematic quant, infrastructure builder.  
GitHub: [@ducksinwar](https://github.com/ducksinwar)