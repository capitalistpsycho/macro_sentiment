"""
Cross-asset correlation-regime monitor.

When volatility compresses across equities, rates and FX at once, vol-target and
risk-parity funds mechanically lever into the same names — and when correlations
spike, diversification fails just when it's needed. Tracking the average pairwise
cross-asset correlation (and the stock–bond correlation specifically) flags both:
a positive stock–bond correlation is the 2022-style regime where 60/40 offers no
hedge; a rising average correlation is risk-off contagion.
"""

from __future__ import annotations

import numpy as np

from data import store

_BASKET = [("SPY", "Equities"), ("TLT", "Duration"), ("GLD", "Gold"),
           ("HYG", "Credit"), ("DX-Y.NYB", "USD")]


def correlation_state(window: int = 63) -> dict:
    closes = store.closes([t for t, _ in _BASKET])
    if closes.empty:
        return {}
    rets = closes.pct_change().dropna()
    if len(rets) < 30:
        return {}
    window = min(window, len(rets) - 5)

    recent = rets.tail(window)
    iu = np.triu_indices(recent.shape[1], 1)

    sb = None
    if "SPY" in recent and "TLT" in recent:
        sb = round(float(recent["SPY"].corr(recent["TLT"])), 2)

    avg = round(float(np.nanmean(recent.corr().values[iu])), 2)

    avg_prior = None
    if len(rets) >= window * 2:
        prior = rets.tail(window * 2).head(window)
        avg_prior = round(float(np.nanmean(prior.corr().values[iu])), 2)

    rising = avg_prior is not None and avg > avg_prior + 0.05
    return {
        "stock_bond": sb,
        "avg_pairwise": avg,
        "avg_prior": avg_prior,
        "rising": rising,
        "window": window,
        "read": _read(sb, avg, rising),
    }


def _read(sb, avg, rising) -> str:
    if sb is not None and sb > 0.1:
        return ("Stock–bond correlation is positive — bonds aren't hedging equities "
                "(2022-style regime); 60/40 offers little protection.")
    if rising:
        return "Cross-asset correlations are rising — diversification weakening, risk-off contagion."
    if avg < 0.1:
        return "Correlations low — healthy dispersion, diversification working."
    return "Correlations mid-range — no acute cross-asset stress."
