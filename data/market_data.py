"""
Price fetching (yfinance) and per-ticker metric computation.

Downloads ~1 year of daily closes for every ticker in the registry, computes
returns over six horizons plus moving averages, RSI(14) and 20-day realized
volatility, and writes the full time series into daily_prices.
"""

from __future__ import annotations

import logging
import math

import numpy as np
import pandas as pd

from data import tickers as T
from data.db import init_db, upsert_daily_prices

logger = logging.getLogger(__name__)

# Short-horizon returns stay on trading-day counts (1 session / 1 week).
_WINDOWS = {
    "return_1d":  1,
    "return_5d":  5,
}

# Longer horizons are anchored to actual calendar dates so they line up with how
# Koyfin/Bloomberg report them (1M = same day last month, not 21 sessions ago).
_CAL_OFFSETS = {
    "return_1m": pd.DateOffset(months=1),
    "return_3m": pd.DateOffset(months=3),
    "return_6m": pd.DateOffset(months=6),
    "return_1y": pd.DateOffset(years=1),
}


def _cal_return(close: pd.Series, offset: pd.DateOffset) -> pd.Series:
    """Return %, anchored to the last close on/before (each date − offset)."""
    idx = close.index
    vals = close.to_numpy()
    targets = idx - offset
    # Position of the last index at or before each target (−1 if before start).
    pos = idx.searchsorted(targets, side="right") - 1
    base = np.where(pos >= 0, vals[pos.clip(min=0)], np.nan)
    return (vals / base - 1.0) * 100.0


def _ytd_return(close: pd.Series) -> pd.Series:
    """Return % since the last close of the prior calendar year (Dec 31 base)."""
    years = close.index.year
    # Base = last close on/before Dec 31 of the previous year, per row.
    bases = {y: close.loc[:f"{y - 1}-12-31"].iloc[-1]
             if not close.loc[:f"{y - 1}-12-31"].empty else np.nan
             for y in set(years)}
    base = np.array([bases[y] for y in years], dtype=float)
    return (close.to_numpy() / base - 1.0) * 100.0


def normalize_yield(ticker: str, value: float | None) -> float | None:
    """^TNX/^IRX etc. are sometimes quoted x10 (42.5 == 4.25%). Normalize to %."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return value
    if ticker in T.YIELD_TICKERS and value > 25:
        return value / 10.0
    return value


def download_closes(period: str = "2y") -> pd.DataFrame:
    """Return a wide DataFrame of daily closes (index=date, cols=tickers)."""
    import yfinance as yf

    raw = yf.download(
        T.ALL_TICKERS,
        period=period,
        interval="1d",
        auto_adjust=True,
        progress=False,
        threads=True,
    )
    if raw is None or raw.empty:
        return pd.DataFrame()

    # With multiple tickers yfinance returns a column MultiIndex (field, ticker)
    if isinstance(raw.columns, pd.MultiIndex):
        if "Close" in raw.columns.get_level_values(0):
            closes = raw["Close"].copy()
        else:
            closes = raw.xs("Close", axis=1, level=0).copy()
    else:
        # Single ticker fallback
        closes = raw[["Close"]].copy()
        closes.columns = [T.ALL_TICKERS[0]]

    closes.index = pd.to_datetime(closes.index).tz_localize(None)
    # Normalize yield quotes
    for tk in closes.columns:
        if tk in T.YIELD_TICKERS:
            closes[tk] = closes[tk].apply(lambda v: normalize_yield(tk, v))
    return closes


def _rsi14(close: pd.Series) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def compute_metrics(close: pd.Series) -> pd.DataFrame:
    """Given a clean close series, return a DataFrame of all stored metrics."""
    close = close.dropna()
    if close.empty:
        return pd.DataFrame()

    out = pd.DataFrame({"close": close})
    for col, n in _WINDOWS.items():
        out[col] = (close / close.shift(n) - 1.0) * 100.0
    for col, off in _CAL_OFFSETS.items():
        out[col] = _cal_return(close, off)
    out["return_ytd"] = _ytd_return(close)
    out["ma20"]  = close.rolling(20).mean()
    out["ma50"]  = close.rolling(50).mean()
    out["ma200"] = close.rolling(200).mean()
    out["rsi14"] = _rsi14(close)
    out["vol20d"] = close.pct_change().rolling(20).std() * math.sqrt(252) * 100.0
    return out


def _to_db_rows(ticker: str, metrics: pd.DataFrame) -> list[tuple]:
    rows = []
    for dt, r in metrics.iterrows():
        def g(c):
            v = r.get(c)
            if v is None or (isinstance(v, float) and math.isnan(v)):
                return None
            return float(v)
        rows.append((
            ticker, dt.strftime("%Y-%m-%d"), g("close"),
            g("return_1d"), g("return_5d"), g("return_1m"),
            g("return_3m"), g("return_6m"), g("return_1y"), g("return_ytd"),
            g("ma20"), g("ma50"), g("ma200"), g("rsi14"), g("vol20d"),
        ))
    return rows


def refresh_prices(period: str = "2y") -> dict:
    """Download, compute and persist daily_prices for all tickers. Returns stats."""
    init_db()
    closes = download_closes(period=period)
    if closes.empty:
        logger.error("No price data returned from yfinance.")
        return {"tickers": 0, "rows": 0, "missing": list(T.ALL_TICKERS)}

    all_rows: list[tuple] = []
    ok, missing = [], []
    for tk in T.ALL_TICKERS:
        if tk not in closes.columns:
            missing.append(tk)
            continue
        metrics = compute_metrics(closes[tk])
        if metrics.empty:
            missing.append(tk)
            continue
        all_rows.extend(_to_db_rows(tk, metrics))
        ok.append(tk)

    n = upsert_daily_prices(all_rows)
    logger.info("Stored %d rows for %d tickers (%d missing).", n, len(ok), len(missing))
    return {"tickers": len(ok), "rows": n, "missing": missing}
