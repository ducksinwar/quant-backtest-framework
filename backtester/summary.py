from __future__ import annotations

import numpy as np
import pandas as pd


class Summary:
    def __init__(self, spec: dict):
        self._spec = spec
        self._reports_spec = spec.get("reports", {})
        self._missing_mode = spec.get("missing_data_mode", "any")
        self._output = spec.get("output")

    def generate(
        self,
        trade_history: list,
        cost_model,
        fx_rates: dict[str, pd.Series] | None = None,
        trading_days: list[str] | None = None,
    ) -> dict | None:
        self._trading_days = trading_days
        cost_map = cost_model.compute_costs(trade_history) if cost_model else {}

        leg_data = self._extract_leg_data(trade_history, cost_map, trading_days)

        results: dict[str, pd.DataFrame] = {}
        self._generate_report_tree(
            self._reports_spec, trade_history, leg_data, cost_map,
            fx_rates, [], results,
        )

        if self._output:
            self._write_output(results)
            return None

        return results

    def _extract_leg_data(
        self, trade_history: list, cost_map: dict,
        trading_days: list[str] | None = None,
    ) -> list[dict]:
        rows = []
        for trade in trade_history:
            for structure in trade.structure_history:
                for leg in structure.legs:
                    pnl_list = leg.daily_total_pnl
                    if trading_days is not None and len(pnl_list) > 0:
                        entry_idx = trading_days.index(trade.entry_date or "")
                        pnl_start = entry_idx + 1

                        if trade.exit_date is not None:
                            pnl_end = trading_days.index(trade.exit_date)
                        else:
                            pnl_end = len(trading_days) - 1

                        pnl_dates = trading_days[pnl_start:pnl_end + 1]

                        if len(pnl_dates) == len(pnl_list):
                            gross = pd.Series(pnl_list, index=pnl_dates, dtype=float)
                        else:
                            gross = pd.Series(pnl_list, index=trading_days[:len(pnl_list)], dtype=float)

                        if trade.entry_date and trade.entry_date not in gross.index:
                            gross = pd.concat([
                                pd.Series(0.0, index=[trade.entry_date], dtype=float),
                                gross,
                            ])
                    else:
                        gross = pd.Series(pnl_list, dtype=float)

                    cost_series = cost_map.get(leg.leg_id, pd.Series(dtype=float))
                    cost_aligned = cost_series.reindex(
                        gross.index, fill_value=0.0,
                    )

                    net = gross - cost_aligned

                    rows.append({
                        "trade": trade,
                        "trade_id": trade.trade_id,
                        "structure": structure,
                        "leg": leg,
                        "leg_id": leg.leg_id,
                        "ticker": leg.ticker,
                        "currency": leg.currency,
                        "gross": gross,
                        "cost": cost_aligned,
                        "net": net,
                    })
        return rows

    def _generate_report_tree(
        self, reports_spec: dict, trade_history: list,
        leg_data: list[dict], cost_map: dict,
        fx_rates: dict | None, path: list[str],
        results: dict[str, pd.DataFrame],
        parent_filter=None,
    ):
        root_filter = reports_spec.get("filter") if "filter" in reports_spec else None

        effective_filter = None
        if parent_filter is not None and root_filter is not None:
            effective_filter = lambda t, pf=parent_filter, rf=root_filter: pf(t) and rf(t)
        elif parent_filter is not None:
            effective_filter = parent_filter
        elif root_filter is not None:
            effective_filter = root_filter

        for key, value in reports_spec.items():
            if key == "filter":
                continue

            if isinstance(value, dict) and "reports" in value:
                group_filter = value.get("filter")
                combined = effective_filter
                if group_filter is not None:
                    if combined is not None:
                        combined = lambda t, c=combined, g=group_filter: c(t) and g(t)
                    else:
                        combined = group_filter

                self._generate_report_tree(
                    value["reports"], trade_history, leg_data, cost_map,
                    fx_rates, path + [key], results, combined,
                )
            else:
                filtered_trades = self._filter_trades(trade_history, effective_filter)
                filtered_leg_data = [d for d in leg_data if d["trade"] in filtered_trades]

                report_name = "_".join(path + [key])
                self._build_report(
                    key, value, filtered_trades, filtered_leg_data,
                    fx_rates, report_name, results,
                )

    def _filter_trades(self, trades: list, filter_fn) -> list:
        if filter_fn is None:
            return list(trades)
        return [t for t in trades if filter_fn(t)]

    def _build_report(
        self, report_name: str, config, trades: list,
        leg_data: list[dict], fx_rates: dict | None,
        output_name: str, results: dict,
    ):
        if report_name == "equity_curve":
            self._build_equity_curve(config, leg_data, fx_rates, output_name, results)
        elif report_name == "trade_summary":
            self._build_trade_summary(config, trades, leg_data, fx_rates, output_name, results)
        elif report_name == "metrics":
            self._build_metrics(config, leg_data, fx_rates, output_name, results)
        elif report_name == "hit_ratio":
            self._build_hit_ratio(config, leg_data, fx_rates, output_name, results)
        elif report_name == "drawdown_table":
            self._build_drawdown_table(config, leg_data, fx_rates, output_name, results)
        elif report_name == "by_underlying":
            self._build_by_underlying(config, trades, leg_data, fx_rates, output_name, results)

    def _aggregate_series(
        self, leg_data: list[dict], key: str, fx_rates: dict | None = None,
    ) -> pd.Series:
        if not leg_data:
            return pd.Series(dtype=float)

        trading_days = self._trading_days
        if trading_days is not None and self._missing_mode != "per_leg":
            td_index = pd.Index(trading_days, dtype=object)

            filled_series = []
            nan_masks = []
            for d in leg_data:
                s = d[key]
                s_filled = s.reindex(td_index, fill_value=0.0)
                filled_series.append(s_filled)

                if self._missing_mode == "all":
                    alive_nan = s.isna()                     # vectorized, same result as the loop
                    nan_mask = alive_nan.reindex(td_index, fill_value=False)
                    nan_masks.append(nan_mask)

            result = sum(filled_series)

            if self._missing_mode == "all" and nan_masks:
                any_nan = pd.concat(nan_masks, axis=1).any(axis=1)
                result[any_nan] = np.nan

            return result

        series_list = []
        for d in leg_data:
            s = d[key]
            if self._missing_mode == "per_leg":
                series_list.append(s.rename(d["leg_id"]))
            else:
                s_filled = s.fillna(0.0) if self._missing_mode == "any" else s
                series_list.append(s_filled)

        if self._missing_mode == "per_leg":
            result = pd.concat(series_list, axis=1)
        else:
            result = sum(series_list)
            if self._missing_mode == "all":
                any_nan_mask = pd.concat([s.isna() for s in series_list], axis=1).any(axis=1)
                result[any_nan_mask] = np.nan

        return result

    def _build_equity_curve(
        self, config, leg_data: list[dict], fx_rates: dict | None,
        output_name: str, results: dict,
    ):
        cfg = self._normalize_config(config)
        include = cfg.get("include")

        gross = self._aggregate_series(leg_data, "gross", fx_rates)
        cost  = self._aggregate_series(leg_data, "cost",  fx_rates)
        net   = self._aggregate_series(leg_data, "net",   fx_rates)

        series_map = {"gross": gross, "cost": cost, "net": net}

        cols = {
            key: series_map[key].cumsum()
            for key in series_map
            if include is None or key in include
        }

        df = pd.DataFrame(cols)
        if not df.empty:
            results[output_name] = df

    def _build_trade_summary(
        self, config, trades: list, leg_data: list[dict],
        fx_rates: dict | None, output_name: str, results: dict,
    ):
        cfg = self._normalize_config(config)
        include = cfg.get("include")

        rows = []
        for trade in trades:
            trade_legs = [d for d in leg_data if d["trade_id"] == trade.trade_id]

            gross_total = sum(
                d["gross"].fillna(0.0).sum() for d in trade_legs
            )
            cost_total = sum(
                d["cost"].fillna(0.0).sum() for d in trade_legs
            )
            net_total = sum(
                d["net"].fillna(0.0).sum() for d in trade_legs
            )

            row = {}
            row["trade_id"] = trade.trade_id
            row["entry_date"] = trade.entry_date
            row["exit_date"] = trade.exit_date
            if include is None or "holding_days" in include:
                if (
                    self._trading_days
                    and trade.entry_date
                    and trade.entry_date in self._trading_days
                ):
                    end = (
                        trade.exit_date
                        if trade.exit_date and trade.exit_date in self._trading_days
                        else self._trading_days[-1]
                    )
                    holding = (
                        self._trading_days.index(end)
                        - self._trading_days.index(trade.entry_date)
                        + 1
                    )
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

            rows.append(row)

        if rows:
            results[output_name] = pd.DataFrame(rows)

    def _build_metrics(
        self, config, leg_data: list[dict], fx_rates: dict | None,
        output_name: str, results: dict,
    ):
        cfg = self._normalize_config(config)
        include = cfg.get("include")
        annualization = cfg.get("annualization", 252)
        if isinstance(annualization, bool):
            annualization = 252

        gross = self._aggregate_series(leg_data, "gross", fx_rates)
        net = self._aggregate_series(leg_data, "net", fx_rates)

        want_all = include is None

        metrics = {}
        for label, series in [("gross", gross), ("net", net)]:
            if want_all or f"sharpe_{label}" in (include or []):
                ann_ret = series.mean() * annualization
                ann_vol = series.std() * np.sqrt(annualization)
                metrics[f"sharpe_{label}"] = ann_ret / ann_vol if ann_vol > 0 else 0.0

            if want_all or f"max_drawdown_{label}" in (include or []):
                cumulative = series.fillna(0.0).cumsum()
                running_max = cumulative.cummax()
                drawdown = cumulative - running_max
                metrics[f"max_drawdown_{label}"] = drawdown.min()

        if want_all or any("annualized_return" in (i or "") for i in (include or [])):
            ann_ret_gross = gross.mean() * annualization
            metrics["annualized_return_gross"] = ann_ret_gross
            ann_ret_net = net.mean() * annualization
            metrics["annualized_return_net"] = ann_ret_net

        if want_all or any("calmar" in (i or "").lower() for i in (include or [])):
            cumulative = gross.fillna(0.0).cumsum()
            running_max = cumulative.cummax()
            dd = cumulative - running_max
            mdd = dd.min()
            ann_ret = gross.mean() * annualization
            metrics["calmar_gross"] = ann_ret / abs(mdd) if mdd != 0 else 0.0

            cumulative_n = net.fillna(0.0).cumsum()
            running_max_n = cumulative_n.cummax()
            dd_n = cumulative_n - running_max_n
            mdd_n = dd_n.min()
            ann_ret_n = net.mean() * annualization
            metrics["calmar_net"] = ann_ret_n / abs(mdd_n) if mdd_n != 0 else 0.0

        if want_all or any("hit_ratio" in (i or "") for i in (include or [])):
            pos_gross = (gross.fillna(0.0) > 0).mean()
            pos_net = (net.fillna(0.0) > 0).mean()
            metrics["hit_ratio_gross"] = pos_gross
            metrics["hit_ratio_net"] = pos_net

        if metrics:
            results[output_name] = pd.DataFrame([metrics])

    def _build_hit_ratio(
        self, config, leg_data: list[dict], fx_rates: dict | None,
        output_name: str, results: dict,
    ):
        cfg = self._normalize_config(config)
        timeframe = cfg.get("timeframe", "yearly")
        include = cfg.get("include")

        gross = self._aggregate_series(leg_data, "gross", fx_rates)
        net = self._aggregate_series(leg_data, "net", fx_rates)

        cols = {}
        if include is None or "gross" in include:
            cols["hit_ratio_gross"] = self._compute_hit_ratio(gross, timeframe)
        if include is None or "net" in include:
            cols["hit_ratio_net"] = self._compute_hit_ratio(net, timeframe)

        if cols:
            results[output_name] = pd.DataFrame(cols)

    def _compute_hit_ratio(self, series: pd.Series, timeframe: str) -> pd.Series:
        series = series.fillna(0.0)
        try:
            idx_series = pd.to_datetime(series.index, errors="coerce")
            if timeframe == "monthly":
                grouper = idx_series.strftime("%Y-%m")
            else:
                grouper = idx_series.strftime("%Y")
        except Exception:
            return pd.Series({"overall": (series > 0).mean()})

        grouped = series.groupby(grouper)
        hit = grouped.apply(lambda g: (g > 0).mean())
        return hit

    def _build_drawdown_table(
        self, config, leg_data: list[dict], fx_rates: dict | None,
        output_name: str, results: dict,
    ):
        cfg = self._normalize_config(config)
        top_n = cfg.get("top_n", 10)
        include = cfg.get("include")

        gross = self._aggregate_series(leg_data, "gross", fx_rates)
        net = self._aggregate_series(leg_data, "net", fx_rates)

        if include is None or "gross" in include:
            dd_df = self._compute_drawdown_table(gross, top_n)
            if dd_df is not None:
                results[f"{output_name}_gross"] = dd_df

        if include is None or "net" in include:
            dd_df = self._compute_drawdown_table(net, top_n)
            if dd_df is not None:
                results[f"{output_name}_net"] = dd_df

    def _compute_drawdown_table(
        self, series: pd.Series, top_n: int
    ) -> pd.DataFrame | None:
        cumulative = series.fillna(0.0).cumsum()
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
                start = i
                peak_val = running_max.iloc[i]
                in_dd = True
            elif dd_val >= 0 and in_dd:
                end = i - 1
                trough = drawdown.iloc[start:end+1].min()
                trough_date = drawdown.iloc[start:end+1].idxmin()
                dd_periods.append({
                    "start": drawdown.index[start],
                    "end": drawdown.index[end],
                    "trough_date": trough_date,
                    "depth": trough,
                    "peak": peak_val,
                    "underwater_days": end - start + 1,
                })
                in_dd = False

        if in_dd:
            end = len(drawdown) - 1
            trough = drawdown.iloc[start:end+1].min()
            trough_date = drawdown.iloc[start:end+1].idxmin()
            dd_periods.append({
                "start": drawdown.index[start],
                "end": drawdown.index[end],
                "trough_date": trough_date,
                "depth": trough,
                "peak": peak_val,
                "underwater_days": end - start + 1,
            })

        dd_periods.sort(key=lambda x: x["depth"])
        return pd.DataFrame(dd_periods[:top_n])

    def _build_by_underlying(
        self, config, trades: list, leg_data: list[dict],
        fx_rates: dict | None, output_name: str, results: dict,
    ):
        cfg = self._normalize_config(config)
        include = cfg.get("include") or {}

        by_ticker: dict[str, list[dict]] = {}
        for d in leg_data:
            ticker = d["ticker"]
            by_ticker.setdefault(ticker, []).append(d)

        build_all = not bool(include)

        for ticker, ticker_leg_data in by_ticker.items():
            sub_results: dict[str, pd.DataFrame] = {}

            if build_all or "equity_curve" in include:
                ec_cfg = include.get("equity_curve", {}) if not build_all else {}
                self._build_equity_curve(ec_cfg, ticker_leg_data, fx_rates, "equity_curve", sub_results)
            if build_all or "metrics" in include:
                m_cfg = include.get("metrics", {}) if not build_all else {}
                self._build_metrics(m_cfg, ticker_leg_data, fx_rates, "metrics", sub_results)
            if build_all or "drawdown_table" in include:
                dd_cfg = include.get("drawdown_table", {}) if not build_all else {}
                self._build_drawdown_table(dd_cfg, ticker_leg_data, fx_rates, "drawdown_table", sub_results)
            if build_all or "hit_ratio" in include:
                hr_cfg = include.get("hit_ratio", {}) if not build_all else {}
                self._build_hit_ratio(hr_cfg, ticker_leg_data, fx_rates, "hit_ratio", sub_results)

            for sub_name, sub_df in sub_results.items():
                key = f"{ticker}_{sub_name}"
                results[key] = sub_df

    def _normalize_config(self, config) -> dict:
        if config is True:
            return {}
        if config is None:
            return {}
        if isinstance(config, dict):
            return config
        return {}

    def _write_output(self, results: dict):
        fmt = self._output.get("format", "csv")
        path = self._output.get("path", "summary_output")

        if fmt == "excel":
            with pd.ExcelWriter(f"{path}.xlsx") as writer:
                for name, df in results.items():
                    safe_name = name[:31]
                    df.to_excel(writer, sheet_name=safe_name)
        elif fmt == "csv":
            import os
            os.makedirs(path, exist_ok=True)
            for name, df in results.items():
                df.to_csv(f"{path}/{name}.csv")
        elif fmt == "parquet":
            import os
            os.makedirs(path, exist_ok=True)
            for name, df in results.items():
                df.to_parquet(f"{path}/{name}.parquet")
