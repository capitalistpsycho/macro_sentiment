"""
Rule-based macro narrative — turns the computed state into a written read.

Institutional research leads with a *view*, not a data dump. This composes a short
paragraph from the signals already computed (regime + conviction + probabilities,
financial conditions, the curve, credit, crowding and the nearest historical
analogue) so the dashboard states what it thinks, in words.
"""

from __future__ import annotations


def _pct(v, d=1):
    return f"{v:.{d}f}%" if isinstance(v, (int, float)) else "—"


def macro_brief(sig: dict) -> str:
    parts: list[str] = []
    regime = sig.get("macro_regime")
    conv = sig.get("macro_conviction")
    conv_lbl = (sig.get("macro_conviction_label") or "").lower()
    sec = sig.get("macro_regime_secondary")

    # Regime + conviction (+ model probability if available).
    lead = f"The macro backdrop reads <b>{regime}</b>"
    try:
        from data.regime_model import regime_probabilities
        rp = regime_probabilities()
        if rp.get("top"):
            lead += f" ({rp['top_prob']:.0f}% model probability"
            if rp.get("runner_up_prob", 0) >= 15:
                lead += f", {rp['runner_up_prob']:.0f}% {rp['runner_up'].title()}"
            lead += ")"
    except Exception:
        pass
    if conv is not None:
        lead += f", {conv_lbl} conviction ({conv:.0f}/100)"
        if conv < 45 and sec and sec != regime:
            lead += f" — a borderline call that would flip to {sec} if the pivotal axis turns"
    parts.append(lead + ".")

    # Financial conditions.
    fci = sig.get("financial_conditions") or {}
    if fci.get("label") and fci.get("label") != "—":
        dirn = fci.get("nfci_dir")
        move = ("tightening" if (dirn or 0) > 0.02 else "easing" if (dirn or 0) < -0.02 else "stable")
        parts.append(f"Financial conditions are <b>{fci['label'].lower()}</b> and {move}.")

    # Curve + credit.
    s = sig.get("summary", {})
    cs = s.get("yield_curve_spread")
    if cs is not None:
        shape = ("inverted" if cs < 0 else "flat" if cs < 0.5 else "positively sloped")
        parts.append(f"The 10Y–3M curve is {shape} ({cs:+.2f}).")

    # Crowding.
    try:
        from data.crowding import crowding_score
        cw = crowding_score()
        if cw.get("score") is not None and cw["score"] >= 60:
            parts.append(f"Positioning looks <b>crowded</b> (crowding score {cw['score']:.0f}/100) — "
                         f"an elevated-unwind-risk backdrop.")
    except Exception:
        pass

    # Nearest analogue.
    try:
        from data.analogues import find_analogues
        an = find_analogues()
        best = (an.get("analogues") or [None])[0]
        if best and an.get("avg_fwd") is not None:
            parts.append(f"The closest historical analogue is <b>{best['date']}</b> "
                         f"({best['regime'].title()}); similar states saw the S&P "
                         f"{_pct(an['avg_fwd'])} over the following month on average.")
    except Exception:
        pass

    return " ".join(parts)
