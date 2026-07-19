"""
Bank of Canada (Valet API) — Canada-specific macro the FRED layer can't cover.

For a Canadian-tilted fund the BoC policy path, the Government-of-Canada curve and
CAD are first-order. The Valet API is free and needs no key. Series are cached
into the generic ``fred_series`` table under ``BOC:*`` ids so the FRED reader
serves them alongside US data.
"""

from __future__ import annotations

import logging

import pandas as pd

from data import fred
from data.db import init_db, upsert_fred

logger = logging.getLogger(__name__)

VALET = "https://www.bankofcanada.ca/valet/observations"

# Valet series id -> namespaced cache id
_SERIES = {
    "V39079":            "BOC:policy_rate",   # Target for the overnight rate
    "BD.CDN.2YR.DQ.YLD": "BOC:goc_2y",
    "BD.CDN.5YR.DQ.YLD": "BOC:goc_5y",
    "BD.CDN.10YR.DQ.YLD": "BOC:goc_10y",
    "AVG.INTWO":         "BOC:corra",         # CORRA overnight funding
    "FXUSDCAD":          "BOC:usdcad",         # USD/CAD daily average
}


def refresh_boc(years: int = 6) -> dict:
    """Download and cache the BoC series. Returns stats."""
    init_db()
    import requests
    start = (pd.Timestamp.now() - pd.Timedelta(days=365 * years)).strftime("%Y-%m-%d")
    rows, ok, missing = [], 0, []
    for vid, sid in _SERIES.items():
        try:
            j = requests.get(f"{VALET}/{vid}/json", params={"start_date": start},
                             timeout=30).json()
            got = 0
            for o in j.get("observations", []):
                d = o.get("d")
                v = o.get(vid, {}).get("v")
                if d and v not in (None, ""):
                    try:
                        rows.append((sid, d, float(v)))
                        got += 1
                    except (TypeError, ValueError):
                        pass
            if got:
                ok += 1
            else:
                missing.append(vid)
        except Exception as exc:
            logger.warning("BoC %s failed: %s", vid, exc)
            missing.append(vid)
    n = upsert_fred(rows)
    logger.info("BoC: %d series, %d rows (%d missing).", ok, n, len(missing))
    return {"series": ok, "rows": n, "missing": missing}


def boc_snapshot(as_of: str | None = None) -> dict:
    """Policy rate, GoC curve, CAD, and cross-border derived spreads."""
    def lv(sid):
        return fred.latest(sid, as_of=as_of)

    def chg(sid, n=21):
        s = fred.series(sid, as_of=as_of, point_in_time=False)
        return round(float(s.iloc[-1] - s.iloc[-1 - n]), 3) if len(s) > n else None

    pol, g2, g5, g10 = lv("BOC:policy_rate"), lv("BOC:goc_2y"), lv("BOC:goc_5y"), lv("BOC:goc_10y")
    us10 = fred.latest("DGS10", as_of=as_of)
    us_policy = None  # Fed funds proxy: 3M T-bill via ^IRX lives in prices, not here
    s = fred.series("BOC:usdcad", as_of=as_of)
    return {
        "policy_rate": pol, "goc_2y": g2, "goc_5y": g5, "goc_10y": g10,
        "corra": lv("BOC:corra"), "usdcad": lv("BOC:usdcad"),
        "usdcad_1m_chg": chg("BOC:usdcad"),
        "goc_2s10s": round(g10 - g2, 2) if (g2 is not None and g10 is not None) else None,
        "goc_ust_10y_spread": round(g10 - us10, 2) if (g10 is not None and us10 is not None) else None,
        "as_of": s.index[-1].strftime("%Y-%m-%d") if not s.empty else None,
    }
