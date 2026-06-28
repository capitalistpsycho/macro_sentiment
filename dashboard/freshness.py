"""Data-freshness read for the header strip — based on macro.db latest date."""

from __future__ import annotations

from datetime import date, datetime, timedelta


def get_freshness() -> dict:
    from data.store import latest_date
    d = latest_date()
    stale = False
    if d:
        try:
            last = datetime.strptime(d, "%Y-%m-%d").date()
            # > 1 trading day old (account for weekends): warn if >3 calendar days
            stale = (date.today() - last) > timedelta(days=3)
        except Exception:
            pass
    return {"prices_as_of": d, "stale": stale}
