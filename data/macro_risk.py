"""
Long-sample macro risk models — the institutional downside layer.

  * Recession probability: a 12-month-ahead probit on the 10Y–3M curve (NY Fed /
    Estrella–Mishkin) and a bivariate curve + Excess Bond Premium probit (Fed Board
    staff 2019: performs well out-of-sample; Gilchrist–Zakrajšek 2012: credit
    spreads' recession power is almost entirely the EBP), plus the Fed's own
    published EBP probability and the real-time Sahm rule.
  * Growth-at-Risk (Adrian, Boyarchenko & Giannone, AER 2019): quantile regressions
    of next-year GDP growth and S&P return on the NFCI — financial conditions move
    the *lower tail*, not the median.
  * Term premium (Kim–Wright, Fed Board) and Fed net liquidity (practitioner
    heuristic — evidence debated).
  * Uncertainty/news: EPU (Baker–Bloom–Davis), Geopolitical Risk (Caldara–
    Iacoviello), SF Fed news sentiment — volatility/context gauges, not return calls.

Data live in the ``fred_long`` table (full history), refreshed by run_macro.
"""

from __future__ import annotations

import io
import logging

import numpy as np
import pandas as pd

from data.db import get_db, init_db, upsert_fred_long

logger = logging.getLogger(__name__)

LONG_FRED = ["T10Y3M", "USREC", "SAHMREALTIME", "NFCI", "GDPC1", "THREEFYTP10", "DGS10",
             "WALCL", "WTREGEN", "RRPONTSYD", "WRESBAL", "USEPUINDXD",
             "CPIAUCSL", "CPILFESL", "CPIUFDSL", "GASREGW", "DCOILWTICO",
             "IR3TIB01CAM156N", "DGS2", "GDPNOW", "CFNAI", "ICSA"]
_H = {"User-Agent": "Mozilla/5.0"}
EBP_URL = "https://www.federalreserve.gov/econres/notes/feds-notes/ebp_csv.csv"
GPR_URL = "https://www.matteoiacoviello.com/gpr_files/data_gpr_daily_recent.xls"
NEWS_URL = "https://www.frbsf.org/wp-content/uploads/news_sentiment_data.xlsx"


# ── Refresh / read ────────────────────────────────────────────────────────────

def _frame_rows(sid: str, s: pd.Series) -> list[tuple]:
    s = pd.to_numeric(s, errors="coerce").dropna()
    return [(sid, pd.Timestamp(d).strftime("%Y-%m-%d"), float(v)) for d, v in s.items()]


def refresh_long() -> dict:
    """Full-history refresh of every long-sample input. Each source is optional."""
    import requests
    from data.fred import _fetch_series, _api_key
    init_db()
    rows, ok, missing = [], [], []
    if _api_key():
        for sid in LONG_FRED:
            try:
                got = _fetch_series(sid, "1950-01-01")
                rows += got
                (ok if got else missing).append(sid)
            except Exception as exc:
                logger.warning("fred_long %s failed: %s", sid, exc)
                missing.append(sid)
    try:  # Fed Board: GZ spread, EBP and its model recession probability (monthly).
        e = pd.read_csv(io.StringIO(requests.get(EBP_URL, headers=_H, timeout=60).text),
                        parse_dates=["date"]).set_index("date")
        rows += _frame_rows("EBP", e["ebp"]) + _frame_rows("GZ_SPREAD", e["gz_spread"]) \
            + _frame_rows("EBP_PROB", e["est_prob"] * 100)
        ok.append("EBP")
    except Exception as exc:
        logger.warning("EBP fetch failed: %s", exc)
        missing.append("EBP")
    try:  # Caldara–Iacoviello daily Geopolitical Risk index.
        g = pd.read_excel(io.BytesIO(requests.get(GPR_URL, headers=_H, timeout=90).content))
        g["date"] = pd.to_datetime(g["DAY"].astype(str), format="%Y%m%d")
        rows += _frame_rows("GPRD", g.set_index("date")["GPRD"])
        ok.append("GPRD")
    except Exception as exc:
        logger.warning("GPR fetch failed: %s", exc)
        missing.append("GPRD")
    try:  # SF Fed Daily News Sentiment.
        n = pd.read_excel(io.BytesIO(requests.get(NEWS_URL, headers=_H, timeout=90).content),
                          sheet_name="Data")
        rows += _frame_rows("NEWS_SENT", n.set_index("date")["News Sentiment"])
        ok.append("NEWS_SENT")
    except Exception as exc:
        logger.warning("News sentiment fetch failed: %s", exc)
        missing.append("NEWS_SENT")
    n_rows = upsert_fred_long(rows)
    return {"series": len(ok), "rows": n_rows, "missing": missing}


def long_series(sid: str, as_of: str | None = None) -> pd.Series:
    try:
        with get_db() as c:
            df = pd.read_sql_query(
                "SELECT date, value FROM fred_long WHERE series_id=? AND date<=? ORDER BY date",
                c, params=(sid, as_of or "9999-12-31"))
    except Exception:
        return pd.Series(dtype=float)
    return pd.Series(df["value"].to_numpy(float), index=pd.to_datetime(df["date"]))


