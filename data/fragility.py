"""
Systemic fragility — absorption ratio and financial turbulence (State Street).

Absorption ratio (Kritzman, Li, Page & Rigobon, JPM 2011): the share of total
cross-asset variance explained by the top fifth of principal components. High =
markets tightly coupled, so shocks propagate fast; most major US drawdowns were
preceded by spikes. Read as the standardized 15-day vs 1-year shift.

Turbulence (Kritzman & Li, FAJ 2010): Mahalanobis distance of today's cross-asset
return vector from its trailing mean/covariance — unusual moves *and* unusual
combinations (e.g. stocks and bonds falling together).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from data import store

UNIVERSE = ["SPY", "IWM", "VEA", "EEM", "XIU.TO", "TLT", "IEF", "TIP", "HYG", "LQD",
            "GLD", "CL=F", "HG=F", "DX-Y.NYB", "CADUSD=X"]
WINDOW = 252


def _returns() -> pd.DataFrame:
    cols = {}
    for tk in UNIVERSE:
        s = store.series(tk)
        if not s.empty:
            cols[tk] = s.set_index("date")["close"].astype(float)
    px = pd.DataFrame(cols).ffill().dropna()
    return np.log(px).diff().dropna()


def fragility() -> dict:
    R = _returns()
    if len(R) < WINDOW + 40 or R.shape[1] < 6:
        return {}
    X = R.to_numpy()
    n_pc = max(1, int(np.ceil(X.shape[1] / 5)))
    ar, turb, dates = [], [], R.index[WINDOW:]
    for t in range(WINDOW, len(X)):
        win = X[t - WINDOW:t]
        S = np.cov(win, rowvar=False)
        # Correlation matrix for the AR so oil/copper's vol doesn't dominate the PCs.
        sd = np.sqrt(np.diag(S))
        ev = np.linalg.eigvalsh(S / np.outer(sd, sd))[::-1]
        ar.append(ev[:n_pc].sum() / ev.sum())
        d = X[t] - win.mean(axis=0)
        turb.append(float(d @ np.linalg.pinv(S) @ d))
    ar = pd.Series(ar, index=dates)
    turb = pd.Series(turb, index=dates)
    sd = ar.rolling(WINDOW, min_periods=60).std()
    shift = ((ar.rolling(15).mean() - ar.rolling(WINDOW, min_periods=60).mean()) / sd).dropna()
    t20 = turb.rolling(20).mean()
    return {
        "absorption": round(float(ar.iloc[-1]), 3),
        "ar_shift": round(float(shift.iloc[-1]), 2) if not shift.empty else None,
        "n_assets": X.shape[1], "n_pc": n_pc,
        "turbulence": round(float(turb.iloc[-1]), 1),
        "turb_20d": round(float(t20.iloc[-1]), 1),
        "turb_20d_pct": round(float((t20.dropna() <= t20.iloc[-1]).mean()) * 100, 0),
        # Under multivariate normality turbulence ~ chi²(N): mean N.
        "turb_expected": X.shape[1],
        "history": pd.DataFrame({"absorption": ar, "turbulence_20d": t20}),
    }
