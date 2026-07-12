"""
Fear & Greed composite — a yfinance/FRED-based approximation of the CNN index.

Six components, each scored 0-100, averaged into a single reading. Built from
data already in macro.db (prices + cached FRED credit spreads) so it is cheap to
recompute live and point-in-time (any ``as_of``). This is an *approximation* of
CNN's index, not a replica — we lack CBOE put/call and McClellan breadth, so
those concepts are proxied.

Design notes (recalibrated 2026-07): VIX feeds exactly one component (it used to
drive two, doubling its weight); the breadth clamp is widened so it no longer
pins at 100; and junk-bond demand reads the *real* FRED high-yield OAS percentile
rather than a 5-day HYG−IEF price proxy (which falls back in if FRED is absent).
"""

from __future__ import annotations

from data import store


def _norm(x: float, lo: float, hi: float) -> float:
    """Linear map x in [lo,hi] -> [0,100], clamped."""
    if hi == lo:
        return 50.0
    return max(0.0, min(100.0, (x - lo) / (hi - lo) * 100.0))


def _g(m, tk, f="close"):
    v = m.get(tk, {}).get(f)
    return v if isinstance(v, (int, float)) else None


def fear_greed(metrics: dict | None = None, as_of: str | None = None) -> dict:
    m = metrics if metrics is not None else store.latest_metrics(as_of=as_of)
    comps: dict[str, float] = {}

    # 1. Market Momentum — SPY vs its 125-day average (CNN's momentum gauge).
    spy = _g(m, "SPY")
    spy_s = store.series("SPY", days=130, as_of=as_of)
    if spy is not None and not spy_s.empty:
        ma125 = float(spy_s["close"].tail(125).mean())
        comps["Market Momentum"] = _norm((spy / ma125 - 1) * 100, -10, 10)

    # 2. Stock Price Strength — breadth of the sector/benchmark basket above its
    #    200-day MA. Widened clamp [10,90] so a strong tape doesn't pin at 100.
    from data import tickers as T
    basket = [t for t, _, _ in (T.SECTOR_US + T.EQUITY_BENCHMARKS) if t != "^VIX"]
    rated = [(_g(m, t), _g(m, t, "ma200")) for t in basket]
    rated = [(c, ma) for c, ma in rated if c is not None and ma is not None]
    if rated:
        above = sum(1 for c, ma in rated if c > ma)
        comps["Price Strength"] = _norm(above / len(rated) * 100, 10, 90)

    # 3. Stock Price Breadth — equal-weight vs cap-weight 1m (RSP vs SPY): when
    #    breadth is broad the average stock (RSP) keeps pace with the mega-caps.
    rsp, spy_r = _g(m, "RSP", "return_1m"), _g(m, "SPY", "return_1m")
    if rsp is not None and spy_r is not None:
        comps["Price Breadth"] = _norm(rsp - spy_r, -4, 4)

    # 4. Market Volatility — VIX vs its 50-day average (CNN uses the 50-day).
    #    This is the ONLY component driven by VIX (previously two were).
    vix = _g(m, "^VIX")
    vs = store.series("^VIX", days=55, as_of=as_of)
    if vix is not None and not vs.empty:
        avg50 = float(vs["close"].tail(50).mean())
        comps["Volatility"] = _norm(avg50 - vix, -6, 6)

    # 5. Safe-Haven Demand — stocks vs bonds over ~20 sessions (SPY vs TLT 1m).
    spy1m, tlt1m = _g(m, "SPY", "return_1m"), _g(m, "TLT", "return_1m")
    if spy1m is not None and tlt1m is not None:
        comps["Safe-Haven Demand"] = _norm(spy1m - tlt1m, -6, 6)

    # 6. Junk-Bond Demand — real FRED high-yield OAS percentile, inverted (tight
    #    spreads = greed). Falls back to the HYG−IEF price proxy if FRED absent.
    comps["Junk-Bond Demand"] = _junk_bond_demand(m, as_of)

    comps = {k: v for k, v in comps.items() if v is not None}
    score = round(sum(comps.values()) / len(comps), 1) if comps else 50.0

    return {"score": score, "components": {k: round(v, 1) for k, v in comps.items()},
            "label": label_for(score)}


def _junk_bond_demand(m: dict, as_of: str | None) -> float | None:
    """Greed from credit: 100 − percentile of the current HY OAS vs its history."""
    try:
        from data import fred
        from data.stats import percentile_rank
        hy = fred.series("BAMLH0A0HYM2", as_of=as_of)
        if not hy.empty:
            pct = percentile_rank(float(hy.iloc[-1]), hy)  # high OAS = wide = fear
            if pct is not None:
                return 100.0 - pct
    except Exception:
        pass
    # Fallback: 5-day HYG vs IEF price proxy (works offline / without FRED).
    hyg5, ief5 = _g(m, "HYG", "return_5d"), _g(m, "IEF", "return_5d")
    if hyg5 is not None and ief5 is not None:
        return _norm(hyg5 - ief5, -2, 2)
    return None


def label_for(score: float) -> str:
    if score < 25: return "Extreme Fear"
    if score < 45: return "Fear"
    if score < 55: return "Neutral"
    if score < 75: return "Greed"
    return "Extreme Greed"
