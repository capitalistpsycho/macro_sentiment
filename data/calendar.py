"""
Economic event calendar — the event-risk layer.

FMP's calendar is paywalled on the current plan, so this is built from FRED's
per-release scheduled dates (free) for the highest-impact US macro releases,
plus the FOMC. Each event carries its days-until and, where useful, the latest
printed value from the cached FRED series for context.

    from data.calendar import upcoming_events
    upcoming_events(days=21)   # list of {date, label, impact, days_until, last}
"""

from __future__ import annotations

import logging
from datetime import date, datetime

logger = logging.getLogger(__name__)

FRED_BASE = "https://api.stlouisfed.org/fred"

# FOMC is handled separately: FRED release 101 ("FOMC Press Release") logs a
# release date for *every* calendar day, so it can't be used to find the rate
# decision. Instead we hardcode the Fed's published meeting schedule (the
# decision is announced on the second day). Update once a year when the Fed
# publishes the next year's dates.
FOMC_DECISION_DATES: list[str] = [
    # 2026 (https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm)
    "2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17",
    "2026-07-29", "2026-09-16", "2026-10-28", "2026-12-09",
    # 2027 (tentative — verify when the Fed confirms)
    "2027-01-27", "2027-03-17", "2027-04-28", "2027-06-16",
    "2027-07-28", "2027-09-22", "2027-11-03", "2027-12-15",
]

# release_id -> (label, impact, context_series, context_fmt)
RELEASES: dict[int, tuple] = {
    50:  ("Jobs Report (NFP)",       "high",   "UNRATE",   "Unemp {:.1f}%"),
    10:  ("CPI Inflation",           "high",   "CPILFESL", None),
    54:  ("PCE / Personal Income",   "high",   None,       None),
    53:  ("GDP",                     "medium", None,       None),
    46:  ("PPI",                     "medium", None,       None),
    9:   ("Retail Sales",            "medium", None,       None),
    192: ("JOLTS Job Openings",      "medium", None,       None),
    194: ("ADP Employment",          "low",    None,       None),
}


def _api_key() -> str:
    from config.secrets import get_secret
    return get_secret("FRED_API_KEY")


def _next_dates(release_id: int, key: str, limit: int = 2) -> list[str]:
    import requests
    today = date.today().isoformat()
    r = requests.get(f"{FRED_BASE}/release/dates", timeout=15, params={
        "release_id": release_id, "api_key": key, "file_type": "json",
        "include_release_dates_with_no_data": "true",
        "realtime_start": today, "sort_order": "asc", "limit": str(limit),
    })
    r.raise_for_status()
    return [x["date"] for x in r.json().get("release_dates", []) if x["date"] >= today]


def _context(series_id: str | None, fmt: str | None) -> str | None:
    if not series_id:
        return None
    try:
        from data.fred import latest, yoy
        if fmt:
            v = latest(series_id)
            return fmt.format(v) if v is not None else None
        # default: YoY for price indices
        v = yoy(series_id)
        return f"last {v:+.1f}% YoY" if v is not None else None
    except Exception:
        return None


def upcoming_events(days: int = 21) -> list[dict]:
    """Upcoming high-impact US macro releases within the next `days`."""
    key = _api_key()
    if not key:
        return []
    today = date.today()
    out = []

    # FOMC from the hardcoded schedule (nearest upcoming decision in window).
    for d in FOMC_DECISION_DATES:
        try:
            du = (datetime.strptime(d, "%Y-%m-%d").date() - today).days
        except ValueError:
            continue
        if 0 <= du <= days:
            out.append({"date": d, "label": "FOMC Rate Decision",
                        "impact": "high", "days_until": du, "last": None})
            break

    for rid, (label, impact, cser, cfmt) in RELEASES.items():
        try:
            dts = _next_dates(rid, key)
        except Exception as exc:
            logger.debug("calendar %s failed: %s", label, exc)
            continue
        for d in dts:
            try:
                du = (datetime.strptime(d, "%Y-%m-%d").date() - today).days
            except ValueError:
                continue
            if 0 <= du <= days:
                out.append({
                    "date": d, "label": label, "impact": impact,
                    "days_until": du, "last": _context(cser, cfmt),
                })
                break  # only the nearest occurrence per release
    out.sort(key=lambda e: e["date"])
    return out
