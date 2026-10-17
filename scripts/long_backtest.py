"""
Long-history, out-of-sample validation of the headline signals (2007 → today).

The live track record sits on ~18 months of overlapping daily windows — noise.
This rebuilds the MacroCompass dimensions and the risk-on/off composite at every
month-end since HYG listed (Apr 2007) from max-length yfinance history, using the
*same* scoring functions as the live engine, then grades them the way the
literature does:

  * non-overlapping monthly forward S&P returns (no overlap inflation);
  * Spearman IC with its t-stat;
  * Campbell–Thompson (2008) out-of-sample R² vs the expanding historical mean
    (Welch & Goyal 2008 benchmark), with the CT sign/positivity restrictions;
  * current hand-set weights vs an equal-weight composite (combination puzzle).

Writes data/long_validation.json (small, committed) — the dashboard reads it, so
the seed DB doesn't grow. Re-run occasionally:  python scripts/long_backtest.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from data import signals as S  # noqa: E402
from data.market_data import compute_metrics  # noqa: E402

TICKERS = ["SPY", "^GSPTSE", "IWF", "IWD", "EEM", "^TNX", "^IRX", "HYG", "IEF",
           "CL=F", "HG=F", "^VIX", "DX-Y.NYB", "GC=F"]
START = "2007-05-31"   # HYG listed Apr 2007; need 1m of returns
MIN_TRAIN = 60         # months before the first out-of-sample forecast
OUT = ROOT / "data" / "long_validation.json"


def _download() -> pd.DataFrame:
    import yfinance as yf
    raw = yf.download(TICKERS, period="max", interval="1d", auto_adjust=True,
                      progress=False, threads=True)
    px = raw["Close"].copy()
    px.index = pd.to_datetime(px.index).tz_localize(None)
    return px


def _panel(px: pd.DataFrame) -> dict[str, pd.DataFrame]:
    return {tk: compute_metrics(px[tk]) for tk in TICKERS if tk in px}


def _snapshot(panel: dict, d: pd.Timestamp, vix: pd.Series) -> dict | None:
    m = {}
    for tk, df in panel.items():
        sub = df.loc[:d]
        if not sub.empty:
            m[tk] = sub.iloc[-1].to_dict()
    if "SPY" not in m or "HYG" not in m:
        return None
    vix_level = S._g(m, "^VIX", "close")
    vix_avg = float(vix.loc[:d].tail(20).mean())
    tnx, irx = S._g(m, "^TNX", "close"), S._g(m, "^IRX", "close")
    curve = (tnx - irx) if (tnx is not None and irx is not None) else None
    hyg, ief = S._g(m, "HYG", "return_5d"), S._g(m, "IEF", "return_5d")
    credit = (hyg - ief) if (hyg is not None and ief is not None) else None
    dims = {
        "equity_momentum": S._equity_momentum(m),
        "style": S._style_signal(m),
        "regional": S._regional_signal(m),
        "yield_curve": S._yield_curve_signal(curve),
        "credit": S._credit_signal(m),
        "commodity": S._commodity_signal(m),
        "volatility": S._volatility_signal(vix_level, vix_avg),
    }
    risk, _ = S._risk_composite(vix_level, vix_avg, credit,
                                S._g(m, "DX-Y.NYB", "return_1m"), S._g(m, "GC=F", "return_1m"))
    w = S.WEIGHTS
    row = {f"dim_{k}": v for k, v in dims.items()}
    row["compass"] = sum(dims[k] * w[k] for k in dims) / sum(w.values())
    row["compass_equal"] = sum(dims.values()) / len(dims)
    row["risk_score"] = risk
    return row


def _oos_r2(x: np.ndarray, y: np.ndarray) -> float | None:
    """Campbell–Thompson OOS R²: expanding OLS forecast vs expanding mean."""
    f_m, f_h, act = [], [], []
    for t in range(MIN_TRAIN, len(y)):
        xs, ys = x[:t], y[:t]
        hist = ys.mean()
        if np.std(xs) == 0:
            fc = hist
        else:
            b = np.cov(xs, ys, bias=True)[0, 1] / np.var(xs)
            fc = hist + b * (x[t] - xs.mean())
            if b < 0:          # CT: wrong-signed slope -> fall back to the mean
                fc = hist
        f_m.append(max(fc, 0.0))  # CT: no negative equity-return forecast
        f_h.append(hist)
        act.append(y[t])
    act, f_m, f_h = map(np.asarray, (act, f_m, f_h))
    sse_h = ((act - f_h) ** 2).sum()
    return round(float(1 - ((act - f_m) ** 2).sum() / sse_h) * 100, 2) if sse_h else None


def _ic(x: pd.Series, y: pd.Series) -> tuple[float, float]:
    from scipy.stats import spearmanr
    ic = float(spearmanr(x, y).statistic)
    return ic, ic * np.sqrt((len(x) - 2) / max(1e-9, 1 - ic ** 2))


def grade(df: pd.DataFrame) -> dict:
    out = {}
    for col in [c for c in df.columns if c not in ("fwd", "fwd_vol")]:
        d = df[[col, "fwd", "fwd_vol"]].dropna()
        if len(d) < MIN_TRAIN + 12 or d[col].nunique() < 2:
            continue
        ic, t = _ic(d[col], d["fwd"])
        vic, vt = _ic(d[col], d["fwd_vol"])
        q1, q2 = d[col].quantile([1 / 3, 2 / 3])
        hi, lo = d[d[col] > q2]["fwd"], d[d[col] < q1]["fwd"]
        if hi.empty or lo.empty:  # discrete signals: split at the median instead
            med = d[col].median()
            hi, lo = d[d[col] > med]["fwd"], d[d[col] <= med]["fwd"]
            if hi.empty:
                hi, lo = d[d[col] >= med]["fwd"], d[d[col] < med]["fwd"]
        out[col] = {
            "ic": round(ic, 3), "t": round(float(t), 2), "n": len(d),
            "oos_r2": _oos_r2(d[col].to_numpy(float), d["fwd"].to_numpy(float)),
            "high_mean": round(float(hi.mean()), 2), "low_mean": round(float(lo.mean()), 2),
            "spread": round(float(hi.mean() - lo.mean()), 2),
            # Risk-state signals should predict *volatility* (expect a negative IC:
            # risk-on reading -> calmer next month).
            "vol_ic": round(vic, 3), "vol_t": round(float(vt), 2),
        }
    return out


def main() -> int:
    px = _download()
    panel = _panel(px)
    vix = px["^VIX"].dropna()
    spy = px["SPY"].dropna()
    month_ends = spy.loc[START:].resample("ME").last().index
    rows = {}
    for me in month_ends:
        d = spy.loc[:me].index[-1]  # last trading day of the month
        snap = _snapshot(panel, d, vix)
        if snap:
            rows[d] = snap
    df = pd.DataFrame.from_dict(rows, orient="index").sort_index()
    # Non-overlapping 1-month forward return (month-end to next month-end), %.
    closes = spy.reindex(df.index)
    df["fwd"] = (closes.shift(-1) / closes - 1) * 100
    # Next month's realized vol (annualized %) from daily returns inside the month.
    r = np.log(spy).diff()
    edges = list(df.index) + [spy.index[-1]]
    df["fwd_vol"] = [float(r.loc[a:b].iloc[1:].std() * np.sqrt(252) * 100)
                     for a, b in zip(edges[:-1], edges[1:])]
    df = df.iloc[:-1]
    res = {
        "_meta": {"start": df.index[0].strftime("%Y-%m"), "end": df.index[-1].strftime("%Y-%m"),
                  "months": len(df), "horizon": "1M non-overlapping",
                  "benchmark": "expanding historical mean (Welch–Goyal)",
                  "generated": datetime.now().strftime("%Y-%m-%d")},
        "signals": grade(df),
    }
    OUT.write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
