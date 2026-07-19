"""
Signal track record — does the MacroCompass / risk score actually predict returns?

A dashboard that grades itself earns more trust than one that just asserts. For
each headline signal we measure the information coefficient (rank correlation of
the signal with the subsequent S&P forward return) and the spread between the
forward returns that followed high vs low readings. Signals are point-in-time (the
backfill uses only data available at each date, incl. the FRED publication-lag
discipline), so this isn't look-ahead — but overlapping windows make it descriptive,
not an iid backtest.
"""

from __future__ import annotations

import pandas as pd

from data import store


def _fwd(ticker: str = "SPY", horizon: int = 21) -> pd.Series:
    s = store.series(ticker)
    if s.empty:
        return pd.Series(dtype=float)
    c = s.set_index("date")["close"].astype(float)
    return ((c.shift(-horizon) / c - 1.0) * 100).dropna()


def signal_track_record(horizon: int = 21) -> dict:
    fwd = _fwd("SPY", horizon)
    if fwd.empty:
        return {}
    out: dict = {"_horizon": horizon}
    specs = [
        ("MacroCompass", store.signal_history("signal_scores"), "compass_score"),
        ("Risk-on/off", store.signal_history("macro_signals"), "risk_score"),
    ]
    for name, df, col in specs:
        if df.empty or col not in df.columns:
            continue
        d = df.dropna(subset=[col]).copy()
        d = d.set_index(pd.to_datetime(d["date"]))
        j = pd.DataFrame({"sig": d[col]}).join(fwd.rename("fwd"), how="inner").dropna()
        if len(j) < 30:
            continue
        try:
            from scipy.stats import spearmanr
            ic = float(spearmanr(j["sig"], j["fwd"]).statistic)
        except Exception:
            ic = float(j["sig"].corr(j["fwd"], method="spearman"))
        q1, q2 = j["sig"].quantile([1 / 3, 2 / 3])
        hi, lo = j[j["sig"] >= q2]["fwd"], j[j["sig"] <= q1]["fwd"]
        out[name] = {
            "ic": round(ic, 2),
            "n": int(len(j)),
            "high_mean": round(float(hi.mean()), 2),
            "high_hit": round(float((hi > 0).mean()) * 100),
            "low_mean": round(float(lo.mean()), 2),
            "low_hit": round(float((lo > 0).mean()) * 100),
            "spread": round(float(hi.mean() - lo.mean()), 2),
        }
    return out
