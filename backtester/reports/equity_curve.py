from __future__ import annotations

import pandas as pd

from backtester.reports._base import BaseReport


class EquityCurveReport(BaseReport):
    def build(self, summary, trades, leg_data, report_config, fx_rates, output_name):
        cfg = summary._normalize_config(report_config)
        include = cfg.get("include")

        cols = {}
        if include is None or "gross" in include:
            cols["gross"] = summary.get_cumulative_series(leg_data, "gross")
        if include is None or "cost" in include:
            cols["cost"] = summary.get_cumulative_series(leg_data, "cost")
        if include is None or "net" in include:
            cols["net"] = summary.get_cumulative_series(leg_data, "net")

        if summary.capital is not None and summary.capital > 0:
            if include is None or "gross_pct" in include:
                cols["gross_pct"] = (
                    summary.get_cumulative_series(leg_data, "gross")
                    / summary.capital * 100
                )
            if include is None or "cost_pct" in include:
                cols["cost_pct"] = (
                    summary.get_cumulative_series(leg_data, "cost")
                    / summary.capital * 100
                )
            if include is None or "net_pct" in include:
                cols["net_pct"] = (
                    summary.get_cumulative_series(leg_data, "net")
                    / summary.capital * 100
                )

        df = pd.DataFrame(cols)
        if df.empty:
            return {}
        return {output_name: df}
