"""
Ensemble regime — agreement across the independent regime reads.

Multi-model desks don't trust one classifier; they look at whether independent
methods agree. We have three: the FRED growth×inflation nowcast, the ETF-momentum
proxy, and the Gaussian-Bayes probability model. When they agree, conviction is
real; when they split, that disagreement is itself the signal.
"""

from __future__ import annotations

from collections import Counter

from data import signals, store


def ensemble_regime(as_of: str | None = None) -> dict:
    m = store.latest_metrics(as_of=as_of)

    # 1. FRED growth×inflation nowcast.
    fred_reg = None
    try:
        from data import fred
        fred_reg = fred.macro_nowcast(as_of=as_of).get("regime")
    except Exception:
        pass

    # 2. ETF-momentum proxy (independent methodology).
    tnx, irx = signals._g(m, "^TNX"), signals._g(m, "^IRX")
    curve = (tnx - irx) if (tnx is not None and irx is not None) else None
    proxy_reg = signals._macro_regime(m, curve)

    # 3. Gaussian-Bayes probability model.
    model_reg = None
    try:
        from data.regime_model import regime_probabilities
        model_reg = regime_probabilities().get("top")
    except Exception:
        pass

    votes = [r for r in (fred_reg, proxy_reg, model_reg) if r]
    if not votes:
        return {}
    cnt = Counter(votes)
    consensus, top_n = cnt.most_common(1)[0]
    return {
        "fred": fred_reg,
        "proxy": proxy_reg,
        "model": model_reg,
        "consensus": consensus,
        "agreement": f"{top_n}/{len(votes)}",
        "unanimous": top_n == len(votes),
        "split": top_n < len(votes),
    }
