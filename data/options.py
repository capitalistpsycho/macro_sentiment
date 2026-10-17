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
import time

logger = logging.getLogger(__name__)

# put_call and iv_skew load on the same page within a second of each other and
# hit the same SPY chains; Yahoo rate-limits that burst. Memoise the Ticker's
# expiry list and each chain briefly so the second caller reuses the first's.
_MEMO_TTL = 300
_memo: dict[tuple, tuple[float, object]] = {}


def _retry(fn, *args):
    """Call fn, backing off once if Yahoo rate-limits ("Too Many Requests")."""
    from yfinance.exceptions import YFRateLimitError
    try:
        return fn(*args)
    except YFRateLimitError:
        time.sleep(3)
        return fn(*args)


def _cached(key: tuple, fn, *args):
    hit = _memo.get(key)
    if hit and time.time() - hit[0] < _MEMO_TTL:
        return hit[1]
    val = _retry(fn, *args)
    _memo[key] = (time.time(), val)
    return val


def _expiries(ticker: str) -> list[str]:
    import yfinance as yf
    return _cached(("exps", ticker), lambda: list(yf.Ticker(ticker).options or []))


def _chain(ticker: str, expiry: str):
    import yfinance as yf
    return _cached(("chain", ticker, expiry), lambda: yf.Ticker(ticker).option_chain(expiry))


def _log_failure(what: str, ticker: str, exc: Exception) -> None:
    from yfinance.exceptions import YFRateLimitError
    if isinstance(exc, YFRateLimitError):
        # Transient and expected on Yahoo's free feed; the page shows "unavailable".
        logger.info("%s for %s: Yahoo rate-limited, skipping this refresh", what, ticker)
    else:
        logger.warning("%s for %s failed: %s", what, ticker, exc)


def put_call(ticker: str = "SPY", expiries: int = 3) -> dict:
    """Aggregate put/call ratios across the nearest `expiries` expirations."""
    try:
        exps = _expiries(ticker)[:expiries]
        if not exps:
            return {}
        pv = cv = poi = coi = 0.0
        for e in exps:
            ch = _chain(ticker, e)
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
        _log_failure("put/call", ticker, exc)
        return {}


def _bs_gamma(S, K, T, iv, r=0.04):
    import numpy as np
    from scipy.stats import norm
    d1 = (np.log(S / K) + (r + 0.5 * iv ** 2) * T) / (iv * np.sqrt(T))
    return norm.pdf(d1) / (S * iv * np.sqrt(T))


def dealer_gamma(ticker: str = "SPY", expiries: int = 6) -> dict:
    """Estimated dealer gamma exposure (GEX) and the gamma-flip level.

    Naive convention (vendor standard, an *assumption*): dealers are long the calls
    and short the puts customers trade, so call gamma counts +, put gamma −.
    GEX = Σ gamma × OI × 100 × S² × 1% — dollars of delta dealers must trade per
    1% move. Positive = dealers hedge against moves (dampening); negative = with
    them (amplifying) — Baltussen et al. (JFE 2021) find S&P intraday momentum
    when dealers are short gamma. Open interest doesn't reveal who holds what, so
    treat the sign as an estimate.
    """
    try:
        import numpy as np
        import pandas as pd
        from datetime import datetime
        import yfinance as yf
        exps = _expiries(ticker)[:expiries]
        if not exps:
            return {}
        spot = yf.Ticker(ticker).fast_info.get("last_price")
        if not spot:  # Yahoo returns no live price off-hours/weekends -> last stored close
            from data import store
            s = store.series(ticker)
            spot = float(s["close"].iloc[-1]) if not s.empty else None
        if not spot:
            return {}
        spot = float(spot)
        today = datetime.now()
        legs = []
        for e in exps:
            T = max((datetime.strptime(e, "%Y-%m-%d") - today).days + 1, 1) / 365
            ch = _chain(ticker, e)
            for df, sign in ((ch.calls, 1.0), (ch.puts, -1.0)):
                d = df[["strike", "impliedVolatility", "openInterest"]].dropna()
                d = d[(d["impliedVolatility"] > 0.03) & (d["impliedVolatility"] < 2) & (d["openInterest"] > 0)]
                legs.append(pd.DataFrame({"K": d["strike"], "iv": d["impliedVolatility"],
                                          "oi": d["openInterest"] * sign, "T": T}))
        L = pd.concat(legs)
        if L.empty:
            return {}
        K, iv, oi, T = (L[c].to_numpy(float) for c in ("K", "iv", "oi", "T"))

        def gex(S):
            return float((_bs_gamma(S, K, T, iv) * oi * 100 * S * S * 0.01).sum())
        total = gex(spot)
        grid = np.linspace(spot * 0.85, spot * 1.15, 121)
        prof = np.array([gex(s) for s in grid])
        # Linear interpolation of each sign change -> the zero-gamma spot level.
        flips = [grid[i] - prof[i] * (grid[i + 1] - grid[i]) / (prof[i + 1] - prof[i])
                 for i in range(len(grid) - 1) if np.sign(prof[i]) != np.sign(prof[i + 1])]
        flip = min(flips, key=lambda x: abs(x - spot)) if flips else None
        return {
            "ticker": ticker, "spot": round(spot, 2), "gex_bn": round(total / 1e9, 2),
            "flip": round(float(flip), 1) if flip is not None else None,
            "regime": "positive gamma — dealers dampen moves" if total > 0
                      else "negative gamma — dealers amplify moves",
            "expiries": len(exps),
        }
    except Exception as exc:
        _log_failure("dealer_gamma", ticker, exc)
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
        exps = _expiries(ticker)
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
            ch = _chain(ticker, e)
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
        _log_failure("iv_skew", ticker, exc)
        return {}
