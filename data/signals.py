"""
MacroSignal scoring engine.

Pure function of macro.db: reads the latest per-ticker metrics and produces the
risk-on/risk-off composite, the seven MacroSignal dimensions (-2..+2), the
MacroCompass score (0-100), the five-state market regime and the four-state
macro regime. The dashboard calls compute_signals() live (cached); run_macro
also persists the output so history accrues.
"""

from __future__ import annotations

from datetime import datetime

from data import store

# ── Dimension weights for the MacroCompass score ──────────────────────────────
WEIGHTS = {
    "equity_momentum": 0.20,
    "yield_curve":     0.20,
    "credit":          0.20,
    "volatility":      0.15,
    "commodity":       0.10,
    "regional":        0.10,
    "style":           0.05,
}


def _g(m: dict, ticker: str, field: str = "close"):
    v = m.get(ticker, {}).get(field)
    return v if isinstance(v, (int, float)) else None


def _clamp_signal(x: float) -> int:
    return int(max(-2, min(2, round(x))))


# ── Seven MacroSignal dimensions ──────────────────────────────────────────────

def _equity_momentum(m: dict) -> int:
    score = 0
    for tk in ("SPY", "^GSPTSE"):
        ma20, ma50 = _g(m, tk, "ma20"), _g(m, tk, "ma50")
        if ma20 is not None and ma50 is not None:
            score += 1 if ma20 > ma50 else -1
    return _clamp_signal(score)


def _style_signal(m: dict) -> int:
    g, v = _g(m, "IWF", "return_1m"), _g(m, "IWD", "return_1m")
    if g is None or v is None:
        return 0
    spread = g - v
    if spread > 2:   return 1
    if spread > 0.5: return 1 if spread > 1 else 0
    if spread < -2:  return -1
    return 0


def _regional_signal(m: dict) -> int:
    us, em = _g(m, "SPY", "return_1m"), _g(m, "EEM", "return_1m")
    if us is None or em is None:
        return 0
    spread = us - em
    if spread > 2:  return 1
    if spread < -2: return -1
    return 0


def _yield_curve_signal(spread: float | None) -> int:
    if spread is None:
        return 0
    # Inverted curve is bearish; steep positive is bullish
    if spread < -0.5: return -2
    if spread < 0:    return -1
    if spread > 1.5:  return 2
    if spread > 0.5:  return 1
    return 0


def _credit_signal(m: dict) -> int:
    hyg, ief = _g(m, "HYG", "return_5d"), _g(m, "IEF", "return_5d")
    if hyg is None or ief is None:
        return 0
    spread = hyg - ief  # HYG outperforming = risk-on / spreads tightening
    if spread > 1:   return 2
    if spread > 0.2: return 1
    if spread < -1:  return -2
    if spread < -0.2: return -1
    return 0


def _commodity_signal(m: dict) -> int:
    oil, cop = _g(m, "CL=F", "return_1m"), _g(m, "HG=F", "return_1m")
    vals = [x for x in (oil, cop) if x is not None]
    if not vals:
        return 0
    avg = sum(vals) / len(vals)
    if avg > 5:  return 2
    if avg > 1:  return 1
    if avg < -5: return -2
    if avg < -1: return -1
    return 0


def _volatility_signal(level: float | None, avg: float | None) -> int:
    if level is None or avg is None:
        return 0
    if level < avg * 0.85: return 2
    if level < avg:        return 1
    if level > avg * 1.15: return -2
    if level > avg:        return -1
    return 0


# ── Risk-on/off composite (0-100) ─────────────────────────────────────────────

