from __future__ import annotations

from collections import defaultdict

import pandas as pd

from backtester.reports._base import BaseReport


class ByUnderlyingReport(BaseReport):
    requires_local_currency = True

    def build(self, summary, trades, leg_data, report_config, output_name,
              fx_series):
        from backtester.reports import REPORTS

        cfg = summary._normalize_config(report_config)
        include = cfg.get("include") or {}
        currency = cfg.get("currency", "base")

        if summary._base_leg_data:
            trade_ids = {t.trade_id for t in trades}
            base_dataset = [
                d for d in summary._base_leg_data if d["trade_id"] in trade_ids
            ]
        else:
            base_dataset = leg_data
        if currency == "local":
            datasets = [(None, leg_data)]
        elif currency == "both":
            datasets = [(fx_series, base_dataset), (None, leg_data)]
        else:  # "base" (default)
            datasets = [(fx_series, base_dataset)]

        build_all = not bool(include)

        results: dict[str, pd.DataFrame] = {}

        for sub_fx, dataset in datasets:
            by_ticker: dict[str, list[dict]] = defaultdict(list)
            for d in dataset:
                by_ticker[d["ticker"]].append(d)

            is_secondary_local_pass = dataset is leg_data and currency == "both"
            for ticker, ticker_leg_data in by_ticker.items():
                if (
                    is_secondary_local_pass
                    and ticker_leg_data[0]["currency"] == summary._base_currency
                ):
                    continue

                sub_trades = [
                    t for t in trades
                    if any(d["trade_id"] == t.trade_id for d in ticker_leg_data)
                ]

                ticker_fx = None
                if not is_secondary_local_pass and sub_fx is not None:
                    pair_key = (
                        f"fx_{ticker_leg_data[0]['currency']}"
                        f"{summary._base_currency}"
                    )
                    if pair_key in sub_fx:
                        ticker_fx = {pair_key: sub_fx[pair_key]}

                sub_results: dict[str, pd.DataFrame] = {}

                def _build_sub_report(name, sub_cfg):
                    report_cls = REPORTS.get(name)
                    if report_cls is None:
                        return
                    sub_report = report_cls()
                    sub_results.update(
                        sub_report.build(
                            summary, sub_trades, ticker_leg_data,
                            sub_cfg, name, ticker_fx,
                        )
                    )

                sub_names = [
                    ("equity_curve", "equity_curve"),
                    ("trade_summary", "trade_summary"),
                    ("metrics", "metrics"),
                    ("drawdown_table", "drawdown_table"),
                    ("hit_ratio", "hit_ratio"),
                    ("periodic_metrics", "periodic_metrics"),
                ]
                for sub_req, sub_name in sub_names:
                    if build_all or sub_req in include:
                        sub_cfg = include.get(sub_req, {}) if not build_all else {}
                        _build_sub_report(sub_name, sub_cfg)

                for sub_name, sub_df in sub_results.items():
                    key = f"{ticker}_{sub_name}"
                    if is_secondary_local_pass:
                        key = f"{ticker}_{sub_name}_local"
                    results[key] = sub_df

        return results