def _monthly(sid: str) -> pd.Series:
    s = long_series(sid)
    return s.resample("MS").mean() if not s.empty else s


def _pct(cur: float, s: pd.Series) -> float:
    return round(float((s <= cur).mean()) * 100, 0)


# ── Recession probability ─────────────────────────────────────────────────────

def _probit_fit(X: np.ndarray, y: np.ndarray) -> np.ndarray:
    from scipy.optimize import minimize
    from scipy.stats import norm

    def nll(b):
        p = np.clip(norm.cdf(X @ b), 1e-9, 1 - 1e-9)
        return -(y * np.log(p) + (1 - y) * np.log(1 - p)).sum()
    return minimize(nll, np.zeros(X.shape[1]), method="BFGS").x


def recession_risk() -> dict:
    """12-month-ahead recession probabilities from curve, curve+EBP, Fed, Sahm."""
    from scipy.stats import norm
    rec, curve, ebp = _monthly("USREC"), _monthly("T10Y3M"), _monthly("EBP")
    if rec.empty or curve.empty:
        return {}
    # Target: an NBER recession month anywhere in t+1 … t+12.
    fut = pd.concat([rec.shift(-k) for k in range(1, 13)], axis=1)
    y = fut.max(axis=1).where(fut.notna().all(axis=1))
    out: dict = {"as_of": curve.index[-1].strftime("%Y-%m")}

    d = pd.DataFrame({"y": y, "curve": curve}).dropna()
    b = _probit_fit(np.column_stack([np.ones(len(d)), d["curve"]]), d["y"].to_numpy())
    out["curve_prob"] = round(float(norm.cdf(b[0] + b[1] * curve.iloc[-1])) * 100, 1)
    out["curve_spread"] = round(float(curve.iloc[-1]), 2)
    out["curve_since"] = d.index[0].strftime("%Y")

    if not ebp.empty:
        d2 = pd.DataFrame({"y": y, "curve": curve, "ebp": ebp}).dropna()
        b2 = _probit_fit(np.column_stack([np.ones(len(d2)), d2["curve"], d2["ebp"]]),
                         d2["y"].to_numpy())
        last = pd.DataFrame({"curve": curve, "ebp": ebp}).dropna().iloc[-1]
        out["curve_ebp_prob"] = round(float(norm.cdf(b2[0] + b2[1] * last["curve"]
                                                     + b2[2] * last["ebp"])) * 100, 1)
        out["ebp"] = round(float(ebp.iloc[-1]), 2)
        out["ebp_month"] = ebp.index[-1].strftime("%Y-%m")
    fed = long_series("EBP_PROB")
    if not fed.empty:
        out["fed_ebp_prob"] = round(float(fed.iloc[-1]), 1)
    sahm = long_series("SAHMREALTIME")
    if not sahm.empty:
        out["sahm"] = round(float(sahm.iloc[-1]), 2)
        out["sahm_triggered"] = bool(sahm.iloc[-1] >= 0.5)
    return out


# ── Growth-at-Risk ────────────────────────────────────────────────────────────

def _qreg(X: np.ndarray, y: np.ndarray, tau: float) -> np.ndarray:
    """Quantile regression as a linear program (min Σ check-loss)."""
    from scipy import sparse
    from scipy.optimize import linprog
    n, k = X.shape
    eye = sparse.eye(n)
    A = sparse.hstack([sparse.csr_matrix(X), eye, -eye])
    c = np.r_[np.zeros(k), tau * np.ones(n), (1 - tau) * np.ones(n)]
    bounds = [(None, None)] * k + [(0, None)] * (2 * n)
    return linprog(c, A_eq=A, b_eq=y, bounds=bounds, method="highs").x[:k]


QUANTILES = (0.05, 0.25, 0.5, 0.75, 0.95)


def _gar(y: pd.Series, X: pd.DataFrame, x_now: np.ndarray) -> dict:
    d = pd.concat([y.rename("y"), X], axis=1).dropna()
    Xm = np.column_stack([np.ones(len(d)), d[X.columns].to_numpy(float)])
    xq = np.r_[1.0, x_now]
    preds = sorted(float(xq @ _qreg(Xm, d["y"].to_numpy(float), q)) for q in QUANTILES)
    return {f"q{int(q * 100)}": round(p, 1) for q, p in zip(QUANTILES, preds)} | \
        {"n": len(d), "since": d.index[0].strftime("%Y")}


