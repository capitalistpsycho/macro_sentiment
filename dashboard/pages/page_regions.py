"""Page III — REGIONS & GEOGRAPHY."""

from __future__ import annotations

import streamlit as st

from dashboard.styles import GOLD, WHITE, GREY, GREEN, RED, CARD, BORDER, section_header
from dashboard.components import (
    perf_heatmap_html, line_chart, stat_card, pct_color, fmt_pct, fmt_num,
)
from dashboard.page_data import load_metrics
from data import store, fx as fxmod, flows

PERIODS = [("return_5d", "1W"), ("return_1m", "1M"), ("return_3m", "3M"),
           ("return_6m", "6M"), ("return_1y", "1Y")]

REGIONS = [("SPY", "United States"), ("EWC", "Canada"), ("VGK", "Europe"),
           ("EWJ", "Japan"), ("MCHI", "China"), ("EEM", "Emerging Markets")]


def render(ctx: dict) -> None:
    m = load_metrics()

    # ── World performance table ────────────────────────────────────────────
    st.markdown(section_header("WORLD PERFORMANCE (USD)"), unsafe_allow_html=True)
    rows = []
    for tk, name in REGIONS:
        r = m.get(tk, {})
        rows.append({"name": name, **{k: r.get(k) for k, _ in PERIODS}})
    st.markdown(perf_heatmap_html(rows, PERIODS), unsafe_allow_html=True)

    # ── CAD/USD panel + US vs Canada ───────────────────────────────────────
    c1, c2 = st.columns([1, 1.3])
    with c1:
        st.markdown(section_header("CAD / USD IMPACT"), unsafe_allow_html=True)
        cad = fxmod.cad_usd_panel(m)
        rate_txt = fmt_num(cad["rate"], 4) if cad["rate"] else "—"
        st.markdown(stat_card("CAD/USD", rate_txt, f"1M {fmt_pct(cad['trend_1m'])}",
                              pct_color(cad["trend_1m"])), unsafe_allow_html=True)
        st.markdown(f'<div style="background:{CARD};border:1px solid {BORDER};border-radius:8px;'
                    f'padding:12px 16px;margin-top:10px;font-size:12px;color:{WHITE};line-height:1.5">'
                    f'{cad["implication"]}</div>', unsafe_allow_html=True)
    with c2:
        st.markdown(section_header("US vs CANADA — SPY / XIU.TO"), unsafe_allow_html=True)
        rr = store.ratio("SPY", "XIU.TO", days=252).dropna()
        if not rr.empty:
            fig = line_chart([{"x": rr.index, "y": rr.values, "name": "SPY/XIU", "color": GOLD}],
                             height=240, showlegend=False)
            st.plotly_chart(fig, width='stretch', config={"displayModeBar": False})
            st.caption("Rising = US equities outpacing Canada; falling = Canada (resource-heavy) leading.")

    # ── EM vs DM + Regional momentum ───────────────────────────────────────
    c3, c4 = st.columns([1.3, 1])
    with c3:
        st.markdown(section_header("EM vs DM — EEM / VEA"), unsafe_allow_html=True)
        rr2 = store.ratio("EEM", "VEA", days=252).dropna()
        if not rr2.empty:
            fig = line_chart([{"x": rr2.index, "y": rr2.values, "name": "EEM/VEA", "color": GREEN}],
                             height=240, showlegend=False)
            st.plotly_chart(fig, width='stretch', config={"displayModeBar": False})
            st.caption("Rising = EM outperforming — typically a weaker USD and broadening global growth.")
    with c4:
        st.markdown(section_header("REGIONAL MOMENTUM (3M)"), unsafe_allow_html=True)
        ranking = flows.momentum_ranking(REGIONS, field="return_3m")
        body = ""
        for i, r in enumerate(ranking, 1):
            v = r["value"]
            arrow = ("▲" if (v or 0) > 1 else ("▼" if (v or 0) < -1 else "→"))
            body += (f'<div style="display:flex;justify-content:space-between;padding:6px 0;'
                     f'border-bottom:1px solid #1e1e1e"><span><b style="color:{GOLD}">{i}.</b> '
                     f'{r["label"]}</span><span style="font-family:JetBrains Mono,monospace;'
                     f'color:{pct_color(v)}">{arrow} {fmt_pct(v)}</span></div>')
        st.markdown(f'<div style="background:{CARD};border:1px solid {BORDER};border-radius:8px;'
                    f'padding:8px 16px">{body}</div>', unsafe_allow_html=True)

    # ── China watch ────────────────────────────────────────────────────────
    st.markdown(section_header("CHINA WATCH — MCHI"), unsafe_allow_html=True)
    r = m.get("MCHI", {})
    s = store.series("MCHI")
    ytd = None
    if not s.empty:
        yr = s["date"].dt.year.max()
        jan = s[s["date"].dt.year == yr]
        if not jan.empty:
            ytd = (float(s["close"].iloc[-1]) / float(jan["close"].iloc[0]) - 1) * 100
    cc1, cc2, cc3 = st.columns(3)
    with cc1:
        st.markdown(stat_card("MCHI Price", fmt_num(r.get("close")), "China large-cap ETF", WHITE),
                    unsafe_allow_html=True)
    with cc2:
        st.markdown(stat_card("1-Month", fmt_pct(r.get("return_1m")), "",
                              pct_color(r.get("return_1m"))), unsafe_allow_html=True)
    with cc3:
        st.markdown(stat_card("Year-to-Date", fmt_pct(ytd), "", pct_color(ytd)),
                    unsafe_allow_html=True)
    st.markdown(f'<div style="background:{CARD};border:1px solid {BORDER};border-radius:8px;'
                f'padding:12px 16px;margin-top:10px;font-size:12px;color:{GREY};line-height:1.5">'
                f'China demand is a key driver of oil, copper and lumber — and therefore of the '
                f'resource-heavy TSX and the Northstar Fund\'s energy and materials exposure. '
                f'Watch MCHI as a leading tell on Canadian commodity earnings.</div>',
                unsafe_allow_html=True)
