"""
FRED macro data — the institutional macro layer of the Macro Compass.

Pulls a curated set of economic series (growth, inflation, financial conditions,
credit) from the St. Louis Fed (FRED), caches them in macro.db (``fred_series``),
and turns them into a *real* growth x inflation macro regime plus a financial-
conditions read — replacing the previous ETF-momentum proxy with actual data.

    from data.fred import refresh_fred, macro_nowcast, financial_conditions
    refresh_fred()              # called by run_macro
    macro_nowcast()            # {growth, inflation, regime, ...}
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

import pandas as pd

from config.secrets import get_secret
from data.db import get_db, init_db, upsert_fred

logger = logging.getLogger(__name__)

FRED_BASE = "https://api.stlouisfed.org/fred"

# series_id -> (label, kind)  — kind drives how it is read in the nowcast
SERIES: dict[str, tuple[str, str]] = {
    "CPIAUCSL":     ("CPI (headline)",            "inflation"),
    "CPILFESL":     ("Core CPI",                  "inflation"),
    "T10YIE":       ("10y Breakeven Inflation",   "inflation"),
    "CFNAI":        ("Chicago Fed Nat. Activity", "growth"),
    "INDPRO":       ("Industrial Production",      "growth"),
    "PAYEMS":       ("Nonfarm Payrolls",          "growth"),
    "ICSA":         ("Initial Jobless Claims",     "growth"),
    "UNRATE":       ("Unemployment Rate",          "growth"),
    "NFCI":         ("Nat. Financial Conditions",  "fci"),
    "ANFCI":        ("Adj. Financial Conditions",  "fci"),
    "NFCIRISK":     ("NFCI Risk Subindex",         "fci"),
    "NFCICREDIT":   ("NFCI Credit Subindex",       "fci"),
    "NFCILEVERAGE": ("NFCI Leverage Subindex",     "fci"),
    "STLFSI4":      ("St.Louis Fed Stress Index",  "fci"),
    "BAMLH0A0HYM2": ("US High-Yield OAS",          "credit"),
    "BAMLC0A0CM":   ("US Inv-Grade OAS",           "credit"),
    "DGS10":        ("US 10Y Treasury",            "rates"),
    "T10Y2Y":       ("10Y-2Y Spread",              "rates"),
}


# ── Fetch / cache ─────────────────────────────────────────────────────────────

def _api_key() -> str:
    return get_secret("FRED_API_KEY")


def _fetch_series(series_id: str, start: str) -> list[tuple]:
    import requests
    key = _api_key()
    if not key:
        return []
    r = requests.get(f"{FRED_BASE}/series/observations", timeout=30, params={
        "series_id": series_id, "api_key": key, "file_type": "json",
        "observation_start": start, "sort_order": "asc",
    })
    r.raise_for_status()
    out = []
    for o in r.json().get("observations", []):
        v = o.get("value")
        if v in (None, ".", ""):
            continue
        try:
            out.append((series_id, o["date"], float(v)))
        except (ValueError, KeyError):
            continue
    return out


def refresh_fred(years: int = 6) -> dict:
    """Download and cache all catalogued FRED series. Returns stats."""
    init_db()
    start = (datetime.now() - timedelta(days=365 * years)).strftime("%Y-%m-%d")
    if not _api_key():
        logger.warning("No FRED_API_KEY — skipping macro data refresh.")
        return {"series": 0, "rows": 0, "missing": list(SERIES)}
    rows, ok, missing = [], [], []
    for sid in SERIES:
        try:
            s = _fetch_series(sid, start)
            if s:
                rows.extend(s); ok.append(sid)
            else:
                missing.append(sid)
        except Exception as exc:
            logger.warning("FRED %s failed: %s", sid, exc)
            missing.append(sid)
    n = upsert_fred(rows)
    logger.info("FRED: %d series, %d rows (%d missing).", len(ok), n, len(missing))
    return {"series": len(ok), "rows": n, "missing": missing}


# ── Read helpers ──────────────────────────────────────────────────────────────

def series(series_id: str, as_of: str | None = None) -> pd.Series:
    """Cached FRED series as a date-indexed pd.Series (ascending)."""
    try:
        with get_db() as c:
            if as_of:
                df = pd.read_sql_query(
                    "SELECT date, value FROM fred_series WHERE series_id=? AND date<=? "
                    "ORDER BY date", c, params=(series_id, as_of))
            else:
                df = pd.read_sql_query(
                    "SELECT date, value FROM fred_series WHERE series_id=? ORDER BY date",
                    c, params=(series_id,))
    except Exception:
        return pd.Series(dtype=float)
    if df.empty:
        return pd.Series(dtype=float)
    s = pd.Series(df["value"].values, index=pd.to_datetime(df["date"]))
    return s


def latest(series_id: str, as_of: str | None = None):
    s = series(series_id, as_of=as_of)
    return float(s.iloc[-1]) if not s.empty else None


def yoy(series_id: str, as_of: str | None = None) -> float | None:
    """Year-over-year % change of a monthly series."""
    s = series(series_id, as_of=as_of)
    if len(s) < 13:
        return None
    now, prev = s.iloc[-1], s.iloc[-13]
    return round((now / prev - 1) * 100, 2) if prev else None


def _chg(series_id: str, periods: int, as_of: str | None = None) -> float | None:
    s = series(series_id, as_of=as_of)
    if len(s) <= periods:
        return None
    return float(s.iloc[-1] - s.iloc[-1 - periods])


# ── Macro nowcast: real growth x inflation regime ─────────────────────────────

REGIME_DESC = {
    "GOLDILOCKS":     "Growth firm, inflation easing — the best backdrop for equities.",
    "REFLATION":      "Growth firm, inflation rising — favours commodities and value.",
    "STAGFLATION":    "Growth weak, inflation high/rising — the toughest backdrop for equities.",
    "DEFLATION RISK": "Growth weak, inflation easing — favours bonds and defensives.",
}


def _quadrant(growth_up: bool, infl_up: bool) -> str:
    if growth_up and not infl_up:   return "GOLDILOCKS"
    if growth_up and infl_up:       return "REFLATION"
    if not growth_up and infl_up:   return "STAGFLATION"
    return "DEFLATION RISK"


def _clamp(x: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def _weighted(parts: list[tuple[float | None, float]]) -> float | None:
    """Weighted average over the parts whose value is not None (reweighted)."""
    live = [(v, w) for v, w in parts if v is not None]
    if not live:
        return None
    wsum = sum(w for _, w in live)
    return sum(v * w for v, w in live) / wsum if wsum else None


def macro_nowcast(as_of: str | None = None) -> dict:
    """Real growth x inflation regime from FRED. Falls back to {} if no data.

    Beyond the hard quadrant label, this scores each axis on a continuous
    [-1, +1] scale, derives a conviction level from how far the *pivotal* axis
    sits from its zero line, and names the secondary regime the call would flip
    to if that axis crossed — so a borderline read is shown as borderline.
    """
    cfnai = series("CFNAI", as_of=as_of)
    core = series("CPILFESL", as_of=as_of)
    if cfnai.empty or core.empty:
        return {}

    # ── Growth axis ───────────────────────────────────────────────────────────
    # CFNAI is a deviation-from-trend nowcast (0 = trend growth).
    cfnai_ma3 = float(cfnai.tail(3).mean())
    cfnai_dir = float(cfnai.tail(3).mean() - cfnai.tail(6).head(3).mean()) if len(cfnai) >= 6 else 0.0
    indpro_yoy = yoy("INDPRO", as_of=as_of)
    claims_chg = _chg("ICSA", 13, as_of=as_of)  # vs ~3 months ago (weekly series)

    # Continuous growth score in [-1, 1]. CFNAI level carries most of the weight;
    # its direction, industrial-production YoY and jobless-claims trend confirm.
    growth_score = _weighted([
        (_clamp(cfnai_ma3 / 0.7), 0.40),                     # ±0.7 CFNAI ≈ strong signal
        (_clamp(cfnai_dir / 0.5), 0.20),                     # 3m-over-3m acceleration
        (_clamp(indpro_yoy / 3.0) if indpro_yoy is not None else None, 0.25),
        (_clamp(-claims_chg / 100000) if claims_chg is not None else None, 0.15),
    ]) or 0.0
    growth_up = growth_score > 0

    # ── Inflation axis ────────────────────────────────────────────────────────
    core_yoy = yoy("CPILFESL", as_of=as_of)
    core_yoy_6m_ago = None
    if len(core) >= 19:
        core_yoy_6m_ago = round((core.iloc[-7] / core.iloc[-19] - 1) * 100, 2)
    breakeven = latest("T10YIE", as_of=as_of)
    accel_pp = (core_yoy - core_yoy_6m_ago) if (core_yoy is not None and core_yoy_6m_ago is not None) else None

    # Continuous inflation score in [-1, 1]: level vs the 2% target + 6m
    # acceleration + market-implied breakeven. Positive = inflationary.
    inflation_score = _weighted([
        (_clamp((core_yoy - 2.0) / 2.0) if core_yoy is not None else None, 0.45),   # 2%→0, 4%→+1
        (_clamp(accel_pp / 1.0) if accel_pp is not None else None, 0.35),           # ±1pp swing ≈ full
        (_clamp((breakeven - 2.3) / 1.0) if breakeven is not None else None, 0.20),
    ]) or 0.0
    infl_up = inflation_score > 0

    regime = _quadrant(growth_up, infl_up)

    # ── Conviction + secondary call ───────────────────────────────────────────
    # The label flips when the axis nearest zero crosses it, so conviction is
    # governed by that pivotal axis; the secondary regime flips its sign.
    pivot = "growth" if abs(growth_score) <= abs(inflation_score) else "inflation"
    margin = min(abs(growth_score), abs(inflation_score))
    conviction = round(min(100.0, margin / 0.35 * 100), 0)   # |pivot|≥0.35 ⇒ full conviction
    if conviction >= 66:   conviction_label = "High"
    elif conviction >= 33: conviction_label = "Moderate"
    else:                  conviction_label = "Low"
    if pivot == "growth":
        regime_secondary = _quadrant(not growth_up, infl_up)
    else:
        regime_secondary = _quadrant(growth_up, not infl_up)

    return {
        "regime": regime,
        "regime_desc": REGIME_DESC[regime],
        "regime_secondary": regime_secondary,
        "regime_secondary_desc": REGIME_DESC[regime_secondary],
        "growth_up": growth_up,
        "inflation_up": infl_up,
        "growth_score": round(growth_score, 2),
        "inflation_score": round(inflation_score, 2),
        "conviction": conviction,
        "conviction_label": conviction_label,
        "pivot_axis": pivot,
        "cfnai_ma3": round(cfnai_ma3, 2),
        "cfnai_dir": round(cfnai_dir, 2),
        "indpro_yoy": indpro_yoy,
        "claims_3m_chg": claims_chg,
        "core_cpi_yoy": core_yoy,
        "core_cpi_yoy_6m_ago": core_yoy_6m_ago,
        "headline_cpi_yoy": yoy("CPIAUCSL", as_of=as_of),
        "breakeven_10y": breakeven,
        "unemployment": latest("UNRATE", as_of=as_of),
        "as_of": core.index[-1].strftime("%Y-%m-%d"),
    }


def financial_conditions(as_of: str | None = None) -> dict:
    """NFCI-based financial-conditions read (negative NFCI = loose/calm)."""
    nfci = latest("NFCI", as_of=as_of)
    anfci = latest("ANFCI", as_of=as_of)
    hy = latest("BAMLH0A0HYM2", as_of=as_of)
    ig = latest("BAMLC0A0CM", as_of=as_of)
    s = series("NFCI", as_of=as_of)
    nfci_dir = None
    if len(s) >= 13:
        nfci_dir = float(s.iloc[-1] - s.iloc[-13])  # vs ~quarter ago (weekly)
    if nfci is None:
        label, tone = "—", "neutral"
    elif nfci < -0.4:
        label, tone = "Loose", "easy"
    elif nfci < 0:
        label, tone = "Slightly loose", "easy"
    elif nfci < 0.4:
        label, tone = "Slightly tight", "tight"
    else:
        label, tone = "Tight", "tight"
    from data.stats import percentile_rank
    hy_series = series("BAMLH0A0HYM2", as_of=as_of)
    return {
        "nfci": nfci, "anfci": anfci, "nfci_dir": nfci_dir,
        "hy_oas": hy, "ig_oas": ig, "label": label, "tone": tone,
        "nfci_pct": percentile_rank(nfci, s) if not s.empty else None,
        "hy_oas_pct": percentile_rank(hy, hy_series) if not hy_series.empty else None,
        "as_of": s.index[-1].strftime("%Y-%m-%d") if not s.empty else None,
    }


def financial_stress(as_of: str | None = None) -> dict:
    """Decompose financial conditions and build a 0-100 composite stress score.

    The NFCI subindices (risk, credit, leverage) show *where* conditions sit;
    the composite averages the point-in-time percentiles of NFCI, the St. Louis
    Fed Stress Index, high-yield credit spreads and equity volatility (VIX) —
    all oriented so higher = more stress.
    """
    from data.stats import percentile_rank, percentile_label
    sub = {
        "Risk": latest("NFCIRISK", as_of=as_of),
        "Credit": latest("NFCICREDIT", as_of=as_of),
        "Leverage": latest("NFCILEVERAGE", as_of=as_of),
    }
    # Composite from four positively-stress-oriented gauges.
    comps: dict[str, float] = {}
    nfci_s = series("NFCI", as_of=as_of)
    if not nfci_s.empty:
        comps["NFCI"] = percentile_rank(float(nfci_s.iloc[-1]), nfci_s)
    stlfsi_s = series("STLFSI4", as_of=as_of)
    if not stlfsi_s.empty:
        comps["Fed Stress"] = percentile_rank(float(stlfsi_s.iloc[-1]), stlfsi_s)
    hy_s = series("BAMLH0A0HYM2", as_of=as_of)
    if not hy_s.empty:
        comps["HY Credit"] = percentile_rank(float(hy_s.iloc[-1]), hy_s)
    try:
        from data import store
        vix = store.series("^VIX", as_of=as_of)
        if not vix.empty:
            comps["Equity Vol"] = percentile_rank(float(vix["close"].iloc[-1]), vix["close"])
    except Exception:
        pass
    vals = [v for v in comps.values() if v is not None]
    composite = round(sum(vals) / len(vals), 1) if vals else None
    return {
        "subindices": sub,
        "components": {k: v for k, v in comps.items() if v is not None},
        "composite": composite,
        "composite_label": percentile_label(composite),
        "as_of": nfci_s.index[-1].strftime("%Y-%m-%d") if not nfci_s.empty else None,
    }
