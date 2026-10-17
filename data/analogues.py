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


def _stock_bond_corr(window: int = 63) -> pd.Series:
    """Rolling SPY/TLT daily-return correlation — a regime feature in Mulliner,
    Harvey et al. (Man AHL, 2025): positive = stocks and bonds fall together."""
    a, b = store.series("SPY"), store.series("TLT")
    if a.empty or b.empty:
        return pd.Series(dtype=float)
    px = pd.DataFrame({"a": a.set_index("date")["close"], "b": b.set_index("date")["close"]}).dropna()
    r = np.log(px.astype(float)).diff()
    return r["a"].rolling(window).corr(r["b"]).dropna()


def find_analogues(k: int = 4, exclude_recent: int = 63, horizon: int = 21) -> dict:
    ms = store.signal_history("macro_signals")
    if ms.empty:
        return {}
    sbc = _stock_bond_corr()
    if not sbc.empty:
        ms = ms.copy()
        ms["stock_bond_corr"] = pd.to_datetime(ms["date"]).map(sbc)
    feats = [f for f in _FEATURES + ["stock_bond_corr"] if f in ms.columns]
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

    def spaced(ranked, gap: int = 10):
        """Top-k picks at least `gap` sessions apart — adjacent days are one episode."""
        picks = []
        for i in ranked:
            if all(abs(int(i) - j) >= gap for j in picks):
                picks.append(int(i))
            if len(picks) == k:
                break
        return picks
    order = spaced(np.argsort(dist))

    spy = store.series("SPY")
    close = spy.set_index("date")["close"].astype(float) if not spy.empty else pd.Series(dtype=float)

    def rows(idx):
        out = []
        for i in idx:
            d = pd.to_datetime(df["date"].iloc[i])
            out.append({
                "date": d.strftime("%Y-%m-%d"),
                "similarity": round(float(1 / (1 + dist[i])) * 100, 0),
                "regime": df["macro_regime"].iloc[i] if "macro_regime" in df else "—",
                "spy_fwd": _fwd_return(close, d, horizon) if not close.empty else None,
            })
        fw = [o["spy_fwd"] for o in out if o["spy_fwd"] is not None]
        return out, (round(sum(fw) / len(fw), 2) if fw else None)

    out, avg = rows(order)
    # Anti-analogues: the least similar past states (Man AHL "anti-regimes") — what
    # followed conditions most *unlike* today, a contrast for the analogue read.
    anti, anti_avg = rows(spaced(np.argsort(dist)[::-1]))
    return {
        "analogues": out,
        "anti": anti,
        "features": feats,
        "avg_fwd": avg,
        "anti_avg_fwd": anti_avg,
        "horizon_days": horizon,
    }
