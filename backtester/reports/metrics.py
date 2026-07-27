from __future__ import annotations

import pandas as pd

from backtester.metrics_registry import METRIC_CALCULATORS, _compute_metrics_row
from backtester.reports._base import BaseReport


class MetricsReport(BaseReport):
    def build(self, summary, trades, leg_data, report_config, fx_rates, output_name):
        cfg = summary._normalize_config(report_config)
        include = cfg.get("include")
        annualization = cfg.get("annualization", 252)
        if isinstance(annualization, bool):
            annualization = 252

        want_all = include is None
        has_capital = summary.capital is not None and summary.capital > 0

        metrics = {}
        for label in ("gross", "net"):
            if want_all:
                label_include = None
            else:
                label_include = {
                    item.rsplit("_", 1)[0]
                    for item in (include or [])
                    if item.endswith(f"_{label}")
                    and item.rsplit("_", 1)[0] in METRIC_CALCULATORS
                }
                if not label_include:
                    continue

            daily = summary.get_daily_series(leg_data, label)
            cumulative = summary.get_cumulative_series(leg_data, label)
            totals = summary.get_trade_totals(leg_data)

            row = _compute_metrics_row(
                daily,
                cumulative,
                totals,
                summary.capital,
                label_include,
                annualization,
                summary,
                label,
            )
            for base_name, value in row.items():
                metrics[f"{base_name}_{label}"] = value
        if has_capital and (want_all or "capital" in (include or [])):
            metrics["capital"] = summary.capital
        if metrics:
            return {output_name: pd.DataFrame([metrics])}
        return {}
