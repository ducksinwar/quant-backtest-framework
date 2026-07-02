import os
import sys

from backtester.backtest_engine import AssetClassConfig, BacktestConfig, Backtester
from backtester.cost_model import CostModel, EquityCostCalculator
from backtester.data.csv_backend import CsvBackend
from backtester.data.data_feed import DataFeed
from backtester.data.typed_providers.equity_price_provider import EquityPriceProvider
from backtester.pricers.equity_pricer import EquityPricer
from backtester.signals.sma_crossover import SMACrossoverSignal
from backtester.summary import Summary


def main():
    csv_path = os.path.join("market_data", "spy_eod.csv")
    if not os.path.exists(csv_path):
        print(f"Error: {csv_path} not found.")
        sys.exit(1)

    # 1. Data backend and feed
    backend = CsvBackend(base_dir="market_data")
    data_feed = DataFeed(backend)

    # 2. Typed provider + pricer
    provider = EquityPriceProvider(data_feed)
    equity_pricer = EquityPricer(provider)

    # 3. Signal
    tickers = ["SPY", "QQQ"]
    notional = 100_000
    signal = SMACrossoverSignal(
        short_window=20,
        long_window=50,
        tickers=tickers,
        notional=notional,
        data_feed=data_feed,
    )

    # 4. Backtester config
    config = BacktestConfig(
        signal=signal,
        start_date="2000-01-01",
        end_date="2025-12-31",
        asset_class_configs={
            "equity": AssetClassConfig(
                pricer=equity_pricer,
                risk_measures=[],
                record_pricing_inputs=False,
            )
        },
        calendar_ticker="SPY",
    )

    # 5. Run backtest
    bt = Backtester(config, data_feed)
    result = bt.run()
    trade_history = list(result.trade_history)
    print(f"Backtest complete. {len(trade_history)} trade(s) executed.")

    if not trade_history:
        print("No trades were generated. Exiting.")
        return

    # 6. Compute costs
    cost_model = CostModel(calculators={"equity": EquityCostCalculator(bps=2.0)})
    costs = cost_model.compute_costs(trade_history)
    total_cost = sum(s.sum() for s in costs.values())
    print(f"Total transaction cost: ${total_cost:,.2f}")

    spec = {
        "reports": {
            "equity_curve": True,
            "trade_summary": True,
            "metrics": True,
            "hit_ratio": True,
            "drawdown_table": True,
            "periodic_metrics": True,
            "by_underlying": True,
        },
        "output": {"format": "excel", "path": "results/backtest_results.xlsx"},
    }

    capital = len(tickers) * notional

    summary = Summary(spec)
    results = summary.generate(
        trade_history, cost_model,
        trading_days=list(result.trading_days),
        capital=capital
    )

    if results is not None:
        # Print metrics
        if "metrics" in results:
            print("\n--- Metrics ---")
            print(results["metrics"].to_string(index=False))

        # Print equity curve head and tail
        if "equity_curve" in results:
            ec = results["equity_curve"]
            print("\n--- Equity Curve (first 5 rows) ---")
            print(ec.head(5).to_string())
            print("\n--- Equity Curve (last 5 rows) ---")
            print(ec.tail(5).to_string())

        # Print trade summary
        if "trade_summary" in results:
            ts = results["trade_summary"]
            print("\n--- Trade Summary ---")
            print(ts.to_string(index=False))


    print("\nPhase 1 end-to-end example ran successfully.")


if __name__ == "__main__":
    main()
