# Quantitative Backtest Framework – Design Notes

## Table of Contents

- [1. Overview](#1-overview)
- [2. Project structure (planned)](#2-project-structure-planned)
- [3. Core classes and their responsibilities](#3-core-classes-and-their-responsibilities)
  - [3.1 Instrument](#31-instrument)
  - [3.2 Strategy Structure](#32-strategy-structure-atomic-leg-grouping)
  - [3.3 Trade](#33-trade)
  - [3.4 MarketData & Data Providers](#34-marketdata--data-providers-phase-1--csv-phase-2--sql--multisource)
  - [3.5 CalendarProvider](#35-calendarprovider)
  - [3.6 Pricer](#36-pricer-basepricer--concrete-implementations)
  - [3.7 Signal](#37-signal-abstract-and-example)
  - [3.8 OrderGenerator](#38-ordergenerator)
  - [3.9 Backtester](#39-backtester)
  - [3.10 Summary](#310-summary)
  - [3.11 Data Extractor](#311-data-extractor)
  - [3.12 PnL Attribution](#312-pnl-attribution-extensible-breakdown)
  - [3.13 Cost Model](#313-cost-model-transaction-cost-handling)
  - [3.14 Persistence of Backtest Results](#314-persistence-of-backtest-results)
  - [3.15 Architecture summary (informal)](#315-architecture-summary-informal)
- [4. Validation framework](#4-validation-framework-to-be-built-after-core-backtester)
  - [4.1 Walk‑forward cross‑validation](#41-walkforward-crossvalidation)
  - [4.2 Nested parameter selection](#42-nested-parameter-selection-within-each-training-window)
  - [4.3 Multiple testing correction across strategies](#43-multiple-testing-correction-across-strategies)
  - [4.4 Randomisation tests for skill](#44-randomisation-tests-for-skill-future-extension)
  - [4.5 Deployment](#45-deployment)
- [5. Implementation plan (Phases)](#5-implementation-plan-phases)
- [6. Technology stack](#6-technology-stack)
- [7. Important conventions](#7-important-conventions)
- [8. Data Infrastructure Evolution](#8-data-infrastructure-evolution)
  - [8.1 The DataFeed Abstraction (current state and future)](#81-the-datafeed-abstraction-current-state-and-future)
  - [8.2 Typed Market Data Providers, Signals, and Multi‑Source Data](#82-typed-market-data-providers-signals-and-multisource-data)
  - [8.3 Scope of the DataFeed (market data only)](#83-scope-of-the-datafeed-market-data-only)
  - [8.4 Migration Path (Phases)](#84-migration-path-phases)
  - [8.5 Long‑term vision: standalone data platform](#85-longterm-vision-standalone-data-platform)
- [9. Overall System Architecture](#9-overall-system-architecture)

## 1. Overview
This project is a rigorous, production‑grade backtesting and validation framework for systematic trading strategies.  
It is designed to:
- Simulate multi‑asset, multi‑leg strategies with proper transaction cost accounting.
- Enforce out‑of‑sample testing through purged walk‑forward cross‑validation.
- Correct for multiple testing bias using Deflated Sharpe Ratio (DSR).
- Serve as both a personal trading research tool and a portfolio piece demonstrating industry best practices.

## 2. Project structure (planned)

The full framework will eventually contain the following modules.  
**Phase 1** implements only the files marked with `(* Phase 1 *)`; the rest are stubbed or not yet created.


```markdown
backtester/
    data/
        data_feed.py                    # (* Phase 1 *) DataFeed class with swappable backends
        csv_backend.py                  # (* Phase 1 *) CSV backend implementation
        typed_providers/
            equity_price_provider.py    # (* Phase 1 *) Thin wrapper around DataFeed for equity prices
            rate_curve_provider.py
            vol_surface_provider.py
            forward_curve_provider.py
            corporate_action_provider.py
    instruments/
        instrument.py                   # (* Phase 1 *) Instrument dataclass
    structures/
        strategy_structure.py           # (* Phase 1 *) StrategyStructure (atomic leg grouping)
    pricers/
        base_pricer.py                  # (* Phase 1 *) Abstract BasePricer
        equity_pricer.py                # (* Phase 1 *) EquityPricer
        fx_forward_pricer.py
        equity_option_pricer.py
        ...
    signals/
        base_signal.py                  # (* Phase 1 *) BaseSignal abstract class
        sma_crossover.py                # (* Phase 1 *) SMA crossover example
    trades/
        trade.py                        # (* Phase 1 *) Trade class
    backtest_engine.py                  # (* Phase 1 *) Backtester daily loop
    summary.py                          # (* Phase 1 *) Summary (standard reports)
    cost_model.py                       # (* Phase 1 *) CostModel (includes FixedCostModel)
    data_extractor.py                   # DataExtractor (raw data extraction)
    pnl_calculator.py                   # AssetPnlCalculator (PnL decomposition)
examples/
    sma_crossover_example.py            # (* Phase 1 *) End‑to‑end example
tests/
    test_trade.py                       # (* Phase 1 *) Unit tests
design_notes.md                         # This file
```
**Notes:**
- `StrategyStructure` is a real, standalone class from Phase 1. Although Phase 1 only uses single‑leg structures, building the class now avoids refactoring `Trade` and the backtester later when multi‑leg support is added.
- The `DataFeed` class is built as a concrete class from Phase 1, with a `CsvBackend` for CSV data. Switching to SQL later only requires writing an `SqlBackend` that implements the same backend protocol and passing it to the `DataFeed` constructor. No consumer code changes.
- `summary.py` and `data_extractor.py` are separate modules because they serve different purposes (opinionated reports vs. raw data).

## 3. Core classes and their responsibilities

### 3.1 Instrument

- A dataclass with common fields:
  - `ticker: str`
  - `asset_class: str`
  - `multiplier: float` (default 1.0)
  - `currency: str` (default `'USD'`) – the currency in which the instrument’s P&L is computed.  
    For USD‑cross FX products this is always `'USD'`, even if the notional is in a foreign currency.  
    This field is used by the summary module to decide whether FX conversion is needed (see Section 3.10).
  - `tags: list[str]` (optional)
  - `leg_id: str` – a globally unique identifier for this leg instance, assigned by the backtester at creation. Used to match cost series and risk data across different parts of the system (e.g., `CostModel` output to `Summary`).
  - `params: dict` – a dictionary of **asset‑specific parameters** needed for pricing and risk. The backtester never inspects this dictionary; it is opaque to the backtester and only interpreted by the pricer.

- **`params` content by asset class (examples):**
  - Equity: `{}` (empty – ticker is sufficient).
  - Equity option: `{'strike': 19000, 'expiry': '2025-12-05', 'option_type': 'call'}`.
  - FX forward: `{'maturity': '2025-06-15', 'notional_currency': 'JPY', 'base_currency': 'USD'}`.
  - IRS / swap: `{'maturity': '2030-01-15', 'fixed_rate': 0.02, 'payment_frequency': '6M', 'day_count': '30/360'}`.
- The `params` dictionary is populated from the `TargetTrade` leg dictionary.  
  The following keys are treated as **common/infrastructure** and are **never** placed in `params`:
  - `ticker`, `size`, `multiplier`, `currency`, `asset_class`, `tags` – standard instrument‑level fields.
  - `structure_id`, `leg_id`, `cost_leg` – internal identifiers and flags used by the backtester; they are consumed during trade construction and discarded from the final `Instrument`.
  All other keys from the leg dict are automatically stored in `params`.
- The Instrument is a **pure data holder** for leg‑level P&L and risk. All P&L calculations are performed by the backtester (see Section 3.9). The pricer reads `params` to know what it is pricing.

- **Internal P&L tracking (populated by the backtester):**
  - `daily_total_pnl: list[float]` – a time series of the daily total P&L changes for this leg, recorded each day the leg is alive.  
    The backtester computes this value and appends it. On days when the pricer returns `None` (data missing), `NaN` is appended.
  - `current_price: float` – the most recent valid mark‑to‑market price. This is updated **only** when the pricer returns a valid price; on missing days, it remains unchanged. This ensures the next valid day’s P&L captures the full return over the gap.
  - `current_size: float` – the number of units currently open.  
    The backtester uses this to scale the per‑unit price change when computing P&L.  
    The meaning of “unit” depends on the asset class:
    - Equities/futures: shares or contracts.
    - FX forwards/swaps: notional, expressed in the notional currency of the contract (e.g., ¥100 M for a USD‑JPY forward).  
      **The pricer’s `price()` method returns a value such that `(price(t) – price(t‑1)) × current_size × multiplier` directly yields the daily P&L in the instrument’s reporting currency (for FX forwards, always USD).**  
      The pricer internally accounts for the notional currency and applies the appropriate pricing formula; the backtester never needs to know whether the notional is in JPY, USD, or another currency.
  - `entry_price: float` – the weighted‑average entry price (or rate) of the open position. Updated by the backtester on partial adds (via weighted average); unaffected by partial unwinds.

  No cumulative realized/unrealized P&L is stored on the Instrument. All derived P&L metrics (total gross, realized, unrealized) are computed on‑the‑fly by consumers (Summary, PortfolioState snapshot builder, DataExtractor) directly from the raw daily P&L series, `current_price`, `current_size`, and `entry_price`.

- **Valuation data storage (for P&L decomposition, populated by the backtester):**
  - For asset classes that support P&L decomposition, the backtester stores all requested valuation‑data measures as per‑measure time series on the Instrument. These include both **risk measures** (e.g., `delta_ts`, `gamma_ts`, `vega_ts`) and **non‑risk building blocks** needed for decomposition formulas (e.g., `price_T_curve_T‑1_ts` for FX forward MTM/carry, or `implied_vol_ts` for certain options).
  - Each measure’s time series is stored in a list attribute named after the measure (e.g., `instrument.price_T_curve_T‑1_ts`, `instrument.delta_ts`).
  - On a valid trading day, the backtester appends the value returned by `pricer.valuation_data(...)` to each list.
  - On a day when the pricer returns `None` (data gap), **`NaN` is appended** to each list to keep them aligned with `daily_total_pnl`.
  - When component PnL is computed on the next valid day, the backtester retrieves the most recent **non‑NaN** entry from each relevant list (by scanning backwards). This provides the “T‑1” value for the P&L decomposition, which will be the last valid data before the gap.

- **Component PnL lists (populated by the backtester when decomposition is enabled):**  
  The backtester computes and stores the resulting component P&L time series alongside `daily_total_pnl`. Examples:
  - `mtm_pnl: list[float]` – the mark‑to‑market component.
  - `carry_pnl: list[float]` – the carry component.
  - `delta_pnl: list[float]`, `gamma_pnl: list[float]`, `vega_pnl: list[float]` – greeks‑based P&L decomposition.
  These lists are appended to on valid days; on missing days, `NaN` is appended.

- **Pricing inputs (optional):**  
  `pricing_inputs: dict[str, list[float]]` – a dictionary mapping variable names to a daily time series of the actual market data used to value this instrument.  
  This is populated only when `record_pricing_inputs = True` in the asset class configuration.  
  Example keys: `'implied_vol'`, `'forward_price'`, `'rate'`, `'days_to_maturity'`, `'dividend_yield'`.  
  The data is ignored by the backtester and standard summary; it is retained for post‑mortem analysis, allowing users to drill into the specific market moves that drove P&L.  
  *(Note: there may be overlap between pricing inputs and valuation data. This is intentional – valuation data feeds the PnL calculator, while pricing inputs provide a complete, human‑readable audit trail. No deduplication is performed.)*

- **Terminology:**
  - **Pricing inputs** = raw market quotes fed into the pricer (e.g., implied vol, forward price). Stored only when `record_pricing_inputs = True`.
  - **Valuation data** = computed outputs of the pricer used for P&L decomposition (e.g., greeks, price‑with‑yesterday’s‑curve). Stored whenever decomposition is configured.

### 3.2 Strategy Structure (atomic leg grouping)

A `StrategyStructure` groups a set of `Instrument` legs that must always be opened, rolled, and unwound together as a single unit.  
It is the natural entity for cost quotation, execution, and rolling.

- **Atomic design:**  
  - `legs` – a fixed list of `Instrument` instances.  
  - Leg sizes move in lockstep: any size‑changing operation (open, add, unwind, roll) scales all legs proportionally. The relative sizes of the legs are constant throughout the structure’s life.
  - No separate active/history leg lists – the whole structure is always opened or closed together.
  - Partial unwind is intended solely for risk‑management adjustments (e.g., delta hedging, dynamic hedge rebalancing). Strategy‑driven scaling‑out is always performed by closing whole structures.

- **FIFO ordering and roll continuity:**  
  - Each structure stores an `original_entry_date` (or a unique `lot_id`) that identifies the economic lot it belongs to.  
  - When a structure is first opened (not from a roll), `original_entry_date` is set to the actual trade date.  
  - When a structure is **rolled**, the new structure inherits the `original_entry_date` of the old structure. This preserves the economic age of the position across contract changes.  
  - When unwinding using FIFO, the backtester (or signal) sorts active structures by `original_entry_date` and closes the oldest lots first. This ensures that rolled positions retain their correct priority.

- **Event log – unit size changes:**  
  The structure maintains a chronological list of lifecycle events: `open`, `partial add`, `partial unwind`, `roll`, `full close`.  
  Each event records the **unit size change** as an absolute number of contracts/shares or a fraction of the structure’s total size.  
  - `open` – initial unit sizes for every leg.  
  - `partial add` – additional units (proportionally distributed).  
  - `partial unwind` – fraction removed.  
  - `roll` – units rolled (recorded on the old structure).  

  Because every size change is logged, the complete time‑series of leg sizes can be derived by applying these events to the initial leg sizes. No separate daily size array is needed on the Instrument.

- **Event log – cost exposure:**  
  Alongside the unit size change, each event **may** also record `cost_exposures` — a dictionary mapping `leg_id` to a dictionary of **per‑unit** risk metrics (e.g., `{"leg_abc": {"notional_per_unit": 450.0}}`, `{"leg_xyz": {"vega_per_contract": 0.03}}`).
  - These per‑unit metrics are combined with `unit_size_change` by the `CostModel` to compute the transacted exposure and the resulting cost.  
  - They are recorded only for the leg(s) and risk type(s) on which cost is actually quoted. For example, a call ratio spread might only store the vega of the 40‑delta leg, because cost is quoted in terms of that leg’s vega. A straddle, where both legs bear cost, stores entries for both legs.  
  - An event can be marked as **cost‑free** (e.g., the `open` event of a structure created by a roll); the `CostModel` skips such events entirely.  
  - The dictionary key itself is the leg’s `leg_id`, so the `CostModel` can attribute the cost directly to that leg’s local P&L. The previous `cost_leg_id` field is retained for readability but is now redundant (it appears inside the `cost_exposures` key set).

  For multi‑leg structures, the transacted size of each leg is derived from the structure's total `unit_size_change` and the leg's fixed proportion. The `CostModel` multiplies the per‑unit risk metric for each leg by that leg's transacted size. No separate per‑leg `unit_size_change` is required inside `cost_exposures`.

- **Lifecycle methods:**  
  - `open(date, cost_exposures=None)` – records the opening event with initial unit sizes for all legs and the provided `cost_exposures` (if any).  
  - `add_size(date, amount, cost_exposures=None)` – records a partial add event. Leg sizes are increased proportionally and the entry price is updated to a weighted average. The `cost_exposures` reflect the pre‑add state (the metrics are per‑unit, so the cost calculator will multiply by `amount` to get the transacted exposure).  
  - `unwind(date, fraction=1.0, cost_exposures=None)` – records a partial or full unwind event. **The `cost_exposures` must reflect the pre‑unwind state** (computed before leg sizes are reduced).  
  - `roll(new_structure, date)` – records a single `roll` event (unit size and cost exposure) on the old structure, closes it, and opens the new structure with a cost‑free `open`. The new structure inherits the old structure’s `original_entry_date`. The new structure also inherits the old structure’s tags, unless the `new_structure` dict explicitly provides a `'tags'` key (which then replaces the inherited tags).

- **Cost exposure:**  
  The `StrategyStructure` is a **pure event recorder** — it performs no cost‑exposure computation of its own. The backtester calls `pricer.compute_cost_exposure()` (see §3.5) for each cost‑bearing leg at order‑execution time and passes the resulting `{leg_id: per_unit_dict}` mapping to the structure’s lifecycle methods. The structure stores this dict directly in the event log entry under the key `"cost_exposures"`.  
  The set of cost‑bearing legs is determined once when the structure is created (see §3.7) and stored in `structure.cost_leg_ids`. The backtester uses this list to know which legs to call `compute_cost_exposure` for.  
  The `CostModel` only reads the logged `cost_exposures` values from the event log; it has no direct dependency on the pricer.

- **Analytical grouping (optional):**  
  - Underlying / instrument‑based grouping is native: the summary module can inspect the legs to determine the underlying ticker, currency pair, or asset class. No tags are needed for that.  
  - User‑defined tags: Structures can carry an optional list of string tags. Tags are copied from the `TargetStructure` when the structure is created. Tags are completely ignored by the backtester and cost model; they exist solely for the summary module.

- **Phase 1 default:**  
  In Phase 1, every `StrategyStructure` contains exactly one `Instrument` (an equity). This abstraction adds zero overhead but provides the natural upgrade path for multi‑leg, multi‑currency strategies.

### 3.3 Trade

A `Trade` represents a strategy‑level position that may consist of one or more **strategy structures** (each an atomic grouping of instruments).  
It mirrors the backtester’s two‑list pattern: `active_structures` for currently live structures, and `structure_history` for the immutable record.

- **Internal state:**
  - `active_structures` – list of currently open `StrategyStructure` objects.
  - `structure_history` – list of **all** `StrategyStructure` objects ever added to this trade (never removed).
  - `tags` – an optional list of user‑defined string tags (e.g., `['EM_Asia', 'carry', 'live']`).  
    Tags are assigned when the trade is created (copied from the `TargetTrade`). They serve two purposes:
    - **Post‑backtest analysis:** The summary module can filter, group, and recombine trades by tag without re‑running the backtest.
    - **Signal/hedging logic:** Tags are included in the `PortfolioState` snapshot (see Section 3.7), so signals can read them to make state‑dependent decisions (e.g., identifying which structures are hedges vs. alpha legs).
    Tags have no effect on the core backtester loop or the cost model.
  - `entry_date: str` – the date the trade was first opened (its first structure was added).  
    Set once when the trade is created; never changes.
  - `exit_date: str | None` – the date the trade was fully closed (all structures unwound).  
    Set when the trade is removed from `active_trades`; `None` while any structure remains alive.

- **Lifecycle methods:**
  - `add_structure(structure, date, cost_exposures=None)` – adds a new `StrategyStructure` to the trade. Used both when a trade is first created and later when a signal scales into a position. The structure is appended to `active_structures` and `structure_history`, and the `cost_exposures` (if provided) are forwarded to `structure.open(date, cost_exposures)`.  
  - `add_to_structure(structure, date, additional_size, cost_exposures=None)` – a thin passthrough that delegates directly to `structure.add_size(date, additional_size, cost_exposures)`. The structure handles all leg-size scaling and entry-price updates internally, recording the event in its log. This method is intended for **risk‑management adjustments** (e.g., increasing a hedge position).  
  - `unwind_structure(structure, date, fraction=1.0, cost_exposures=None)` – reduces or fully closes a structure.  
    - If `fraction == 1.0`, the structure is removed from `active_structures` (it stays in `structure_history`). The `cost_exposures` (reflecting the pre‑unwind state) are forwarded to `structure.unwind(date, fraction, cost_exposures)`.  
    - If `0 < fraction < 1`, the structure remains in `active_structures` with its size reduced proportionally; the unwound portion records a closing cost event.  
    - **The backtester must compute `cost_exposures` before calling this method**, since leg sizes are reduced inside the call and the pricer needs the pre‑unwind sizes for correct exposure values.  
    - Partial unwind is intended for **risk‑management adjustments** (e.g., delta hedging, dynamic hedge rebalancing). For ordinary strategy scaling‑out, closing whole structures is preferred.  
  - `roll_structure(old_structure, new_structure, date, cost_exposures=None)` – simultaneously closes the old structure and opens a new one on the same date. The `cost_exposures` are forwarded to the old structure’s roll event. The new structure’s `open` event is marked **cost‑free**. This avoids double‑counting and reflects that rolling is a distinct transaction from an unwind + new.

- **Scaling in and out:**
  - **Scaling in** is achieved by calling `add_structure(...)` multiple times on the same trade, each time adding a new structure. (Partial scaling‑in via `add_to_structure` is reserved for hedge adjustments.)
  - **Scaling out** is achieved by calling `unwind_structure(...)` on one or more structures. When the scaling‑out amount matches the size of a whole structure, a full unwind is used; otherwise, a partial unwind on the last structure handles the residual.

- **P&L and risk aggregation:**  
  The authoritative P&L and risk data lives at the leg level. The `Trade` object does not store or compute aggregated values; it only holds the structures and their event logs. The `Summary` and `PortfolioState` consumers work directly from leg‑level data.

- **No cost deduction inside Trade.**  
  Cost calculation is entirely deferred to the `CostModel`, which consumes the event logs stored on each `StrategyStructure` (see Section 3.13).

**Phase 1 simplification:**  
In Phase 1, every trade contains exactly one `StrategyStructure` with a single equity instrument leg. All structure‑management methods work identically, making the upgrade to multi‑structure, multi‑leg trades purely additive.

### 3.4 MarketData & Data Providers (Phase 1 – CSV, Phase 2+ – SQL & multi‑source)

The framework uses a **DataFeed** class from Phase 1 – a single, concrete class that serves all market data to the research engine. Internally, it delegates to a swappable **backend** object. The initial backend is a `CsvBackend` that reads daily adjusted close prices from CSV files.
```python
class DataFeed:
    def __init__(self, backend):
        self._backend = backend

    def get_value(self, dataset: str, date: str, ticker: str = None, **params) -> float:
        return self._backend.get_value(dataset, date, ticker, **params)

    def get_series(self, dataset: str, start: str, end: str, ticker: str = None, **params) -> pd.Series:
        return self._backend.get_series(dataset, start, end, ticker, **params)
```
**Why this design?**
- **Single point of storage change**: switching from CSV to a full SQL database with source‑tracking requires only writing a new backend that follows the same protocol and passing it to the `DataFeed` constructor. No consumer code changes.
- **Separation of concerns**: pricers get clean, typed interfaces (e.g., `EquityPriceProvider` wrapping the `DataFeed`), while signals can use the `DataFeed` directly for any ad‑hoc or alternative data.
- **Multi‑source robustness**: the `DataFeed` can be configured to select between multiple sources (`source='bloomberg'` vs `'refinitiv'`) and observation times (`observation_time='ny_close'`), enabling vendor‑robustness checks and point‑in‑time backtests.

**Single‑instance & caching:**
- The `DataFeed` and all typed providers are designed to be **instantiated once** and shared across the entire backtesting session – including all instruments, pricers, and validation folds.
- Providers maintain internal caches to avoid redundant computation:
  - For simple price lookups (O(1) from in‑memory data), no additional caching is required.
  - For term‑structure providers (`VolSurfaceProvider`, `RateCurveProvider`, `ForwardCurveProvider`), the cache key is the combination of (underlying identifier, date, **tenor/expiry**, and any other necessary parameters such as strike or delta). For example, a vol surface provider would cache the computed volatility for (HSI, 2025‑12‑05, strike=19000), or (HSI, 2025‑12‑05, delta=25, expiry=2025‑12‑05).
  - These caches are shared across all folds during walk‑forward validation, so that expensive operations like surface construction and interpolation are performed only once per unique key.

**Missing data handling:**
- The backend can be configured with a `max_forward_fill_days` parameter (per data type, default 2).  
  - For gaps ≤ `max_forward_fill_days`, the backend forward‑fills the last available value. This handles weekends, single holidays, and minor data glitches smoothly.  
  - For gaps > `max_forward_fill_days`, the backend returns `None`.  
- The pricer then returns `None` for any instrument that depends on a missing input, and the backtester records `NaN` in the leg’s P&L for that day (without updating `current_price`).

**Data‑source selection (external to backtester):**
- The choice of data source (Bloomberg vs Refinitiv, CSV vs SQL) is made when the typed data providers are instantiated and passed to the pricer. The backtester has no knowledge of which source is being used; it only interacts with the pricer interface.
- To run a robustness check with alternative data, you simply create new provider instances (e.g., a `VolSurfaceProvider` pointed at Refinitiv instead of Bloomberg), build a new pricer map, and re‑run the backtester with that configuration. No backtester code or configuration fields need to change.

**Holiday masking (optional):**  
- For OTC instruments where data may exist on local holidays but liquidity is questionable, the `DataFeed` can be configured with an optional holiday calendar (per instrument or per asset class).  
- When a calendar is provided, the `DataFeed` treats any date listed as a holiday as having no valid data, even if raw data exists in the database. This ensures that pricing and P&L are only computed on days with genuine market liquidity.  
- The masking is applied before the forward‑fill logic: a holiday is not a “gap” to be filled; it is simply excluded from the valid date series entirely.  
- In Phase 1 (CSV only), this feature is not used. It will be implemented as part of the SQL data pipeline (Phase 2), where a `holiday_calendar` table or configuration can be added.

**Initialization sequence (summary):**
1. Create the `DataFeed` with a `CsvBackend` (later, an `SqlBackend`).
2. Create typed data providers (`EquityPriceProvider`, `VolSurfaceProvider`, `RateCurveProvider`, etc.), passing them the `DataFeed`.
3. Create pricers (`EquityPricer`, `EquityOptionPricer`, etc.), passing each the typed providers it requires.
4. Create the signal (passing the `DataFeed` if the signal needs it).
5. Assemble the `asset_class_configs` dictionary, where each entry’s `AssetClassConfig` bundles the `pricer`, `risk_measures`, `pnl_calculator`, and `record_pricing_inputs`.
6. Create the `Backtester` with the config (signal, `asset_class_configs`).
7. After the backtest, create a `Summary` instance with the desired `SummarySpec` and call `summary.generate(trade_history, cost_model, ...)` to produce the requested reports.
All objects are created once and reused across the entire backtest and any validation folds.

See Section 8 for the full evolution plan, including SQL migration, typed providers, point‑in‑time data, and the long‑term vision.

### 3.5 CalendarProvider

The CalendarProvider is a shared service that provides trading‑day calendars to the backtester, OrderGenerator (§3.8), and pricers. It is not part of the DataFeed, because calendars are a cross‑cutting concern that spans multiple components.

**Holiday calendar model:**
- Calendars are defined by holiday codes (e.g. Bloomberg‑style `"US"`, `"HK"`).
- Each instrument may depend on multiple codes: trading calendar, settlement calendar, fixing calendar.
- The provider maps these codes to lists of non‑trading dates.

**Default calendar:**
- If no holiday codes are specified, the provider returns all business days (Monday–Friday).
- A special code `"all"` returns every calendar day.

**Multi‑asset handling:**
- Supports **union** (for the simulation loop) and **intersection** (for order execution).
- For multi‑leg orders, the OrderGenerator uses intersection to verify all legs' markets are open.

**Core methods:**
- `trading_days(holiday_codes, start, end) -> list[str]` — union calendar for simulation.
- `is_trading_day(holiday_code, date) -> bool` — used for order‑execution checks.
- `next_trading_day(holiday_code, date) -> str` — used by pricers (settlement, fixing) and the backtester (futures rolls).

**Signal data scoping:**
Before requesting price data from the DataFeed, the signal's data‑scoping layer (part of the OrderGenerator) uses the CalendarProvider to find the last valid trading day for each instrument. This ensures indicators are computed only on actual trading days.

**Phase 2 implementation:**
The CalendarProvider will be built first in Phase 2. It will initially load holiday lists from simple CSV files (one per calendar code) and support union/intersection logic. Point‑in‑time holiday data is deferred.

**Phase 1 status:**
Not yet implemented. The current `BacktestConfig.calendar_ticker` is a temporary surrogate that will be replaced by a CalendarProvider instance in Phase 2.

### 3.6 Pricer (BasePricer + concrete implementations)

- **BasePricer** is an abstract class that defines the core interface:
  - `price(instrument, date) -> float | None` – the mark‑to‑market price of the instrument on that date. Returns `None` if a required market data input is missing (beyond the forward‑fill limit).
  - `valuation_data(instrument, date, measures: list[str]) -> dict[str, float] | None` – returns a dictionary of building‑block numbers required for PnL decomposition and risk attribution.  
    The keys depend on the asset class and the requested measures (e.g., `'T_price_curve_T-1'`, `'delta'`, `'gamma'`, `'vega'`).  
    When no decomposition is needed, the method returns an empty dict. If the price is `None`, this method also returns `None`.
  - `resolve_instrument(leg_dict: dict, date: str) -> dict | None` – takes a leg dictionary from a `TargetTrade` (which may be missing instrument‑specific contract parameters) and returns a completed leg dictionary with all required static parameters filled in. The returned dict is used to construct the `Instrument`. The entry price is **not** part of this method; it is obtained separately via `price()`. Returns `None` if the required market data is unavailable.
    - For an equity, `leg_dict` might be `{'ticker': '0700.HK', 'size': 1000}`; the pricer returns the same dict unchanged (no extra parameters needed).
    - For an exchange‑traded option, `leg_dict` already contains `'strike'`, and the pricer validates/returns it unchanged.
    - For an OTC option, `leg_dict` contains `'delta'` and `'tenor'`; the pricer computes the strike from the vol surface and forward curve, and returns the dict with `'strike'` added and `'delta'`/`'tenor'` removed.
    - For an FX forward, `leg_dict` contains no strike; the pricer fetches the current forward rate and returns the dict with `'strike'` set to that rate. If the leg_dict contains a `'tenor'` instead of an explicit `'maturity'`, the pricer resolves it to an absolute maturity date (see the general tenor resolution rule). When the backtester subsequently calls `pricer.price(instrument, date=T)`, the entry price will be **zero** (the instrument is struck at the prevailing market rate, so its MTM value is zero).
    - **General tenor resolution:** For any instrument where a relative tenor is given (e.g., `'1M'`, `'3M'`), the pricer converts it to an absolute maturity date using the appropriate calendar and date‑rolling conventions. This includes options, forwards, swaps, and any other contract that can be specified by tenor. The resolved date is stored as `'maturity'` in the returned leg dictionary.
     This single method isolates all instrument‑specific parameter resolution inside the pricer, keeping the backtester completely generic.
     - **Cost‑leg marking:** For multi‑leg structures where only some legs bear transaction cost (e.g., a swap where only the far leg incurs execution fees), the pricer may add a boolean field `"cost_leg"` to any leg dict. A value of `true` marks that leg as cost‑bearing; omitted or `false` means the leg is cost‑free.  
       For single‑leg instruments the field is typically omitted; the backtester defaults to treating the sole leg as the cost leg.
   - `pricing_inputs(instrument, date) -> dict[str, float] | None` – returns the raw market data values that the pricer used to compute the price on that date (e.g., `{'implied_vol': 20.5, 'forward_price': 1.23, 'rate': 0.05}`). This is entirely separate from `valuation_data`. The backtester calls this method only when `record_pricing_inputs = True` in the asset class configuration, and stores the resulting dictionary in `Instrument.pricing_inputs`. Returns `None` if the price could not be computed (data missing). This method is optional for pricers that do not support diagnostic recording (e.g., a simple `EquityPricer` may return an empty dict).
   - `compute_cost_exposure(instrument, date: str) -> dict[str, float] | None` – returns a dictionary of **per‑unit** risk metrics that the `CostModel` uses to compute transaction costs.  
     The key names are asset‑class‑specific (e.g., `"notional_per_unit"`, `"vega_per_contract"`, `"dv01_per_unit"`).  
     The `CostModel` multiplies each per‑unit value by `event["unit_size_change"]` to obtain the transacted exposure.  
     Returns `None` if the required market data is unavailable.  
     **No default implementation** — every concrete pricer must implement this method.  
     **This method is called only at order‑execution time (open, add, unwind, roll)**, never during the daily PnL loop. It uses the event date’s market data and the instrument’s pre‑event state (sizes, prices).  
     Examples:
     - `EquityPricer`: `{"notional_per_unit": instrument.current_price}`
     - `EquityOptionPricer`: `{"vega_per_contract": total_vega / instrument.current_size}`
     - `FXForwardPricer`: `{"dv01_per_unit": computed_dv01 / instrument.current_size}`
     - For multi‑leg structures (e.g., a straddle), the backtester calls this method once per cost‑bearing leg.
- Concrete pricers (`EquityPricer`, `FXForwardPricer`, `EquityOptionPricer`, etc.) implement these methods using the appropriate typed data providers.

**Single‑instance & caching:**
- Pricers are designed to be **instantiated once** and shared across all instruments, trades, and backtest runs. A single `EquityOptionPricer`, for example, will price every option in the portfolio.
- Each pricer maintains an internal cache to avoid redundant computation. The cache key is the **full instrument identity** — i.e., all the attributes that uniquely define the contract (ticker, asset class, plus the contents of `params`) — combined with the date.
  - For a simple equity, the key is essentially `(ticker, date)`.
  - For a specific option (e.g., a 23‑delta HSI call expiring on 2025‑12‑05), the key includes the instrument’s ticker, strike, expiry, and option type from `params`, ensuring that two options with the same ticker but different strikes receive distinct cached entries.
- On the first call for a given key, the pricer performs all expensive data fetching and model calculations. **Which values are computed and cached depends on the backtest configuration and which methods are called:**  
  - The pricer always computes and caches the base `price`.  
  - Risk measures (greeks) are **only** computed and cached if the asset class's `risk_measures` list in `asset_class_configs` is non‑empty. If no risk decomposition is requested, no greeks are calculated or stored.  
  - `compute_cost_exposure` reuses the same shared cache. If a greek (e.g., vega) was already computed by `valuation_data` on the same `(instrument, date)`, the cost‑exposure call retrieves it instantly at zero extra cost, and vice versa.  
  - This ensures that the cache does not waste memory or CPU on computations that will never be used.
- If later calls (within the same backtest or validation fold) request additional measures that were not previously cached, the pricer uses the already‑available underlying data (from the instrument and data providers) to compute only the new values and updates the cache.
- This design is essential for performance during walk‑forward validation: the same pricer instances are reused across all folds, so that heavy pricing operations are performed only once per instrument per date, and only for the measures actually needed.

- The backtester never needs to know *how* the pricer obtains the building blocks; it only calls the methods and uses the returned numbers.

### 3.7 Signal (abstract and example)

- **BaseSignal** is an abstract class with a method:
  `generate_signals(current_date, portfolio_state: PortfolioState | None = None, trade_history_snapshot: tuple[TradeRecord, ...] | None = None) -> list[dict]`
  Each returned dictionary is a **TargetTrade** with the following structure (shown as a Python dictionary):
  ```python
  {
      'Action': 'NEW' | 'UNWIND' | 'ROLL',
      'trade_id': str | None,
      'info': [ ... ]   # structure depends on Action
  }
  ```
- **Portfolio state requirement:**  
  `BaseSignal` has a class attribute `requires_portfolio_state: bool` (default `False`).  
  The backtester reads this flag: only if `True` does it build a `PortfolioState` snapshot and pass it to the signal.  
- **Trade history requirement:**  
  `BaseSignal` also has a class attribute `requires_trade_history: bool` (default `False`).  
  If `True`, the backtester builds a `trade_history_snapshot` (a tuple of `TradeRecord` objects) from the current `trade_history` list and passes it to the signal.  
  This allows the signal to access past trade information without mutating live objects.

- **Semantics of the `TargetTrade` dictionary:**

  | Action   | trade_id  | info content | Meaning |
  |----------|-----------|--------------|---------|
  | `NEW`    | `None`    | List of structure dicts (each with `legs`) | **Create a new trade** with the given structures. Structure IDs may be provided or auto‑generated. |
  | `NEW`    | Not `None` | List of structure dicts where `structure_id` is **not** set (or `None`) | **Add new structures** to the existing trade. |
  | `NEW`    | Not `None` | A list containing a single structure dict with an **existing** `structure_id` and a `'size'` key | **Partial‑add** to that structure: increase its size by `size` units, scaling all legs proportionally. |
  | `UNWIND` | Not `None` | Empty list (`[]`) or omitted | **Fully unwind the entire trade** – all structures are closed. |
  | `UNWIND` | Not `None` | List of structure dicts, each with an existing `structure_id` and **no** `'size'` key | **Fully unwind each specified structure**. If all structures are unwound, the trade is closed. |
  | `UNWIND` | Not `None` | List containing a single structure dict with an existing `structure_id` and a `'size'` key | **Partial‑unwind** that structure: reduce its size by `size` units. |
  | `ROLL`   | Not `None` | List of roll descriptors, each containing `'old_structure_id'` and `'new_structure'` (a structure dict with `legs` and optional `structure_id`) | **Roll one or more structures**: close the old structure(s) and simultaneously open new one(s) with a single cost event. The new structures inherit the `original_entry_date` from the old ones. |

- **`ROLL` info structure:**
  Each element in the `info` list is a dictionary, shown below as a template:
  ```python
  {
    'old_structure_id': 'struct_123',          # ID of the structure to close (must exist and be active)
    'new_structure': {                         # definition of the replacement structure
        'structure_id': 'struct_456',          # optional; if omitted, backtester generates one
        'legs': [                              # list of leg dictionaries, same format as for NEW
            {'ticker': 'HSI', 'size': 10, 'asset_class': 'equity_future', 'multiplier': 50},
            # ... more legs if multi‑leg structure
        ],
        'tags': ['hedge']                      # optional; if absent, inherits old structure's tags
    }
  }
  ```
  Multiple roll entries can be provided to roll several structures (e.g., different hedge legs) in a single signal. The new structure’s ID is generated automatically (or the signal may optionally provide one). The new structure inherits the old structure’s `original_entry_date`. By default, the new structure also inherits the old structure’s tags. To override the tags, provide a `'tags'` key inside the `new_structure` dictionary.

- **Leg dictionary fields:**  
  Common fields (always present): `ticker`, `size` (for `NEW` or partial‑add).  
  Optional common fields: `multiplier`, `currency`, `tags`, `asset_class` (if not resolvable from a ticker‑to‑asset‑class mapping).  
  All other fields are treated as **instrument‑specific parameters** and are stored in the `Instrument.params` dictionary. Examples:
  - Equities: no extra fields needed.
  - Equity options: `'strike'`, `'expiry'`, `'option_type'` (and possibly `'exercise_style'`). Alternatively, `'delta'` and `'tenor'` may be given for OTC options.
  - FX forwards: `'maturity'` (an absolute date) **or** `'tenor'` (e.g., `'1M'`, `'3M'`), along with `'notional_currency'`, `'base_currency'`. The pricer resolves the tenor to an absolute maturity date.
  - Swaps: `'maturity'` (or `'tenor'`), `'fixed_rate'`, `'payment_frequency'`, `'day_count'`, etc.
  The backtester does **not** validate or interpret these parameters; it simply passes them through. Only the pricer (and later, the execution module) knows what to do with them.

- **Instrument resolution:**  
  The leg dictionary may omit instrument‑specific parameters that are not known at signal‑generation time (e.g., the exact strike of an OTC option, the forward rate of an FX forward, or the absolute maturity date when only a tenor is given). The pricer’s `resolve_instrument` method (Section 3.6) is responsible for filling in any missing fields at execution time. The backtester simply passes the leg dictionary to the pricer and uses the completed result.

- The signal is **stateless**: it does not retain any internal memory that cannot be reconstructed from the data passed to it at each call. It uses market data available *up to* `current_date - 1` (i.e., yesterday’s close, or earlier) and, optionally, the current `portfolio_state` snapshot and/or the `trade_history_snapshot`, to produce orders for `current_date`.  

  For continuation runs (where the backtester is re‑started from a previous state), any necessary positional awareness (e.g., whether the strategy is already in a position) is derived from the `PortfolioState` snapshot or the `trade_history_snapshot`—not from serialized internal state. A signal that requires such awareness simply sets the appropriate flag (`requires_portfolio_state` or `requires_trade_history`) and reads the relevant data from the snapshot(s).  

  The backtester calls `signal.generate_signals(date=T, portfolio_state=state_T-1, trade_history_snapshot=snapshot_T-1)` and **immediately** executes the returned orders at the close of day T.

- **PortfolioState snapshot (optional):**  
  When `requires_portfolio_state` is `True`, the backtester creates a **`PortfolioState` snapshot** at the end of day T‑1 (after all T‑1 processing is complete, before any day‑T work).  
  This snapshot is a read‑only, frozen dataclass containing:
  - `date` – the “as of” date (T‑1).
  - `trades` – a tuple of `TradeSnapshot` objects.
  - Each `TradeSnapshot` holds a tuple of `StructureSnapshot` objects, and each `StructureSnapshot` holds a tuple of `LegSnapshot` objects.
  - `LegSnapshot` includes: `ticker`, `instrument_type`, `size`, `entry_price`, `current_price` (as of T‑1 close), `daily_total_pnl` (the full time series up to T‑1), `component_pnls: dict`, and `risk_measures: dict`.
  - The snapshot provides **only the raw leg data**. It does not pre‑compute cumulative realized/unrealized P&L or any other derived metric. If a signal needs those values, it computes them on‑the‑fly from the raw fields (e.g., `total_gross = sum(daily_total_pnl)`, `unrealized = (current_price - entry_price) * size`).
  - `TradeSnapshot` may also include a `trade_id` field so the signal can reference trades.
  - The snapshot contains **no** live references to `Trade`/`Instrument` objects.

- **TradeHistory snapshot (optional):**  
  When the backtester calls `generate_signals()`, if the signal’s `requires_trade_history` flag is `True`, the backtester also passes a `trade_history_snapshot` argument. This snapshot is a **tuple of `TradeRecord` dataclasses**, each an immutable, read‑only summary of one trade.  
  The snapshot is built at the **end of day T‑1** (after all T‑1 processing, before any day‑T work), exactly like the `PortfolioState`. It reflects the full trade history as it stood at that point—no day‑T price or order information is included.  

  A `TradeRecord` contains:
  - `trade_id: str`
  - `entry_date: str` (date of first structure open)
  - `exit_date: str | None` (date of last structure close, or `None` if still open)
  - `tags: tuple[str, ...]` (frozen copy of the trade’s tags)
  - `is_open: bool` (convenience flag derived from `exit_date`)

  No mutable references to live `Trade`, `Structure`, or `Instrument` objects are exposed. The signal can safely inspect this snapshot to enforce cooldowns, count trades, or apply any other logic that requires knowledge of past trading activity, without any risk of corrupting the backtester’s internal state.

- **SMACrossoverSignal** (example): parameters `short_window`, `long_window`. Uses market data up to `current_date - 1`.  
  `requires_portfolio_state = True` – it checks the `PortfolioState` snapshot for any open trade with the target ticker to determine whether it is currently in a position. No internal state is stored; the signal is fully stateless.  
  Returns orders like the examples shown below (in Python dict form):
  ```python
  # Open new long
  {'Action': 'NEW', 'trade_id': None, 'info': [{'structure_id': None, 'legs': [{'ticker': 'SPY', 'size': 100}]}]}
  # Close (full unwind)
  {'Action': 'UNWIND', 'trade_id': 'trade_123', 'info': []}
  ```

- **Separation of alpha and execution:**  
  **In Phase 1**, `BaseSignal.generate_signals()` directly produces `TargetTrade` dictionaries for simplicity. The signal may delegate mechanical operations (scaling, hedging, rolling) to separate helper modules that also emit `TargetTrade` dicts.

  **In Phase 2**, the design separates alpha from execution:
  - Alpha signals produce **pure intent dicts** (e.g. `{"action": "BUY", "ticker": "SPY", "target_size": 200}`) — no mechanical concerns.
  - A separate **OrderGenerator** (§3.8) transforms these intents into executable `TargetTrade` orders by applying a chain of swappable `OrderRule` instances (scaling, hedging, rolling, calendar validation, scheduling).
  - The alpha signal remains stateless and calendar‑unaware.
  - Existing helper modules (`ScalingModule`, `DeltaHedgeModule`, `RollModule`) will be migrated into `OrderRule` implementations within the OrderGenerator.
  These modules are not required in Phase 1 but are planned for Phase 2.

### 3.8 OrderGenerator

The OrderGenerator is a stateless component that sits between the alpha signal and the backtester. It transforms a pure **alpha intent dict** into executable `TargetTrade` orders by applying a chain of swappable **OrderRule** instances.

**Alpha intent format (example):**
```python
{"action": "BUY", "ticker": "SPY", "target_size": 200}
```

**Initialization and execution:**
- The OrderGenerator is initialized with a list of `OrderRule` instances, following the same registry pattern as the CostModel's `BaseCostCalculator` (§3.13).
- On each call it receives: the intent, current date, portfolio state, trade history snapshot, and the CalendarProvider.
- It runs each rule in sequence; the final rule emits the `TargetTrade` dicts (or an empty list if the order is discarded).

**Stateless:** No internal queues. Orders that cannot be executed are discarded and may be regenerated by the signal on the next trading day.

**Phase 2 implementation plan:**
The first rule to be built is **CalendarValidationRule**, which uses the CalendarProvider (§3.5) to reject orders when any leg's market is closed. Later, additional rules will be added: `ScalingRule`, `DeltaHedgeRule`, `RollRule`, and `TradingSchedule`.

**CalendarValidationRule:**
- Checks each leg's holiday calendar(s) to determine if its market is open on the execution date.
- If any leg is on holiday, the entire order is **rejected** (discarded) — no partial trade is allowed.
- It does **not** postpone; the signal will naturally re‑evaluate on the next open day.

**TradingSchedule (future):** Adjusts a fixed‑frequency schedule (e.g., "every Monday") by recomputing the first fully open day of the week using the CalendarProvider, remaining stateless.

### 3.9 Backtester

- The backtester is initialised with a single configuration object (`BacktestConfig`) that bundles all settings:
  - `signal` – the `BaseSignal` instance that generates trading orders.
  - `start_date`, `end_date` – the simulation period.
  - `asset_class_configs` – a dictionary mapping each **asset class** to an `AssetClassConfig` dataclass.  
    An `AssetClassConfig` contains:
    - `pricer` – the `BasePricer` instance responsible for pricing all instruments of this asset class.
    - `risk_measures` – a list of PnL decomposition/risk measures to compute for all instruments of this type (e.g., `['mtm','carry']` for FX forwards, `['delta','gamma','vega']` for options). An empty list means no decomposition.
    - `pnl_calculator` – an **optional** instance of `AssetPnlCalculator` (see Section 3.12). Required when `risk_measures` is non‑empty; the backtester delegates to this calculator for all component‑PnL computations. If `None` or absent, no decomposition is performed.
    - `record_pricing_inputs` – an optional boolean (default `False`). If `True`, the pricer is instructed to return the raw pricing inputs (e.g., implied vol, forward price) that were used on each date. These are stored on `Instrument.pricing_inputs`.

- **No pre‑defined instrument universe.** The backtester does not hold a list of instruments ahead of time.  
  Instruments are created dynamically by the signal when it returns `TargetTrade` dictionaries. Each `TargetTrade` specifies the `Instrument` (ticker, asset class, multiplier, etc.) that the backtester uses to open a new `Trade`.  
  If a signal generates an instrument whose `asset_class` is not recognised (i.e., not present in `asset_class_configs`), the backtester raises an error immediately.

- **Internal state:**
  - `active_trades` – list of currently open `Trade` objects. These are the *only* positions that are marked to market each day.  
    Each `Trade` object holds the relevant `StrategyStructure`(s) and their `Instrument` legs, and accumulates P&L, risk, and event history.
  - `trade_history` – list of **all** trades ever opened. A trade is added to `trade_history` when it is first created and **never removed**.  
    After a trade is closed, it remains in `trade_history` in its final state; it is simply removed from `active_trades`.  
    `trade_history` provides the immutable, complete audit trail for post‑backtest analysis.

- **Daily loop order:**  
  For each trading day T (as determined by the `DataFeed`’s calendar):

  1. **Compute PnL (T‑1 → T):**  
     For every leg in every active structure of every active trade:
       - Ask the pricer for `price_today` by calling `pricer.price(instrument, date=T)`.
       - **If the price is `None`** (critical data missing beyond the forward‑fill limit):
           - Append `NaN` to the leg’s `daily_total_pnl` list.
           - Do **not** change the leg’s `current_price` (the last valid mark is retained).
           - Skip any risk decomposition or component‑PnL computation for this leg today.
       - **If the price is valid:**
           - Compute the daily gross P&L:  
             `daily_pnl = (price_today - leg.current_price) * multiplier * leg.current_size`.
           - Append `daily_pnl` to the leg’s `daily_total_pnl` list.
           - Update `leg.current_price = price_today`.
           - **If decomposition is configured** (the asset class’s `AssetClassConfig` includes both `risk_measures` and a `pnl_calculator`):
               - Call `pricer.valuation_data(instrument, date=T, risk_measures)` to get today’s building‑block numbers.
               - From the Instrument’s valuation‑data time series, retrieve the most recent **non‑NaN** entry for each required measure (this gives the T‑1 values).
               - Pass the T‑1 and T data to the calculator:  
                 `component_pnls = pnl_calculator.compute_component_pnl(instrument, prev_data, curr_data, risk_measures)`.
               - Append each returned value to the corresponding component‑PnL list on the Instrument (e.g., `instrument.delta_pnl.append(...)`).
           - **If `record_pricing_inputs` is enabled**, call `pricer.pricing_inputs(instrument, date=T)`.  
             If the result is not `None`, append its keys and values to the leg’s `pricing_inputs` dictionary time series; if the price had been `None`, append `NaN` for each key to keep the series aligned.

  2. **Request and execute today’s orders:**  
      *(Phase 1:* calls `signal.generate_signals()` directly. *Phase 2:* calls signal to get alpha intents, then passes them through the OrderGenerator (§3.8) to obtain `TargetTrade` orders.*)
      - **Portfolio state snapshot (conditional):**
       If `signal.requires_portfolio_state` is `True`, the backtester has already created a `PortfolioState` from `active_trades` at the end of day T‑1 (after all T‑1 processing). This snapshot is passed as `portfolio_state`.  
       If the flag is `False` (default), `portfolio_state` is `None`.
     - **Trade history snapshot (conditional):**  
       If `signal.requires_trade_history` is `True`, the backtester has already built a `trade_history_snapshot` – a tuple of `TradeRecord` objects – at the end of day T‑1 from the `trade_history` list as it stood at that time (all trades ever opened up to and including day T‑1). This snapshot is passed as `trade_history_snapshot`.  
       If the flag is `False` (default), `trade_history_snapshot` is `None`.
     - Call `signal.generate_signals(current_date=T, portfolio_state=state_T-1, trade_history_snapshot=snapshot_T-1)`. The signal returns a list of `TargetTrade` dictionaries.

     - *Implementation note:* Building the full snapshot from `trade_history` is O(#trades). For typical strategy‑level trade counts (hundreds to low thousands) this is negligible. If it ever becomes a performance concern, future optimisations could include a signal‑declared lookback window or an incremental update, but these are not required for Phase 1.

     - **Data availability check (all orders):**  
       Before executing any order (whether `NEW`, `UNWIND`, or `ROLL`), the backtester verifies that the pricer can produce a valid `price()` for every instrument involved on date T.  
       - If all prices are valid, the order is executed as described below.  
       - If any instrument returns `None` (data gap exceeding the forward‑fill limit), the entire order is **rejected** (skipped, with a warning logged). This simulates a real‑world execution failure where the market is not reliably priced. No trades are opened, closed, or rolled on that day for the affected instruments.  
       Short disruptions (≤ the forward‑fill limit) are handled automatically by data providers and do not cause rejection.

     - **Instrument resolution (all `NEW` orders):**  
       For every `NEW` order, before creating any `Trade` or `StrategyStructure`, the backtester passes each leg dictionary to the appropriate pricer via `pricer.resolve_instrument(leg_dict, date=T)`.  
        - If the pricer returns a completed dictionary, the backtester uses it to construct the `Instrument` (extracting common fields like `ticker`, `size`, `multiplier`, `currency`, `tags`, and placing all other keys into `params`).  
        - **Infrastructure keys discarded:** The common‑keys filter (see §3.1) now also strips `"cost_leg"`, `"structure_id"`, and `"leg_id"` so they never appear in `Instrument.params`.  
        - The backtester then calls `pricer.price(instrument, date=T)` to obtain the execution price. This value is set as both the `entry_price` and the initial `current_price` of the leg.  
        - If the pricer returns `None` (required market data missing), the entire `NEW` order is rejected.  
        This step completely isolates all instrument‑specific parameter resolution inside the pricer. The backtester has no knowledge of how any missing fields were filled in.

      - **Instrument construction, `leg_id`, and cost‑leg identification:** When the completed leg dictionary is returned by `resolve_instrument`, the backtester constructs the `Instrument` object. At this point, the backtester:  
        1. Generates a globally unique `leg_id` (e.g., a UUID) and stores it on the `Instrument`. This `leg_id` remains unchanged for the lifetime of the leg object.  
        2. Inspects the resolved leg dict for the `"cost_leg"` boolean. If `true` (or if the structure has only one leg and the field is omitted), the leg’s `leg_id` is added to the structure’s `cost_leg_ids` list — the set of legs for which the backtester will compute cost exposure at order‑execution time.

     - **`NEW` orders (Action = `'NEW'`):**  
       (Legs have already been resolved into complete instrument specifications with entry prices set.)  
       - **New trade (`trade_id` is `None`):**  
         For each structure dict in `info`, create a new `StrategyStructure` from the resolved legs. If a `structure_id` is given, use it; otherwise, generate a unique ID. Add all structures to a new `Trade` (assign a new unique `trade_id`). Add the trade to `active_trades` and `trade_history`. Set `trade.entry_date = T` (the current trading day). Copy any tags.
       - **Add structures to existing trade (`trade_id` not `None`, `info` contains structure dicts without `structure_id` or with `structure_id=None`):**  
         Look up the trade by `trade_id`. For each structure dict, create a new `StrategyStructure` and call `trade.add_structure(...)`.
       - **Partial‑add to a structure (`trade_id` not `None`, `info` has a single entry with an existing `structure_id` and a `'size'` key):**  
         Look up the trade and the specific structure. Call `trade.add_to_structure(structure, date, additional_size=info[0]['size'])`. The structure scales its legs proportionally and records a partial‑add cost event.

     - **`UNWIND` orders (Action = `'UNWIND'`):**  
       - **Full unwind of entire trade (`trade_id` not `None`, `info` is empty or missing):**  
        Look up the trade. For each active structure, call `trade.unwind_structure(structure, fraction=1.0)`. Set `trade.exit_date = T` (the current trading day) and remove the trade from `active_trades`.
       - **Full unwind of specific structures (`trade_id` not `None`, `info` contains structure dicts with existing `structure_id` and **no** `'size'` key):**  
        For each such structure, call `trade.unwind_structure(structure, fraction=1.0)`. If the trade has no remaining active structures after these unwinds, set `trade.exit_date = T` and remove it from `active_trades`.
       - **Partial unwind of a specific structure (`trade_id` not `None`, `info` has a single entry with an existing `structure_id` and a `'size'` key):**  
         Let `unwind_fraction = info[0]['size'] / structure.current_size`. Call `trade.unwind_structure(structure, fraction=unwind_fraction)`. The structure records a partial‑unwind cost event. The trade remains in `active_trades` if any size remains.

     - **`ROLL` orders (Action = `'ROLL'`):**  
       - `trade_id` must be provided.  
       - For each entry in `info`:
         - Look up the old structure by `old_structure_id` in the trade.  
         - Create a new `StrategyStructure` from the `new_structure` dict (generate a new `structure_id` if not provided).  
         - Call `trade.roll_structure(old_structure, new_structure, date=T)`.  
           This records a single `roll` cost event on the old structure (based on its exposure), closes the old structure, and opens the new structure with a cost‑free `open` event. The new structure inherits the `original_entry_date` and tags of the old one (unless overridden).
       - If after rolling, the trade still has active structures, it remains in `active_trades`.

      - Tags are only applied when a new trade is created. For existing trades, the tags remain unchanged.

      - **Cost‑exposure computation (all order types):**  
        Before any `StrategyStructure` lifecycle method is called, the backtester computes the cost exposures for the transaction:
        1. For each cost‑bearing leg in the affected structure(s) (identified by `structure.cost_leg_ids`), call `pricer.compute_cost_exposure(leg, date=T)`.  
        2. **For NEW orders**, the exposure is computed on the freshly‑constructed `Instrument` using the entry price.  
        3. **For UNWIND and partial‑add orders**, the exposure is computed on the **pre‑event** instrument state (before `current_size` or `entry_price` are modified).  
        4. Collect the results into a `{leg_id: per_unit_dict}` mapping.  
        5. If any `compute_cost_exposure` call returns `None` (data unavailable), log a warning and exclude that leg from the `cost_exposures` map for this event (the event is still recorded; the affected leg is simply treated as cost‑free for this transaction).  
        6. Pass `cost_exposures` through `Trade` methods to the `StrategyStructure` lifecycle method, which stores it in the event log entry under `"cost_exposures"`.  
        **No cost arithmetic is performed by the backtester** — it only collects and forwards the raw per‑unit metrics.

  3. **Compute risk at T (forward‑looking):**  
     After all trades have been updated, for each remaining structure in `active_trades`, call `pricer.valuation_data(...)` for each leg to obtain current Greeks and other risk metrics (skip if the pricer returns `None`). Store these values on the `Instrument`. They will be used for tomorrow’s PnL decomposition and, in future phases, for delta hedging decisions.

     *Implementation note:* This risk computation uses the **post‑trade** portfolio — after all `NEW`, `UNWIND`, and `ROLL` orders for day T have been executed. Positions opened or modified today are included, ensuring that the stored greeks accurately represent the portfolio’s risk at the close of day T. This is essential for correct PnL decomposition on day T+1 and for any future delta‑hedging logic.

  4. **Move to next day.**

- After the backtest loop, the backtester returns the `trade_history` list (and optionally the `active_trades` for any open positions). This raw output is completely independent of the backtester, pricers, and data providers. The caller then passes it to a `Summary` object (Section 3.10) together with a `CostModel` and any desired FX rates to produce performance metrics.

- **No cost or summary logic inside the backtester.** Cost events are recorded on structures but not evaluated; the `Summary` and `CostModel` are entirely external. This allows changing cost assumptions, FX rates, metric specs, or filtering rules without re‑running the simulation.

- This design:
  - Follows the correct temporal order: PnL (backward) → Signal (now) → Risk (forward).
  - Handles missing data gracefully: forward‑fills short gaps, skips long gaps, preserves cumulative P&L via `current_price`.
  - Uses T‑1 greeks for PnL attribution, eliminating look‑ahead bias.
  - Leaves a natural hook for future delta hedging (after risk computation).
  - Decouples instrument universe from the backtester – signals decide what to trade.
  - Groups configuration by asset class, with consistent risk‑measure and data‑source settings.
  - Fully separates cost calculation (deferred to the summary phase, via structure‑level event logs), so cost assumptions can be changed without re‑running the backtest.
  - Maintains leg‑level daily P&L series and cumulative realised/unrealised P&L, enabling straightforward post‑backtest analysis and P&L attribution.
  - Supports scaling‑in, scaling‑out, partial adds/unwinds, and rolling of structures, all through a uniform dictionary‑based signal output.
  - Is fully backward‑compatible with Phase 1: a single `'equity'` asset class, one pricer, no risk measures, no overrides, and every trade contains one structure with one leg.

- **Future extension – order retry on missing data:**  
  In later phases, a `'on_missing'` field could be added to `TargetTrade` dictionaries (values `'reject'` or `'retry'`). Retried orders would be held in a pending queue and executed on the first subsequent day with valid data, mimicking real‑world execution disruptions. This is not needed for Phase 1 daily‑frequency equities.

- **Future extension – incremental backtesting (burn‑in, live OOS, slippage comparison):**  
  The backtester’s complete state (active trades, trade history, leg time series) can be serialised at any point. In future phases, the backtester will accept an optional initial state so that a new instance can be created with pre‑loaded active trades and history. This enables three important workflows:
  - **Burn‑in periods in walk‑forward validation** – after training, carry open positions into the validation window, run a burn‑in phase, then continue into the evaluation phase without resetting state.
  - **Daily live out‑of‑sample comparison** – after deploying a strategy, run the backtester forward by one day (or any number of days since the last run) to produce the theoretical P&L, which can be compared against actual broker‑filled trades to monitor slippage. The resulting theoretical equity curve provides a pure, AUM‑independent view of strategy performance, serving as the benchmark against which actual realised P&L is compared.
  - **General continuation** – a `run_continuation(new_end_date)` method will reload a saved state, accept updated market data for the new dates, and run the daily loop from the last processed date to `new_end_date`. The signal is re‑instantiated from its type and parameters; any positional state is recovered from the initial `PortfolioState` (or `trade_history_snapshot`). The signal does not need to be serialized.

### 3.10 Summary

The `Summary` class provides standard reports – predefined templates for common analyses. For raw data extraction, see Section 3.11 (Data Extractor).

**Summary specification (`SummarySpec`):**

The `Summary` constructor takes a single dictionary with the following keys:

- `reports`: a dictionary that defines the reports to generate.  
  - The dictionary may optionally contain a top‑level `'filter'` key – a callable that applies to every report in this dictionary.
  - Every other key is either a **report name** or a **group name**.
    - If the key maps to a dictionary that itself contains a `'reports'` key, it is treated as a **report group**. A group must have a `'filter'` key, which applies to all reports inside it.
    - Otherwise, the key is a **report name**, and its value is the report config (which may be `True` or a sub‑dictionary with options like `'include'`, `'annualization'`, etc.). Reports do **not** accept a `'filter'` key; filtering is handled entirely by the root filter and group filters.
  
  Groups can be nested arbitrarily. A report’s effective filter is the logical AND of the root `'filter'` and the filters of all enclosing groups.

- `missing_data_mode`: string, `'any'` (default), `'all'`, or `'per_leg'`. Applies to **all** reports in this run. To compare different missing‑data modes, call `generate()` again with a different value.

- `output`: optional output configuration.  
  - `'format'`: `'excel'`, `'csv'`, or `'parquet'`.  
  - `'path'`: the file path to write to.  
  For Excel, each report becomes a separate sheet; for CSV/Parquet, each report becomes a separate file.  
  An output name is the underscore‑joined path of all enclosing group names, the report name, and for `'by_underlying'` the underlying ticker. The string `by_underlying` does **not** appear in the output name; it is a report template, not a naming component.  
  If `'output'` is omitted, reports are returned as a dictionary of DataFrames, keyed by their output names.

Parameters that affect computation (annualization, cost inclusion) are specified per report, not globally, so that only the reports that need them carry the extra configuration.

**Standard reports:**

Standard reports are predefined templates that compute specific, well‑known outputs. They can optionally be restricted to a subset of columns and configured with report‑specific parameters.

| Report name       | Description | Options | Available `'include'` groups |
|-------------------|-------------|---------|------------------------------|
| `'equity_curve'` | Daily portfolio‑level equity series. | `include` | `'gross'` (cumulative gross P&L), `'cost'` (cumulative cost), `'net'` (cumulative net P&L), `'decomposition'` (daily P&L decomposition, if configured). If FX rates were supplied, the equity curve also includes the spot FX rate used for each currency conversion (e.g., `fx_USDJPY`). If `'include'` is omitted, all groups are produced. |
| `'by_underlying'` | One sheet per underlying instrument. | `include` | `'include'` is a **dictionary** mapping metric groups to their sub‑report configs. Supported keys and their sub‑configs:<br>• `'equity_curve'`: `{'include': ['gross','cost','net','decomposition']}`<br>• `'risk'`: `{'include': ['greeks']}`<br>• `'drawdown_table'`: `{'include': ['gross','net'], 'top_n': <int>}`<br>• `'hit_ratio'`: `{'include': ['gross','net'], 'timeframe': 'yearly'\|'monthly'}`<br>• `'metrics'`: `{'include': ['sharpe_gross', …], 'annualization': <int>}`<br>`'by_underlying'` does **not** accept a `'filter'` key directly. Wrap it in a report group to filter. |
| `'trade_summary'` | One row per trade with key attributes and P&L. | `include` | `'identifiers'` (trade ID, entry/exit dates), `'tags'`, `'gross_pnl'`, `'cost'`, `'net_pnl'`, `'local_pnl'`, `'usd_pnl'`. If omitted, all groups are included (equivalent to `'full'`). |
| `'hit_ratio'`     | Hit ratio over a configurable timeframe. | `timeframe` (default `'yearly'`), `include` | When `include` is specified, it controls whether the gross, cost, and net versions are computed. Examples: `'include': ['gross']` (only gross hit ratio), `'include': ['gross','net']` (gross and net of costs). If omitted, both gross and net are produced. |
| `'drawdown_table'`| Top N drawdowns with dates and underwater days. | `top_n` (default 10), `include` | Same `include` logic as `'hit_ratio'`: controls gross vs. net drawdowns. |
| `'metrics'`       | Standard scalar metrics (Sharpe, Calmar, annualized return, max drawdown, hit ratio). | `include`, `annualization` (default 252) | `include` specifies which metrics to compute (e.g., `['sharpe','max_drawdown']`). Each metric can be requested in `'gross'` or `'net'` form by adding a suffix (e.g., `'sharpe_gross'`, `'sharpe_net'`). If `include` is omitted, all available metrics are produced in both gross and net versions. |

**Output format for `'by_underlying'`:**

When `'by_underlying'` is requested, the `Summary` returns a dictionary keyed by underlying ticker. Each value is itself a dictionary containing one DataFrame per requested metric group (e.g., `'equity_curve'`, `'drawdown_table'`, `'hit_ratio'`, `'metrics'`). The groups present depend on the `'include'` parameter.

In file/sheet naming, the underlying ticker is used directly as the sheet name (e.g., `HSI`, `SPX`). If the `by_underlying` report is inside a group, the group name is prefixed as usual (e.g., `momentum_HSI_equity_curve`). This keeps names short and matches the familiar convention of using the underlying ticker as the identifier.

All standard reports return their results as separate DataFrames (or sheets, if Excel output is specified). If you want a single combined table — for example, an overall metrics row alongside per‑underlying metrics — concatenate the relevant DataFrames yourself. This keeps the `Summary` focused on data production, not presentation.

**Examples with `'include'`:**
```python
# Equity curve with only gross and net (no cost, no decomposition)
'equity_curve': {
    'include': ['gross', 'net']
}

# Trade summary with only identifiers and gross P&L
'trade_summary': {
    'include': ['identifiers', 'gross_pnl']
}

# Metrics with only Sharpe and max drawdown, gross only
'metrics': {
    'include': ['sharpe_gross', 'max_drawdown_gross'],
    'annualization': 252
}

# Hit ratio gross only, over monthly timeframe
'hit_ratio': {
    'timeframe': 'monthly',
    'include': ['gross']
}
```
**Examples with report groups:**
```python
spec = {
    'reports': {
        # Flat report – overall equity curve, no filter
        'equity_curve': {'include': ['gross', 'net']},

        # Group for momentum‑tagged trades
        'momentum': {
            'filter': lambda t: 'momentum' in t.tags,
            'reports': {
                'equity_curve': {'include': ['gross']},
                'metrics': {'include': ['sharpe_gross']},
                'drawdown_table': {'top_n': 5}
            }
        },

        # Group for carry‑tagged trades
        'carry': {
            'filter': lambda t: 'carry' in t.tags,
            'reports': {
                'equity_curve': True,
                'trade_summary': True
            }
        },

        # Per‑underlying breakdown – can be wrapped in a group if filtering is needed
        'by_underlying': {
            'include': {
                'equity_curve': {'include': ['gross']},
                'metrics': {'include': ['sharpe_gross']}
            }
        }
    },
    'output': {'format': 'excel', 'path': '/results/backtest.xlsx'}
}

# With the spec above, Excel sheet names would include:
#   equity_curve
#   momentum_equity_curve
#   momentum_metrics
#   momentum_drawdown_table
#   carry_equity_curve
#   carry_trade_summary
#   HSI_equity_curve
#   HSI_metrics
#   SPX_equity_curve
#   … etc.
```

**Example – filtered per‑underlying breakdown:**
```python
# Momentum‑only per‑underlying breakdown
'momentum_by_underlying': {
    'filter': lambda t: 'momentum' in t.tags,
    'reports': {
        'by_underlying': {
            'include': {
                'equity_curve': {'include': ['gross']},
                'metrics': {'include': ['sharpe_gross', 'max_drawdown_net']}
            }
        }
    }
}
```
**Initialisation example (standard workflow):**
```python
spec = {
    'reports': {
        'equity_curve': True,
        'by_underlying': True,
        'trade_summary': True,
        'hit_ratio': {'timeframe': 'yearly'},
        'drawdown_table': {'top_n': 10},
        'metrics': True
    },
    'output': {'format': 'excel', 'path': '/results/backtest.xlsx'}
}
summary = Summary(spec)
```
**Primary method:**

- `generate(trade_history: list[Trade], cost_model: CostModel, fx_rates: dict[str, pd.Series] | None = None) -> dict | None`
  Applies the cost model (for standard reports that need it), handles missing data, and produces the requested reports.  
  `fx_rates` is an optional dictionary mapping currency pairs (e.g., `'USDJPY'`) to a `pd.Series` of daily spot rates.  
  - **If `fx_rates` is provided**, local‑currency P&L is converted to the base currency (USD) and portfolio‑level metrics are computed.
  - **If `fx_rates` is omitted**, no cross‑currency aggregation is performed. Reports that require a single‑currency portfolio are either omitted or broken down by underlying/currency.

**Processing steps (inside `generate`):**

  1. **Local‑currency gross P&L (per leg):** Read `daily_total_pnl` from every leg. `NaN` values are preserved.

  2. **Aggregation and missing‑data handling:**  
     - `'any'` (default): Leg `NaN`s are treated as zero; the true economic P&L is preserved.
     - `'all'`: Days with any leg `NaN` are presented as `NaN` in output, but the cumulative curve remains economically correct.
     - `'per_leg'`: Unaggregated per‑leg series are used directly.

  3. **Cost application:** The `CostModel.compute_costs()` returns a dictionary mapping `leg_id` to a per‑leg daily cost series, each in the leg’s local currency. For each leg in the trade history, the `Summary` uses the leg’s `leg_id` to look up the corresponding cost series and computes its local net P&L as `net_local = gross_local - cost_local` (with missing cost treated as zero).

  4. **Base‑currency conversion (if `fx_rates` provided):**  
     If `fx_rates` is not `None`, for each leg whose `currency` differs from the base currency (USD):
       - The cumulative local net P&L series (i.e., local gross P&L minus the local cost series produced by the `CostModel`) is taken.
       - This cumulative net series is multiplied by the corresponding spot FX series (e.g., `USDJPY` for JPY‑denominated legs).
       - The daily USD net P&L is obtained by differencing the resulting cumulative USD series.
       - Any **component PnL** series (e.g., `delta_pnl`, `gamma_pnl`) are also converted to USD using the same cumulative method.
       - **Risk measures** (e.g., `delta_ts`, `gamma_ts`) are converted to USD by multiplying each day’s value by the day’s spot rate, producing dollar greeks that are directly comparable across all legs.
     The USD net P&L series, converted component series, and dollar‑greek series from all legs are then aggregated to form the single portfolio‑level equity curve, attribution tables, and risk summaries.  
     The FX spot rate used for each conversion is included in the equity curve DataFrame (as an additional column, e.g., `fx_USDJPY`), so that the user can distinguish FX‑driven P&L from underlying‑driven P&L.

     If `fx_rates` is `None`, no cross‑currency aggregation is performed. Local‑currency series are kept separate, and any report that inherently requires a single‑currency portfolio (e.g., `'equity_curve'`, `'metrics'`, `'drawdown_table'`) will either be omitted or produced in a per‑underlying/currency breakdown.

  5. **Report generation:**  
     - Standard reports are built using predefined logic. Filters from the root `reports` dict and from any containing groups are applied. Reports do not have their own `'filter'`; all filtering is handled by the root and group levels. The data is then aggregated according to the report’s `include` spec.

- All of this runs on the **already‑saved `trade_history`** — no backtest re‑run is needed. You can change any part of the spec and call `generate()` again immediately.

**Extending the Summary module:**

- Add new standard reports by writing a new method on the `Summary` class. For raw data extraction, extend the `DataExtractor` class instead (Section 3.11).
- The `Summary` class is a plain Python object; you can subclass it or compose it with your own analysis functions.

### 3.11 Data Extractor

The `DataExtractor` class provides a flexible, lightweight pipeline for extracting raw data from the `trade_history`. It performs **no** aggregation, grouping, metric computation, or cost application. It simply returns the exact attributes you request, leaving all further processing to you.

**Extractor specification:**

The constructor takes no arguments. The primary method is:

- `extract(trade_history: list[Trade], spec: dict) -> dict`

The `spec` dictionary contains:

- `'granularity'`: `'trade'`, `'structure'`, or `'instrument'`.  
  Defines the unit of output.
- `'filter'` (optional): a **callable** that receives a `Trade` and returns `True`/`False`. If omitted, all trades are included.
- `'attributes'`: a list of **attribute names** to extract from each output unit. These can be:
  - Simple scalar fields of the unit: `'trade_id'`, `'structure_id'`, `'entry_date'`, `'exit_date'`, `'tags'`, `'gross_pnl'`, `'entry_price'`, etc.
  - **Parent attributes via dot‑notation** – when the granularity is `'instrument'`, attributes of the parent `Structure` or `Trade` are accessible using paths like `'structure.tags'`, `'structure.entry_date'`, `'trade.entry_date'`, `'trade.tags'`, etc. The special identifiers `'trade_id'` and `'structure_id'` are always available as shorthand for `'trade.trade_id'` and `'structure.structure_id'`.
  - Convenience derived fields: `'underlying'` (the underlying ticker derived from the instrument’s `params`), `'asset_class'`, `'strike'`, `'expiry'`, etc.
  - Time‑series fields: `'daily_total_pnl'`, `'delta_ts'`, `'gamma_ts'`, etc.
  - **Structure event logs** – at `'structure'` granularity, the derived attribute `'event_log_flat'` returns a DataFrame where each row is a single event. Columns include `structure_id`, `trade_id`, and all fields from the event dictionary (`event_type`, `date`, `unit_size_change`, `cost_exposures`, `cost_free`).

**Output format:**

The method returns a **dictionary** where each key is one of the requested attribute names and the value is:

- For a **scalar** attribute → a `pd.Series` indexed by the output unit identifier.
- For a **time‑series** attribute → a `pd.DataFrame` with dates as the row index and output unit identifiers as columns (aligned to the backtest’s full trading calendar, `NaN` where the unit wasn’t alive).

**Ordering guarantee:** The column headers in any time‑series DataFrame exactly match the index order of any scalar Series returned from the same call.

**Convenience inspection method:**

- `inspect(trade_history: list[Trade], unit_type: str, unit_id: str, cost_model: CostModel | None = None, fx_rates: dict[str, pd.Series] | None = None, start_date: str | None = None, end_date: str | None = None) -> pd.DataFrame`

Returns a date‑indexed DataFrame containing every available raw P&L, risk, component P&L, and pricing‑input time series for the specified unit.  
`unit_type` must be one of `'trade'`, `'structure'`, or `'instrument'`.  
`unit_id` is the unique identifier for that unit type:
  - For `'trade'`: the `trade_id`.
  - For `'structure'`: the `structure_id`.
  - For `'instrument'`: the `leg_id`.

`cost_model` and `fx_rates` are optional. They are only used to add derived columns (cumulative net P&L, USD‑converted series) and are not required for the raw data that `inspect()` returns. If omitted, only raw time‑series data from the leg is included.

This includes:

- `daily_total_pnl` (always)
- All component‑PnL lists (e.g., `delta_pnl`, `gamma_pnl`, `mtm_pnl`, `carry_pnl`) that were stored on the leg during the backtest, if P&L decomposition was configured.
- All risk‑measure time series (e.g., `delta_ts`, `gamma_ts`, `vega_ts`)
- All pricing‑input time series (e.g., `implied_vol`, `forward_price`, `rate`)

In addition, the DataFrame always contains **cumulative gross P&L** (`cum_gross`), computed from the leg’s `daily_total_pnl`.  
If a `cost_model` is supplied, it also includes **cumulative net P&L** (`cum_net`).  
If `fx_rates` is supplied and the leg’s currency is not USD:

  - The cumulative P&L columns (`cum_gross`, `cum_net`) are provided in USD as `cum_gross_usd` and `cum_net_usd`.
  - All **component PnL** columns (e.g., `delta_pnl_usd`, `gamma_pnl_usd`) are converted to USD using the same cumulative‑spot‑differencing method.
  - All **risk measures** (e.g., `delta_ts`, `gamma_ts`, `vega_ts`) are converted to USD by multiplying each day’s value by the day’s spot rate (since greeks are expressed in the leg’s local currency per unit, multiplying by spot gives the dollar‑equivalent sensitivity). The converted columns are named `delta_ts_usd`, `gamma_ts_usd`, etc.
  - The FX spot rate used for the conversion is included as a column (e.g., `fx_USDJPY`).

When `start_date` is specified, all cumulative columns are reset to zero at that date, so they represent the P&L accrued only within the window. The returned DataFrame is sliced to `[start_date, end_date]` (if provided).  
This method is purely a convenience wrapper around `extract()`; you can always reproduce its output manually.

**Examples:**

1. **“Trades entered in January 2025 – get entry/exit dates and gross P&L”**
  ```python
  'jan_trades': {
    'granularity': 'trade',
    'filter': lambda t: t.entry_date >= '2025-01-01' and t.entry_date <= '2025-01-31',
    'attributes': ['entry_date', 'exit_date', 'gross_pnl']
  }
  ```
2. **“Delta history for all legs of trades that started in January, with underlying and structure ID”**
  ```python
  'delta_jan': {
    'granularity': 'instrument',
    'filter': lambda t: t.entry_date >= '2025-01-01' and t.entry_date <= '2025-01-31',
    'attributes': ['delta_ts', 'underlying', 'structure_id']
  }
  ```
  Then you can aggregate:
  ```python
  delta_df = result['delta_jan']['delta_ts']
  # By underlying
  underly_map = result['delta_jan']['underlying']
  total_delta_by_underlying = delta_df.groupby(underly_map, axis=1).sum()
  # By structure
  struct_map = result['delta_jan']['structure_id']
  total_delta_per_structure = delta_df.groupby(struct_map, axis=1).sum()
  ```
3. **“All delta history aggregated to structure level (no filter)”**
  ```python
  'delta_struct_all': {
    'granularity': 'instrument',
    'attributes': ['delta_ts', 'structure_id']
  }
  ```
  Then:
  ```python
  delta_df = result['delta_struct_all']['delta_ts']
  struct_map = result['delta_struct_all']['structure_id']
  total_delta_per_structure = delta_df.groupby(struct_map, axis=1).sum()
  ```
**Example: investigating suspicious P&L around a specific date**

**Scenario:** You want to know exactly which trades contributed the most to the portfolio’s P&L in January 2025, and then drill into the largest positive or negative contributor to see what drove it (delta, vega, vol move, etc.).

**1. Identify trades that were active in January 2025 and compute their P&L over that window.**

Use `extract()` at the `'trade'` granularity to pull all trades with their entry/exit dates and gross P&L time series. Then filter to those that were alive in January and sum their daily P&L over that month.
```python
extractor = DataExtractor()
all_trades = extractor.extract(trade_history, {
    'granularity': 'trade',
    'attributes': ['trade_id', 'entry_date', 'exit_date', 'daily_total_pnl']
})
# Pull the time-series of daily P&L for each trade
pnl_df = all_trades['daily_total_pnl']               # dates x trade IDs
entries = all_trades['entry_date']                   # Series index = trade ID
exits  = all_trades['exit_date']                     # Series index = trade ID

# Restrict to trades that were alive in Jan 2025
jan_mask = (pd.to_datetime(entries) <= '2025-01-31') & (pd.to_datetime(exits) >= '2025-01-01')
jan_pnl = pnl_df.loc['2025-01-01':'2025-01-31', jan_mask].sum()   # total P&L per trade over Jan
jan_pnl = jan_pnl.sort_values(ascending=False)
# jan_pnl.index holds the trade IDs, jan_pnl.values the Jan P&L
```
**2. Get the leg IDs belonging to the biggest contributor.**

Pull instrument‑level data for that trade, so you know which legs to inspect.
```python
biggest_trade_id = jan_pnl.index[0]
legs_info = extractor.extract(trade_history, {
    'granularity': 'instrument',
    'filter': lambda t: t.trade_id == biggest_trade_id,
    'attributes': ['trade_id', 'structure_id', 'ticker', 'underlying', 'gross_pnl']
})
leg_ids = legs_info['trade_id'].index.tolist()
```
**3. Drill into each leg of that trade with `inspect()`.**
```python
cost_model = FixedCostModel(...)   # from Phase 1
fx_rates = price_provider.get_fx_series(['USDJPY', 'USDHKD'])  # example

for leg_id in leg_ids:
    leg_df = extractor.inspect(
        trade_history,
        unit_type='instrument',
        unit_id=leg_id,
        cost_model=cost_model,
        fx_rates=fx_rates,
        start_date='2025-01-01',
        end_date='2025-01-31'
    )
    print(f"=== Leg {leg_id} ===")
    print(leg_df)
```
This prints a DataFrame indexed by date for each leg, showing daily P&L, all risk measures (delta, gamma, vega, …), component P&L (if decomposition was configured), and any recorded pricing inputs (implied vol, forward price, etc.). You can immediately see what moved.

**4. For context, also compare the trade’s P&L against the overall portfolio and its underlying group.**
```python
# The overall and by-underlying comparison should use the same cost model and FX rates
# as the inspection for consistency. You can either reuse the Summary with those settings
# or aggregate the raw extractor data as shown below.

all_legs = extractor.extract(trade_history, {
    'granularity': 'instrument',
    'attributes': ['daily_total_pnl', 'underlying']
})
jan_leg_pnl = all_legs['daily_total_pnl'].loc['2025-01-01':'2025-01-31'].sum()
underlying_map = all_legs['underlying']
jan_pnl_by_underlying = jan_leg_pnl.groupby(underlying_map).sum()
print(jan_pnl_by_underlying)
```
No new functions are needed—`extract()` and `inspect()` cover the full workflow. This example can be adapted to any date range, any filter, and any level of granularity.

### 3.12 PnL Attribution (extensible breakdown)

The framework supports decomposing daily PnL into user‑specified risk factors (carry, mark‑to‑market, delta, vega, etc.) without altering the core backtester loop.

**AssetPnlCalculator interface:**
- An abstract class `AssetPnlCalculator` defines the contract for all asset‑specific decomposition logic:
  ```python
  class AssetPnlCalculator(ABC):
      @abstractmethod
      def compute_component_pnl(
          self,
          instrument: Instrument,
          prev_valuation_data: dict[str, float],
          current_valuation_data: dict[str, float],
          risk_measures: list[str]
      ) -> dict[str, float]:
          """
          Given yesterday’s and today’s building‑block data (e.g., greeks, curve‑specific prices),
          compute the daily component P&L for each requested measure.
          Returns a dict mapping the same keys to the P&L values.
          """
  ```
- Concrete implementations are provided for each asset class (e.g., `EquityOptionPnlCalculator`, `FXForwardPnlCalculator`). Each calculator knows the appropriate formulas (e.g., delta PnL = `delta(T-1) × dSpot`, carry = …).

**Integration with the backtester:**
- The `AssetClassConfig` contains an optional `pnl_calculator` field. When a strategy requires decomposition, the user supplies the appropriate calculator for that asset class.
- During the daily PnL step (step 1), the backtester:
  1. Fetches `valuation_data` from the pricer for the current date T and retrieves the stored T‑1 data from the Instrument.
  2. Calls `pnl_calculator.compute_component_pnl(instrument, prev_data, curr_data, risk_measures)`.
  3. Appends the returned values to the Instrument’s component PnL lists.
- This entirely decouples the backtester from the asset‑specific math, so new asset classes can be added with zero changes to the backtester loop.

**Extensibility:**
- To add a new decomposition (e.g., a new risk factor), you only need to update the calculator for that asset class and extend the `risk_measures` list in the configuration. The backtester and the Instrument’s storage remain unchanged.
- For asset classes with no decomposition (Phase 1 equities), the `pnl_calculator` is `None` and no extra work is performed.

### 3.13 Cost Model (transaction cost handling)

Transaction costs are fully decoupled from the backtester’s daily P&L loop.  
The backtester records cost‑relevant events at the **structure** level: each `StrategyStructure` logs events (open, partial add, partial/full unwind, roll) together with the structure’s per‑unit risk exposure at that moment.  
A separate `CostModel` object converts those structure‑level events into a cost time series during the summary phase, delegating asset‑specific cost arithmetic to a per‑asset‑class `BaseCostCalculator`.

**Key design properties:**
- **Costs can be changed without re‑running the backtest.**  
  The backtest produces gross P&L and an event log per structure. Changing cost assumptions only requires re‑computing the cost series from those logs.
- **Cost granularity matches the structure.**  
  Costs are incurred at the structure level – i.e., at trade entry, rolls, and each unwind event. Partial unwinds incur proportional costs.
- **Per‑unit metrics × unit size change = transacted exposure.**  
  The event log stores **per‑unit** risk metrics (e.g., `notional_per_unit`, `vega_per_contract`) alongside `unit_size_change`. The cost calculator multiplies them to obtain the transacted exposure, ensuring partial unwinds are charged correctly (50% unwind charges 50% of the exposure).  
- **Cost calculators are asset‑class‑specific.**  
  For options, cost may be a function of total vega; for equities/futures, a function of notional; for interest rate swaps, a function of dv01. Each calculator knows the formula for its asset class.
- **Extensible from fixed to dynamic models.**  
  Phase 1 uses a simple fixed‑bps model via `EquityCostCalculator`.  
  Future phases can implement cost as a function of time, size, and market conditions (including optional `DataFeed` access), without any changes to the backtester or trade classes.

**`BaseCostCalculator` (abstract):**

```python
class BaseCostCalculator(ABC):
    @abstractmethod
    def compute_cost(self, leg_id: str, event: dict,
                     data_feed: DataFeed | None = None) -> float:
        """
        Return the cost in the leg's local currency for a single event.

        The event dict contains:
          - "date": str
          - "event_type": str
          - "unit_size_change": float
          - "cost_exposures": dict[str, dict]  # leg_id -> per-unit metrics
          - "cost_free": bool
          - "cost_leg_id": str  (retained for readability)

        The calculator:
          1. Reads event["cost_exposures"][leg_id] to get the per-unit metrics.
          2. Multiplies each per-unit metric by event["unit_size_change"]
             to obtain the transacted exposure.
          3. Applies the asset-class cost formula (e.g., bps on notional).

        The event dict is READ-ONLY; calculators must not modify it.

        Cost-free events (event["cost_free"] == True) are skipped by the
        CostModel before this method is ever called; the calculator does
        not need to handle that case.

        data_feed is optional and may be None for simple fixed models.
        """
```

**`CostModel`:**

```python
class CostModel:
    def __init__(self, calculators: dict[str, BaseCostCalculator],
                 data_feed: DataFeed | None = None):
        """
        calculators: mapping from asset_class (str) to BaseCostCalculator
        data_feed: optional DataFeed for calculators that need market data
        """

    def compute_costs(self, trades: list[Trade]) -> dict[str, pd.Series]:
        """
        Walk every structure in every trade.
        For each structure, walk its event log.
        For each cost‑bearing event (cost_free == False):
          - Find the leg's asset_class (via the structure's leg).
          - Look up the appropriate BaseCostCalculator.
          - For each cost‑bearing leg_id in event["cost_exposures"]:
              Call calculator.compute_cost(leg_id, event, data_feed).
          - Aggregate costs by date into per‑leg daily pd.Series.

        Returns:
            A dictionary mapping `leg_id` (str) to a `pd.Series` of daily
            costs in the leg’s local currency.
            Legs that never incur a cost are omitted from the returned dict.
        """
```

**Phase 1 default:**

`EquityCostCalculator` (replaces the old `FixedCostModel`):
```python
class EquityCostCalculator(BaseCostCalculator):
    """Charges a constant bps fee on transacted notional."""
    def __init__(self, bps: float):
        self._bps = bps

    def compute_cost(self, leg_id: str, event: dict,
                     data_feed: DataFeed | None = None) -> float:
        per_unit = event["cost_exposures"][leg_id]
        notional_per_unit = per_unit["notional_per_unit"]
        transacted_notional = notional_per_unit * event["unit_size_change"]
        return transacted_notional * self._bps / 10000.0
```

Usage:
```python
calculators = {"equity": EquityCostCalculator(bps=2.0)}
cost_model = CostModel(calculators)
costs = cost_model.compute_costs(trade_history)
```

This replaces the old `FixedCostModel`; no functionality is lost. To add a new asset class (e.g., equity options), write an `EquityOptionCostCalculator` implementing `compute_cost` with vega‑based pricing, and register it under `"equity_option"` in the calculators dict. No core backtester, Trade, StrategyStructure, Summary, or CostModel code changes.

### 3.14 Persistence of Backtest Results

- After the backtest completes, the entire `trade_history` list (together with any `CostModel` and `Summary` outputs) can be **serialized to disk** (e.g., via `pickle`, `joblib`, or custom JSON/Parquet writers).
- This saved state is completely independent of the backtester, pricers, and data providers. It contains:
  - Every trade, structure, and leg with full daily P&L, risk, and component breakdowns.
  - All cost event logs.
  - All user‑defined tags and metadata.
- Once reloaded, a new `Summary` instance (with a different spec, filters, or FX rates) can be applied to the saved `trade_history` without re‑running the backtest.
- This enables a workflow where a heavy backtest is executed once, and subsequent analysis, filtering, and reporting are performed interactively or at a later time, without duplicating computation.

### 3.15 Architecture summary (informal)
```markdown
Backtester
├── active_trades: list[Trade]
└── trade_history: list[Trade]

Trade
├── active_structures: list[StrategyStructure]
└── structure_history: list[StrategyStructure]

StrategyStructure
├── legs: list[Instrument]
└── event_log: list[CostEvent]

Instrument
└── per‑leg PnL, risk
```

## 4. Validation framework (to be built after core backtester)

### 4.1 Walk‑forward cross‑validation

- Split the full historical period into multiple folds, each with a training window and a subsequent validation window.
- Use a `FoldGenerator` that:
  - Takes start_date, end_date, train_length (e.g., 2 years), validation_length (e.g., 6 months), step_size (e.g., 6 months), purge_length (equal to the maximum lookback window used by the strategy, e.g., 50 days), embargo_length (1 day to simulate realistic execution delay).
  - Yields (train_start, train_end, val_start, val_end) for each fold.
- Purging: Ensure that no data from the validation period leaks into the training set via lookback. So train_end must be at least `purge_length` before val_start.
- Embargo: Add a gap of `embargo_length` after train_end before val_start to avoid trading on information that wasn’t available.

- **Burn‑in period (optional future extension):**  
  When open positions are carried from the training window into the validation window, the first few days of validation may be distorted by legacy trades that were entered on training data. A `burn_in_days` parameter discards the P&L from the earliest part of the validation window, allowing those legacy positions to be closed by their own exit signals (or to roll off naturally) while new OOS‑driven positions are established.  
  - For **scaling‑in strategies**, the burn‑in lets the portfolio reach its intended size.
  - For **signal‑in/signal‑out strategies**, the burn‑in flushes out positions that originated on training data, leaving a clean state where all open trades reflect OOS decisions.
  Implementation is runner‑level only; the `Backtester` already supports initialisation from a pre‑existing state (see Section 3.9).

- **Combinatorial Purged Cross‑Validation (CPCV) – future extension:**  
  - For each test window, the `FoldGenerator` can produce multiple training windows of different lengths (e.g., 2, 3, and 4 years) that all end at the test start date. Running the backtester on each combination yields an **ensemble of out‑of‑sample paths** for the same test period.  
  - Aggregating these paths provides a **distribution of performance metrics** (Sharpe, maximum drawdown, etc.), which is especially valuable for non‑smooth statistics like max drawdown. This enables risk‑management insights such as worst‑case and median drawdown without introducing additional overfitting bias.  
  - Because the `Backtester` is fully parameterised and the `FoldGenerator` can trivially vary training‑window lengths, CPCV requires no changes to any core component—it is purely an extension of the walk‑forward runner.

### 4.2 Nested parameter selection (within each training window)

- **Rule‑based strategies** (e.g., SMA crossover): parameters are fixed thresholds that do not change based on the data. For each fold, the backtester is run on the full training window with each parameter combination, and the combination that yields the highest value of the selected performance metric (typically Sharpe) **on that same training window** is selected. Then the strategy is tested on the validation window. No inner train/validation split is needed.
- **Model‑based strategies** (e.g., machine learning models): parameters include both hyper‑parameters and learned coefficients that depend on the training data. To prevent selection bias, the training window is further split into **sub‑training** (e.g., first 80%) and **sub‑validation** (last 20%).
  - For each parameter combination, the model is fitted on the sub‑training set and then evaluated on the sub‑validation set using the selected performance metric.
  - The parameter combination with the highest sub‑validation metric value is selected.
  - The selected model is retrained on the full training window (sub‑training + sub‑validation) and then evaluated on the true validation window.
- In both cases, the backtester is run on the training window first to **warm up the signal** (so that any necessary lookback state is available) before continuing into the validation period. This ensures seamless transition and prevents look‑ahead.
- After all folds are complete, the out‑of‑sample `trade_history` lists from each validation window are concatenated into a single list and passed to the `Summary` module to produce the aggregated OOS net P&L series.

### 4.3 Multiple testing correction across strategies

- Over time, we will test many distinct strategies (different asset classes, signal ideas).
- Each strategy will produce an **aggregated out‑of‑sample `trade_history`** (the concatenated list of `Trade` objects from all walk‑forward folds). This raw trade list is the durable output; all derived series are produced from it.
- To decide if the best‑performing strategy is genuine, we use the **Deflated Sharpe Ratio (DSR)** (or other multiple‑testing corrections that account for strategy correlations).
- **Strategy Graveyard:** maintain a log per independent trading universe (e.g., “US Equities”, “FX”). Each entry contains:
  - **Concatenated OOS `trade_history`:** the raw list of `Trade` objects from the out‑of‑sample windows of the walk‑forward. This is serialized to disk and is the durable record of what the strategy traded.
  - **Reproducibility configuration:** a complete description of the environment used to produce the `trade_history`, sufficient to instantiate a functionally identical backtester for extension runs. This includes:
    - The signal definition (type and parameters).
    - The `pricer_map` and `asset_class_configs` used.
    - The `DataFeed` and typed data‑provider configurations, including:
      - Data source(s) (e.g., `'bloomberg'`, `'refinitiv'`, `'csv'`).
      - Observation time (e.g., `'ny_close'`).
      - **Point‑in‑time (PIT) vintage** – the specific vintage date of the data used (e.g., `'2024-06-15'`). If PIT data was not available and the final revised series was used as a proxy, this is explicitly recorded as `"final_revised"`, and the resulting look‑ahead bias is accepted for extension comparisons.
    - The `CostModel` definition (or the exact cost parameters, so the same net P&L can be reproduced).
    - Any random seeds or other non‑signal state necessary for deterministic replay.
    Signal internal state (e.g., a moving average window, an “in‑position” flag) is **not** serialized separately; it is reconstructed by the signal from the initial `PortfolioState` and market data at the start of the extension run.
  - **Optional CPCV `trade_history` set:** if Combinatorial Purged Cross‑Validation was performed, the additional OOS trade histories from alternative training‑window lengths are also stored. CPCV paths cannot be generated later without re‑running the backtest with different training windows, so they must be saved at the time of the CPCV run. They are not required for DSR and may be discarded when no longer needed for risk analysis.
  - **Classification metadata:**
    - Strategy name, parameters, tags, date tested.
    - `asset_class` / `universe` label (e.g., `'US Equities'`, `'FX'`). For a multi‑asset strategy, this is a list.
    - `underlyings`: list of tickers or identifiers traded by the strategy. If the list contains more than one entry, the strategy is a basket.
    - `is_integrated`: boolean indicating whether the strategy’s legs are economically inseparable (e.g., a pair trade). If `True`, the combined OOS P&L is the atomic unit for DSR testing and must not be decomposed.
  - No pre‑computed performance metrics (Sharpe, drawdown, per‑underlying series) are stored in the graveyard. All of these are produced on demand by the `Summary` from the saved `trade_history` (or CPCV trade histories, if available).

- **Basket vs. single‑ticker strategies:**  
  - A strategy that trades a single instrument (e.g., TSLA) is assigned to the graveyard of its underlying’s asset class.
  - A strategy that applies the **same independent signal** to multiple underlyings (e.g., a timing signal that triggers separately on HSI and TPX) may be decomposed: each underlying’s OOS P&L contribution can be tested against the corresponding single‑asset graveyard.
  - A strategy whose legs are **economically inseparable** (e.g., a pair trade that longs TPX and shorts HSI; a call‑spread structure) must be treated as a single, atomic unit. Its combined OOS P&L is tested against a graveyard that reflects the strategy’s integrated nature (e.g., a “multi‑asset integrated” graveyard, or a dedicated “pair trades” graveyard). **It must not be decomposed**—the short leg may be designed to lose money, and testing it in isolation would produce meaningless statistics.
  The classification metadata includes an `is_integrated` flag to control whether per‑underlying decomposition is permitted.

- **DSR budgeting across asset classes:**  
  Each independent trading universe (e.g., “US Equities”, “FX”) maintains its own graveyard of stored `trade_history` records. When the DSR is computed for a graveyard, the required OOS net P&L series are produced **dynamically** by the `Summary` from the saved `trade_history` (and reproducibility configuration) of every strategy that belongs to that universe.  
  For a strategy that trades only US equities, its full OOS series is included directly. For a multi‑asset strategy with independent legs, the `Summary` can filter its stored `trade_history` by underlying or tag to extract the contribution to a specific asset class (e.g., the equity portion for the US Equities graveyard, the FX portion for the FX graveyard). This extraction is done on‑the‑fly; no pre‑computed per‑underlying series need to be stored.  
  The DSR then uses the correlation matrix of the assembled series to estimate the distribution of the maximum Sharpe, automatically penalising strategies that are highly correlated. Integrated strategies (e.g., pair trades) are **not** decomposed; their combined OOS series is tested as a single unit in the appropriate multi‑asset graveyard.

- **Risk‑management use of CPCV drawdowns:**  
  The pre‑deployment CPCV analysis produces a distribution of historical drawdowns (worst‑case, median, 95th‑percentile, etc.) across varied training windows. These metrics can be stored in the graveyard as a static reference. During live trading, if the actual drawdown approaches or exceeds, say, 80% of the historical worst‑case drawdown, it serves as an early warning that the strategy may be degrading.  
  **Contrast with in‑sample drawdown:** This is fundamentally different from the common but statistically invalid practice of filtering strategies by their *in‑sample* drawdown, which is always optimistic because it is measured on the same data used for optimisation. CPCV drawdowns are computed on truly unseen out‑of‑sample paths, making them honest estimates of the strategy’s real‑world risk.

- To keep all return series aligned to the same date range, the OOS `trade_history` of **every strategy in the graveyard is re‑extended up to the current date** whenever a new strategy is added. Using the stored **reproducibility configuration**, a backtester is instantiated with the same signal, pricers, data providers, and cost model as the original run, and the walk‑forward is continued over the new out‑of‑sample period. The `Summary` then produces the aligned net P&L series from the extended trade lists, and the full set is used to compute the DSR (or other correlation‑adjusted statistics).
- DSR threshold: if DSR > 0.95, consider the strategy significant. If not, do not trade it.
- Reset the graveyard only when moving to a completely independent asset class with no overlap in return history.
- In Phase 3, the graveyard will be a simple file‑based log (JSON/Parquet). In later phases, it will migrate to a **SQL database** for efficient storage and querying of many strategies.

### 4.4 Randomisation tests for skill (future extension)

- **Trade‑date randomisation test (placebo test) – timing strategies:**  
  For strategies whose edge lies in *when* to enter and exit a given instrument, a placebo test checks whether the performance is simply due to being exposed to the underlying’s beta over the strategy’s typical holding periods.
  - Extract the realised trades (entry date, exit date, holding period, P&L) from the OOS `trade_history`.
  - Randomly reassign each trade’s entry date within the OOS timeline, preserving the holding period and any overlap restrictions.
  - A dedicated **signal‑generator module** (built in Phase 2+) translates the reshuffled dates into a `TargetTrade` sequence and feeds the `Backtester`. For each of many simulations (e.g., 1,000), the `Summary` computes the chosen performance metric (typically Sharpe).
  - Compare the actual strategy’s metric to the resulting null distribution. A significantly higher actual metric indicates genuine timing skill beyond random entry.

- **Cross‑sectional bootstrap test (random asset selection) – ticker‑picking strategies:**  
  For strategies that periodically select a subset of instruments from a universe (e.g., monthly long/short baskets based on a factor), the corresponding test randomises *which* tickers are chosen, while preserving the selection frequency and position‑sizing rules.
  - From the OOS `trade_history`, identify every rebalancing date and the set of tickers that were actually selected.
  - For each simulation, at each rebalancing date, randomly draw the same number of tickers from the universe that was available at that time.
  - The same **signal‑generator module** translates the randomised selections into `TargetTrade` orders, the `Backtester` runs, and the `Summary` produces the metric to build the null distribution.
  - If the actual strategy’s Sharpe lies in the upper tail of the distribution (e.g., above the 95th percentile), the strategy demonstrates genuine selection alpha beyond what random stock‑picking would achieve.

Both tests are purely runner‑level: they use the existing `Backtester`, `Summary`, and trade data. The only new component is a **dummy‑signal generator** that converts permuted trade schedules or randomised tickers into `TargetTrade` orders—a thin, reusable module planned for Phase 2+.

### 4.5 Deployment

- Once a strategy passes DSR (and, where applicable, the appropriate randomisation test), we deploy it with parameters re‑estimated on all available data (the entire historical dataset, using the same nested selection procedure). This provides the best estimate of parameters for live trading.
- Live performance should be monitored by running the backtester in incremental mode (see Section 3.9, “Future extension – incremental backtesting”), producing a theoretical P&L each day that can be compared against actual broker‑filled trades to track slippage and strategy drift.
- The incremental theoretical P&L produced by the backtester each day is the **cleanest measure of the strategy’s ongoing performance**. Unlike actual realised P&L, which can be affected by fluctuating AUM, capital allocations, and execution timing, the theoretical OOS series reflects exactly what the strategy’s logic would produce under ideal, unconfounded conditions. This makes it the primary diagnostic for detecting strategy drift or degradation, independent of operational factors.
- Periodic refitting (e.g., monthly) follows the same walk‑forward logic, extending the training window as new data arrives.

## 5. Implementation plan (Phases)

### Phase 1: Core skeleton (minimal end‑to‑end)
Build the following in order, each tested before moving on:

1. **Instrument** – pure dataclass with `params`, P&L lists (`daily_total_pnl`, `current_price`, `current_size`, `entry_price`), valuation‑data and component‑PnL lists (initially empty), and `pricing_inputs`.
2. **DataFeed and CsvBackend** – the `DataFeed` class with `get_value()` and `get_series()` methods, and a `CsvBackend` that reads a CSV of daily adjusted close prices. Also includes a thin `EquityPriceProvider` that wraps the `DataFeed` and exposes `get_price(ticker, date)`. The backtester and pricers depend only on the `DataFeed` interface; the backend is swappable.
3. **EquityPricer** – implements `price()`, `valuation_data()` (empty for equities), `resolve_instrument()` (pass‑through for equities), and `pricing_inputs()` (returns an empty dict).
4. **StrategyStructure** – a standalone class with `legs` (list of `Instrument`, always one leg in Phase 1), an event log for cost, and lifecycle methods `open(date)`, `unwind(date, fraction=1.0)`, and `roll(new_structure, date)` (stubbed – raises `NotImplementedError` in Phase 1). Building this as a real class from day one avoids any refactoring of `Trade`, the backtester, or signals when multi‑leg support is added later.
5. **Trade** – with `active_structures` / `structure_history`, lifecycle methods (`add_structure`, `unwind_structure`), tags, and cost‑event recording. In Phase 1 every trade contains exactly one structure with one leg. `roll_structure` may be implemented as a stub; it is not exercised by the SMA example.
6. **CostModel** – `FixedCostModel` that charges a constant bps fee on notional, applied at each structure event. Returns a dictionary of **per‑leg daily cost series** (in the leg’s local currency), matching the `Summary`’s expected interface (Section 3.13).
7. **BaseSignal** and **SMACrossoverSignal** – signal returns `TargetTrade` dictionaries with `NEW` / `UNWIND` actions; one‑day lag handled internally.
8. **Backtester** – full daily loop with P&L computation, instrument resolution, data‑availability checks, and order execution (`NEW` and `UNWIND`). `ROLL` handling can be stubbed; it is not required for the SMA example.
9. **Summary** – accepts `SummarySpec`, produces standard reports (equity curve, trade summary, metrics, hit ratio, drawdown table), and calls `CostModel.compute_costs()`.
10. **Example script** – `examples/sma_crossover_example.py` that:
    - Loads a CSV of SPY daily data (date, close) from a local file.
    - Creates a `DataFeed` with a `CsvBackend`, an `EquityPriceProvider`, `EquityPricer`, `FixedCostModel`, `SMACrossoverSignal`, `Backtester`, and `Summary`.
    - Runs the backtest from 2020-01-01 to 2022-12-31.
    - Prints the equity curve and standard metrics.
11. **Unit tests** – for Instrument, MarketData, Trade, and CostModel using pytest. StrategyStructure tests are covered by Trade tests until it becomes a standalone class.

### Phase 2: Validation
1. **CalendarProvider** (§3.5): Implement with CSV holiday files, union/intersection logic, and core methods (`trading_days`, `is_trading_day`, `next_trading_day`). Replace `BacktestConfig.calendar_ticker` with a CalendarProvider instance.
2. **OrderGenerator** (§3.8): Build the rule‑chain infrastructure. Implement **CalendarValidationRule** as the first `OrderRule`, using CalendarProvider to reject orders on holidays. Migrate any existing scaling/hedging logic into additional rules as needed.
3. **Backtester pipeline update:** Modify the daily loop to use the new signal → OrderGenerator → execution pipeline (§3.9).
4. Implement `FoldGenerator` with purge/embargo.
5. Implement nested parameter selection: walk‑forward loop that, per fold, does grid search using a sub‑training/sub‑validation split within the train window, then evaluates best params on validation.
6. Extend Summary to aggregate out‑of‑sample trades across folds.

### Phase 3: Statistical rigor
1. Implement Deflated Sharpe Ratio calculation.
2. Build a simple Strategy Graveyard (JSON file).
3. Add a top‑level script that compares multiple strategies and reports DSR.

## 6. Technology stack

- Python 3.12
- pandas, numpy, matplotlib, pyyaml, pytest
- All code will be written in a modular, docstring‑documented style.

## 7. Important conventions

- **Signal lag:** Signal output is always based on data up to T‑1, and orders are executed at T close. The signal itself handles the lag internally; the backtester never delays orders.
- **Transaction costs:** Cost events are recorded on `StrategyStructure` objects at every lifecycle event (open, partial add, partial unwind, roll, full close). The `CostModel` converts those events into a daily cost series during the summary phase. Gross and net P&L are always separate.
- **Instrument parameters:** All instrument‑specific fields beyond `ticker`, `asset_class`, `multiplier`, `currency`, and `tags` are stored in the `params` dictionary. The backtester never inspects `params`; only the pricer does.
- **Instrument resolution:** The leg dictionary in a `TargetTrade` may omit instrument‑specific parameters (e.g., strike, maturity). The pricer’s `resolve_instrument()` method fills in any missing fields at execution time.
- **P&L is always return‑centric:** The Instrument stores daily P&L changes, not cumulative balances. Cumulative P&L, realized/unrealized splits, and other derived metrics are computed on‑the‑fly by the Summary.
- **Cost and FX are post‑processing:** The backtester never computes costs or converts currencies. Both are handled externally by the `CostModel` and the Summary (or the user), allowing assumptions to be changed without re‑running the simulation.
- **Missing data:** Data providers forward‑fill short gaps (≤ configurable limit). For longer gaps, the pricer returns `None`, the backtester records `NaN` in the leg’s P&L, but `current_price` is not updated, preserving cumulative P&L integrity.
- **T‑1 greeks for P&L attribution:** Greeks‑based P&L decomposition always uses T‑1 greeks to avoid look‑ahead bias.
- **No pre‑defined instrument universe:** The backtester does not know which instruments will be traded ahead of time. Instruments are created dynamically by the signal.
- **No partial adds for scaling in:** Strategy‑driven scaling in/out uses multiple whole structures. Partial adds and unwinds are reserved for risk‑management adjustments (e.g., delta hedging).
- **Tags are analytical, not operational:** Tags on trades, structures, and instruments are for post‑backtest filtering and grouping. They are never used by the backtester or cost model to make execution decisions.
- **Prices (Phase 1):** All prices are assumed to be dividend‑adjusted close prices, with splits and dividends already handled in the CSV. This simplification will be revisited if the framework later incorporates margin modelling, intraday execution, or cash‑flow‑aware testing. Date formats are always `YYYY-MM-DD`.
- **Data access boundaries:** The `DataFeed` is for market data only. Validation, execution, and operational data are accessed through their own dedicated interfaces, even when they share the same physical database.
- **Margin and cash flow (Phase 1 scope):** Margin calculations, funding costs, borrow fees, and cash‑flow modelling are not part of the core research framework. They belong to the **Risk & Margin** pillar described in Section 9.

## 8. Data Infrastructure Evolution

### 8.1 The DataFeed Abstraction (current state and future)

The framework uses a **DataFeed** class from Phase 1—a single, concrete class that sits between the research engine and any physical storage. Internally, it delegates to a swappable **backend** object. The initial backend is a `CsvBackend` that reads daily adjusted close prices from CSV files.
```python
class DataFeed:
    def __init__(self, backend):
        self._backend = backend

    def get_value(self, dataset: str, date: str, ticker: str = None, **params) -> float:
        return self._backend.get_value(dataset, date, ticker, **params)

    def get_series(self, dataset: str, start: str, end: str, ticker: str = None, **params) -> pd.Series:
        return self._backend.get_series(dataset, start, end, ticker, **params)
```
**Key features:**
- `dataset` is a logical name (e.g., `eod_prices`, `spx_vol_surface`, `trump_likes_24h`).
- The backend protocol requires only `get_value` and `get_series`; any object implementing those can serve as a backend.
- The `DataFeed` is the **only** piece of code that knows whether data lives in a CSV, a SQLite database, a PostgreSQL cluster, or a Bloomberg session.
- It can be configured to select between multiple sources (`source='bloomberg'` vs `'refinitiv'`) and observation times (`observation_time='ny_close'`), enabling point‑in‑time backtests and vendor‑robustness checks.
- New methods (e.g., for point‑in‑time data) can be added to the `DataFeed` class without affecting existing consumers.

In Phase 2, an `SqlBackend` will be written, and the system will switch from CSV to SQL by changing a single constructor argument—no backtester, pricer, or signal code will change.

### 8.2 Typed Market Data Providers, Signals, and Multi‑Source Data

**Typed providers for pricers:**
Complex instruments need more than raw numbers—they need volatility surface interpolation, rate curve bootstrapping, forward curve construction, etc. These tasks are handled by typed providers that wrap the `DataFeed`.

| Provider Interface       | Purpose                                      | Example Usage                              |
|--------------------------|----------------------------------------------|--------------------------------------------|
| `EquityPriceProvider`    | Underlying asset prices (equities, ETFs)     | `get_price(ticker, date)`                  |
| `RateCurveProvider`      | Interest rate curves (single‑ or multi‑curve)| `get_discount_factor(ccy, date, tenor)`    |
| `VolSurfaceProvider`     | Volatility surfaces (equity, FX)             | `get_atm_vol(ticker, date, tenor)`         |
| `ForwardCurveProvider`   | Forward curves (equity dividends, FX points) | `get_forward(ticker, date, expiry)`        |
| `CorporateActionProvider`| Splits, dividends, symbol changes            | `get_ex_dividend_date(ticker, date)`       |

Each typed provider uses the `DataFeed` internally to fetch raw market quotes, then applies its specific financial model. Pricers are initialised with exactly the providers they need:
```python
option_pricer = EquityOptionPricer(vol_provider, rate_provider, equity_price_provider, dividend_provider)
```
*(The `dividend_provider` is a placeholder for a future dividend‑yield or projected‑dividend data provider; it is not required for Phase 1.)*

**Shared instances & caching:**
Typed providers are intended to be shared across all pricers. They may maintain internal caches keyed by date and instrument, so that repeated requests return instantly. During walk‑forward validation, a single set of provider instances is reused across all folds.

**Inheritance for similar providers:**
Where multiple asset classes share fundamentally similar data types (e.g., volatility surfaces for equities and FX), a single abstract base class (`VolSurfaceProvider`) provides common interpolation, caching, and interface logic. Concrete subclasses specialise only the data‑parsing and quote‑conversion steps.

**File organisation:**
The abstract base class lives in its own module (e.g., `vol_surface_provider.py`). Each concrete provider is in a separate file, keeping implementations independent, easy to test, and following the one‑provider‑per‑file convention.

**Signals and alternative data:**
Signals may require data that does not fit into standard market‑data categories—sentiment indicators, macro statistics, alternative data. They access this data directly through the `DataFeed`, without going through typed providers:
```python
likes = data_feed.get_value("trump_likes_24h", date="2026-06-01")
```
This gives signals maximum flexibility while still insulating them from storage mechanics.

**Multi‑source data and observation times:**
When the `SQLDataFeed` is in use, the database schema allows multiple records for the same instrument, date, and dataset, differentiated by:
- `source` (e.g., `'bloomberg'`, `'refinitiv'`) – the vendor or data origin.
- `observation_time` (e.g., `'asia_close'`, `'ny_close'`) – the specific cut at which the data was observed.

The `DataFeed` is configured with a default source and preferred observation time. For robustness testing, the entire backtest can be re‑run with a different configuration without code changes:
```yaml
data_feed:
  type: sql
  source: bloomberg           # default vendor
  observation_time: ny_close  # use New York close prices
```
```bash
python run_backtest.py --config data_feed.source=refinitiv
```
```bash
python run_backtest.py --config data_feed.observation_time=asia_close
```
### 8.3 Scope of the DataFeed (market data only)

The `DataFeed` interface is dedicated to **market and alternative data** consumed by the research engine—prices, volatility surfaces, rate curves, fundamentals, and any other inputs required for signal generation and instrument pricing.

Other data types in the platform have their own dedicated interfaces and storage, even if they eventually reside in the same SQL database:

| Data type | Examples | Interface / storage |
|-----------|----------|---------------------|
| **Market data** | Prices, vol surfaces, rate curves, alternative data | `DataFeed` (this section) |
| **Validation data** | Strategy graveyard, CPCV results, reproducibility configurations | `GraveyardStore` (see Section 4.3) |
| **Execution data** | OMS orders, fills, slippage reports | Execution pillar (see Section 9) – consumed via `TargetTrade` return channel |
| **Operational data** | Risk limits, margin calls, cash balances | Risk & Margin pillar (see Section 9) |

This separation ensures that the research engine never depends on the schemas of other pillars. Adding a new execution report or a new graveyard metric requires no changes to the `DataFeed`, the pricers, or the backtester.

### 8.4 Migration Path (Phases)

- **Phase 1 (current):** The `DataFeed` class and a `CsvBackend` are implemented, providing market data from CSV files. A thin `EquityPriceProvider` wraps the `DataFeed`. No `MarketData` class exists; the abstraction is real from day one.

- **Phase 2 (SQL integration):**  
  A separate ETL (Extract‑Transform‑Load) pipeline is built to pull, clean, and store data in a SQL database. The database schema supports `source` and `observation_time` columns from the start.  
  A `SQLDataFeed` is implemented, fulfilling all the same dataset names as the CSV version. The `CSVDataFeed` is swapped out for the `SQLDataFeed` via configuration—the entire research framework remains untouched.  
  - **Calendar system:** Introduce the `CalendarProvider` (§3.5). Replace the temporary `calendar_ticker` with a calendar configuration. The provider will initially load holiday lists from simple CSV files and support union/intersection logic. Point‑in‑time holiday data will be added when the SQL data pipeline supports versioned calendars.
  **Holiday calendars** (per currency, exchange, or instrument) are stored in the database and made available through the `DataFeed`. These serve two purposes:
    - **Pricing input:** required for computing cash‑flow schedules (swaps), converting tenors to absolute maturity dates (forwards, options), and determining settlement dates. The Pricer’s `resolve_instrument` method (Section 3.6) consumes these calendars.
    - **Liquidity masking:** for OTC instruments where data may exist on local holidays but liquidity is questionable, the `DataFeed` can use a holiday calendar to treat those dates as having no valid data, even if raw quotes exist. This ensures that pricing and P&L are only computed on days with genuine market liquidity.

- **Phase 3 (typed providers for complex instruments):**  
  As options, futures, or FX instruments are added, the corresponding typed providers (`VolSurfaceProvider`, `RateCurveProvider`, etc.) are implemented. They all consume the `DataFeed` internally, so they instantly work with both CSV (test) and SQL (production) backends.  
  This phase adds the ability to price complex derivatives, but the core simulation loop and validation pipeline do not change—new instruments are simply new pricer and data‑provider classes that plug into the existing interfaces.

- **Phase 4 (point‑in‑time data):**  
  For datasets that are revised over time (macro‑economic series, analyst forecasts, projected dividends, etc.), the SQL schema is extended to support **point‑in‑time (PIT) storage**. Each data point is stored with a `vintage_date` (the date on which the value became known), in addition to the `reference_date` (the date the value pertains to).  
  The `SQLDataFeed` is enhanced to serve PIT‑aware queries, allowing strategies to ask *“what was the GDP forecast for 2025‑Q1 as it was known on 2024‑12‑15?”* without introducing look‑ahead bias.  
  This is a significant data‑pipeline upgrade that must be completed before any strategy can use revised data honestly. When historical PIT data is unavailable, it may sometimes be necessary to use the final (fully revised) series as a proxy—but that introduces unknown look‑ahead bias, and Phase 4 exists to eliminate that situation wherever possible.

**Backward compatibility:** Every change described above is strictly additive. The backtester’s daily loop, the signal interface, the `Trade` class, and the entire validation pipeline never depend on how data is stored. They only interact with the `DataFeed` or typed provider interfaces. Strategies validated in Phase 1 will produce identical results in Phase 4, guaranteeing full reproducibility and trust.

### 8.5 Long‑term vision: standalone data platform

The data infrastructure described in this section is designed so that it can eventually be extracted into a separate, standalone data platform. The `DataFeed` interface and typed providers already form a clean API boundary. When the data layer grows to include automated ETL, multi‑vendor normalisation, point‑in‑time snapshots, and a dedicated database cluster, it will be maintained as its own project, independently of the research framework. The backtester, pricers, and signals will consume it through the same `DataFeed` interface, whether it lives locally or as a separate service.

## 9. Overall System Architecture

This research framework is one of four pillars that together form a complete systematic trading platform:

| Pillar | Purpose | Key interfaces |
|--------|---------|----------------|
| **Data** | Ingestion, cleaning, storage, and serving of market and alternative data. | Produces clean, timestamped, multi‑source data consumed by the `DataFeed`. |
| **Research** | Strategy simulation, validation, and analysis. *(This project.)* | Consumes cleaned data; produces `TargetTrade` dicts (for execution), `PortfolioState` snapshots (for risk), and `trade_history` (for analysis). |
| **Execution** | Order management, broker connectivity, and fill reconciliation. | Consumes `TargetTrade` dicts from the research engine; produces execution reports. |
| **Risk & Margin** | Real‑time risk monitoring, margin calculations, funding and cash‑flow modelling. | Consumes position, greek, and P&L data from the research engine and execution reports. |

Each pillar is designed to be built and maintained independently, communicating through stable, well‑defined interfaces. The research framework already implements the interfaces that the other pillars will consume, so those pillars can be developed later without any changes to the backtester or summary modules.

This section is a long‑term vision statement; none of the other pillars are required for Phase 1.