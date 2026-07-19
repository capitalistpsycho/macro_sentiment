"""
Regime → positioning: All-Weather-style tilts + a vol-targeted exposure scalar.

This turns the regime *call* into an *allocation* the way Bridgewater's All Weather
frames it — balance exposure across the growth×inflation environments, then tilt
toward the environment the nowcast says we're in. Tilts are blended by the live
regime probabilities (soft, not a hard switch). Separately, a vol-target scalar
scales gross exposure so realised risk sits near a chosen budget (systematic desks
manage to a vol target, e.g. Bridgewater Pure Alpha ~12%).

Tilts are stylised playbook guidance (−2 strong underweight … +2 strong overweight),
NOT portfolio advice.
"""

from __future__ import annotations

from data import store

ASSETS = ["Equities", "Duration (bonds)", "Credit", "Commodities", "Gold", "Cash / T-bills"]

# Per-regime tilt (-2..+2) by asset class — the environment each asset prefers.
_REGIME_TILTS = {
    "GOLDILOCKS":     {"Equities": +2, "Duration (bonds)": +1, "Credit": +2, "Commodities": -1, "Gold": -1, "Cash / T-bills": -2},
    "REFLATION":      {"Equities": +1, "Duration (bonds)": -2, "Credit": +1, "Commodities": +2, "Gold": +1, "Cash / T-bills": -1},
    "STAGFLATION":    {"Equities": -2, "Duration (bonds)": -1, "Credit": -1, "Commodities": +2, "Gold": +2, "Cash / T-bills": +1},
    "DEFLATION RISK": {"Equities": -1, "Duration (bonds)": +2, "Credit": -2, "Commodities": -2, "Gold": +1, "Cash / T-bills": +1},
}


def suggested_tilts(probs: dict | None = None) -> dict:
    """Probability-blended asset-class tilts. probs: {regime: pct}."""
    if not probs:
        try:
            from data.regime_model import regime_probabilities
            probs = regime_probabilities().get("probabilities", {})
        except Exception:
            probs = {}
    if not probs:
        return {}
    wsum = sum(probs.values()) or 1.0
    blended = {}
    for a in ASSETS:
        blended[a] = round(sum(_REGIME_TILTS[r][a] * (probs.get(r, 0) / wsum)
                               for r in _REGIME_TILTS), 2)
    return {"tilts": blended, "probs": probs}


def vol_target(target_annual: float = 12.0, cap: float = 1.5) -> dict:
    """Vol-target gross-exposure scalar from current realised/implied equity vol.

    exposure = clamp(target / current_vol, 0.25, cap). Uses SPY 20-day realised
    vol, falling back to VIX. Lower vol → scale up; stress → scale down.
    """
    cur = None
    s = store.series("SPY", days=40)
    if not s.empty and len(s) > 21:
        import numpy as np
        rets = s["close"].astype(float).pct_change().dropna()
        cur = float(rets.tail(20).std() * np.sqrt(252) * 100)
    if cur is None or cur <= 0:
        vix = store.latest_metrics().get("^VIX", {}).get("close")
        cur = float(vix) if vix else None
    if not cur:
        return {}
    raw = target_annual / cur
    exposure = max(0.25, min(cap, raw))
    return {
        "current_vol": round(cur, 1),
        "target_vol": target_annual,
        "exposure": round(exposure, 2),
        "capped": raw > cap,
        "read": ("low vol — room to add risk to hit the vol budget" if exposure > 1.05 else
                 "elevated vol — trim gross to hold the vol budget" if exposure < 0.95 else
                 "vol near target — neutral sizing"),
    }
