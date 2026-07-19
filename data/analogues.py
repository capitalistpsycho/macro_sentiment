"""
Historical-analogue engine — "today's macro state most resembles [past date]".

Regime-aware / analogue-based methods condition on historically similar periods
rather than a static model, and retrieval-augmented macro forecasting that does
this has been shown to outperform non-conditioned baselines out-of-sample. Here we
build a standardized macro state vector per day from the signal history, find the
nearest past states (excluding the recent window so we don't just match yesterday),
and report what the market did next — a cheap, transparent analogue lookup.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from data import store

_FEATURES = ["growth_score", "inflation_score", "risk_score", "breadth",
             "vix_level", "yield_curve_spread", "credit_spread_proxy"]


def _fwd_return(close: pd.Series, d: pd.Timestamp, horizon: int) -> float | None:
    pos = close.index.searchsorted(d)
    if pos >= len(close) or pos + horizon >= len(close):
        return None
    return round(float(close.iloc[pos + horizon] / close.iloc[pos] - 1.0) * 100, 2)


def find_analogues(k: int = 4, exclude_recent: int = 63, horizon: int = 21) -> dict:
    ms = store.signal_history("macro_signals")
    if ms.empty:
        return {}
    feats = [f for f in _FEATURES if f in ms.columns]
    df = ms.dropna(subset=feats).reset_index(drop=True)
    if len(df) < 40:
        return {}
    X = df[feats].to_numpy(dtype=float)
    mu, sd = X.mean(axis=0), X.std(axis=0)
    sd[sd == 0] = 1.0
    Z = (X - mu) / sd
    today = Z[-1]

    pool = max(1, len(Z) - exclude_recent)
    dist = np.sqrt(((Z[:pool] - today) ** 2).sum(axis=1))
    order = np.argsort(dist)[:k]

    spy = store.series("SPY")
    close = spy.set_index("date")["close"].astype(float) if not spy.empty else pd.Series(dtype=float)

    out = []
    for i in order:
        d = pd.to_datetime(df["date"].iloc[i])
        out.append({
            "date": d.strftime("%Y-%m-%d"),
            "similarity": round(float(1 / (1 + dist[i])) * 100, 0),
            "regime": df["macro_regime"].iloc[i] if "macro_regime" in df else "—",
            "spy_fwd": _fwd_return(close, d, horizon) if not close.empty else None,
        })
    fwds = [o["spy_fwd"] for o in out if o["spy_fwd"] is not None]
    return {
        "analogues": out,
        "features": feats,
        "avg_fwd": round(sum(fwds) / len(fwds), 2) if fwds else None,
        "horizon_days": horizon,
    }
