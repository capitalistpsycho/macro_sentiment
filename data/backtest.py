"""
Regime backtest — turns the regime label into evidence.

For each market regime in the signal history, measures what actually happened
next: the average forward return and hit rate (% positive) of the S&P 500 and
S&P/TSX over the following month and quarter. This is what lets a PM trust (or
discount) the current regime call rather than taking it on faith.

Forward windows overlap (daily observations), so treat hit rates as descriptive
context, not an iid backtest.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from data import store

HORIZONS = [(21, "1M"), (63, "3M")]
ASSETS = [("SPY", "S&P 500"), ("^GSPTSE", "S&P/TSX")]


def _forward_returns(ticker: str, horizon: int) -> pd.Series:
    """date -> forward `horizon`-trading-day return (%), indexed by date."""
    s = store.series(ticker)
    if s.empty:
        return pd.Series(dtype=float)
    close = s.set_index("date")["close"].astype(float)
    fwd = (close.shift(-horizon) / close - 1.0) * 100.0
    return fwd.dropna()


def regime_backtest(regime_col: str = "regime") -> dict:
    """Per-regime forward-return stats for each asset/horizon.

    Returns {regime: {asset_label: {horizon_label: {mean, hit, n}}}, "_order": [...]}.
    """
    ms = store.signal_history("macro_signals")
    if ms.empty or regime_col not in ms:
        return {}
    ms = ms[["date", regime_col]].dropna()
    ms = ms.set_index(pd.to_datetime(ms["date"]))

    fwd_cache = {(tk, h): _forward_returns(tk, h) for tk, _ in ASSETS for h, _ in HORIZONS}

    out: dict = {}
    counts: dict = {}
    for regime, grp in ms.groupby(regime_col):
        dates = grp.index
        out[regime] = {}
        counts[regime] = len(dates)
        for tk, alabel in ASSETS:
            out[regime][alabel] = {}
            for h, hlabel in HORIZONS:
                fwd = fwd_cache[(tk, h)]
                vals = fwd.reindex(dates).dropna()
                if len(vals) >= 3:
                    out[regime][alabel][hlabel] = {
                        "mean": round(float(vals.mean()), 2),
                        "hit": round(float((vals > 0).mean()) * 100, 0),
                        "n": int(len(vals)),
                    }
                else:
                    out[regime][alabel][hlabel] = {"mean": None, "hit": None, "n": int(len(vals))}
    out["_order"] = sorted(counts, key=lambda r: counts[r], reverse=True)
    out["_days"] = counts
    return out
