"""
Probabilistic regime model — soft 4-regime probabilities with persistence.

The base nowcast emits a hard quadrant label plus a heuristic conviction. This
layers a data-driven probability on top, the way institutional desks do it
(Two Sigma fit a Gaussian mixture on factor returns and report four regime
probabilities that sum to 100%; HMMs add the temporal persistence a plain GMM
lacks). Here we:

  1. fit a Gaussian to the (growth_score, inflation_score) points that history
     actually labelled each regime — a Gaussian-Bayes emission model;
  2. score today's point under each regime via Bayes → emission probabilities;
  3. blend with the empirical Markov transition from yesterday's regime so the
     probabilities respect persistence (regimes are sticky).

numpy only — no sklearn/hmmlearn dependency, keeping the cloud build light.
"""

from __future__ import annotations

import numpy as np

from data import store

REGIMES = ["GOLDILOCKS", "REFLATION", "STAGFLATION", "DEFLATION RISK"]

# How much weight the persistence prior gets vs today's emission read.
_PERSIST = 0.35


def _history():
    ms = store.signal_history("macro_signals")
    if ms.empty or "growth_score" not in ms.columns:
        return None
    ms = ms.dropna(subset=["growth_score", "inflation_score", "macro_regime"])
    return ms if len(ms) >= 20 else None


def _transition_row(labels: np.ndarray, prev: str) -> dict:
    """Empirical P(next=r | prev) from the realised label sequence."""
    nxt = {}
    for a, b in zip(labels[:-1], labels[1:]):
        if a == prev:
            nxt[b] = nxt.get(b, 0) + 1
    tot = sum(nxt.values())
    if not tot:
        return {}
    return {r: nxt.get(r, 0) / tot for r in REGIMES}


def regime_probabilities(growth: float | None = None, inflation: float | None = None) -> dict:
    """Soft probabilities over the four regimes for the given (or latest) point."""
    ms = _history()
    if ms is None:
        return {}
    X = ms[["growth_score", "inflation_score"]].to_numpy(dtype=float)
    labels = ms["macro_regime"].to_numpy()

    if growth is None or inflation is None:
        growth = float(ms["growth_score"].iloc[-1])
        inflation = float(ms["inflation_score"].iloc[-1])
    pt = np.array([growth, inflation], dtype=float)

    global_var = np.clip(X.var(axis=0), 1e-3, None)  # variance floor for stability
    logp = {}
    for r in REGIMES:
        mask = labels == r
        n = int(mask.sum())
        if n == 0:
            continue
        mu = X[mask].mean(axis=0)
        v = np.clip(X[mask].var(axis=0), global_var * 0.5, None) if n > 2 else global_var
        ll = -0.5 * np.sum((pt - mu) ** 2 / v + np.log(2 * np.pi * v))
        logp[r] = ll + np.log(n)  # + log prior (regime frequency)
    if not logp:
        return {}

    hi = max(logp.values())
    ex = {r: float(np.exp(logp[r] - hi)) for r in logp}
    z = sum(ex.values())
    emission = {r: ex.get(r, 0.0) / z for r in REGIMES}

    # Persistence blend from yesterday's realised regime.
    prev = labels[-2] if len(labels) >= 2 else labels[-1]
    trow = _transition_row(labels, prev)
    if trow:
        blended = {r: (1 - _PERSIST) * emission[r] + _PERSIST * trow.get(r, 0.0) for r in REGIMES}
    else:
        blended = emission
    zb = sum(blended.values()) or 1.0
    probs = {r: blended[r] / zb for r in REGIMES}

    ranked = sorted(probs.items(), key=lambda kv: kv[1], reverse=True)
    return {
        "probabilities": {r: round(probs[r] * 100, 1) for r in REGIMES},
        "top": ranked[0][0], "top_prob": round(ranked[0][1] * 100, 1),
        "runner_up": ranked[1][0], "runner_up_prob": round(ranked[1][1] * 100, 1),
        "n_train": int(len(X)),
    }


def regime_transitions(steps: int = 21) -> dict:
    """Markov transition analytics: where the regime goes next + how long it lasts.

    Estimates the 4×4 day-to-day transition matrix from the realised label
    sequence, then raises it to ``steps`` (≈1 month of trading days) for the
    forward distribution from today's regime, and reads expected persistence off
    the diagonal (geometric mean duration = 1/(1−P_stay)).
    """
    ms = _history()
    if ms is None:
        return {}
    labels = ms["macro_regime"].to_numpy()
    idx = {r: i for i, r in enumerate(REGIMES)}
    M = np.zeros((4, 4))
    for a, b in zip(labels[:-1], labels[1:]):
        if a in idx and b in idx:
            M[idx[a], idx[b]] += 1
    rs = M.sum(axis=1, keepdims=True)
    rs[rs == 0] = 1.0
    P = M / rs

    cur = labels[-1]
    if cur not in idx:
        return {}
    Pn = np.linalg.matrix_power(P, max(1, steps))
    dist = Pn[idx[cur]]
    p_stay = float(P[idx[cur], idx[cur]])
    exp_dur = round(1 / (1 - p_stay)) if p_stay < 0.999 else None

    nxt = {r: round(float(dist[idx[r]]) * 100, 1) for r in REGIMES}
    ranked = sorted(nxt.items(), key=lambda kv: kv[1], reverse=True)
    return {
        "current": cur,
        "steps": steps,
        "next_period": nxt,
        "most_likely_next": ranked[0][0],
        "change_prob": round(100 - nxt.get(cur, 0), 1),  # P(not in current regime in `steps`)
        "stay_prob_daily": round(p_stay * 100, 1),
        "expected_duration_days": exp_dur,
        "matrix": {a: {b: round(float(P[idx[a], idx[b]]) * 100, 1) for b in REGIMES} for a in REGIMES},
    }
