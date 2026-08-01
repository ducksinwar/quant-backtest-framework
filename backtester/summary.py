from __future__ import annotations

import pandas as pd


class Summary:
    def __init__(self, spec: dict):
        self._spec = spec
        self._reports_spec = spec.get("reports", {})
        self._missing_mode = spec.get("missing_data_mode", "any")
        self._capital = None
        self._output = spec.get("output")

    @property
    def capital(self):
        return self._capital

    def generate(
        self,
        trade_history: list,
        cost_model,
        trading_days: list[str],
        fx_rates: dict[str, pd.Series] | None = None,
        capital: float | None = None,
    ) -> dict | None:
        self._trading_days = trading_days
        self._agg_cache: dict[tuple, pd.Series] = {}
        self._cache: dict[tuple, object] = {}
        self._capital = capital
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

        return results

    def _extract_leg_data(
        self, trade_history: list, cost_map: dict,
        trading_days: list[str],
    ) -> list[dict]:

        rows = []
        for trade in trade_history:
            for structure in trade.structure_history:
                for leg_state in structure.legs:
                    pnl_list = leg_state.daily_total_pnl
                    if len(pnl_list) > 0:
                        entry_date = structure.original_entry_date
                        if not entry_date:
                            raise ValueError(
                                f"Structure {structure.structure_id} "
                                f"(trade {trade.trade_id}) is missing "
                                f"original_entry_date; cannot align leg "
                                f"{leg_state.leg_id} P&L."
                            )
                        entry_idx = trading_days.index(entry_date)
                        pnl_start = entry_idx

                        if trade.exit_date is not None:
                            pnl_end = trading_days.index(trade.exit_date)
                        else:
                            pnl_end = len(trading_days) - 1

                        pnl_dates = trading_days[pnl_start:pnl_end + 1]

                        if len(pnl_dates) != len(pnl_list):
                            raise ValueError(
                                f"P&L length mismatch for leg {leg_state.leg_id} "
                                f"(trade {trade.trade_id}, structure "
                                f"{structure.structure_id}): expected "
                                f"{len(pnl_dates)} day(s) "
                                f"[{entry_date} -> "
                                f"{trade.exit_date or trading_days[-1]}], "
                                f"but leg has {len(pnl_list)} P&L entries."
                            )
                        gross = pd.Series(pnl_list, index=pnl_dates, dtype=float)
                    else:
                        gross = pd.Series(pnl_list, dtype=float)

                    cost_series = cost_map.get(leg_state.leg_id, pd.Series(dtype=float))
                    cost_aligned = cost_series.reindex(
                        gross.index, fill_value=0.0,
                    )

                    net = gross - cost_aligned

                    rows.append({
                        "trade": trade,
                        "trade_id": trade.trade_id,
                        "structure": structure,
                        "structure_id": structure.structure_id,
                        "leg": leg_state,
                        "leg_id": leg_state.leg_id,
                        "ticker": leg_state.contract.ticker,
                        "currency": leg_state.contract.currency,
                        "multiplier": leg_state.contract.multiplier,
                        "tags": leg_state.tags,
                        "params": leg_state.contract.params,
                        "gross": gross,
                        "cost": cost_aligned,
                        "net": net,
                    })
                    for measure, ts_list in leg_state.valuation_data.items():
                        key = f"{measure}_ts"
                        if len(ts_list) > 0:
                            rows[-1][key] = pd.Series(
                                ts_list, index=gross.index, dtype=float,
                            )
                        else:
                            rows[-1][key] = pd.Series(ts_list, dtype=float)
                    for key, ts_list in leg_state.pricing_inputs.items():
                        if len(ts_list) > 0:
                            rows[-1][key] = pd.Series(
                                ts_list, index=gross.index, dtype=float,
                            )
                        else:
                            rows[-1][key] = pd.Series(ts_list, dtype=float)
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
                series_keys = [k for k, v in d.items() if isinstance(v, pd.Series)]

                for key in series_keys:
                    s = d[key]

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

                    s_aligned = s.reindex(td_index, fill_value=0.0)

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
        from backtester.reports import REPORTS

        report_cls = REPORTS.get(report_name)
        if report_cls is None:
            return
        report = report_cls()
        dfs = report.build(self, trades, leg_data, config, fx_rates, output_name)
        results.update(dfs)

    def get_daily_series(
        self, leg_data: list[dict], key: str, fx_rates: dict | None = None,
    ) -> pd.Series:
        if not leg_data:
            return pd.Series(dtype=float)

        legs_key = tuple(sorted(d['leg_id'] for d in leg_data))
        cache_key = (legs_key, key, self._missing_mode)
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

    def get_cumulative_series(
        self, leg_data: list[dict], key: str
    ) -> pd.Series:
        legs_key = tuple(sorted(d['leg_id'] for d in leg_data))
        cache_key = ("cum", legs_key, key)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        daily = self.get_daily_series(leg_data, key)
        result = daily.fillna(0.0).cumsum()
        self._cache[cache_key] = result
        return result

    def get_trade_totals(
        self, leg_data: list[dict]
    ) -> dict[str, dict[str, float]]:
        legs_key = tuple(sorted(d['leg_id'] for d in leg_data))
        cache_key = ("trade_totals", legs_key)
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

    @staticmethod
    def _normalize_config(config) -> dict:
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
            with pd.ExcelWriter(path) as writer:
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