def _risk_composite(vix_level, vix_avg, credit_spread, usd_trend, gold_trend) -> tuple[float, list[str]]:
    """Weighted 0-100 risk-on score + the biggest drivers."""
    subs, drivers = [], []

    # VIX direction (35%) — falling/below-average VIX = risk-on
    if vix_level is not None and vix_avg is not None:
        v = 0.5 + (vix_avg - vix_level) / max(vix_avg, 1) * 1.2
        v = max(0, min(1, v))
        subs.append((v, 0.35))
        if v > 0.6:   drivers.append(("VIX below its 20-day average — calm tape", v))
        elif v < 0.4: drivers.append(("VIX rising above its 20-day average — fear building", v))

    # Credit direction (30%) — tightening spreads (HYG>IEF) = risk-on
    if credit_spread is not None:
        v = 0.5 + max(-0.5, min(0.5, credit_spread / 4))
        subs.append((v, 0.30))
        if v > 0.6:   drivers.append(("Credit spreads tightening — high yield bid", v))
        elif v < 0.4: drivers.append(("Credit spreads widening — risk appetite fading", v))

    # USD direction (20%) — softer USD = risk-on
    if usd_trend is not None:
        v = 0.5 - max(-0.5, min(0.5, usd_trend / 6))
        subs.append((v, 0.20))
        if v > 0.6:   drivers.append(("US dollar softening — supportive for risk assets", v))
        elif v < 0.4: drivers.append(("US dollar strengthening — a headwind for risk", v))

    # Gold direction (15%) — falling gold = risk-on
    if gold_trend is not None:
        v = 0.5 - max(-0.5, min(0.5, gold_trend / 8))
        subs.append((v, 0.15))
        if v < 0.4:   drivers.append(("Gold bid — defensive demand present", 1 - v))

    if not subs:
        return 50.0, ["Insufficient data to score risk appetite."]
    wsum = sum(w for _, w in subs)
    score = sum(s * w for s, w in subs) / wsum * 100
    drivers.sort(key=lambda d: abs(d[1] - 0.5), reverse=True)
    return round(score, 1), [d[0] for d in drivers[:3]]


# ── Regimes ───────────────────────────────────────────────────────────────────

REGIME_DESC = {
    "RISK-ON BULL":     "Low volatility, positive momentum, normal curve — favour cyclicals, growth, beta.",
    "LATE CYCLE":       "Rising volatility with strong momentum and a flattening curve — favour quality, energy, value.",
    "RISK-OFF":         "Elevated volatility and fading momentum — favour defensives, low-vol, cash.",
    "RECESSION SIGNAL": "Inverted curve, widening credit, falling momentum — favour duration, staples, utilities.",
    "RECOVERY":         "Falling volatility, early momentum, steep curve — favour small caps, financials, cyclicals.",
}


def _market_regime(vix_level, vix_avg, curve_spread, spy_mom) -> str:
    rising_vix = vix_level is not None and vix_avg is not None and vix_level > vix_avg
    high_vix   = vix_level is not None and vix_level > 22
    inverted   = curve_spread is not None and curve_spread < 0
    steep      = curve_spread is not None and curve_spread > 1.0
    pos_mom    = spy_mom is not None and spy_mom > 0
    strong_mom = spy_mom is not None and spy_mom > 4

    if inverted and not pos_mom:
        return "RECESSION SIGNAL"
    if high_vix and not pos_mom:
        return "RISK-OFF"
    if rising_vix and strong_mom:
        return "LATE CYCLE"
    if steep and not rising_vix and pos_mom:
        return "RECOVERY"
    if not high_vix and pos_mom:
        return "RISK-ON BULL"
    return "LATE CYCLE"


MACRO_REGIME_DESC = {
    "GOLDILOCKS":    "Growth firm, inflation easing — the best backdrop for equities.",
    "REFLATION":     "Growth firm, inflation rising — favours commodities and value.",
    "STAGFLATION":   "Growth weak, inflation high — the toughest backdrop for equities.",
    "DEFLATION RISK":"Growth weak, inflation easing — favours bonds and defensives.",
}


