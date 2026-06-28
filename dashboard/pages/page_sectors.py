"""Page IV — SECTOR ROTATION."""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from dashboard.styles import (
    GOLD, WHITE, GREY, GREEN, RED, AMBER, CARD, BG, BORDER, section_header, apply_theme,
)
from dashboard.components import perf_heatmap_html, line_chart, pct_color, fmt_pct, fmt_num
from dashboard.page_data import load_metrics
from data import store

PERIODS = [("return_5d", "1W"), ("return_1m", "1M"), ("return_3m", "3M"),
           ("return_6m", "6M"), ("return_1y", "1Y")]

# Cycle order clockwise from early recovery → defensive
CYCLE = [
    ("XLK", "Technology"), ("XLF", "Financials"),
    ("XLY", "Cons. Disc."), ("XLI", "Industrials"),
    ("XLE", "Energy"), ("XLB", "Materials"),
    ("XLP", "Cons. Staples"), ("XLV", "Health Care"),
    ("XLU", "Utilities"), ("XLRE", "Real Estate"), ("XLC", "Comms"),
]
SECTORS_US = [("XLK", "Technology"), ("XLF", "Financials"), ("XLE", "Energy"),
              ("XLV", "Health Care"), ("XLI", "Industrials"), ("XLY", "Cons. Disc."),
              ("XLP", "Cons. Staples"), ("XLU", "Utilities"), ("XLRE", "Real Estate"),
              ("XLB", "Materials"), ("XLC", "Comms")]
SECTORS_CA = [("XEG.TO", "Energy"), ("XFN.TO", "Financials"), ("XIT.TO", "Technology"),
              ("XMA.TO", "Materials"), ("XRE.TO", "REITs"), ("ZUH.TO", "Health Care")]


def _heat_rows(m, items):
    return [{"name": name, **{k: m.get(tk, {}).get(k) for k, _ in PERIODS}}
            for tk, name in items]


def _rotation_wheel(m) -> go.Figure:
    labels, radii, colors = [], [], []
    vals = [m.get(tk, {}).get("return_3m") for tk, _ in CYCLE]
    clean = [v for v in vals if v is not None]
    hi = max(clean) if clean else 1
    lo = min(clean) if clean else -1
    for (tk, name), v in zip(CYCLE, vals):
        labels.append(name)
        radii.append((v if v is not None else 0))
        if v is None:
            colors.append("#2a2a2a")
        elif v >= (hi * 0.5 if hi > 0 else 0):
            colors.append(GOLD)
        elif v <= 0:
            colors.append("#444")
        else:
            colors.append("rgba(201,162,39,0.4)")
    # Shift radii to positive for barpolar
    base = min(radii) if radii else 0
    plot_r = [r - base + 1 for r in radii]
    fig = go.Figure(go.Barpolar(
        r=plot_r, theta=labels, marker_color=colors,
        marker_line_color=BG, marker_line_width=2,
        hovertext=[f"{n}: {fmt_pct(v)}" for (_, n), v in zip(CYCLE, vals)],
        hoverinfo="text",
    ))
    fig.update_layout(
        paper_bgcolor=CARD, height=380, margin=dict(l=30, r=30, t=30, b=30),
        font=dict(color=WHITE, size=10),
        polar=dict(bgcolor=CARD,
                   radialaxis=dict(showticklabels=False, ticks="", gridcolor=BORDER),
                   angularaxis=dict(direction="clockwise", rotation=90,
                                    tickfont=dict(color=GREY, size=10), gridcolor=BORDER)),
    )
    return fig


def _label_for(m, tk):
    r = m.get(tk, {})
    r3 = r.get("return_3m")
    above = (r.get("close") or 0) > (r.get("ma200") or 1e9)
    if r3 is None:
        return "NEUTRAL", GREY
    if r3 > 3 and above:
        return "LEADING", GREEN
    if r3 < -3 or not above:
        return "LAGGING", RED
    return "NEUTRAL", AMBER


