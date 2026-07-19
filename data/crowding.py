"""
Crowding / positioning composite — the tail-risk lens beyond CFTC net positioning.

Crowding is an asymmetric risk: it builds slowly and unwinds all at once, and a
one-SD rise in crowding is associated with materially higher negative skew
(Macrosynergy / Jain-Conlon-Cotter). We can't buy S3-style ownership data, but
several institutional crowding proxies are buildable from what we already cache:

  - mega-cap concentration  (RSP/SPY — equal-weight lagging = crowded into the top)
  - momentum crowding       (MTUM/SPY relative strength at an extreme)
  - volatility complacency  (very low VIX percentile = leverage/vol-target buildup)
  - futures positioning      (CFTC net at an extreme percentile)

Each maps to 0-100 (higher = more crowded); the composite is their average.
"""

from __future__ import annotations

from data import store
from data.stats import percentile_rank


def crowding_score(as_of: str | None = None) -> dict:
    comps: dict[str, float] = {}

    # 1. Mega-cap concentration: low RSP/SPY (equal-weight lagging) = crowded top.
    rsp = store.ratio("RSP", "SPY")
    if not rsp.empty:
        p = percentile_rank(float(rsp.iloc[-1]), rsp)
        if p is not None:
            comps["Mega-cap concentration"] = 100 - p

    # 2. Momentum crowding: MTUM strongly outperforming = crowded momentum factor.
    mt = store.ratio("MTUM", "SPY")
    if not mt.empty:
        p = percentile_rank(float(mt.iloc[-1]), mt)
        if p is not None:
            comps["Momentum crowding"] = p

    # 3. Volatility complacency: very low VIX percentile = leverage/vol-target buildup.
    vix = store.series("^VIX")
    if not vix.empty:
        p = percentile_rank(float(vix["close"].iloc[-1]), vix["close"])
        if p is not None:
            comps["Vol complacency"] = 100 - p

    # 4. Futures positioning: most-extreme CFTC net percentile (distance from neutral).
    try:
        from data.positioning import positioning_summary
        devs = [abs((r.get("percentile") or 50) - 50) * 2
                for r in positioning_summary() if r.get("percentile") is not None]
        if devs:
            comps["Futures positioning"] = min(100.0, max(devs))
    except Exception:
        pass

    vals = [v for v in comps.values() if v is not None]
    score = round(sum(vals) / len(vals), 1) if vals else None
    return {"score": score, "components": {k: round(v, 1) for k, v in comps.items()},
            "label": _label(score)}


def _label(s: float | None) -> str:
    if s is None:
        return "—"
    if s >= 70:
        return "Crowded — elevated unwind/tail risk"
    if s >= 55:
        return "Above average"
    if s <= 30:
        return "Uncrowded"
    return "Balanced"
