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
import pandas as pd

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


def _intensity(S: np.ndarray, C: np.ndarray) -> np.ndarray:
    """Projection of sorted windows onto the calm→stressed centroid axis."""
    axis = C[1] - C[0]
    return (S - C[0]) @ axis / (axis @ axis)


def _load(as_of: str | None):
    src, px = "^GSPC", store.long_closes("^GSPC", as_of=as_of)
    if len(px) < WINDOW * 8:
        src, px = "SPY", store.series("SPY", as_of=as_of)
    return src, px


def wk_history(as_of: str | None = None) -> pd.DataFrame:
    """Daily [date, intensity, stressed] for every trailing 20-day window.

    ponytail: centroids fit once on the whole history (in-sample) — fine for a
    chart; the live read in wk_regime() is the point-in-time one.
    """
    _, px = _load(as_of)
    if px.empty or len(px) < WINDOW * 8:
        return pd.DataFrame()
    r = np.diff(np.log(px["close"].astype(float).to_numpy()))
    S = np.sort(np.lib.stride_tricks.sliding_window_view(r, WINDOW), axis=1)
    C, _ = wk_means(S[::STEP])
    d = np.abs(S[:, None, :] - C[None]).mean(axis=2)
    return pd.DataFrame({"date": px["date"].iloc[WINDOW:].to_numpy(),
                         "intensity": _intensity(S, C), "stressed": d[:, 1] < d[:, 0]})


def wk_regime(as_of: str | None = None) -> dict:
    """Calm/stressed read for the latest (or `as_of`) 20-day window of S&P 500 returns.

    Uses the max-length ^GSPC history (1927+) so "stressed" means crisis-grade,
    falling back to the 2y SPY series in daily_prices if long_closes is empty.
    """
    src, px = _load(as_of)
    if px.empty or len(px) < WINDOW * 8:
        return {}
    r = np.diff(np.log(px["close"].astype(float).to_numpy()))
    hist = _windows(r[:-WINDOW])  # past windows only — no look-ahead
    C, lab = wk_means(hist)
    # Last 6 trailing windows (t-5 … t) scored on the same point-in-time centroids.
    recent = np.sort(np.lib.stride_tricks.sliding_window_view(r[-WINDOW - 5:], WINDOW), axis=1)
    today = recent[-1]
    d = np.abs(C - today).mean(axis=1)
    # Position along calm→stressed centroid axis in quantile space: 0 = calm,
    # 1 = typical stress, >1 = beyond it (a distance ratio saturates near 0.5 in crashes).
    inten = _intensity(recent, C)
    return {
        "state": "STRESSED" if d[1] < d[0] else "CALM",
        "intensity": round(float(inten[-1]), 2),
        "chg_1d": round(float(inten[-1] - inten[-2]), 2),
        "chg_5d": round(float(inten[-1] - inten[0]), 2),
        "calm_vol": round(float(C[0].std() * np.sqrt(252) * 100), 1),
        "stress_vol": round(float(C[1].std() * np.sqrt(252) * 100), 1),
        "stressed_share": round(float((lab == 1).mean()) * 100, 0),
        "source": src,
        "since": px["date"].iloc[0].strftime("%Y"),
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
