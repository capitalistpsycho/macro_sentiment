"""
Wasserstein k-means market-state regime (Horvath, Issa & Muguruza, SSRN 3947905).

The quadrant models answer "what macro regime?"; this answers "is the tape calm or
stressed?" straight from the shape of the return distribution. Each rolling window
of SPY daily log-returns is an empirical distribution; k-means runs on those using
the 1-Wasserstein distance (mean |sorted a - sorted b|) and the W1 barycenter
(element-wise median of the sorted windows). Robust to fat tails where a Gaussian
model blurs regimes. Point-in-time: centroids are fit on past windows only, then
today's window is assigned.
"""

from __future__ import annotations

import numpy as np

from data import store

WINDOW, STEP, ITERS = 20, 5, 50


def _windows(r: np.ndarray) -> np.ndarray:
    """Sorted rolling windows (rows) — sorting once makes W1 a plain mean-abs-diff."""
    idx = range(0, len(r) - WINDOW + 1, STEP)
    return np.sort(np.stack([r[i:i + WINDOW] for i in idx]), axis=1)


def wk_means(W: np.ndarray, k: int = 2, seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
    """Centroids sorted by variance (0 = calm) and labels for each sorted window."""
    rng = np.random.default_rng(seed)
    C = W[rng.choice(len(W), k, replace=False)]
    for _ in range(ITERS):
        lab = np.abs(W[:, None, :] - C[None]).mean(axis=2).argmin(axis=1)
        new = np.stack([np.median(W[lab == j], axis=0) if (lab == j).any() else C[j]
                        for j in range(k)])
        if np.abs(new - C).mean(axis=1).sum() < 1e-10:
            break
        C = new
    C = C[np.argsort(C.var(axis=1))]
    lab = np.abs(W[:, None, :] - C[None]).mean(axis=2).argmin(axis=1)
    return C, lab


def wk_regime(ticker: str = "SPY") -> dict:
    px = store.series(ticker)
    if px.empty or len(px) < WINDOW * 8:
        return {}
    r = np.diff(np.log(px["close"].astype(float).to_numpy()))
    today = np.sort(r[-WINDOW:])
    hist = _windows(r[:-WINDOW])  # past windows only — no look-ahead
    C, lab = wk_means(hist)
    d = np.abs(C - today).mean(axis=1)
    return {
        "state": "STRESSED" if d[1] < d[0] else "CALM",
        "p_stressed": round(float(d[0] / (d[0] + d[1])) * 100, 0),
        "calm_vol": round(float(C[0].std() * np.sqrt(252) * 100), 1),
        "stress_vol": round(float(C[1].std() * np.sqrt(252) * 100), 1),
        "stressed_share": round(float((lab == 1).mean()) * 100, 0),
    }


if __name__ == "__main__":
    # Self-check: calm/turbulent synthetic blocks must separate cleanly.
    rng = np.random.default_rng(1)
    blocks = [rng.normal(0, 0.007 if i % 2 == 0 else 0.025, 200) for i in range(6)]
    W = _windows(np.concatenate(blocks))
    C, lab = wk_means(W)
    assert C[0].std() < C[1].std()
    truth = np.array([(i * STEP + WINDOW // 2) // 200 % 2 for i in range(len(W))])
    acc = (lab == truth).mean()
    assert acc > 0.9, acc
    print(f"ok: synthetic accuracy {acc:.0%}")