def _macro_regime(m: dict, curve_spread) -> str:
    # Growth proxy: cyclicals vs defensives 1m; Inflation proxy: commodity 1m + breakevens
    cyc = [_g(m, t, "return_1m") for t in ("XLI", "XLY", "SPY")]
    cyc = [x for x in cyc if x is not None]
    growth_up = (sum(cyc) / len(cyc) > 0) if cyc else (curve_spread or 0) > 0

    infl = [_g(m, t, "return_1m") for t in ("CL=F", "HG=F", "GC=F")]
    infl = [x for x in infl if x is not None]
    infl_up = (sum(infl) / len(infl) > 1.5) if infl else False

    if growth_up and not infl_up:  return "GOLDILOCKS"
    if growth_up and infl_up:      return "REFLATION"
    if not growth_up and infl_up:  return "STAGFLATION"
    return "DEFLATION RISK"


# ── Breadth ───────────────────────────────────────────────────────────────────

def _breadth(m: dict) -> float | None:
    from data import tickers as T
    basket = [t for t, _, _ in (T.SECTOR_US + T.EQUITY_BENCHMARKS)
              if t not in ("^VIX",)]
    above, total = 0, 0
    for tk in basket:
        close, ma200 = _g(m, tk, "close"), _g(m, tk, "ma200")
        if close is not None and ma200 is not None:
            total += 1
            if close > ma200:
                above += 1
    return round(above / total * 100, 1) if total else None


# ── Top-level ─────────────────────────────────────────────────────────────────

def compute_signals(metrics: dict | None = None, as_of: str | None = None) -> dict:
    m = metrics if metrics is not None else store.latest_metrics(as_of=as_of)

    vix_level = _g(m, "^VIX", "close")
    # 20-day average VIX from its series
    vix_avg = None
    vs = store.series("^VIX", days=21, as_of=as_of)
    if not vs.empty:
        vix_avg = round(float(vs["close"].tail(20).mean()), 2)

    tnx = _g(m, "^TNX", "close")
    irx = _g(m, "^IRX", "close")
    curve_spread = round(tnx - irx, 2) if (tnx is not None and irx is not None) else None

    hyg_r = _g(m, "HYG", "return_5d")
    ief_r = _g(m, "IEF", "return_5d")
    credit_spread = round(hyg_r - ief_r, 2) if (hyg_r is not None and ief_r is not None) else None

    usd_trend = _g(m, "DX-Y.NYB", "return_1m")
    gold_trend = _g(m, "GC=F", "return_1m")
    oil_trend = _g(m, "CL=F", "return_1m")
    copper_trend = _g(m, "HG=F", "return_1m")
    breadth = _breadth(m)
    spy_mom = _g(m, "SPY", "return_1m")

    risk_score, drivers = _risk_composite(vix_level, vix_avg, credit_spread, usd_trend, gold_trend)
    regime = _market_regime(vix_level, vix_avg, curve_spread, spy_mom)

    # Prefer the real growth x inflation nowcast from FRED data; fall back to the
    # ETF-momentum proxy when FRED data is unavailable (e.g. no API key).
    nowcast, fci = {}, {}
    try:
        from data import fred
        nowcast = fred.macro_nowcast(as_of=as_of)
        fci = fred.financial_conditions(as_of=as_of)
    except Exception:
        nowcast, fci = {}, {}
    if nowcast.get("regime"):
        macro_regime = nowcast["regime"]
        macro_regime_desc = nowcast["regime_desc"]
        macro_source = "FRED"
    else:
        macro_regime = _macro_regime(m, curve_spread)
        macro_regime_desc = MACRO_REGIME_DESC.get(macro_regime, "")
        macro_source = "proxy"
    macro_conviction = nowcast.get("conviction")
    macro_conviction_label = nowcast.get("conviction_label")
    macro_regime_secondary = nowcast.get("regime_secondary")
    macro_regime_secondary_desc = nowcast.get("regime_secondary_desc")

    dims = {
        "equity_momentum": _equity_momentum(m),
        "style":           _style_signal(m),
        "regional":        _regional_signal(m),
        "yield_curve":     _yield_curve_signal(curve_spread),
        "credit":          _credit_signal(m),
        "commodity":       _commodity_signal(m),
        "volatility":      _volatility_signal(vix_level, vix_avg),
    }

    # Compass score: weighted avg of dims (-2..2) mapped to 0..100
    wsum = sum(WEIGHTS[k] for k in dims)
    weighted = sum(dims[k] * WEIGHTS[k] for k in dims) / wsum  # -2..2
    compass_score = round((weighted + 2) / 4 * 100, 1)

    today = (as_of or store.latest_date() or datetime.now().strftime("%Y-%m-%d"))
    return {
        "date": today,
        "summary": {
            "vix_level": vix_level,
            "vix_20d_avg": vix_avg,
            "yield_curve_spread": curve_spread,
            "credit_spread_proxy": credit_spread,
            "usd_trend": usd_trend,
            "gold_trend": gold_trend,
            "oil_trend": oil_trend,
            "copper_trend": copper_trend,
            "breadth": breadth,
            "risk_score": risk_score,
        },
        "dimensions": dims,
        "compass_score": compass_score,
        "risk_score": risk_score,
        "risk_drivers": drivers,
        "regime": regime,
        "regime_desc": REGIME_DESC.get(regime, ""),
        "macro_regime": macro_regime,
        "macro_regime_desc": macro_regime_desc,
        "macro_regime_secondary": macro_regime_secondary,
        "macro_regime_secondary_desc": macro_regime_secondary_desc,
        "macro_conviction": macro_conviction,
        "macro_conviction_label": macro_conviction_label,
        "macro_source": macro_source,
        "macro_nowcast": nowcast,
        "financial_conditions": fci,
    }


