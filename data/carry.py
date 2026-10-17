"""
Cross-asset carry and trend — the two premia every multi-asset desk runs.

Carry (Koijen, Moskowitz, Pedersen & Vrugt, JFE 2018): the return an asset earns if
prices don't move. It predicts returns in every asset class studied, is distinct
from value and momentum, and carry strategies crash together in global recessions.
Here: bond carry + roll-down, FX carry (CAD vs USD), equity carry (dividend yield
− bill). Commodity carry needs futures-curve data we don't have.

Trend (Moskowitz, Ooi & Pedersen, JFE 2012; Hurst, Ooi & Pedersen, 1880–2016):
12-1m time-series momentum plus the 1/3/12m blend, vol-scaled to a 10% risk
target. Caveat (Kim, Tse & Wald): much of TSMOM's alpha comes from the vol scaling.
"""

from __future__ import annotations

import numpy as np

from data import store

# Approx. modified duration of a 10y par bond — enough for a roll-down estimate.
_DUR10 = 8.5

TREND_UNIVERSE = [
    ("SPY", "US equities"), ("VEA", "Intl developed"), ("EEM", "Emerging mkts"),
    ("XIU.TO", "Canada equities"), ("TLT", "Long Treasuries"), ("IEF", "7-10y Treasuries"),
    ("TIP", "TIPS"), ("HYG", "High yield"), ("GLD", "Gold"), ("CL=F", "Crude oil"),
    ("HG=F", "Copper"), ("DX-Y.NYB", "US dollar"), ("CADUSD=X", "CAD vs USD"),
]
TARGET_VOL = 0.10


def _last(tk: str) -> float | None:
    s = store.series(tk)
    return float(s["close"].iloc[-1]) if not s.empty else None


def _spy_div_yield() -> float | None:
    """Trailing-12m SPY dividends / price (%). One yfinance call; None offline."""
    try:
        import pandas as pd
        import yfinance as yf
        d = yf.Ticker("SPY").dividends
        d.index = d.index.tz_localize(None)
        ttm = float(d[d.index > pd.Timestamp.now() - pd.DateOffset(years=1)].sum())
        px = _last("SPY")
        return round(ttm / px * 100, 2) if ttm and px else None
    except Exception:
        return None


def carry_panel() -> list[dict]:
    rows = []
    tnx, fvx, irx = _last("^TNX"), _last("^FVX"), _last("^IRX")
    if None not in (tnx, fvx, irx):
        roll = _DUR10 * (tnx - fvx) / 5
        rows.append({"asset": "US 10Y Treasury", "carry": round(tnx - irx, 2), "roll": round(roll, 2),
                     "detail": f"10Y {tnx:.2f}% − 3M bill {irx:.2f}%; roll ≈ dur × 5s10s slope/yr"})
    try:
        from data.boc import boc_snapshot
        b = boc_snapshot()
    except Exception:
        b = {}
    if b.get("goc_10y") is not None and b.get("corra") is not None:
        roll = _DUR10 * (b["goc_10y"] - (b.get("goc_5y") or b["goc_10y"])) / 5
        rows.append({"asset": "Canada 10Y (GoC)", "carry": round(b["goc_10y"] - b["corra"], 2),
                     "roll": round(roll, 2), "detail": f"GoC 10Y {b['goc_10y']:.2f}% − CORRA {b['corra']:.2f}%"})
    try:
        from data.fred import latest
        sofr = latest("SOFR30DAYAVG")
    except Exception:
        sofr = None
    if b.get("corra") is not None and sofr is not None:
        rows.append({"asset": "Long CAD / short USD", "carry": round(b["corra"] - sofr, 2), "roll": 0.0,
                     "detail": f"CORRA {b['corra']:.2f}% − SOFR {sofr:.2f}%"})
    dy = _spy_div_yield()
    if dy is not None and irx is not None:
        rows.append({"asset": "US equities (SPY)", "carry": round(dy - irx, 2), "roll": 0.0,
                     "detail": f"dividend yield {dy:.2f}% − 3M bill {irx:.2f}%"})
    for r in rows:
        r["total"] = round(r["carry"] + r["roll"], 2)
    return rows


def trend_panel() -> list[dict]:
    rows = []
    for tk, label in TREND_UNIVERSE:
        s = store.series(tk)
        if s.empty or len(s) < 260:
            continue
        c = s["close"].astype(float).to_numpy()
        r = np.diff(np.log(c))
        vol = float(r[-63:].std() * np.sqrt(252))
        r12_1 = c[-22] / c[-253] - 1
        signs = [np.sign(c[-1] / c[-1 - n] - 1) for n in (21, 63, 252)]
        blend = float(np.mean(signs))
        pos = float(np.clip(blend * TARGET_VOL / vol, -2, 2)) if vol else 0.0
        rows.append({"asset": label, "ticker": tk, "r12_1": round(r12_1 * 100, 1),
                     "tsmom": int(np.sign(r12_1)), "blend": round(blend, 2),
                     "vol": round(vol * 100, 1), "position": round(pos, 2)})
    return rows
