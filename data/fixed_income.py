"""Fixed-income helpers: yield curve construction and curve-spread history."""

from __future__ import annotations

import pandas as pd

from data import store

# Maturity points available via yfinance yield tickers
CURVE_POINTS = [
    ("^IRX", "3M",  0.25),
    ("^FVX", "5Y",  5.0),
    ("^TNX", "10Y", 10.0),
    ("^TYX", "30Y", 30.0),
]


def current_curve() -> pd.DataFrame:
    """Current yields plus the level 3 months (~63 trading days) ago."""
    rows = []
    for tk, lbl, mat in CURVE_POINTS:
        s = store.series(tk)
        if s.empty:
            continue
        now = float(s["close"].iloc[-1])
        prev = float(s["close"].iloc[-63]) if len(s) > 63 else None
        rows.append({"label": lbl, "maturity": mat, "yield_now": now, "yield_3m_ago": prev})
    return pd.DataFrame(rows)


def curve_spread_history(short="^IRX", long="^TNX", days: int = 504) -> pd.Series:
    """10y minus 3m spread time series (the dashboard's 2-10 proxy)."""
    w = store.closes([short, long], days=days).dropna()
    if w.empty:
        return pd.Series(dtype=float)
    return (w[long] - w[short]).dropna()


def credit_environment(metrics: dict) -> dict:
    """HYG vs TLT relative move as a credit-spread direction read."""
    def g(tk, f):
        v = metrics.get(tk, {}).get(f)
        return v if isinstance(v, (int, float)) else None
    hyg = g("HYG", "return_1m")
    tlt = g("TLT", "return_1m")
    direction = "—"
    if hyg is not None and tlt is not None:
        direction = "Tightening (risk-on)" if hyg > tlt else "Widening (risk-off)"
    return {"hyg_1m": hyg, "tlt_1m": tlt, "direction": direction}
