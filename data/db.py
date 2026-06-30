"""
SQLite storage for the Macro Compass (cache/macro.db).

Three tables:
  daily_prices   — full 1-year time series per ticker with rolling metrics
  macro_signals  — one row per refresh: VIX, spreads, trends, risk score, regime
  signal_scores  — one row per refresh: the 7 MacroSignal dimensions + compass score

History accrues one row per calendar date (INSERT OR REPLACE), so the signal
tables double as a time series for the sentiment-trend charts.
"""

from __future__ import annotations

import os
import shutil
import sqlite3
from contextlib import contextmanager

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.environ.get("NORTHSTAR_MACRO_DB", os.path.join(_ROOT, "cache", "macro.db"))

# A committed snapshot of macro.db. On an ephemeral host (e.g. Streamlit Cloud)
# the working cache under cache/ starts empty on every boot, so we restore this
# seed once per process to ship history. Refresh it with:
#   cp cache/macro.db data/seed_macro.db && git commit
_SEED_PATH = os.path.join(_ROOT, "data", "seed_macro.db")
_seeded = False


def _ensure_db_file() -> None:
    """Restore the committed seed into the cache path if no live DB exists yet."""
    global _seeded
    if _seeded:
        return
    _seeded = True
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    if not os.path.exists(DB_PATH) and os.path.exists(_SEED_PATH):
        try:
            shutil.copy2(_SEED_PATH, DB_PATH)
        except Exception:
            pass


@contextmanager
def get_db():
    _ensure_db_file()
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS daily_prices (
            ticker     TEXT NOT NULL,
            date       TEXT NOT NULL,
            close      REAL,
            return_1d  REAL,
            return_5d  REAL,
            return_1m  REAL,
            return_3m  REAL,
            return_6m  REAL,
            return_1y  REAL,
            ma20       REAL,
            ma50       REAL,
            ma200      REAL,
            rsi14      REAL,
            vol20d     REAL,
            PRIMARY KEY (ticker, date)
        );
        CREATE INDEX IF NOT EXISTS idx_dp_ticker ON daily_prices(ticker);
        CREATE INDEX IF NOT EXISTS idx_dp_date   ON daily_prices(date);

        CREATE TABLE IF NOT EXISTS macro_signals (
            date                TEXT PRIMARY KEY,
            run_ts              TEXT,
            vix_level           REAL,
            vix_20d_avg         REAL,
            yield_curve_spread  REAL,
            credit_spread_proxy REAL,
            usd_trend           REAL,
            gold_trend          REAL,
            oil_trend           REAL,
            copper_trend        REAL,
            breadth             REAL,
            risk_score          REAL,
            regime              TEXT,
            macro_regime        TEXT
        );

        CREATE TABLE IF NOT EXISTS signal_scores (
            date            TEXT PRIMARY KEY,
            run_ts          TEXT,
            equity_momentum REAL,
            style           REAL,
            regional        REAL,
            yield_curve     REAL,
            credit          REAL,
            commodity       REAL,
            volatility      REAL,
            compass_score   REAL
        );

        CREATE TABLE IF NOT EXISTS fred_series (
            series_id  TEXT NOT NULL,
            date       TEXT NOT NULL,
            value      REAL,
            PRIMARY KEY (series_id, date)
        );
        CREATE INDEX IF NOT EXISTS idx_fred_series ON fred_series(series_id);

        CREATE TABLE IF NOT EXISTS cot_positioning (
            market      TEXT NOT NULL,
            report_date TEXT NOT NULL,
            net         REAL,
            long_pos    REAL,
            short_pos   REAL,
            open_interest REAL,
            PRIMARY KEY (market, report_date)
        );

        CREATE TABLE IF NOT EXISTS pm_journal (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            ts        TEXT,
            date      TEXT,
            regime    TEXT,
            note      TEXT
        );
        """)


# ── Writers ───────────────────────────────────────────────────────────────────

_PRICE_COLS = [
    "ticker", "date", "close", "return_1d", "return_5d", "return_1m",
    "return_3m", "return_6m", "return_1y", "ma20", "ma50", "ma200",
    "rsi14", "vol20d",
]


def upsert_daily_prices(rows: list[tuple]) -> int:
    """rows: list of tuples matching _PRICE_COLS order."""
    if not rows:
        return 0
    placeholders = ",".join("?" * len(_PRICE_COLS))
    sql = f"INSERT OR REPLACE INTO daily_prices ({','.join(_PRICE_COLS)}) VALUES ({placeholders})"
    with get_db() as c:
        c.executemany(sql, rows)
    return len(rows)


def store_macro_signals(d: dict) -> None:
    cols = ["date", "run_ts", "vix_level", "vix_20d_avg", "yield_curve_spread",
            "credit_spread_proxy", "usd_trend", "gold_trend", "oil_trend",
            "copper_trend", "breadth", "risk_score", "regime", "macro_regime"]
    vals = [d.get(k) for k in cols]
    placeholders = ",".join("?" * len(cols))
    with get_db() as c:
        c.execute(f"INSERT OR REPLACE INTO macro_signals ({','.join(cols)}) "
                  f"VALUES ({placeholders})", vals)


def store_signal_scores(d: dict) -> None:
    cols = ["date", "run_ts", "equity_momentum", "style", "regional",
            "yield_curve", "credit", "commodity", "volatility", "compass_score"]
    vals = [d.get(k) for k in cols]
    placeholders = ",".join("?" * len(cols))
    with get_db() as c:
        c.execute(f"INSERT OR REPLACE INTO signal_scores ({','.join(cols)}) "
                  f"VALUES ({placeholders})", vals)


def upsert_fred(rows: list[tuple]) -> int:
    """rows: (series_id, date, value)."""
    if not rows:
        return 0
    with get_db() as c:
        c.executemany("INSERT OR REPLACE INTO fred_series (series_id, date, value) "
                      "VALUES (?,?,?)", rows)
    return len(rows)


def upsert_cot(rows: list[tuple]) -> int:
    """rows: (market, report_date, net, long_pos, short_pos, open_interest)."""
    if not rows:
        return 0
    with get_db() as c:
        c.executemany("INSERT OR REPLACE INTO cot_positioning "
                      "(market, report_date, net, long_pos, short_pos, open_interest) "
                      "VALUES (?,?,?,?,?,?)", rows)
    return len(rows)


def add_journal_note(date: str, regime: str, note: str) -> None:
    from datetime import datetime
    with get_db() as c:
        c.execute("INSERT INTO pm_journal (ts, date, regime, note) VALUES (?,?,?,?)",
                  (datetime.now().isoformat(timespec="seconds"), date, regime, note))


def journal_notes(limit: int = 50) -> list[dict]:
    try:
        with get_db() as c:
            rows = c.execute("SELECT id, ts, date, regime, note FROM pm_journal "
                             "ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []
