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


# ── Style / factor / region performance conditioned on the macro regime ───────

REGIME_UNIVERSES = {
    "Styles / Factors": [
        ("IWF", "Growth"), ("IWD", "Value"), ("MTUM", "Momentum"),
        ("QUAL", "Quality"), ("USMV", "Low Vol"), ("IWM", "Small Cap"),
    ],
    "Regions": [
        ("EEM", "Emerging Mkts"), ("VEA", "Developed ex-US"), ("VGK", "Europe"),
        ("EWJ", "Japan"), ("MCHI", "China"), ("EWC", "Canada"), ("^GSPTSE", "S&P/TSX"),
    ],
}


def regime_performance(universe: list[tuple[str, str]], regime_col: str = "macro_regime",
                       horizon: int = 21, benchmark: str = "SPY") -> dict:
    """Per-regime forward performance of each instrument in ``universe``.

    For every regime in the signal history, measures each instrument's average
    forward ``horizon``-day return, its *excess* over ``benchmark`` (the more
    telling number — it strips out the market's general direction in that
    regime) and its hit rate. Overlapping daily windows ⇒ descriptive, not iid.

    Returns {regime: {label: {mean, excess, hit, n}}, "_order", "_days", "_horizon"}.
    """
    ms = store.signal_history("macro_signals")
    if ms.empty or regime_col not in ms.columns:
        return {}
    ms = ms[["date", regime_col]].dropna()
    ms = ms.set_index(pd.to_datetime(ms["date"]))

    bench_fwd = _forward_returns(benchmark, horizon)
    fwd = {tk: _forward_returns(tk, horizon) for tk, _ in universe}

    out: dict = {}
    counts: dict = {}
    for regime, grp in ms.groupby(regime_col):
        dates = grp.index
        counts[regime] = len(dates)
        out[regime] = {}
        for tk, label in universe:
            f = fwd.get(tk)
            vals = f.reindex(dates).dropna() if f is not None and not f.empty else pd.Series(dtype=float)
            if len(vals) < 3:
                out[regime][label] = {"mean": None, "excess": None, "hit": None, "n": int(len(vals))}
                continue
            common = vals.index.intersection(bench_fwd.index)
            excess = None
            if len(common) >= 3:
                excess = float((vals.reindex(common) - bench_fwd.reindex(common)).mean())
            out[regime][label] = {
                "mean": round(float(vals.mean()), 2),
                "excess": round(excess, 2) if excess is not None else None,
                "hit": round(float((vals > 0).mean()) * 100, 0),
                "n": int(len(vals)),
            }
    out["_order"] = sorted(counts, key=lambda r: counts[r], reverse=True)
    out["_days"] = counts
    out["_horizon"] = horizon
    return out


def regime_risk_profile(regime_col: str = "macro_regime", horizon: int = 21,
                        ticker: str = "SPY") -> dict:
    """Per-regime tail/risk profile of forward returns — mean, vol, CVaR, skew.

    Desks manage to a risk budget, not just an average: this reports the shape of
    the forward-return distribution conditional on each regime (downside as well
    as central tendency). Overlapping windows ⇒ descriptive.
    """
    ms = store.signal_history("macro_signals")
    if ms.empty or regime_col not in ms.columns:
        return {}
    ms = ms[["date", regime_col]].dropna()
    ms = ms.set_index(pd.to_datetime(ms["date"]))
    fwd = _forward_returns(ticker, horizon)

    out, counts = {}, {}
    for regime, grp in ms.groupby(regime_col):
        vals = fwd.reindex(grp.index).dropna()
        counts[regime] = len(vals)
        if len(vals) < 5:
            out[regime] = {"mean": None, "vol": None, "cvar5": None, "worst": None,
                           "skew": None, "hit": None, "n": int(len(vals))}
            continue
        v = np.sort(vals.to_numpy(dtype=float))
        tail_n = max(1, int(len(v) * 0.05))
        out[regime] = {
            "mean": round(float(v.mean()), 2),
            "vol": round(float(v.std(ddof=1)), 2),
            "cvar5": round(float(v[:tail_n].mean()), 2),   # mean of worst 5%
            "worst": round(float(v.min()), 2),
            "skew": round(float(pd.Series(v).skew()), 2),
            "hit": round(float((vals > 0).mean()) * 100, 0),
            "n": int(len(vals)),
        }
    out["_order"] = sorted(counts, key=lambda r: counts[r], reverse=True)
    out["_horizon"] = horizon
    out["_ticker"] = ticker
    return out