def signal_context() -> dict:
    """Percentile context for the headline signals vs their own history.

    Turns absolute readings into relative ones ("risk appetite at the 78th
    percentile of the past year") — the institutional way to read a level.
    """
    from data.stats import percentile_rank, percentile_label
    out: dict = {}
    ss = store.signal_history("signal_scores")
    ms = store.signal_history("macro_signals")
    if not ss.empty and "compass_score" in ss:
        cur = float(ss["compass_score"].iloc[-1])
        p = percentile_rank(cur, ss["compass_score"])
        out["compass_pct"] = p
        out["compass_pct_label"] = percentile_label(p)
    if not ms.empty and "risk_score" in ms:
        cur = float(ms["risk_score"].iloc[-1])
        p = percentile_rank(cur, ms["risk_score"])
        out["risk_pct"] = p
        out["risk_pct_label"] = percentile_label(p)
        if "breadth" in ms and ms["breadth"].notna().any():
            out["breadth_pct"] = percentile_rank(float(ms["breadth"].iloc[-1]), ms["breadth"])
    vs = store.series("^VIX")
    if not vs.empty:
        out["vix_pct"] = percentile_rank(float(vs["close"].iloc[-1]), vs["close"])
    return out


def persist_signals(sig: dict) -> None:
    """Write the computed signals to macro.db for history tracking."""
    from data.db import store_macro_signals, store_signal_scores
    run_ts = datetime.now().isoformat(timespec="seconds")
    s = sig["summary"]
    nc = sig.get("macro_nowcast") or {}
    store_macro_signals({
        "date": sig["date"], "run_ts": run_ts,
        "vix_level": s["vix_level"], "vix_20d_avg": s["vix_20d_avg"],
        "yield_curve_spread": s["yield_curve_spread"],
        "credit_spread_proxy": s["credit_spread_proxy"],
        "usd_trend": s["usd_trend"], "gold_trend": s["gold_trend"],
        "oil_trend": s["oil_trend"], "copper_trend": s["copper_trend"],
        "breadth": s["breadth"], "risk_score": sig["risk_score"],
        "regime": sig["regime"], "macro_regime": sig["macro_regime"],
        "growth_score": nc.get("growth_score"), "inflation_score": nc.get("inflation_score"),
        "conviction": sig.get("macro_conviction"),
    })
    d = sig["dimensions"]
    store_signal_scores({
        "date": sig["date"], "run_ts": run_ts,
        "equity_momentum": d["equity_momentum"], "style": d["style"],
        "regional": d["regional"], "yield_curve": d["yield_curve"],
        "credit": d["credit"], "commodity": d["commodity"],
        "volatility": d["volatility"], "compass_score": sig["compass_score"],
    })
