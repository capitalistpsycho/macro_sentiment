"""
Polaris — the macro-focused AI analyst for the Macro Compass.

Self-contained: builds a compact live snapshot of current market conditions
(signals, regimes, sentiment, key trends) and answers questions via the Claude
API using the shared get_secret() helper. Degrades gracefully with no API key.
"""

from __future__ import annotations

import json
import logging
import os

logger = logging.getLogger(__name__)

POLARIS_MACRO_PERSONA = """You are Polaris, the macro strategist for Taynton Bay Capital's Northstar Fund.

You answer questions about market regimes, style and sector rotation, regional
flows, the rate and credit environment, commodities and investor sentiment.

CRITICAL RULES — NO EXCEPTIONS:
- NEVER show code, JSON, variable names, or technical implementation details.
- NEVER fabricate data — if a figure is unavailable, say "data not available as of [date]".
- ALWAYS show the as-of date on any level, yield or return you cite.
- ALWAYS respond in an institutional register — concise, evidence-based, for a fund PM.
- Tie answers back to positioning implications for a Canadian equity fund (the
  TSX is ~18% energy and ~12% materials, so commodity and USD trends matter).
- Keep answers under ~250 words unless asked for depth.

The current live market context is provided below — use it to ground every answer."""


def _has_key() -> bool:
    try:
        from config.secrets import get_secret
        return bool(get_secret("ANTHROPIC_API_KEY"))
    except Exception:
        return bool(os.environ.get("ANTHROPIC_API_KEY"))


def build_macro_context() -> dict:
    """Compact snapshot of current macro conditions for Polaris."""
    from data import store
    from data.signals import compute_signals
    from data.sentiment import fear_greed

    m = store.latest_metrics()
    sig = compute_signals(m)
    fg = fear_greed(m)

    def snap(tk):
        r = m.get(tk, {})
        return {"px": r.get("close"), "1d": r.get("return_1d"),
                "1m": r.get("return_1m"), "3m": r.get("return_3m")}

    return {
        "as_of": sig["date"],
        "macro_compass_score": sig["compass_score"],
        "risk_on_off_score": sig["risk_score"],
        "risk_drivers": sig["risk_drivers"],
        "market_regime": sig["regime"],
        "market_regime_meaning": sig["regime_desc"],
        "macro_regime": sig["macro_regime"],
        "macro_regime_meaning": sig["macro_regime_desc"],
        "macro_regime_source": sig.get("macro_source"),
        "macro_nowcast_fred": sig.get("macro_nowcast"),
        "financial_conditions_fred": sig.get("financial_conditions"),
        "signal_dimensions_-2_to_+2": sig["dimensions"],
        "summary": sig["summary"],
        "fear_greed": {"score": fg["score"], "label": fg["label"]},
        "benchmarks": {tk: snap(tk) for tk in ("^GSPTSE", "^GSPC", "^IXIC", "^RUT")},
        "style": {tk: snap(tk) for tk in ("IWF", "IWD", "MTUM", "USMV", "QUAL")},
        "regions": {tk: snap(tk) for tk in ("SPY", "EWC", "VGK", "EWJ", "MCHI", "EEM")},
        "commodities": {tk: snap(tk) for tk in ("GC=F", "CL=F", "HG=F")},
        "fx": {tk: snap(tk) for tk in ("CADUSD=X", "DX-Y.NYB")},
    }


def _system_prompt(ctx: dict) -> str:
    body = json.dumps(ctx, default=str)[:16000]
    return f"{POLARIS_MACRO_PERSONA}\n\n=== LIVE MACRO CONTEXT ===\n{body}"


def ask_polaris(question: str, ctx: dict, history: list[dict] | None = None,
                model: str = "claude-sonnet-4-6") -> str:
    if not _has_key():
        return ("Polaris is offline — set ANTHROPIC_API_KEY in .env or "
                ".streamlit/secrets.toml to enable live macro Q&A.")
    try:
        import anthropic
        from config.secrets import get_secret
        client = anthropic.Anthropic(api_key=get_secret("ANTHROPIC_API_KEY"))
        messages = []
        if history:
            messages.extend(history[-6:])
        messages.append({"role": "user", "content": question})
        resp = client.messages.create(
            model=model, max_tokens=1100,
            system=[{"type": "text", "text": _system_prompt(ctx),
                     "cache_control": {"type": "ephemeral"}}],
            messages=messages,
        )
        return next((b.text for b in resp.content if b.type == "text"), "")
    except Exception as exc:
        logger.error("Polaris error: %s", exc)
        return "Polaris is temporarily unavailable. Check ANTHROPIC_API_KEY and try again."


def render_polaris_bar(ctx: dict) -> None:
    """The macro ask-bar used on the Overview page."""
    import streamlit as st
    from dashboard.styles import GOLD, GREY

    st.markdown('<div class="polaris-label">✦ Ask Polaris — Macro Compass</div>',
                unsafe_allow_html=True)

    if "polaris_history" not in st.session_state:
        st.session_state["polaris_history"] = []
    if not st.session_state.get("polaris_briefed"):
        briefing = first_load_briefing(ctx)
        st.markdown(
            f'<div class="polaris-response" style="border-color:{GOLD};margin-bottom:8px">'
            f'<span style="color:{GOLD};font-size:11px;font-weight:600">POLARIS BRIEFING</span>'
            f'<br><br>{briefing}</div>', unsafe_allow_html=True)
        st.session_state["polaris_briefed"] = True

    col_in, col_btn = st.columns([5, 1])
    with col_in:
        q = st.text_input("question", key="polaris_question",
                          placeholder="Ask about any market trend, sector, or macro theme…",
                          label_visibility="collapsed")
    with col_btn:
        send = st.button("Ask", type="primary", width='stretch')

    if send and q.strip():
        with st.spinner(""):
            resp = ask_polaris(q.strip(), ctx, history=st.session_state["polaris_history"])
        st.session_state["polaris_history"].extend([
            {"role": "user", "content": q.strip()},
            {"role": "assistant", "content": resp},
        ])
        st.session_state["polaris_history"] = st.session_state["polaris_history"][-12:]

    for msg in reversed(st.session_state["polaris_history"][-4:]):
        if msg["role"] == "assistant":
            st.markdown(f'<div class="polaris-response">{msg["content"]}</div>',
                        unsafe_allow_html=True)
        else:
            st.markdown(f'<div style="color:{GREY};font-size:12px;padding:6px 0">'
                        f'<b style="color:{GOLD}">You:</b> {msg["content"]}</div>',
                        unsafe_allow_html=True)


def first_load_briefing(ctx: dict) -> str:
    """A one-line proactive read of current conditions."""
    regime = ctx.get("market_regime", "—")
    score = ctx.get("macro_compass_score")
    risk = ctx.get("risk_on_off_score")
    fg = ctx.get("fear_greed", {})
    drivers = ctx.get("risk_drivers", [])
    lead = f"Regime: {regime}. MacroCompass {score}/100, risk-on/off {risk}/100, "
    lead += f"sentiment {fg.get('label','—')} ({fg.get('score','—')})."
    if drivers:
        lead += " Key drivers: " + "; ".join(drivers[:2]) + "."
    return lead
