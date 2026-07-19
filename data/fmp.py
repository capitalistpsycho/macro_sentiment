"""
FMP data layer — the full US Treasury yield curve (paid tier, key already on hand).

The base dashboard reads only ^TNX/^IRX (two points). FMP's treasury-rates
endpoint delivers the whole daily curve across 12 tenors, which unlocks proper
curve analytics: 2s10s, 3m10y, 5s30s and curvature. Curve points are cached into
the generic ``fred_series`` table under ``UST:*`` ids so the existing FRED reader
serves them.
"""

from __future__ import annotations

import logging

from config.secrets import get_secret
from data import fred
from data.db import init_db, upsert_fred

logger = logging.getLogger(__name__)

FMP_BASE = "https://financialmodelingprep.com/stable"

# FMP field -> (namespaced series id, years-to-maturity, display label)
_TENORS = [
    ("month1", "UST:1M", 1 / 12, "1M"), ("month2", "UST:2M", 2 / 12, "2M"),
    ("month3", "UST:3M", 0.25, "3M"), ("month6", "UST:6M", 0.5, "6M"),
    ("year1", "UST:1Y", 1, "1Y"), ("year2", "UST:2Y", 2, "2Y"),
    ("year3", "UST:3Y", 3, "3Y"), ("year5", "UST:5Y", 5, "5Y"),
    ("year7", "UST:7Y", 7, "7Y"), ("year10", "UST:10Y", 10, "10Y"),
    ("year20", "UST:20Y", 20, "20Y"), ("year30", "UST:30Y", 30, "30Y"),
]


def _key() -> str:
    return get_secret("FMP_API_KEY")


def refresh_treasury() -> dict:
    """Download and cache the daily UST curve. Returns stats."""
    init_db()
    if not _key():
        logger.warning("No FMP_API_KEY — skipping Treasury curve refresh.")
        return {"rows": 0, "days": 0}
    import requests
    r = requests.get(f"{FMP_BASE}/treasury-rates", params={"apikey": _key()}, timeout=30)
    r.raise_for_status()
    data = r.json() or []
    rows = []
    for row in data:
        d = row.get("date")
        if not d:
            continue
        for field, sid, _, _ in _TENORS:
            v = row.get(field)
            if v is not None:
                try:
                    rows.append((sid, d, float(v)))
                except (TypeError, ValueError):
                    pass
    n = upsert_fred(rows)
    logger.info("FMP Treasury: %d rows (%d days).", n, len(data))
    return {"rows": n, "days": len(data)}


def treasury_curve(as_of: str | None = None) -> list[dict]:
    """Latest full curve as [{tenor, years, yield}], short→long."""
    out = []
    for _, sid, yrs, label in _TENORS:
        v = fred.latest(sid, as_of=as_of)
        if v is not None:
            out.append({"tenor": label, "years": yrs, "yield": v})
    return out


def curve_analytics(as_of: str | None = None) -> dict:
    """Key curve slopes + curvature + 2s10s history."""
    def lv(sid):
        return fred.latest(sid, as_of=as_of)

    def sp(a, b):
        return round(a - b, 2) if (a is not None and b is not None) else None

    y2, y5, y10, y30, m3 = lv("UST:2Y"), lv("UST:5Y"), lv("UST:10Y"), lv("UST:30Y"), lv("UST:3M")
    curvature = round(2 * y5 - y2 - y10, 2) if None not in (y2, y5, y10) else None

    s2 = fred.series("UST:2Y", as_of=as_of, point_in_time=False)
    s10 = fred.series("UST:10Y", as_of=as_of, point_in_time=False)
    hist = None
    if not s2.empty and not s10.empty:
        idx = s2.index.intersection(s10.index)
        if len(idx):
            hist = (s10.reindex(idx) - s2.reindex(idx)).dropna()
    return {
        "2s10s": sp(y10, y2), "3m10y": sp(y10, m3), "5s30s": sp(y30, y5),
        "curvature": curvature, "hist_2s10s": hist,
        "as_of": (s10.index[-1].strftime("%Y-%m-%d") if not s10.empty else None),
    }
