"""
Flow proxies. True ETF creation/redemption flows aren't on yfinance, so we proxy
'where money is going' with relative-strength ratios and momentum rankings.
"""

from __future__ import annotations

import pandas as pd

from data import store


def relative_strength(num: str, den: str, days: int = 252) -> pd.Series:
    """Ratio series rebased to 100 at the window start."""
    r = store.ratio(num, den, days=days).dropna()
    if r.empty:
        return r
    return r / r.iloc[0] * 100


def momentum_ranking(items: list[tuple[str, str]], field: str = "return_3m") -> list[dict]:
    """Rank (ticker,label) pairs by a momentum field, descending."""
    m = store.latest_metrics()
    rows = []
    for tk, lbl in items:
        v = m.get(tk, {}).get(field)
        rows.append({"ticker": tk, "label": lbl, "value": v if isinstance(v, (int, float)) else None})
    rows.sort(key=lambda r: (r["value"] is not None, r["value"] or -1e9), reverse=True)
    return rows
