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
        trading_days: list[str],
        fx_rates: dict[str, pd.Series] | None = None,
    ) -> dict | None:
        self._trading_days = trading_days
        self._agg_cache: dict[tuple, pd.Series] = {}
        self._cache: dict[tuple, object] = {}
        cost_map = cost_model.compute_costs(trade_history) if cost_model else {}

        leg_data = self._extract_leg_data(trade_history, cost_map, trading_days)

        if self._missing_mode == "all":
            self._adjust_for_missing_legs(leg_data, trading_days)

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
        trading_days: list[str],
    ) -> list[dict]:
        rows = []
        for trade in trade_history:
            for structure in trade.structure_history:
                for leg in structure.legs:
                    pnl_list = leg.daily_total_pnl
                    if len(pnl_list) > 0:
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

    @staticmethod
    def _group_legs_by_trade(leg_data: list[dict]) -> dict[str, list[dict]]:
        groups: dict[str, list[dict]] = {}
        for d in leg_data:
            tid = d["trade_id"]
            if tid not in groups:
                groups[tid] = []
            groups[tid].append(d)
        return groups

    def _adjust_for_missing_legs(
        self, leg_data: list[dict], trading_days: list[str]
    ) -> None:
        td_index = pd.Index(trading_days, dtype=object)

        groups = self._group_legs_by_trade(leg_data)

        for trade_id, trade_legs in groups.items():
            combined_mask = pd.Series(False, index=td_index)
            for d in trade_legs:
                gross = d["gross"]
                genuine_nan = gross.isna()
                mask = genuine_nan.reindex(td_index, fill_value=False)
                combined_mask = combined_mask | mask

            for d in trade_legs:
                for key, s in list(d.items()):
                    if not isinstance(s, pd.Series):
                        continue

                    s_aligned = s.reindex(td_index, fill_value=0.0)

                    if key.endswith("_ts"):
                        s_filled_original = s.ffill()
                        d[key] = s_filled_original.reindex(td_index, fill_value=0.0)
                        continue

                    is_pnl = (
                        key in {"gross", "cost", "net"}
                        or key.endswith("_pnl")
                    )
                    if not is_pnl:
                        continue

                    s_work = s_aligned.fillna(0.0)
                    cs = s_work.cumsum()
                    cs_valid = cs[~combined_mask]
                    adjusted_daily = cs_valid.diff()
                    if len(adjusted_daily) > 0:
                        adjusted_daily.iloc[0] = cs_valid.iloc[0]
                    new_s = pd.Series(0.0, index=td_index)
                    new_s[adjusted_daily.index] = adjusted_daily
                    d[key] = new_s

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

    def _get_daily_series(
        self, leg_data: list[dict], key: str, fx_rates: dict | None = None,
    ) -> pd.Series:
        if not leg_data:
            return pd.Series(dtype=float)

        cache_key = (id(leg_data), key, self._missing_mode)
        cached = self._agg_cache.get(cache_key)
        if cached is not None:
            return cached

        td_index = pd.Index(self._trading_days, dtype=object)

        if self._missing_mode == "per_leg":
            result = pd.concat(
                [d[key].rename(d["leg_id"]) for d in leg_data], axis=1
            )
            self._agg_cache[cache_key] = result
            return result

        filled = [d[key].fillna(0.0).reindex(td_index, fill_value=0.0) for d in leg_data]
        result = sum(filled)

        self._agg_cache[cache_key] = result
        return result

    def _get_cumulative_series(
        self, leg_data: list[dict], key: str
    ) -> pd.Series:
        cache_key = ("cum", id(leg_data), key)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        daily = self._get_daily_series(leg_data, key)
        result = daily.fillna(0.0).cumsum()
        self._cache[cache_key] = result
        return result

    def _get_trade_totals(
        self, leg_data: list[dict]
    ) -> dict[str, dict[str, float]]:
        cache_key = ("trade_totals", id(leg_data))
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        groups = self._group_legs_by_trade(leg_data)
        result: dict[str, dict[str, float]] = {}
        for trade_id, legs in groups.items():
            gross_total = sum(d["gross"].fillna(0.0).sum() for d in legs)
            cost_total = sum(d["cost"].fillna(0.0).sum() for d in legs)
            net_total = sum(d["net"].fillna(0.0).sum() for d in legs)
            result[trade_id] = {
                "gross": gross_total,
                "cost": cost_total,
                "net": net_total,
            }

        self._cache[cache_key] = result
        return result

    def _build_equity_curve(
        self, config, leg_data: list[dict], fx_rates: dict | None,
        output_name: str, results: dict,
    ):
        cfg = self._normalize_config(config)
        include = cfg.get("include")

        cols = {}
        if include is None or "gross" in include:
            cols["gross"] = self._get_cumulative_series(leg_data, "gross")
        if include is None or "cost" in include:
            cols["cost"] = self._get_cumulative_series(leg_data, "cost")
        if include is None or "net" in include:
            cols["net"] = self._get_cumulative_series(leg_data, "net")

        df = pd.DataFrame(cols)
        if not df.empty:
            results[output_name] = df

    def _build_trade_summary(
        self, config, trades: list, leg_data: list[dict],
        fx_rates: dict | None, output_name: str, results: dict,
    ):
        cfg = self._normalize_config(config)
        include = cfg.get("include")

        totals = self._get_trade_totals(leg_data)

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

        want_all = include is None

        metrics = {}
        for label in ("gross", "net"):
            # --- sharpe ---
            if want_all or f"sharpe_{label}" in (include or []):
                s = self._get_daily_series(leg_data, label)
                ann_ret = s.mean() * annualization
                ann_vol = s.std() * np.sqrt(annualization)
                metrics[f"sharpe_{label}"] = ann_ret / ann_vol if ann_vol > 0 else 0.0

            # --- max_drawdown ---
            if want_all or f"max_drawdown_{label}" in (include or []):
                cum = self._get_cumulative_series(leg_data, label)
                running_max = cum.cummax()
                drawdown = cum - running_max
                metrics[f"max_drawdown_{label}"] = drawdown.min()

            # --- annualized_return ---
            if want_all or f"annualized_return_{label}" in (include or []):
                s = self._get_daily_series(leg_data, label)
                metrics[f"annualized_return_{label}"] = s.mean() * annualization

            # --- calmar ---
            if want_all or f"calmar_{label}" in (include or []):
                s = self._get_daily_series(leg_data, label)
                cum = self._get_cumulative_series(leg_data, label)
                running_max = cum.cummax()
                dd = cum - running_max
                mdd = dd.min()
                ann_ret = s.mean() * annualization
                metrics[f"calmar_{label}"] = ann_ret / abs(mdd) if mdd != 0 else 0.0

            # --- hit_ratio ---
            if want_all or f"hit_ratio_{label}" in (include or []):
                totals = self._get_trade_totals(leg_data)
                tlist = list(totals.values())
                if tlist:
                    pos = sum(1 for t in tlist if t[label] > 0) / len(tlist)
                else:
                    pos = 0.0
                metrics[f"hit_ratio_{label}"] = pos

        if metrics:
            results[output_name] = pd.DataFrame([metrics])

    def _build_hit_ratio(
        self, config, leg_data: list[dict], fx_rates: dict | None,
        output_name: str, results: dict,
    ):
        cfg = self._normalize_config(config)
        timeframe = cfg.get("timeframe", "yearly")
        include = cfg.get("include")

        gross = self._get_daily_series(leg_data, "gross")
        net = self._get_daily_series(leg_data, "net")

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

        if include is None or "gross" in include:
            gross_cum = self._get_cumulative_series(leg_data, "gross")
            dd_df = self._compute_drawdown_table_from_cum(gross_cum, top_n)
            if dd_df is not None:
                results[f"{output_name}_gross"] = dd_df

        if include is None or "net" in include:
            net_cum = self._get_cumulative_series(leg_data, "net")
            dd_df = self._compute_drawdown_table_from_cum(net_cum, top_n)
            if dd_df is not None:
                results[f"{output_name}_net"] = dd_df

    def _compute_drawdown_table_from_cum(
        self, cumulative: pd.Series, top_n: int
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
