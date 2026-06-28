"""
Statistical normalization helpers — the quant layer.

Institutional signals are read in *relative* terms: a level matters only against
its own history. These helpers convert raw series into rolling z-scores and
percentile ranks on a strictly point-in-time basis (each value ranked only
against values up to and including itself — no look-ahead).
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def percentile_rank(value: float | None, history: pd.Series | list) -> float | None:
    """Percentile (0-100) of ``value`` within ``history`` (inclusive)."""
    if value is None:
        return None
    s = pd.Series(history, dtype=float).dropna()
    if s.empty:
        return None
    return round(float((s <= value).mean()) * 100, 1)


def zscore(value: float | None, history: pd.Series | list) -> float | None:
    """Z-score of ``value`` vs the mean/std of ``history``."""
    if value is None:
        return None
    s = pd.Series(history, dtype=float).dropna()
    if len(s) < 3:
        return None
    sd = float(s.std(ddof=0))
    if sd == 0:
        return 0.0
    return round((value - float(s.mean())) / sd, 2)


def rolling_percentile(series: pd.Series, window: int | None = None) -> pd.Series:
    """Point-in-time percentile rank of each value vs prior values (inclusive).

    With ``window`` set, uses a trailing window; otherwise expanding from the
    start. No look-ahead: position i is ranked only against positions <= i.
    """
    s = pd.Series(series, dtype=float)
    out = np.full(len(s), np.nan)
    vals = s.values
    for i in range(len(s)):
        lo = 0 if window is None else max(0, i - window + 1)
        win = vals[lo:i + 1]
        win = win[~np.isnan(win)]
        if win.size:
            out[i] = (win <= vals[i]).mean() * 100
    return pd.Series(out, index=s.index)


def percentile_label(p: float | None) -> str:
    """Plain-English bucket for a 0-100 percentile."""
    if p is None:
        return "—"
    if p >= 90:
        return "extreme high"
    if p >= 75:
        return "elevated"
    if p <= 10:
        return "extreme low"
    if p <= 25:
        return "depressed"
    return "mid-range"
