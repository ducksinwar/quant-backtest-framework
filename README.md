# Quant Backtest Framework

A rigorous, production‑grade backtesting and validation engine for systematic trading strategies.

![Python](https://img.shields.io/badge/python-3.12-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Phase](https://img.shields.io/badge/phase-1%20complete-brightgreen)

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
- **Modular, well‑documented code** with 145 unit tests – easy to extend with new instruments or signals.

## Architecture

The framework is built around a daily event loop:

**Data → Pricer → Signal → Backtester → Summary & Cost Model**

- **DataFeed** abstracts all data access (CSV today, SQL tomorrow).  
- **Pricers** value instruments and supply greeks for P&L decomposition.  
- **Signals** are stateless, return target‑trade dictionaries, and only see information up to T‑1.  
- **Backtester** computes daily P&L, executes orders, and records all lifecycle events.  
- **CostModel** turns those events into a per‑leg cost series; the **Summary** is a thin data coordinator that dispatches report generation through a pluggable `BaseReport` registry, with individual metrics computed by reusable `BaseMetricCalculator` classes.  

Everything is fully decoupled – you can swap a pricer, change the cost model, or add a new report without touching the backtester loop.

A complete class‑level specification is maintained in [design_notes.md](design_notes.md).

## Project Structure
```markdown
backtester/
    data/
        data_feed.py            # DataFeed with swappable backends
        csv_backend.py          # CSV backend implementation
        typed_providers/        # (future) Vol, rate, forward curve providers
    instruments/
        instrument.py           # Instrument dataclass
    structures/
        strategy_structure.py   # Atomic leg grouping with event log
    pricers/
        base_pricer.py          # Abstract BasePricer
        equity_pricer.py        # EquityPricer (Phase 1)
    signals/
        base_signal.py          # BaseSignal abstract class
        sma_crossover.py        # SMA crossover example
    trades/
        trade.py                # Trade class
    snapshots.py                # Frozen snapshot dataclasses
    backtest_engine.py          # Daily loop orchestrator
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
tests/
    test_trade.py               # Unit tests
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
The script backtests a 20/50‑day SMA crossover on SPY and QQQ (notional‑sized) and prints the equity curve, metrics, and trade summary.  
*Replace or add CSVs in `market_data/` (named `<TICKER>_eod.csv`, columns `date`, `close`) to test on different data.*

If you don’t have a `market_data/` folder yet, create one and place your CSV inside – the folder is gitignored so your data stays local.

## Usage

1. Place a CSV of daily adjusted prices (columns: `date`, `close`) in `market_data/`.  
2. Create a signal class that inherits from `BaseSignal` and implements `generate_signals()`.  
3. Instantiate the components:
   - `DataFeed` with a `CsvBackend`
   - `EquityPriceProvider` wrapping the feed
   - `EquityPricer`
   - Your `Signal`
   - `Backtester` with the signal and asset class config
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
| 2 | Purged walk‑forward cross‑validation with nested parameter selection | ⬜ Planned |
| 3 | Deflated Sharpe Ratio, Strategy Graveyard, multiple testing correction | ⬜ Planned |
| 4 | Multi‑leg trades, options, partial unwinds, advanced pricers | ⬜ Planned |

## Design Notes

The full design specification – every class, its methods, and the validation methodology – is in [design_notes.md](design_notes.md).  
If you’re evaluating this project as a hiring manager, that file will give you a detailed view of the system’s depth and my approach to rigorous quant research.

## Testing
```bash
pytest
```
145 unit tests cover `Instrument`, `DataFeed`, `Pricers`, `Trade`, `StrategyStructure`, `CostModel`, `Backtester`, `Summary`, and `Signals`.

## Contributing

This is primarily a personal research tool, but pull requests are welcome. Please open an issue first to discuss what you’d like to change.

## License

MIT – see the `LICENSE` file for details.

## Author

Terry Chan – systematic quant, infrastructure builder.  
GitHub: [@ducksinwar](https://github.com/ducksinwar)