"""
Fear & Greed composite — a yfinance-based approximation of the CNN index.

Seven components, each scored 0-100, averaged into a single reading. Built
purely from data already in macro.db so it is cheap to recompute live.
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

    # 1. Market Momentum — SPY vs 125-day MA (use 200d MA as available proxy ref)
    spy = _g(m, "SPY")
    spy_s = store.series("SPY", days=130, as_of=as_of)
    if spy is not None and not spy_s.empty:
        ma125 = float(spy_s["close"].tail(125).mean())
        comps["Market Momentum"] = _norm((spy / ma125 - 1) * 100, -8, 8)

    # 2. Stock Price Strength — breadth of sector/benchmark basket above 200d MA
    from data import tickers as T
    basket = [t for t, _, _ in T.SECTOR_US]
    above = sum(1 for t in basket
                if (_g(m, t) or 0) > (_g(m, t, "ma200") or 1e9))
    if basket:
        comps["Price Strength"] = _norm(above / len(basket) * 100, 30, 80)

    # 3. Stock Price Breadth — equal-weight vs cap-weight 1m (RSP vs SPY)
    rsp, spy_r = _g(m, "RSP", "return_1m"), _g(m, "SPY", "return_1m")
    if rsp is not None and spy_r is not None:
        comps["Price Breadth"] = _norm(rsp - spy_r, -4, 4)

    # 4. Put/Call proxy — inverse VIX level
    vix = _g(m, "^VIX")
    if vix is not None:
        comps["Put/Call (VIX)"] = _norm(35 - vix, 0, 25)

    # 5. Market Volatility — VIX vs 20-day average
    vs = store.series("^VIX", days=21, as_of=as_of)
    if vix is not None and not vs.empty:
        avg = float(vs["close"].tail(20).mean())
        comps["Volatility"] = _norm(avg - vix, -6, 6)

    # 6. Safe-haven demand — SPY vs TLT 20-day (5d proxy) return
    spy5, tlt5 = _g(m, "SPY", "return_5d"), _g(m, "TLT", "return_5d")
    if spy5 is not None and tlt5 is not None:
        comps["Safe-Haven Demand"] = _norm(spy5 - tlt5, -5, 5)

    # 7. Junk-bond demand — HYG vs IEF 5-day return
    hyg5, ief5 = _g(m, "HYG", "return_5d"), _g(m, "IEF", "return_5d")
    if hyg5 is not None and ief5 is not None:
        comps["Junk-Bond Demand"] = _norm(hyg5 - ief5, -2, 2)

    if comps:
        score = round(sum(comps.values()) / len(comps), 1)
    else:
        score = 50.0

    return {"score": score, "components": {k: round(v, 1) for k, v in comps.items()},
            "label": label_for(score)}


def label_for(score: float) -> str:
    if score < 25: return "Extreme Fear"
    if score < 45: return "Fear"
    if score < 55: return "Neutral"
    if score < 75: return "Greed"
    return "Extreme Greed"
