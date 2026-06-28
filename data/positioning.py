"""
CFTC Commitment of Traders positioning — the crowding / contrarian layer.

Pulls weekly speculative net positioning from the CFTC's public Socrata API
(free, no key) for the markets most relevant to the Northstar Fund: S&P 500 and
the Canadian dollar (Traders-in-Financial-Futures "leveraged money") plus WTI
crude and gold (disaggregated "managed money"). Net positioning is read as a
percentile of its own ~3-year history; extremes are contrarian signals.

    from data.positioning import refresh_cot, positioning_summary
    refresh_cot()              # called by run_macro (weekly data)
    positioning_summary()      # list of per-market reads with percentiles
"""

from __future__ import annotations

import logging

import pandas as pd

from data.db import get_db, init_db, upsert_cot
from data.stats import percentile_rank, percentile_label

logger = logging.getLogger(__name__)

TFF = "https://publicreporting.cftc.gov/resource/gpe5-46if.json"   # financial futures
DISAGG = "https://publicreporting.cftc.gov/resource/kh3c-gbw2.json"  # disaggregated

# market key -> config. group: which trader category drives the "spec" net.
MARKETS: dict[str, dict] = {
    "ES": {
        "label": "S&P 500 (E-mini)", "url": TFF,
        "name": "E-MINI S&P 500 - CHICAGO MERCANTILE EXCHANGE",
        "long": "lev_money_positions_long", "short": "lev_money_positions_short",
        "group": "leveraged funds",
    },
    "CAD": {
        "label": "Canadian Dollar", "url": TFF,
        "name": "CANADIAN DOLLAR - CHICAGO MERCANTILE EXCHANGE",
        "long": "lev_money_positions_long", "short": "lev_money_positions_short",
        "group": "leveraged funds",
    },
    "WTI": {
        "label": "WTI Crude Oil", "url": DISAGG,
        "name": "WTI-PHYSICAL - NEW YORK MERCANTILE EXCHANGE",
        "long": "m_money_positions_long_all", "short": "m_money_positions_short_all",
        "group": "managed money",
    },
    "GOLD": {
        "label": "Gold", "url": DISAGG,
        "name": "GOLD - COMMODITY EXCHANGE INC.",
        "long": "m_money_positions_long_all", "short": "m_money_positions_short_all",
        "group": "managed money",
    },
}


# ── Fetch / cache ─────────────────────────────────────────────────────────────

def _fetch_market(cfg: dict, weeks: int = 160) -> list[tuple]:
    import requests
    params = {
        "$where": f"market_and_exchange_names = '{cfg['name']}'",
        "$order": "report_date_as_yyyy_mm_dd DESC",
        "$limit": str(weeks),
    }
    r = requests.get(cfg["url"], params=params, timeout=40)
    r.raise_for_status()
    rows = []
    for o in r.json():
        try:
            d = o["report_date_as_yyyy_mm_dd"][:10]
            lo = float(o[cfg["long"]]); sh = float(o[cfg["short"]])
            oi = float(o.get("open_interest_all") or 0) or None
            rows.append((d, lo - sh, lo, sh, oi))
        except (KeyError, ValueError, TypeError):
            continue
    return rows


def refresh_cot(weeks: int = 160) -> dict:
    """Download and cache weekly COT net positioning for all markets."""
    init_db()
    total, ok, missing = 0, [], []
    for key, cfg in MARKETS.items():
        try:
            rows = _fetch_market(cfg, weeks=weeks)
            if not rows:
                missing.append(key); continue
            db_rows = [(key, d, net, lo, sh, oi) for d, net, lo, sh, oi in rows]
            total += upsert_cot(db_rows); ok.append(key)
        except Exception as exc:
            logger.warning("COT %s failed: %s", key, exc)
            missing.append(key)
    logger.info("COT: %d markets, %d rows (%d missing).", len(ok), total, len(missing))
    return {"markets": len(ok), "rows": total, "missing": missing}


# ── Read / interpret ──────────────────────────────────────────────────────────

def _history(market: str, as_of: str | None = None) -> pd.DataFrame:
    try:
        with get_db() as c:
            if as_of:
                df = pd.read_sql_query(
                    "SELECT report_date, net, long_pos, short_pos, open_interest "
                    "FROM cot_positioning WHERE market=? AND report_date<=? ORDER BY report_date",
                    c, params=(market, as_of))
            else:
                df = pd.read_sql_query(
                    "SELECT report_date, net, long_pos, short_pos, open_interest "
                    "FROM cot_positioning WHERE market=? ORDER BY report_date",
                    c, params=(market,))
    except Exception:
        return pd.DataFrame()
    return df


def positioning_summary(as_of: str | None = None) -> list[dict]:
    """Per-market net positioning, its 3y percentile and a contrarian read."""
    out = []
    for key, cfg in MARKETS.items():
        df = _history(key, as_of=as_of)
        if df.empty:
            continue
        net = float(df["net"].iloc[-1])
        pct = percentile_rank(net, df["net"])
        prev = float(df["net"].iloc[-2]) if len(df) > 1 else None
        wk_chg = (net - prev) if prev is not None else None
        # Contrarian interpretation of an extreme.
        if pct is not None and pct >= 85:
            read, tone = "Crowded long — contrarian caution", "bearish"
        elif pct is not None and pct <= 15:
            read, tone = "Crowded short — contrarian support", "bullish"
        else:
            read, tone = "Positioning mid-range", "neutral"
        out.append({
            "key": key, "label": cfg["label"], "group": cfg["group"],
            "report_date": df["report_date"].iloc[-1][:10],
            "net": net, "week_change": wk_chg,
            "percentile": pct, "percentile_label": percentile_label(pct),
            "read": read, "tone": tone,
        })
    return out
