"""
Macro Compass daily data refresh.

    python run_macro.py --fast    prices + signals (download dominates, ~1-2 min)
    python run_macro.py --full    same, plus persists signal history snapshots

Both modes download ~1 year of daily closes for every tracked ticker, compute
returns/MAs/RSI/volatility into daily_prices, then compute and persist the
MacroSignal scores. --full is the daily cron entry point; --fast is for quick
intraday top-ups.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s",
                    datefmt="%H:%M:%S")
log = logging.getLogger("run_macro")


def main() -> int:
    ap = argparse.ArgumentParser(description="Macro Compass data refresh")
    ap.add_argument("--fast", action="store_true", help="prices + signals only")
    ap.add_argument("--full", action="store_true", help="everything incl. history")
    args = ap.parse_args()
    mode = "full" if args.full or not args.fast else "fast"

    t0 = time.time()
    log.info("=== Macro Compass refresh (%s) ===", mode.upper())

    # 1. Prices
    from data.market_data import refresh_prices
    stats = refresh_prices(period="2y")
    log.info("Prices: %d tickers, %d rows stored.", stats["tickers"], stats["rows"])
    if stats["missing"]:
        log.warning("No data for: %s", ", ".join(stats["missing"]))
    if stats["tickers"] == 0:
        log.error("No price data fetched — aborting. Check network / yfinance.")
        return 1

    # 1b. FRED macro data (growth, inflation, financial conditions)
    try:
        from data.fred import refresh_fred
        fstats = refresh_fred()
        log.info("FRED: %d series, %d rows.", fstats["series"], fstats["rows"])
    except Exception as exc:
        log.warning("FRED refresh failed (continuing): %s", exc)

    # 1c. CFTC positioning (weekly COT — crowding / contrarian)
    try:
        from data.positioning import refresh_cot
        cstats = refresh_cot()
        log.info("COT: %d markets, %d rows.", cstats["markets"], cstats["rows"])
    except Exception as exc:
        log.warning("COT refresh failed (continuing): %s", exc)

    # 2. Signals (cheap; computed in both modes so the gauge always has data)
    from data.signals import compute_signals, persist_signals
    sig = compute_signals()

    # 2b. Regime-change alert — detect BEFORE persisting (compare to prior day).
    try:
        from data.alerts import detect_regime_change, notify_regime_change
        change = detect_regime_change(sig)
        if change:
            notify_regime_change(change)
    except Exception as exc:
        log.warning("Regime-change check failed (continuing): %s", exc)

    persist_signals(sig)
    log.info("MacroCompass score: %.1f  |  Risk-on/off: %.1f  |  Regime: %s",
             sig["compass_score"], sig["risk_score"], sig["regime"])

    # 3. Sentiment composite (logged; recomputed live by the dashboard)
    from data.sentiment import fear_greed
    fg = fear_greed()
    log.info("Fear & Greed: %.1f (%s)", fg["score"], fg["label"])

    dt = time.time() - t0
    bar = "-" * 56
    print()
    print(bar)
    print(f"  Macro Compass refresh complete ({mode}) in {dt:0.1f}s")
    print(f"  Tickers stored : {stats['tickers']}/{len(stats['missing']) + stats['tickers']}")
    print(f"  MacroCompass   : {sig['compass_score']}/100")
    print(f"  Risk-on/off    : {sig['risk_score']}/100")
    print(f"  Market regime  : {sig['regime']}")
    print(f"  Macro regime   : {sig['macro_regime']}")
    print(f"  Fear & Greed   : {fg['score']} ({fg['label']})")
    print(bar)
    return 0


if __name__ == "__main__":
    sys.exit(main())
