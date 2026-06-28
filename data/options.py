"""
Options-derived sentiment — the positioning-in-fear layer.

Polygon options are not available on the current plan, so put/call is computed
from yfinance option chains. The put/call ratio is a classic contrarian gauge:
a high ratio (heavy put buying) signals fear and often marks short-term lows,
while a very low ratio signals complacency. We aggregate the nearest expiries
by both volume (today's flow) and open interest (standing positioning).

    from data.options import put_call
    put_call("SPY")
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def put_call(ticker: str = "SPY", expiries: int = 3) -> dict:
    """Aggregate put/call ratios across the nearest `expiries` expirations."""
    try:
        import yfinance as yf
        t = yf.Ticker(ticker)
        exps = list(t.options or [])[:expiries]
        if not exps:
            return {}
        pv = cv = poi = coi = 0.0
        for e in exps:
            ch = t.option_chain(e)
            pv += float(ch.puts["volume"].fillna(0).sum())
            cv += float(ch.calls["volume"].fillna(0).sum())
            poi += float(ch.puts["openInterest"].fillna(0).sum())
            coi += float(ch.calls["openInterest"].fillna(0).sum())
        pc_vol = round(pv / cv, 2) if cv else None
        pc_oi = round(poi / coi, 2) if coi else None
        ref = pc_vol if pc_vol is not None else pc_oi
        if ref is None:
            return {}
        if ref >= 1.2:
            tone, read = "bullish", "Heavy put buying — fear elevated (contrarian bullish)"
        elif ref <= 0.7:
            tone, read = "bearish", "Call-heavy — complacency (contrarian caution)"
        else:
            tone, read = "neutral", "Balanced options positioning"
        return {
            "ticker": ticker, "pc_vol": pc_vol, "pc_oi": pc_oi,
            "expiries": exps, "tone": tone, "read": read,
        }
    except Exception as exc:
        logger.warning("put/call for %s failed: %s", ticker, exc)
        return {}
