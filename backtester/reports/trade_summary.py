from __future__ import annotations

import pandas as pd

from backtester.reports._base import BaseReport


class TradeSummaryReport(BaseReport):
    def build(self, summary, trades, leg_data, report_config, fx_rates, output_name):
        cfg = summary._normalize_config(report_config)
        include = cfg.get("include")

        totals = summary.get_trade_totals(leg_data)

        rows = []
        for trade in trades:
            tt = totals.get(trade.trade_id, {"gross": 0.0, "cost": 0.0, "net": 0.0})
            gross_total = tt["gross"]
            cost_total = tt["cost"]
            net_total = tt["net"]

            trade_legs = [d for d in leg_data if d["trade_id"] == trade.trade_id]

            row = {}
            row["trade_id"] = trade.trade_id
            row["entry_date"] = trade.entry_date
            row["exit_date"] = trade.exit_date
            if include is None or "holding_days" in include:
                td = summary._trading_days
                if td and trade.entry_date and trade.entry_date in td:
                    end = (
                        trade.exit_date
                        if trade.exit_date and trade.exit_date in td
                        else td[-1]
                    )
                    holding = td.index(end) - td.index(trade.entry_date) + 1
                    row["holding_days"] = holding
                else:
                    row["holding_days"] = 0
            if include is None or "tags" in include:
                row["tags"] = ",".join(trade.tags) if trade.tags else ""
            if include is None or "underlying" in include:
                tickers = sorted({d["ticker"] for d in trade_legs})
                row["underlying"] = ",".join(tickers)
            if include is None or "gross_pnl" in include:
                row["gross_pnl"] = gross_total
            if include is None or "cost" in include:
                row["cost"] = cost_total
            if include is None or "net_pnl" in include:
                row["net_pnl"] = net_total
            if summary.capital is not None and summary.capital > 0:
                if include is None or "gross_pnl_pct" in include:
                    row["gross_pnl_pct"] = gross_total / summary.capital * 100
                if include is None or "cost_pct" in include:
                    row["cost_pct"] = cost_total / summary.capital * 100
                if include is None or "net_pnl_pct" in include:
                    row["net_pnl_pct"] = net_total / summary.capital * 100
            rows.append(row)

        if rows:
            return {output_name: pd.DataFrame(rows)}
        return {}
