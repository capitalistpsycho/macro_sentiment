"""Commodity helpers: performance table and key cross-commodity ratios."""

from __future__ import annotations

import pandas as pd

from data import store, tickers as T


def performance_table() -> pd.DataFrame:
    """Spot commodities with returns and distance from 52-week high."""
    rows = []
    spot = [("GC=F", "Gold"), ("CL=F", "WTI Crude"), ("SI=F", "Silver"),
            ("HG=F", "Copper"), ("NG=F", "Natural Gas"), ("ZW=F", "Wheat")]
    m = store.latest_metrics()
    for tk, name in spot:
        row = m.get(tk, {})
        s = store.series(tk)
        hi = float(s["close"].max()) if not s.empty else None
        last = row.get("close")
        from_hi = ((last / hi - 1) * 100) if (hi and last) else None
        ytd = _ytd_return(s) if not s.empty else None
        rows.append({
            "ticker": tk, "name": name, "price": last,
            "return_1d": row.get("return_1d"), "return_1m": row.get("return_1m"),
            "return_3m": row.get("return_3m"), "ytd": ytd, "from_high": from_hi,
        })
    return pd.DataFrame(rows)


def _ytd_return(s: pd.DataFrame) -> float | None:
    if s.empty:
        return None
    s = s.copy()
    yr = s["date"].dt.year.max()
    jan = s[s["date"].dt.year == yr]
    if jan.empty:
        return None
    start = float(jan["close"].iloc[0])
    last = float(s["close"].iloc[-1])
    return (last / start - 1) * 100 if start else None


def oil_gold_ratio(days: int = 252) -> pd.Series:
    return store.ratio("CL=F", "GC=F", days=days)


def commodity_equity_ratio(days: int = 252) -> pd.Series:
    return store.ratio("DJP", "SPY", days=days)
