"""
Valuation-based long-run expected returns — a GMO/mean-reversion style view.

Tactical regime signals say what to do now; strategic allocators (GMO, Research
Affiliates) anchor on the fact that valuations mean-revert, so a market far above
its long-term trend has a lower forward return. We approximate this cheaply: fit a
log-linear trend to ~15 years of the index, measure today's deviation from trend,
and map that deviation to an expected annualised return via the historical
relationship between deviation and the subsequent multi-year return. Self-contained
(one yfinance history pull), cached weekly.
"""

from __future__ import annotations

import logging

import numpy as np

logger = logging.getLogger(__name__)


def _fit(index: str = "^GSPC", years: int = 16, horizon_months: int = 60) -> dict:
    try:
        import yfinance as yf
        df = yf.download(index, period=f"{years}y", interval="1mo",
                         auto_adjust=True, progress=False)
        if df is None or df.empty:
            return {}
        close = df["Close"]
        if hasattr(close, "columns"):
            close = close.iloc[:, 0]
        close = close.dropna()
        if len(close) < 120:
            return {}
        y = np.log(close.to_numpy(dtype=float))
        x = np.arange(len(y), dtype=float)
        b1, b0 = np.polyfit(x, y, 1)             # log-linear trend
        trend = b0 + b1 * x
        dev = y - trend                          # log deviation from trend
        dev_now = float(dev[-1])

        # Historical map: deviation at t vs realised annualised return t→t+h.
        h = horizon_months
        if len(y) > h + 12:
            fwd = (y[h:] - y[:-h]) / (h / 12.0)   # annualised log return
            d0 = dev[:-h]
            if len(d0) > 24 and np.std(d0) > 1e-6:
                slope, intercept = np.polyfit(d0, fwd, 1)
                exp_ann = (slope * dev_now + intercept)
                exp_ann = float(np.expm1(exp_ann) * 100)  # back to simple %
            else:
                exp_ann = None
        else:
            exp_ann = None

        pct_above = float(np.expm1(dev_now) * 100)
        return {
            "index": index,
            "pct_from_trend": round(pct_above, 1),
            "exp_annual_return": round(exp_ann, 1) if exp_ann is not None else None,
            "horizon_years": round(horizon_months / 12),
            "years_fit": years,
        }
    except Exception as exc:
        logger.warning("valuation fit failed: %s", exc)
        return {}


def valuation_outlook() -> dict:
    r = _fit("^GSPC")
    if not r:
        return {}
    pa = r["pct_from_trend"]
    r["read"] = ("richly valued vs trend — muted long-run returns implied" if pa > 15 else
                 "cheap vs trend — above-average long-run returns implied" if pa < -15 else
                 "near long-term trend")
    return r
