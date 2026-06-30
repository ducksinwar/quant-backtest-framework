from __future__ import annotations

import numpy as np
import pandas as pd


def compute_return(daily: pd.Series) -> float:
    return daily.sum()


def compute_return_pct(daily: pd.Series, capital: float) -> float:
    return daily.sum() / capital * 100


def compute_sharpe(daily: pd.Series, annualization: int) -> float:
    ann_vol = daily.std() * np.sqrt(annualization)
    if ann_vol == 0:
        return 0.0
    return daily.mean() * annualization / ann_vol


def compute_max_drawdown(cumulative: pd.Series) -> float:
    running_max = cumulative.cummax()
    drawdown = cumulative - running_max
    return drawdown.min()


def compute_max_drawdown_pct(
    cumulative: pd.Series, capital: float, mdd: float | None = None
) -> float:
    if mdd is None:
        mdd = compute_max_drawdown(cumulative)
    return mdd / capital * 100


def compute_calmar(
    daily: pd.Series, cumulative: pd.Series, annualization: int
) -> float:
    mdd = compute_max_drawdown(cumulative)
    if mdd == 0:
        return 0.0
    return daily.mean() * annualization / abs(mdd)


def compute_annualized_return(
    daily: pd.Series, annualization: int, capital: float
) -> float:
    return daily.mean() * annualization / capital * 100
