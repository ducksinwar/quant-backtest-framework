from __future__ import annotations

from collections import defaultdict

import pandas as pd

from backtester.reports._base import BaseReport


class ByUnderlyingReport(BaseReport):
    def build(self, summary, trades, leg_data, report_config, fx_rates, output_name):
        from backtester.reports import REPORTS

        cfg = summary._normalize_config(report_config)
        include = cfg.get("include") or {}

        by_ticker: dict[str, list[dict]] = defaultdict(list)
        for d in leg_data:
            by_ticker[d["ticker"]].append(d)

        build_all = not bool(include)

        results: dict[str, pd.DataFrame] = {}
        for ticker, ticker_leg_data in by_ticker.items():
            sub_trades = [
                t for t in trades
                if any(d["trade_id"] == t.trade_id for d in ticker_leg_data)
            ]

            sub_results: dict[str, pd.DataFrame] = {}

            def _build_sub_report(name, sub_cfg):
                report_cls = REPORTS.get(name)
                if report_cls is None:
                    return
                sub_report = report_cls()
                sub_results.update(
                    sub_report.build(
                        summary, sub_trades, ticker_leg_data,
                        sub_cfg, fx_rates, name,
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
                results[key] = sub_df

        return results
