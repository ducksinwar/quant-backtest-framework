from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from backtester.summary import Summary

CAPITAL_DEPENDENT_METRICS = {"annualized_return", "return_pct", "max_drawdown_pct"}


class BaseMetricCalculator(ABC):
    @abstractmethod
    def compute(
        self,
        summary: Summary,
        label: str,
        context: dict,
        annualization: int,
    ) -> float:
        ...


class ReturnCalculator(BaseMetricCalculator):
    def compute(self, summary, label, context, annualization):
        return float(context["daily"].sum())


class ReturnPctCalculator(BaseMetricCalculator):
    def compute(self, summary, label, context, annualization):
        capital = summary.capital
        if capital is None or capital == 0:
            raise ValueError(
                f"ReturnPctCalculator requires capital to be set; got {capital!r}"
            )
        return float(context["daily"].sum()) / capital * 100


class SharpeCalculator(BaseMetricCalculator):
    def compute(self, summary, label, context, annualization):
        daily = context["daily"]
        ann_vol = daily.std() * np.sqrt(annualization)
        if ann_vol == 0:
            return 0.0
        return float(daily.mean() * annualization / ann_vol)


class MaxDrawdownCalculator(BaseMetricCalculator):
    def compute(self, summary, label, context, annualization):
        cumulative = context["cumulative"]
        running_max = cumulative.cummax()
        drawdown = cumulative - running_max
        mdd = float(drawdown.min())
        context["mdd"] = mdd
        return mdd


class MaxDrawdownPctCalculator(BaseMetricCalculator):
    def compute(self, summary, label, context, annualization):
        capital = summary.capital
        if capital is None or capital == 0:
            raise ValueError(
                f"MaxDrawdownPctCalculator requires capital to be set; got {capital!r}"
            )
        mdd = context.get("mdd")
        if mdd is None:
            cumulative = context["cumulative"]
            running_max = cumulative.cummax()
            drawdown = cumulative - running_max
            mdd = float(drawdown.min())
            context["mdd"] = mdd
        return mdd / capital * 100


class AnnualizedReturnCalculator(BaseMetricCalculator):
    def compute(self, summary, label, context, annualization):
        capital = summary.capital
        if capital is None or capital == 0:
            raise ValueError(
                f"AnnualizedReturnCalculator requires capital to be set; got {capital!r}"
            )
        daily = context["daily"]
        return float(daily.mean() * annualization / capital * 100)


class CalmarCalculator(BaseMetricCalculator):
    def compute(self, summary, label, context, annualization):
        daily = context["daily"]
        cumulative = context["cumulative"]
        mdd = context.get("mdd")
        if mdd is None:
            running_max = cumulative.cummax()
            drawdown = cumulative - running_max
            mdd = float(drawdown.min())
            context["mdd"] = mdd
        if mdd == 0:
            return 0.0
        return float(daily.mean() * annualization / abs(mdd))


class HitRatioCalculator(BaseMetricCalculator):
    def compute(self, summary, label, context, annualization):
        totals = context["totals"]
        tlist = list(totals.values())
        if not tlist:
            return 0.0
        return sum(1 for t in tlist if t[label] > 0) / len(tlist)


METRIC_CALCULATORS: dict[str, BaseMetricCalculator] = {
    "return": ReturnCalculator(),
    "return_pct": ReturnPctCalculator(),
    "sharpe": SharpeCalculator(),
    "max_drawdown": MaxDrawdownCalculator(),
    "max_drawdown_pct": MaxDrawdownPctCalculator(),
    "annualized_return": AnnualizedReturnCalculator(),
    "calmar": CalmarCalculator(),
    "hit_ratio": HitRatioCalculator(),
}


def _compute_metrics_row(
    daily,
    cumulative,
    totals,
    capital,
    include,
    annualization,
    summary,
    label,
) -> dict[str, float]:
    if include is None:
        names = [n for n in METRIC_CALCULATORS]
    else:
        names = list(include)
    if capital is None or capital == 0:
        names = [n for n in names if n not in CAPITAL_DEPENDENT_METRICS]
    names = sorted(names, key=lambda m: m.endswith("_pct"))
    context = {"daily": daily, "cumulative": cumulative, "totals": totals}
    results = {}
    for base_name in names:
        calc = METRIC_CALCULATORS.get(base_name)
        if calc is not None:
            results[base_name] = calc.compute(summary, label, context, annualization)
    return results
