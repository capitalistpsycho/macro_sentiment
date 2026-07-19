"""
GDP-weighted financial conditions index (GS-style) — a market-based complement to
the Chicago Fed NFCI the dashboard already shows.

The NFCI is a weekly 105-variable statistical composite. Goldman's FCI instead
weights a handful of market variables (policy rate, long yields, credit spreads,
equities, the trade-weighted dollar) by their estimated contribution to GDP
growth, giving a *daily*, forward-looking read (a ~1-point tightening ≈ ~1pp less
growth over the next year). We approximate it: z-score each market input against
its own history, orient so positive = tighter, and combine with growth-contribution
weights. All inputs are already cached (FRED + prices).
"""

from __future__ import annotations

import pandas as pd

from data import fred, store
from data.stats import zscore

# label -> (weight, sign)  sign=+1 → higher value tightens conditions
_WEIGHTS = {
    "Short rate":      (0.15, +1),
    "Long real yield": (0.20, +1),
    "Credit (HY OAS)": (0.25, +1),
    "Equity trend":    (0.25, -1),   # rising equities loosen conditions
    "Broad USD":       (0.15, +1),
}


def _z(s: pd.Series, sign: int) -> float | None:
    s = s.dropna()
    if len(s) < 30:
        return None
    z = zscore(float(s.iloc[-1]), s)
    return None if z is None else z * sign


def gs_style_fci(as_of: str | None = None) -> dict:
    """Daily GDP-weighted financial-conditions composite (positive = tighter)."""
    spy = store.series("SPY", as_of=as_of)
    equity_trend = pd.Series(dtype=float)
    if not spy.empty:
        c = spy.set_index("date")["close"].astype(float)
        equity_trend = (c / c.rolling(126).mean() - 1.0).dropna()  # vs 6m trend

    inputs = {
        "Short rate":      _z(fred.series("UST:3M", as_of=as_of, point_in_time=False), +1),
        "Long real yield": _z(fred.series("DFII10", as_of=as_of), +1),
        "Credit (HY OAS)": _z(fred.series("BAMLH0A0HYM2", as_of=as_of), +1),
        "Equity trend":    _z(equity_trend, -1),
        "Broad USD":       _z(fred.series("DTWEXBGS", as_of=as_of), +1),
    }
    contrib, wsum = {}, 0.0
    composite = 0.0
    for name, (w, _) in _WEIGHTS.items():
        z = inputs.get(name)
        if z is None:
            continue
        contrib[name] = round(z * w, 3)
        composite += z * w
        wsum += w
    if wsum == 0:
        return {}
    composite = composite / wsum  # reweight for any missing inputs
    tone = ("Tight" if composite > 0.5 else "Slightly tight" if composite > 0.1 else
            "Neutral" if composite > -0.1 else "Slightly loose" if composite > -0.5 else "Loose")
    return {
        "composite": round(composite, 2),
        "tone": tone,
        "contributions": contrib,
        "growth_impulse": round(-composite, 2),  # tighter ⇒ negative growth impulse
    }
