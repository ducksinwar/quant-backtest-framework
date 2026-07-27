from __future__ import annotations

import pandas as pd

from backtester.reports._base import BaseReport


class DrawdownTableReport(BaseReport):
    def build(self, summary, trades, leg_data, report_config, fx_rates, output_name):
        cfg = summary._normalize_config(report_config)
        top_n = cfg.get("top_n", 10)
        include = cfg.get("include")
        has_capital = summary.capital is not None and summary.capital > 0

        results = {}

        if include is None or "gross" in include:
            gross_cum = summary.get_cumulative_series(leg_data, "gross")
            dd_df = self._compute_drawdown_table_from_cum(gross_cum, top_n)
            if dd_df is not None:
                if has_capital:
                    dd_df["drawdown_pct"] = dd_df["drawdown"] / summary.capital * 100
                dd_df = _reorder_columns(dd_df, has_capital)
                results[f"{output_name}_gross"] = dd_df

        if include is None or "net" in include:
            net_cum = summary.get_cumulative_series(leg_data, "net")
            dd_df = self._compute_drawdown_table_from_cum(net_cum, top_n)
            if dd_df is not None:
                if has_capital:
                    dd_df["drawdown_pct"] = dd_df["drawdown"] / summary.capital * 100
                dd_df = _reorder_columns(dd_df, has_capital)
                results[f"{output_name}_net"] = dd_df

        return results

    @staticmethod
    def _compute_drawdown_table_from_cum(
        cumulative: pd.Series, top_n: int
    ) -> pd.DataFrame | None:
        running_max = cumulative.cummax()
        drawdown = cumulative - running_max

        underwater = drawdown < 0
        if not underwater.any():
            return None

        dd_periods = []
        in_dd = False
        start = None
        peak_val = 0.0

        for i, (idx, dd_val) in enumerate(drawdown.items()):
            if dd_val < 0 and not in_dd:
                start = max(i - 1, 0)
                peak_val = running_max.iloc[start]
                in_dd = True
            elif dd_val >= 0 and in_dd:
                end = i
                drawdown_val = drawdown.iloc[start:end+1].min()
                trough_date = drawdown.iloc[start:end+1].idxmin()
                dd_periods.append({
                    "start": drawdown.index[start],
                    "end": drawdown.index[end],
                    "trough_date": trough_date,
                    "drawdown": drawdown_val,
                    "trough": peak_val + drawdown_val,
                    "peak": peak_val,
                    "underwater_days": end - start + 1,
                })
                in_dd = False

        if in_dd:
            end = len(drawdown) - 1
            drawdown_val = drawdown.iloc[start:end+1].min()
            trough_date = drawdown.iloc[start:end+1].idxmin()
            dd_periods.append({
                "start": drawdown.index[start],
                "end": drawdown.index[end],
                "trough_date": trough_date,
                "drawdown": drawdown_val,
                "trough": peak_val + drawdown_val,
                "peak": peak_val,
                "underwater_days": end - start + 1,
            })

        dd_periods.sort(key=lambda x: x["drawdown"])
        return pd.DataFrame(dd_periods[:top_n])


def _reorder_columns(df: pd.DataFrame, has_capital: bool) -> pd.DataFrame:
    base_order = ["start", "end", "trough_date", "peak", "trough", "drawdown", "underwater_days"]
    if has_capital:
        base_order.insert(base_order.index("drawdown") + 1, "drawdown_pct")
    return df[[c for c in base_order if c in df.columns]]
