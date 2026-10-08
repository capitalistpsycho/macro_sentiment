"""
Analyst-sentiment breadth — a leading equity gauge from FMP (paid key on hand).

Desks watch whether the sell side is upgrading or cutting, and how broadly. FMP's
per-name analyst data doesn't roll up to an index, so we aggregate a curated
large-cap basket (US mega-caps + key Canadian names for the TSX tilt): the net
bullish share of ratings and the average price-target upside. It's an
analyst-sentiment/breadth read (rating distribution + targets), not a formal EPS
revision series. Cached long — it's ~3 API calls per name.

The FMP plan on hand rejects most Canadian symbols (HTTP 402 "Premium Query
Parameter"), so any name FMP refuses falls back to Yahoo's analyst summary on
its TSX listing — same rating buckets, mean target vs current price.
"""

from __future__ import annotations

import logging

from config.secrets import get_secret

logger = logging.getLogger(__name__)

FMP_BASE = "https://financialmodelingprep.com/stable"

BASKET = [
    ("AAPL", "US"), ("MSFT", "US"), ("NVDA", "US"), ("AMZN", "US"),
    ("GOOGL", "US"), ("META", "US"), ("JPM", "US"), ("XOM", "US"),
    # Canadian names via their NYSE dual listings; RY/TD/CNQ are plan-gated on FMP
# and come from Yahoo's TSX listing instead (see _yahoo_name).
    ("RY", "CA"), ("TD", "CA"), ("CNQ", "CA"), ("SHOP", "CA"),
]


def _key() -> str:
    return get_secret("FMP_API_KEY")


YAHOO_SYMBOL = {"RY": "RY.TO", "TD": "TD.TO", "CNQ": "CNQ.TO", "SHOP": "SHOP.TO"}


def _fmp(sess, endpoint: str, sym: str, key: str) -> list:
    """GET an FMP stable endpoint; raises on non-200 (402 = plan-gated symbol)."""
    r = sess.get(f"{FMP_BASE}/{endpoint}",
                 params={"symbol": sym, "apikey": key}, timeout=15)
    if r.status_code != 200:
        raise PermissionError(f"FMP {endpoint} HTTP {r.status_code}")
    return r.json() or []


def _fmp_name(sess, sym: str, key: str) -> tuple[dict | None, float | None]:
    """(rating counts, price-target upside %) from FMP."""
    g = _fmp(sess, "grades-consensus", sym, key)
    counts = g[0] if g else None
    pt = _fmp(sess, "price-target-summary", sym, key)
    q = _fmp(sess, "quote", sym, key)
    tgt = pt[0].get("lastQuarterAvgPriceTarget") if pt else None
    px = q[0].get("price") if q else None
    return counts, ((tgt / px - 1) * 100 if tgt and px else None)


def _yahoo_name(sym: str) -> tuple[dict | None, float | None]:
    """Same shape as _fmp_name, from Yahoo's analyst summary (current month)."""
    import yfinance as yf
    t = yf.Ticker(YAHOO_SYMBOL.get(sym, sym))
    rec = t.recommendations_summary
    counts = None
    if rec is not None and not rec.empty:
        row = rec[rec["period"] == "0m"]
        counts = (row if not row.empty else rec).iloc[0].to_dict()
    pt = t.analyst_price_targets or {}
    tgt, px = pt.get("mean"), pt.get("current")
    return counts, ((tgt / px - 1) * 100 if tgt and px else None)


def analyst_breadth() -> dict:
    key = _key()
    if not key:
        return {}
    import requests
    sess = requests.Session()
    bull = bear = neutral = 0
    upsides, names = [], 0
    for sym, _ in BASKET:
        try:
            try:
                counts, upside = _fmp_name(sess, sym, key)
            except (PermissionError, ValueError) as exc:
                logger.debug("analyst breadth %s: FMP unavailable (%s), using Yahoo", sym, exc)
                counts, upside = _yahoo_name(sym)
        except Exception as exc:
            logger.info("analyst breadth %s skipped: %s", sym, exc)
            continue
        if counts:
            bull += (counts.get("strongBuy", 0) or 0) + (counts.get("buy", 0) or 0)
            bear += (counts.get("sell", 0) or 0) + (counts.get("strongSell", 0) or 0)
            neutral += counts.get("hold", 0) or 0
            names += 1
        if upside is not None:
            upsides.append(upside)
    total = bull + bear + neutral
    if not total:
        return {}
    net_bull = round((bull - bear) / total * 100, 1)
    return {
        "net_bull_pct": net_bull,
        "bull_share": round(bull / total * 100, 1),
        "avg_upside": round(sum(upsides) / len(upsides), 1) if upsides else None,
        "n_names": names,
        "label": ("Broadly bullish" if net_bull > 45 else
                  "Constructive" if net_bull > 20 else
                  "Mixed" if net_bull > 0 else "Cautious"),
    }
