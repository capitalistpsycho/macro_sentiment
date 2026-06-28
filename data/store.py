"""
Read helpers over macro.db — the single access point used by the dashboard
pages and the signal engine. Everything degrades to empty/None on failure so a
missing table never crashes a page.
"""

from __future__ import annotations

import pandas as pd

from data.db import get_db

_METRIC_COLS = [
    "close", "return_1d", "return_5d", "return_1m", "return_3m",
    "return_6m", "return_1y", "ma20", "ma50", "ma200", "rsi14", "vol20d",
]


def latest_date() -> str | None:
    try:
        with get_db() as c:
            r = c.execute("SELECT MAX(date) FROM daily_prices").fetchone()
        return r[0] if r and r[0] else None
    except Exception:
        return None


def trading_dates(start: str | None = None) -> list[str]:
    """Distinct dates present in daily_prices, ascending (optionally from `start`)."""
    try:
        with get_db() as c:
            if start:
                rows = c.execute("SELECT DISTINCT date FROM daily_prices "
                                 "WHERE date >= ? ORDER BY date", (start,)).fetchall()
            else:
                rows = c.execute("SELECT DISTINCT date FROM daily_prices "
                                 "ORDER BY date").fetchall()
        return [r[0] for r in rows]
    except Exception:
        return []


def latest_metrics(as_of: str | None = None) -> dict[str, dict]:
    """ticker -> dict of latest-row metrics (+ 'date').

    With ``as_of`` set (YYYY-MM-DD), returns each ticker's most recent row on or
    before that date — used to reconstruct point-in-time signals for history.
    """
    out: dict[str, dict] = {}
    try:
        with get_db() as c:
            if as_of:
                rows = c.execute(
                    """SELECT dp.* FROM daily_prices dp
                       JOIN (SELECT ticker, MAX(date) AS d FROM daily_prices
                             WHERE date <= ? GROUP BY ticker) m
                         ON dp.ticker = m.ticker AND dp.date = m.d""", (as_of,)
                ).fetchall()
            else:
                rows = c.execute(
                    """SELECT dp.* FROM daily_prices dp
                       JOIN (SELECT ticker, MAX(date) AS d FROM daily_prices GROUP BY ticker) m
                         ON dp.ticker = m.ticker AND dp.date = m.d"""
                ).fetchall()
        for r in rows:
            out[r["ticker"]] = {k: r[k] for k in (_METRIC_COLS + ["date"])}
    except Exception:
        pass
    return out


def metric(metrics: dict, ticker: str, field: str = "close"):
    """Safe nested lookup."""
    v = metrics.get(ticker, {}).get(field)
    return v


def series(ticker: str, days: int | None = None, as_of: str | None = None) -> pd.DataFrame:
    """Return [date, close, ma20, ma50, ma200, rsi14, vol20d] for a ticker.

    ``as_of`` truncates the series to rows on or before that date.
    """
    try:
        with get_db() as c:
            if as_of:
                df = pd.read_sql_query(
                    "SELECT date, close, ma20, ma50, ma200, rsi14, vol20d "
                    "FROM daily_prices WHERE ticker=? AND date<=? ORDER BY date",
                    c, params=(ticker, as_of))
            else:
                df = pd.read_sql_query(
                    "SELECT date, close, ma20, ma50, ma200, rsi14, vol20d "
                    "FROM daily_prices WHERE ticker=? ORDER BY date", c, params=(ticker,))
    except Exception:
        return pd.DataFrame()
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"])
    if days:
        df = df.tail(days)
    return df.reset_index(drop=True)


def closes(tickers: list[str], days: int | None = None) -> pd.DataFrame:
    """Wide DataFrame of closes (index=date) for several tickers, inner-aligned."""
    frames = {}
    for tk in tickers:
        s = series(tk)
        if not s.empty:
            frames[tk] = s.set_index("date")["close"]
    if not frames:
        return pd.DataFrame()
    wide = pd.DataFrame(frames).sort_index()
    if days:
        wide = wide.tail(days)
    return wide


def ratio(num: str, den: str, days: int | None = None) -> pd.Series:
    """Aligned price ratio num/den (e.g. IWM/SPY)."""
    w = closes([num, den], days=days)
    if w.empty or num not in w or den not in w:
        return pd.Series(dtype=float)
    w = w.dropna()
    if w.empty:
        return pd.Series(dtype=float)
    return (w[num] / w[den])


def signal_history(table: str = "signal_scores") -> pd.DataFrame:
    try:
        with get_db() as c:
            df = pd.read_sql_query(f"SELECT * FROM {table} ORDER BY date", c)
        if not df.empty:
            df["date"] = pd.to_datetime(df["date"])
        return df
    except Exception:
        return pd.DataFrame()
