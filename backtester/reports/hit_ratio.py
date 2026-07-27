from __future__ import annotations

import pandas as pd

from backtester.reports._base import BaseReport


class HitRatioReport(BaseReport):
    def build(self, summary, trades, leg_data, report_config, fx_rates, output_name):
        cfg = summary._normalize_config(report_config)
        timeframe = cfg.get("timeframe", "yearly")
        include = cfg.get("include")

        totals = summary.get_trade_totals(leg_data)
        if not totals:
            return {}

        seen: set[str] = set()
        rows = []
        for d in leg_data:
            tid = d["trade_id"]
            if tid in seen:
                continue
            seen.add(tid)
            trade = d["trade"]
            rows.append({
                "entry_date": trade.entry_date or "",
                "gross_total": totals[tid]["gross"],
                "net_total": totals[tid]["net"],
            })

        tdf = pd.DataFrame(rows)
        if tdf.empty:
            return {}

        want_all = include is None

        try:
            dates = pd.to_datetime(tdf["entry_date"], errors="coerce")
            if timeframe == "monthly":
                tdf["group"] = dates.dt.strftime("%Y-%m")
            else:
                tdf["group"] = dates.dt.year.astype(str)
        except Exception:
            n = len(tdf)
            row = {}
            if want_all or "gross" in include:
                row["hit_ratio_gross"] = (tdf["gross_total"] > 0).mean()
            if want_all or "net" in include:
                row["hit_ratio_net"] = (tdf["net_total"] > 0).mean()
            if want_all or "total_trades" in include:
                row["total_trades"] = n
            return {output_name: pd.DataFrame([row], index=["total"])}

        cols = {}
        if want_all or "gross" in include:
            cols["hit_ratio_gross"] = (
                tdf.groupby("group")["gross_total"].apply(lambda x: (x > 0).sum() / len(x))
            )
        if want_all or "net" in include:
            cols["hit_ratio_net"] = (
                tdf.groupby("group")["net_total"].apply(lambda x: (x > 0).sum() / len(x))
            )
        if want_all or "total_trades" in include:
            cols["total_trades"] = tdf.groupby("group").size()

        df = pd.DataFrame(cols)

        total_row = {}
        n = len(tdf)
        if want_all or "gross" in include:
            total_row["hit_ratio_gross"] = (tdf["gross_total"] > 0).mean()
        if want_all or "net" in include:
            total_row["hit_ratio_net"] = (tdf["net_total"] > 0).mean()
        if want_all or "total_trades" in include:
            total_row["total_trades"] = n

        df.loc["total"] = total_row

        if df.empty:
            return {}
        return {output_name: df}
