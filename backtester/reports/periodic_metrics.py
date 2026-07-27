from __future__ import annotations

import pandas as pd

from backtester.metrics_registry import METRIC_CALCULATORS, _compute_metrics_row
from backtester.reports._base import BaseReport

_EXCLUDED_METRICS = {"hit_ratio"}


class PeriodicMetricsReport(BaseReport):
    def build(self, summary, trades, leg_data, report_config, fx_rates, output_name):
        cfg = summary._normalize_config(report_config)
        include = cfg.get("include")
        timeframe = cfg.get("timeframe", "yearly")
        annualization = cfg.get("annualization", 252)
        if isinstance(annualization, bool):
            annualization = 252

        want_all = include is None

        _eligible = tuple(n for n in METRIC_CALCULATORS if n not in _EXCLUDED_METRICS)

        want: dict[str, bool] = {}
        needs: dict[str, bool] = {}
        for label in ("gross", "net"):
            for base_name in _eligible:
                key = f"{base_name}_{label}"
                want[key] = want_all or key in (include or [])
            needs[label] = any(
                want.get(f"{base_name}_{label}", False)
                for base_name in _eligible
            )

        for label in ("gross", "net"):
            if want_all:
                want[f"{label}_label_include"] = list(_eligible)
            else:
                li = {
                    item.rsplit("_", 1)[0]
                    for item in (include or [])
                    if item.endswith(f"_{label}")
                    and item.rsplit("_", 1)[0] in _eligible
                }
                want[f"{label}_label_include"] = li

        if not summary._trading_days:
            return {}

        td_dates = pd.to_datetime(pd.Index(summary._trading_days), errors="coerce")
        if timeframe == "monthly":
            labels = td_dates.strftime("%Y-%m")
        else:
            labels = td_dates.year.astype(str)

        unique_periods = list(dict.fromkeys(labels))

        daily_cache: dict[str, pd.Series] = {}
        cum_cache: dict[str, pd.Series] = {}
        for label in ("gross", "net"):
            if needs[label]:
                daily_cache[label] = summary.get_daily_series(leg_data, label)
                cum_cache[label] = summary.get_cumulative_series(leg_data, label)

        rows = []
        for period in unique_periods:
            period_mask = labels == period
            period_dates_arr = [
                d for d, m in zip(summary._trading_days, period_mask) if m
            ]
            period_idx = pd.Index(period_dates_arr)

            row = {}
            for label in ("gross", "net"):
                if not needs[label]:
                    continue

                daily_full = daily_cache.get(label)
                cum_full = cum_cache.get(label)
                if daily_full is None or daily_full.empty:
                    continue

                daily_period = daily_full.reindex(period_idx, fill_value=0.0)
                cum_period = (
                    cum_full.reindex(period_idx, fill_value=0.0)
                    .ffill()
                    .fillna(0.0)
                )
                cum_period = cum_period - cum_period.iloc[0]
                totals = summary.get_trade_totals(leg_data)

                label_include = want.get(f"{label}_label_include")
                metrics_row = _compute_metrics_row(
                    daily_period, cum_period, totals, summary.capital,
                    label_include, annualization, summary, label,
                )
                for base_name, value in metrics_row.items():
                    row[f"{base_name}_{label}"] = value

            if row:
                rows.append((period, row))

        if not rows:
            return {}

        total_row = {}
        for label in ("gross", "net"):
            if not needs[label]:
                continue
            daily_full = daily_cache.get(label)
            cum_full = cum_cache.get(label)
            if daily_full is None or daily_full.empty:
                continue
            totals = summary.get_trade_totals(leg_data)
            label_include = want.get(f"{label}_label_include")
            metrics_row = _compute_metrics_row(
                daily_full, cum_full, totals, summary.capital,
                label_include, annualization, summary, label,
            )
            for base_name, value in metrics_row.items():
                total_row[f"{base_name}_{label}"] = value

        df = pd.DataFrame([r for _, r in rows], index=[p for p, _ in rows])
        df.loc["total"] = total_row
        return {output_name: df}