def growth_at_risk() -> dict:
    """Conditional distribution of next-year GDP growth and S&P return given the NFCI."""
    nfci = long_series("NFCI")
    gdp = long_series("GDPC1")
    if nfci.empty or gdp.empty:
        return {}
    out: dict = {"nfci": round(float(nfci.iloc[-1]), 2),
                 "nfci_date": nfci.index[-1].strftime("%Y-%m-%d")}
    # GDP: next-4-quarter growth on quarter-avg NFCI + trailing 4q growth (ABG spec).
    g = np.log(gdp) * 100
    fwd = g.shift(-4) - g
    past = g - g.shift(4)
    nq = nfci.resample("QS").mean()
    X = pd.DataFrame({"nfci": nq, "past": past})
    out["gdp"] = _gar(fwd, X, np.array([nfci.iloc[-1], past.dropna().iloc[-1]]))
    out["gdp_median_unconditional"] = round(float(fwd.dropna().median()), 1)
    # Equities: next-12m S&P return on month-avg NFCI.
    from data import store
    spx = store.long_closes("^GSPC")
    if not spx.empty:
        px = spx.set_index("date")["close"].resample("MS").last()
        r12 = (px.shift(-12) / px - 1) * 100
        nm = nfci.resample("MS").mean()
        out["spx"] = _gar(r12, pd.DataFrame({"nfci": nm}), np.array([nfci.iloc[-1]]))
        out["spx_q5_unconditional"] = round(float(r12.loc[nm.dropna().index[0]:].dropna()
                                                  .quantile(0.05)), 1)
    return out


# ── Rates plumbing: term premium & net liquidity ──────────────────────────────

def term_premium() -> dict:
    tp, y10 = long_series("THREEFYTP10"), long_series("DGS10")
    if tp.empty:
        return {}
    cur = float(tp.iloc[-1])
    prev = tp.loc[:tp.index[-1] - pd.Timedelta(days=30)]
    out = {"tp10": round(cur, 2), "chg_1m": round(cur - float(prev.iloc[-1]), 2) if not prev.empty else None,
           "pct": _pct(cur, tp), "since": tp.index[0].strftime("%Y"),
           "as_of": tp.index[-1].strftime("%Y-%m-%d"), "history": tp}
    if not y10.empty:
        y = float(y10.loc[:tp.index[-1]].iloc[-1])
        out["y10"] = round(y, 2)
        out["expected_path"] = round(y - cur, 2)  # avg expected short rate component
    return out


def net_liquidity() -> dict:
    """Fed total assets − TGA − ON RRP ($bn). Practitioner heuristic — evidence debated."""
    walcl, tga, rrp, res = (long_series(s) for s in ("WALCL", "WTREGEN", "RRPONTSYD", "WRESBAL"))
    if walcl.empty or tga.empty:
        return {}
    # Align on the H.4.1 Wednesday release dates (WALCL/WTREGEN share them); daily
    # RRP is carried to each Wednesday. RRP pre-2003 didn't exist -> 0.
    idx = walcl.index
    wk = pd.DataFrame({"walcl": walcl / 1000,
                       "tga": tga.reindex(idx, method="ffill") / 1000,
                       "rrp": rrp.reindex(idx, method="ffill") if not rrp.empty else 0.0})
    wk = wk.dropna(subset=["walcl", "tga"])
    wk["rrp"] = wk["rrp"].fillna(0.0)
    net = wk["walcl"] - wk["tga"] - wk["rrp"]

    def chg(n):
        return round(float(net.iloc[-1] - net.iloc[-1 - n]), 0) if len(net) > n else None
    return {"net": round(float(net.iloc[-1]), 0), "chg_4w": chg(4), "chg_13w": chg(13),
            "fed_assets": round(float(wk["walcl"].iloc[-1]), 0),
            "tga": round(float(wk["tga"].iloc[-1]), 0), "rrp": round(float(wk["rrp"].iloc[-1]), 0),
            "reserves": round(float(res.iloc[-1]) / 1000, 0) if not res.empty else None,
            "as_of": net.index[-1].strftime("%Y-%m-%d"), "history": net}


# ── Uncertainty & news ────────────────────────────────────────────────────────

def uncertainty() -> dict:
    out = {}
    for sid, key, lbl in (("USEPUINDXD", "epu", "Economic Policy Uncertainty"),
                          ("GPRD", "gpr", "Geopolitical Risk"),
                          ("NEWS_SENT", "news", "SF Fed News Sentiment")):
        s = long_series(sid)
        if s.empty:
            continue
        sm = s.rolling(7, min_periods=3).mean().dropna()  # daily series are noisy
        cur = float(sm.iloc[-1])
        out[key] = {"label": lbl, "value": round(cur, 2 if key == "news" else 0),
                    "pct": _pct(cur, sm), "since": s.index[0].strftime("%Y"),
                    "as_of": s.index[-1].strftime("%Y-%m-%d"), "history": sm}
    return out


if __name__ == "__main__":
    # Self-check: quantile regression recovers known quantiles of a location-scale model.
    rng = np.random.default_rng(0)
    x = rng.uniform(0, 1, 2000)
    y = 1 + 2 * x + (0.5 + x) * rng.standard_normal(2000)
    X = np.column_stack([np.ones_like(x), x])
    b5, b95 = _qreg(X, y, 0.05), _qreg(X, y, 0.95)
    assert b5[1] < 2 < b95[1], (b5, b95)          # tail slopes fan out with x
    bp = _probit_fit(X, (y > 2).astype(float))
    assert bp[1] > 0, bp
    print("ok: qreg tails", b5.round(2), b95.round(2), "| probit", bp.round(2))
