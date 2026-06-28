"""
Backfill the macro_signals / signal_scores history from existing daily_prices.

The daily refresh only records one signal snapshot per run, so the sentiment and
MacroCompass trend charts start empty. This script reconstructs point-in-time
signals for every trading day in the most recent year by re-running the scoring
engine ``as_of`` each historical date — giving the trend charts a full year of
history immediately. Idempotent (INSERT OR REPLACE on date); safe to re-run.

    python backfill_history.py            # backfill last 252 trading days
    python backfill_history.py --days 504 # backfill last 2 years (needs 2y prices)
"""

from __future__ import annotations

import argparse
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s",
                    datefmt="%H:%M:%S")
log = logging.getLogger("backfill")


def backfill(days: int = 252) -> int:
    from data import store
    from data.signals import compute_signals, persist_signals

    all_dates = store.trading_dates()
    if not all_dates:
        log.error("No price data in daily_prices — run `python run_macro.py --full` first.")
        return 0

    # Keep only dates with enough lookback for ma200/breadth to be meaningful.
    eligible = all_dates[200:] if len(all_dates) > 200 else all_dates
    target = eligible[-days:] if days else eligible

    log.info("Backfilling %d trading days (%s .. %s) from %d total dates.",
             len(target), target[0], target[-1], len(all_dates))

    n = 0
    for d in target:
        try:
            sig = compute_signals(as_of=d)
            persist_signals(sig)
            n += 1
        except Exception as exc:
            log.warning("Skipped %s: %s", d, exc)

    log.info("Backfill complete: %d signal snapshots written.", n)
    return n


def main() -> int:
    ap = argparse.ArgumentParser(description="Backfill macro signal history")
    ap.add_argument("--days", type=int, default=252,
                    help="number of most-recent trading days to backfill (default 252)")
    args = ap.parse_args()
    backfill(args.days)
    return 0


if __name__ == "__main__":
    sys.exit(main())
