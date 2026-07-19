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


def iv_skew(ticker: str = "SPY") -> dict:
    """Downside IV skew: implied vol of a ~10% OTM put minus a ~10% OTM call.

    A positive skew means downside protection is bid richer than upside — the
    normal state, and a steepening skew flags rising crash/hedging demand. Uses
    the nearest expiry with enough strikes. Live yfinance chain, so it degrades
    to {} out of hours.
    """
    try:
        from datetime import datetime
        import yfinance as yf
        t = yf.Ticker(ticker)
        exps = list(t.options or [])
        if not exps:
            return {}
        spot = None
        try:
            spot = float(t.fast_info.get("last_price"))
        except Exception:
            pass

        # Prefer an expiry ~2-8 weeks out — 0DTE/weekly wings have unstable IV marks.
        today = datetime.now().date()
        def dte(e):
            try:
                return (datetime.strptime(e, "%Y-%m-%d").date() - today).days
            except Exception:
                return 0
        ordered = sorted(exps, key=lambda e: (not (14 <= dte(e) <= 60), dte(e)))

        def iv_at(df, target):
            df = df.dropna(subset=["impliedVolatility"])
            df = df[(df["impliedVolatility"] > 0.03) & (df["impliedVolatility"] < 1.5)]
            if "openInterest" in df:
                liq = df[df["openInterest"].fillna(0) > 0]
                df = liq if not liq.empty else df
            if df.empty:
                return None
            i = (df["strike"] - target).abs().idxmin()
            return float(df.loc[i, "impliedVolatility"])

        for e in ordered[:4]:
            ch = t.option_chain(e)
            puts, calls = ch.puts, ch.calls
            if spot is None and not calls.empty:
                spot = float(calls["strike"].median())
            if spot is None:
                continue
            # 5% OTM strikes — liquid enough to carry a clean IV mark.
            put_iv = iv_at(puts, spot * 0.95)
            call_iv = iv_at(calls, spot * 1.05)
            atm_iv = iv_at(calls, spot)
            if put_iv is None or call_iv is None:
                continue
            skew = round((put_iv - call_iv) * 100, 1)  # vol points
            tone = ("elevated hedging demand" if skew > 8 else
                    "unusually flat — complacency" if skew < 2 else "normal downside skew")
            return {
                "ticker": ticker, "expiry": e, "skew": skew,
                "put_iv": round(put_iv * 100, 1), "call_iv": round(call_iv * 100, 1),
                "atm_iv": round(atm_iv * 100, 1) if atm_iv else None, "tone": tone,
            }
        return {}
    except Exception as exc:
        logger.warning("iv_skew for %s failed: %s", ticker, exc)
        return {}
