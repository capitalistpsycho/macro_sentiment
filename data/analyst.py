"""
Analyst-sentiment breadth — a leading equity gauge from FMP (paid key on hand).

Desks watch whether the sell side is upgrading or cutting, and how broadly. FMP's
per-name analyst data doesn't roll up to an index, so we aggregate a curated
large-cap basket (US mega-caps + key Canadian names for the TSX tilt): the net
bullish share of ratings and the average price-target upside. It's an
analyst-sentiment/breadth read (rating distribution + targets), not a formal EPS
revision series. Cached long — it's ~2 API calls per name.
"""

from __future__ import annotations

import logging

from config.secrets import get_secret

logger = logging.getLogger(__name__)

FMP_BASE = "https://financialmodelingprep.com/stable"

BASKET = [
    ("AAPL", "US"), ("MSFT", "US"), ("NVDA", "US"), ("AMZN", "US"),
    ("GOOGL", "US"), ("META", "US"), ("JPM", "US"), ("XOM", "US"),
    # Canadian names via their NYSE dual listings (FMP covers these, not ".TO").
    ("RY", "CA"), ("TD", "CA"), ("CNQ", "CA"), ("SHOP", "CA"),
]


def _key() -> str:
    return get_secret("FMP_API_KEY")


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
            g = sess.get(f"{FMP_BASE}/grades-consensus",
                         params={"symbol": sym, "apikey": key}, timeout=15).json()
            if g:
                d = g[0]
                b = (d.get("strongBuy", 0) or 0) + (d.get("buy", 0) or 0)
                s = (d.get("sell", 0) or 0) + (d.get("strongSell", 0) or 0)
                h = d.get("hold", 0) or 0
                bull += b; bear += s; neutral += h
                names += 1
            pt = sess.get(f"{FMP_BASE}/price-target-summary",
                          params={"symbol": sym, "apikey": key}, timeout=15).json()
            tgt = (pt[0].get("lastQuarterAvgPriceTarget") if pt else None)
            q = sess.get(f"{FMP_BASE}/quote",
                         params={"symbol": sym, "apikey": key}, timeout=15).json()
            px = (q[0].get("price") if q else None)
            if tgt and px:
                upsides.append((tgt / px - 1) * 100)
        except Exception as exc:
            logger.warning("analyst breadth %s failed: %s", sym, exc)
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