def render(ctx: dict) -> None:
    m = load_metrics()

    # ── Rotation wheel + interpretation ────────────────────────────────────
    st.markdown(section_header("SECTOR ROTATION WHEEL — ECONOMIC CYCLE CLOCK"), unsafe_allow_html=True)
    w1, w2 = st.columns([1.3, 1])
    with w1:
        st.plotly_chart(_rotation_wheel(m), width='stretch',
                        config={"displayModeBar": False})
        st.caption("Bars sized by 3-month return. Gold = current leaders, grey = laggards. "
                   "Order runs early-recovery (Tech/Financials) → defensive (Utilities/Staples).")
    with w2:
        ranked = sorted(SECTORS_US, key=lambda s: (m.get(s[0], {}).get("return_3m") or -1e9),
                        reverse=True)
        lead = [n for _, n in ranked[:3]]
        lag = [n for _, n in ranked[-3:]]
        st.markdown(
            f'<div style="background:{CARD};border:1px solid {GOLD};border-radius:8px;'
            f'padding:16px 20px;margin-top:6px"><div style="color:{GOLD};font-size:11px;'
            f'font-weight:600;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px">'
            f'What the rotation is saying</div>'
            f'<div style="font-size:13px;color:{WHITE};line-height:1.6">'
            f'<b style="color:{GREEN}">Leading (3M):</b> {", ".join(lead)}<br>'
            f'<b style="color:{RED}">Lagging (3M):</b> {", ".join(lag)}<br><br>'
            f'{_interpretation(lead, lag)}</div></div>', unsafe_allow_html=True)

    # ── US + Canada heatmaps ───────────────────────────────────────────────
    st.markdown(section_header("US SECTOR PERFORMANCE"), unsafe_allow_html=True)
    st.markdown(perf_heatmap_html(_heat_rows(m, SECTORS_US), PERIODS), unsafe_allow_html=True)
    st.markdown(section_header("CANADIAN SECTOR PERFORMANCE"), unsafe_allow_html=True)
    st.markdown(perf_heatmap_html(_heat_rows(m, SECTORS_CA), PERIODS), unsafe_allow_html=True)

    # ── Sector momentum table ──────────────────────────────────────────────
    st.markdown(section_header("US SECTOR MOMENTUM"), unsafe_allow_html=True)
    head = ("<tr><th>Sector</th><th style='text-align:right'>1M</th>"
            "<th style='text-align:right'>3M</th><th style='text-align:right'>RSI</th>"
            "<th style='text-align:center'>200d MA</th><th style='text-align:center'>Signal</th></tr>")
    body = ""
    for tk, name in SECTORS_US:
        r = m.get(tk, {})
        lbl, col = _label_for(m, tk)
        above = (r.get("close") or 0) > (r.get("ma200") or 1e9)
        ma = (f'<span style="color:{GREEN}">▲</span>' if above
              else f'<span style="color:{RED}">▼</span>')
        body += (
            f'<tr><td style="font-weight:600">{name}</td>'
            f'<td style="text-align:right;color:{pct_color(r.get("return_1m"))}" class="mono">{fmt_pct(r.get("return_1m"))}</td>'
            f'<td style="text-align:right;color:{pct_color(r.get("return_3m"))}" class="mono">{fmt_pct(r.get("return_3m"))}</td>'
            f'<td style="text-align:right" class="mono">{fmt_num(r.get("rsi14"),0)}</td>'
            f'<td style="text-align:center">{ma}</td>'
            f'<td style="text-align:center"><span style="color:{col};font-weight:600;font-size:11px">{lbl}</span></td></tr>')
    st.markdown(f'<table class="data-grid" style="width:100%"><thead>{head}</thead>'
                f'<tbody>{body}</tbody></table>', unsafe_allow_html=True)

    # ── Relative strength tool ─────────────────────────────────────────────
    st.markdown(section_header("RELATIVE STRENGTH — SECTOR vs SECTOR"), unsafe_allow_html=True)
    names = {tk: name for tk, name in SECTORS_US}
    rc1, rc2, rc3 = st.columns(3)
    with rc1:
        a = st.selectbox("Sector A", list(names), format_func=lambda t: names[t], index=0, key="rs_a")
    with rc2:
        b = st.selectbox("Sector B", list(names), format_func=lambda t: names[t], index=4, key="rs_b")
    with rc3:
        per = st.selectbox("Period", ["3M", "6M", "1Y"], index=2, key="rs_p")
    days = {"3M": 63, "6M": 126, "1Y": 252}[per]
    rr = store.ratio(a, b, days=days).dropna()
    if not rr.empty:
        rr = rr / rr.iloc[0] * 100
        fig = line_chart([{"x": rr.index, "y": rr.values, "name": f"{names[a]}/{names[b]}",
                           "color": GOLD}], height=280, showlegend=False)
        st.plotly_chart(fig, width='stretch', config={"displayModeBar": False})
        lead = names[a] if rr.iloc[-1] > 100 else names[b]
        st.caption(f"Rebased to 100. Rising = {names[a]} outperforming {names[b]}. "
                   f"{lead} has led over the {per} window.")

    # ── Cyclical vs Defensive ──────────────────────────────────────────────
    st.markdown(section_header("CYCLICAL vs DEFENSIVE"), unsafe_allow_html=True)
    cyc = store.closes(["XLI", "XLY", "XLE"], days=252).dropna()
    defn = store.closes(["XLP", "XLU", "XLV"], days=252).dropna()
    if not cyc.empty and not defn.empty:
        idx = cyc.index.intersection(defn.index)
        ratio = (cyc.loc[idx].mean(axis=1) / defn.loc[idx].mean(axis=1))
        ratio = ratio / ratio.iloc[0] * 100
        fig = line_chart([{"x": ratio.index, "y": ratio.values, "name": "Cyclical/Defensive",
                           "color": GREEN}], height=260, showlegend=False)
        st.plotly_chart(fig, width='stretch', config={"displayModeBar": False})
        rising = ratio.iloc[-1] > ratio.iloc[max(0, len(ratio) - 22)]
        st.caption(("Rising — cyclical leadership, risk-on positioning." if rising
                    else "Falling — defensive positioning, market turning cautious."))


def _interpretation(lead, lag) -> str:
    lead_s = set(lead)
    if {"Energy", "Materials"} & lead_s and ("Utilities" in lag or "Cons. Staples" in lag):
        return ("Energy/Materials leading while defensives lag — consistent with late-cycle "
                "positioning or a commodity-demand theme. Constructive for the resource-heavy TSX.")
    if {"Technology", "Cons. Disc."} & lead_s:
        return ("Technology and Consumer Discretionary leading — a risk-on, growth-led tape "
                "typical of early/mid cycle.")
    if {"Utilities", "Cons. Staples", "Health Care"} & lead_s:
        return ("Defensives leading — the market is positioning cautiously; watch breadth and credit.")
    return "Leadership is mixed — no single cycle theme is dominant right now."
