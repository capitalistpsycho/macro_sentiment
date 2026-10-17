"""
Nowcasts — inflation before the CPI print, and macro momentum.

Inflation nowcast (Cleveland Fed method, Knotek & Zaman 2014, simplified): core and
food inflation for the not-yet-released month are their trailing 12-month average
monthly changes; gasoline is read from weekly retail gasoline prices so far in the
month — the only fast-moving piece, and the reason the nowcast beats lagged CPI.

Macro momentum (Brooks/AQR, "A Half Century of Macro Momentum", JPM 2017;
"Economic Trend", 2024): trends in fundamentals — business cycle, inflation,
monetary policy, FX/trade, risk sentiment — standardised against their own
history, then mapped to directional tilts for equities, bonds and the USD. The
business-cycle line doubles as a model-based economic-surprise gauge (revisions
to GDPNow / CFNAI), the free substitute for a consensus-based surprise index.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from data.macro_risk import long_series

# CPI relative-importance weights. ponytail: fixed weights (BLS re-weights each
# December; drift is a few tenths) — read them from BLS if precision matters.
_W_CORE, _W_FOOD, _W_GAS = 0.832, 0.135, 0.033


def _mm(s: pd.Series) -> pd.Series:
    return (s / s.shift(1) - 1) * 100


def inflation_nowcast() -> dict:
    from data.fred import monthly_filled
    cpi, core, food = (monthly_filled(long_series(s)) for s in ("CPIAUCSL", "CPILFESL", "CPIUFDSL"))
    gas = long_series("GASREGW")
    if cpi.empty or core.empty or food.empty or gas.empty:
        return {}
    last = cpi.index[-1]                       # latest released CPI month
    target = last + pd.offsets.MonthBegin(1)   # the month being nowcast
    core_mm = float(_mm(core).tail(12).mean())
    food_mm = float(_mm(food).tail(12).mean())
    g_now = gas[(gas.index >= target) & (gas.index < target + pd.offsets.MonthBegin(1))]
    g_prev = gas[(gas.index >= last) & (gas.index < target)]
    if g_prev.empty:
        return {}
    gas_mm = float(g_now.mean() / g_prev.mean() - 1) * 100 if not g_now.empty else 0.0
    head_mm = _W_CORE * core_mm + _W_FOOD * food_mm + _W_GAS * gas_mm

    def yoy(level_prev_month: float, idx: pd.Series, mm: float) -> float | None:
        base = idx[idx.index == target - pd.DateOffset(years=1)]
        return round((level_prev_month * (1 + mm / 100) / float(base.iloc[0]) - 1) * 100, 2) \
            if not base.empty else None
    return {
        "target": target.strftime("%b %Y"),
        "headline_mm": round(head_mm, 2), "core_mm": round(core_mm, 2),
        "gas_mm": round(gas_mm, 1), "gas_weeks": int(len(g_now)),
        "headline_yoy": yoy(float(cpi.iloc[-1]), cpi, head_mm),
        "core_yoy": yoy(float(core.iloc[-1]), core, core_mm),
        "last_month": last.strftime("%b %Y"),
        "last_headline_yoy": round(float(cpi.iloc[-1] / cpi.iloc[-13] - 1) * 100, 2),
        "last_core_yoy": round(float(core.iloc[-1] / core.iloc[-13] - 1) * 100, 2),
    }


# ── Macro momentum ────────────────────────────────────────────────────────────

def _z(change: pd.Series) -> float | None:
    """Latest change standardised by the std of that change over its own history."""
    c = change.dropna()
    if len(c) < 24 or c.std() == 0:
        return None
    return round(float(np.clip(c.iloc[-1] / c.std(), -3, 3)), 2)


def _monthly(sid: str) -> pd.Series:
    s = long_series(sid)
    return s.resample("ME").last().dropna() if not s.empty else s


def macro_momentum() -> dict:
    from data import store
    ind: dict[str, dict] = {}

    cf = _monthly("CFNAI").rolling(3).mean()
    gdpnow = long_series("GDPNOW")
    claims = _monthly("ICSA")
    growth_parts = [_z(cf - cf.shift(3)), _z(-(claims / claims.shift(3) - 1))]
    if not gdpnow.empty:  # revisions to the current-quarter nowcast ≈ data surprises
        g = gdpnow.resample("W").last().ffill()
        growth_parts.append(_z(g - g.shift(4)))
    gp = [x for x in growth_parts if x is not None]
    if gp:
        ind["growth"] = {"label": "Business cycle (CFNAI Δ3m, claims, GDPNow revisions)",
                         "z": round(float(np.mean(gp)), 2)}

    from data.fred import monthly_filled
    core = monthly_filled(long_series("CPILFESL"))
    if not core.empty:
        ann3 = ((core / core.shift(3)) ** 4 - 1) * 100
        yoy = (core / core.shift(12) - 1) * 100
        z = _z(ann3 - yoy)
        if z is not None:
            ind["inflation"] = {"label": "Inflation trend (core 3m ann. − y/y)", "z": z}

    y2 = _monthly("DGS2")
    if not y2.empty:
        z = _z(y2 - y2.shift(3))
        if z is not None:
            ind["policy"] = {"label": "Monetary policy (2Y yield Δ3m; + = tightening)", "z": z}

    try:
        from data.fred import series as fs
        usd = fs("DTWEXBGS").resample("ME").last().dropna()
        z = _z((usd / usd.shift(3) - 1) * 100) if len(usd) > 30 else None
        if z is not None:
            ind["usd"] = {"label": "Trade / FX (broad USD Δ3m; + = stronger)", "z": z}
    except Exception:
        pass

    spx = store.long_closes("^GSPC")
    if not spx.empty:
        px = spx.set_index("date")["close"].resample("ME").last()
        z = _z((px / px.shift(12) - 1) * 100)
        if z is not None:
            ind["risk"] = {"label": "Risk sentiment (S&P 12m return)", "z": z}
    if not ind:
        return {}

    def g(k):
        return ind.get(k, {}).get("z") or 0.0
    # Brooks/AQR directional mappings (sign of each fundamental trend per asset).
    tilts = {
        "Equities": (g("growth") - g("policy") - 0.5 * g("usd") + g("risk")) / 3.5,
        "Bonds (duration)": (-g("growth") - g("inflation") - g("policy") - 0.5 * g("risk")) / 3.5,
        "US dollar": (g("growth") + g("policy") - 0.5 * g("risk")) / 2.5,
    }
    return {"indicators": ind,
            "tilts": {k: round(float(v), 2) for k, v in tilts.items()}}


if __name__ == "__main__":
    # Self-check: _z standardises and clips.
    s = pd.Series(np.r_[np.random.default_rng(0).standard_normal(100), 10.0])
    assert _z(s) == 3.0
    assert _z(pd.Series([1.0] * 10)) is None
    print("ok")
