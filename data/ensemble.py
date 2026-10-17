"""
Ensemble regime — agreement across the independent regime reads.

Multi-model desks don't trust one classifier; they look at whether independent
methods agree. Two reads are genuinely independent: the FRED growth×inflation
nowcast (economic data) and the ETF-momentum proxy (market prices). The
Gaussian-Bayes probability model is *trained on the nowcast's own labels*, so it
is shown as the nowcast's confidence, not counted as a third vote — counting it
would overstate agreement ("2/3") when it mostly echoes vote #1.
"""

from __future__ import annotations

from data import signals, store


def ensemble_regime(as_of: str | None = None) -> dict:
    m = store.latest_metrics(as_of=as_of)

    # 1. FRED growth×inflation nowcast (economic data).
    fred_reg = None
    try:
        from data import fred
        fred_reg = fred.macro_nowcast(as_of=as_of).get("regime")
    except Exception:
        pass

    # 2. ETF-momentum proxy (market prices — independent methodology).
    tnx, irx = signals._g(m, "^TNX"), signals._g(m, "^IRX")
    curve = (tnx - irx) if (tnx is not None and irx is not None) else None
    proxy_reg = signals._macro_regime(m, curve)

    # Confidence on the nowcast (derived from it — not a vote).
    model = {}
    try:
        from data.regime_model import regime_probabilities
        model = regime_probabilities() if as_of is None else {}
    except Exception:
        pass

    votes = [r for r in (fred_reg, proxy_reg) if r]
    if not votes:
        return {}
    consensus = fred_reg or proxy_reg  # the economic-data read leads on a split
    agree = len(votes) == 2 and fred_reg == proxy_reg

    # Market-state overlay (calm/stressed) — a different label space, so not a vote.
    stress = {}
    try:
        from data.wk_regime import wk_regime
        stress = wk_regime(as_of=as_of)
    except Exception:
        pass
    return {
        "stress": stress,
        "fred": fred_reg,
        "proxy": proxy_reg,
        "model": model.get("top"),
        "model_prob": model.get("top_prob"),
        "consensus": consensus,
        "agreement": f"{2 if agree else 1}/{len(votes)}",
        "unanimous": agree,
        "split": len(votes) == 2 and not agree,
    }
