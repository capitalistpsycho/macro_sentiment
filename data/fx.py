"""FX helpers: CAD/USD read-through and currency performance."""

from __future__ import annotations

from data import store, tickers as T


def cad_usd_panel(metrics: dict) -> dict:
    row = metrics.get("CADUSD=X", {})
    rate = row.get("close")
    trend = row.get("return_1m")
    if trend is None:
        implication = "—"
    elif trend > 0:
        implication = ("CAD strengthening — USD-denominated assets translate to "
                       "fewer CAD; unhedged US returns look weaker in CAD terms.")
    else:
        implication = ("CAD weakening — USD-denominated assets translate to more "
                       "CAD; unhedged US returns are flattered in CAD terms.")
    return {"rate": rate, "trend_1m": trend, "implication": implication}


def fx_table(metrics: dict) -> list[dict]:
    out = []
    for tk, lbl, _ in T.FX:
        row = metrics.get(tk, {})
        out.append({"ticker": tk, "label": lbl, "rate": row.get("close"),
                    "return_1m": row.get("return_1m"), "return_3m": row.get("return_3m")})
    return out
