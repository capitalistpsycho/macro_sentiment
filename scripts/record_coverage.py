"""
Write data/refresh_status.json — a provenance record for the daily seed refresh.

Every data source in run_macro.py is wrapped so a missing key or a dead endpoint
degrades gracefully. That keeps the dashboard up, but it also means a green
workflow run says nothing about what actually got fetched: the FMP Treasury
curve skipped silently for two months and the seed simply carried stale rows.

Actions logs need authentication to read, so this records the same answer in a
committed file instead: which keys the run had, and how current each source is.
Cheap to eyeball, and the dashboard's freshness strip can read it later.
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
from datetime import datetime, timezone

DB = os.path.join("cache", "macro.db")
OUT = os.path.join("data", "refresh_status.json")

# label -> (table, predicate on the id column) ; None predicate = whole table
SOURCES = {
    "prices":     ("daily_prices", None),
    "fred":       ("fred_series", "series_id NOT LIKE 'UST:%' AND series_id NOT LIKE 'BOC:%'"),
    "ust_curve":  ("fred_series", "series_id LIKE 'UST:%'"),
    "boc":        ("fred_series", "series_id LIKE 'BOC:%'"),
    "signals":    ("macro_signals", None),
}


def main() -> int:
    if not os.path.exists(DB):
        print(f"No {DB} — nothing to record.", file=sys.stderr)
        return 1

    con = sqlite3.connect(DB)
    coverage = {}
    for label, (table, where) in SOURCES.items():
        clause = f" WHERE {where}" if where else ""
        rows, latest = con.execute(
            f"SELECT COUNT(*), MAX(date) FROM {table}{clause}").fetchone()
        coverage[label] = {"rows": rows, "latest": latest}

    # COT is keyed by report_date, not date.
    rows, latest = con.execute(
        "SELECT COUNT(*), MAX(report_date) FROM cot_positioning").fetchone()
    coverage["cot"] = {"rows": rows, "latest": latest}

    status = {
        "refreshed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        # Booleans only — never the key values themselves.
        "keys_present": {
            "FRED_API_KEY": os.environ.get("FRED_KEY_PRESENT") == "true",
            "FMP_API_KEY": os.environ.get("FMP_KEY_PRESENT") == "true",
        },
        "coverage": coverage,
    }

    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(status, fh, indent=2)
        fh.write("\n")
    print(json.dumps(status, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
