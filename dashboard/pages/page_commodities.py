"""Page VII — COMMODITIES."""

from __future__ import annotations

import streamlit as st

from dashboard.styles import GOLD, WHITE, GREY, GREEN, RED, CARD, BORDER, section_header
from dashboard.components import line_chart, stat_card, pct_color, fmt_pct, fmt_num
from dashboard.page_data import load_metrics
from data import store, commodities as cm


def _panel_chart(ticker, color, days=126):
    s = store.series(ticker, days=days)
    if s.empty:
        return None
    hi, lo = float(s["close"].max()), float(s["close"].min())
    fig = line_chart([{"x": s["date"], "y": s["close"], "name": ticker, "color": color}],
                     height=240, showlegend=False,
                     hlines=[{"y": hi, "label": "52w high", "color": GREY},
                             {"y": lo, "label": "52w low", "color": GREY}])
    return fig


def render(ctx: dict) -> None:
    m = load_metrics()

    # ── Performance table ──────────────────────────────────────────────────
    st.markdown(section_header("COMMODITY PERFORMANCE"), unsafe_allow_html=True)
    tbl = cm.performance_table()
    head = ("<tr><th>Commodity</th><th style='text-align:right'>Price (USD)</th>"
            "<th style='text-align:right'>1D</th><th style='text-align:right'>1M</th>"
            "<th style='text-align:right'>3M</th><th style='text-align:right'>YTD</th>"
            "<th style='text-align:right'>From 52w High</th></tr>")
    body = ""
    for _, r in tbl.iterrows():
        body += (
            f'<tr><td style="font-weight:600">{r["name"]}</td>'
            f'<td style="text-align:right" class="mono">{fmt_num(r["price"])}</td>'
            f'<td style="text-align:right;color:{pct_color(r["return_1d"])}" class="mono">{fmt_pct(r["return_1d"])}</td>'
            f'<td style="text-align:right;color:{pct_color(r["return_1m"])}" class="mono">{fmt_pct(r["return_1m"])}</td>'
            f'<td style="text-align:right;color:{pct_color(r["return_3m"])}" class="mono">{fmt_pct(r["return_3m"])}</td>'
            f'<td style="text-align:right;color:{pct_color(r["ytd"])}" class="mono">{fmt_pct(r["ytd"])}</td>'
            f'<td style="text-align:right;color:{pct_color(r["from_high"])}" class="mono">{fmt_pct(r["from_high"])}</td></tr>')
    st.markdown(f'<table class="data-grid" style="width:100%"><thead>{head}</thead>'
                f'<tbody>{body}</tbody></table>', unsafe_allow_html=True)

    # ── Oil + Gold panels ──────────────────────────────────────────────────
    o1, o2 = st.columns(2)
    with o1:
        st.markdown(section_header("OIL — WTI CRUDE (6M)"), unsafe_allow_html=True)
        fig = _panel_chart("CL=F", GOLD)
        if fig:
            st.plotly_chart(fig, width='stretch', config={"displayModeBar": False})
        st.caption("Direct read-through to Canadian energy holdings (CNQ, ARX, SES, TCW in the "
                   "Northstar portfolio). Higher oil supports TSX energy earnings.")
    with o2:
        st.markdown(section_header("GOLD — SPOT (6M)"), unsafe_allow_html=True)
        fig = _panel_chart("GC=F", "#FACC15")
        if fig:
            st.plotly_chart(fig, width='stretch', config={"displayModeBar": False})
        gold_1m = m.get("GC=F", {}).get("return_1m")
        usd_1m = m.get("DX-Y.NYB", {}).get("return_1m")
        tip_tlt = store.ratio("TIP", "TLT", days=21).dropna()
        real_falling = (not tip_tlt.empty and tip_tlt.iloc[-1] > tip_tlt.iloc[0])
        consistent = ((gold_1m or 0) > 0 and ((usd_1m or 0) < 0 or real_falling))
        note = ("consistent with its classic drivers (softer USD / falling real yields)"
                if consistent else "running against its usual USD / real-yield drivers")
        st.caption(f"Gold tends to rise when real yields fall and/or the USD weakens. "
                   f"The current move is {note}.")

    # ── Copper panel ───────────────────────────────────────────────────────
    st.markdown(section_header("COPPER — GLOBAL GROWTH INDICATOR (6M)"), unsafe_allow_html=True)
    cc1, cc2 = st.columns([1.4, 1])
    with cc1:
        fig = _panel_chart("HG=F", "#fb923c")
        if fig:
            st.plotly_chart(fig, width='stretch', config={"displayModeBar": False})
    with cc2:
        r = m.get("HG=F", {})
        st.markdown(stat_card("Copper", fmt_num(r.get("close")), f"1M {fmt_pct(r.get('return_1m'))}",
                              pct_color(r.get("return_1m"))), unsafe_allow_html=True)
        st.markdown(f'<div style="background:{CARD};border:1px solid {BORDER};border-radius:8px;'
                    f'padding:12px 16px;margin-top:10px;font-size:12px;color:{GREY};line-height:1.5">'
                    f'Copper is a key input for the electrification and EV-transition theme and a '
                    f'leading tell on global industrial demand. Relevant to materials/mining exposure '
                    f'and to the broader TSX.</div>', unsafe_allow_html=True)

    # ── Uranium ────────────────────────────────────────────────────────────
    st.markdown(section_header("URANIUM — NUCLEAR FUEL COMPLEX (6M)"), unsafe_allow_html=True)
    u1, u2 = st.columns([1.4, 1])
    URANIUM = [("U-UN.TO", "SPUT (physical spot)"), ("URA", "Miners ETF"),
               ("URNM", "Pure-Play Miners"), ("CCJ", "Cameco")]
    with u1:
        fig = _panel_chart("URA", "#84cc16")
        if fig:
            st.plotly_chart(fig, width='stretch', config={"displayModeBar": False})
        else:
            st.info("Uranium data will populate on the next data refresh (run_macro.py).")
    with u2:
        head = ("<tr><th>Instrument</th><th style='text-align:right'>1M</th>"
                "<th style='text-align:right'>3M</th><th style='text-align:right'>YTD</th></tr>")
        rows = ""
        for tk, name in URANIUM:
            r = m.get(tk, {})
            rows += (
                f'<tr><td style="font-weight:600;font-size:12px">{name}</td>'
                f'<td style="text-align:right;color:{pct_color(r.get("return_1m"))}" class="mono">{fmt_pct(r.get("return_1m"))}</td>'
                f'<td style="text-align:right;color:{pct_color(r.get("return_3m"))}" class="mono">{fmt_pct(r.get("return_3m"))}</td>'
                f'<td style="text-align:right;color:{pct_color(r.get("return_ytd"))}" class="mono">{fmt_pct(r.get("return_ytd"))}</td></tr>')
        st.markdown(f'<table class="data-grid" style="width:100%"><thead>{head}</thead>'
                    f'<tbody>{rows}</tbody></table>', unsafe_allow_html=True)
        st.markdown(f'<div style="background:{CARD};border:1px solid {BORDER};border-radius:8px;'
                    f'padding:10px 14px;margin-top:10px;font-size:12px;color:{GREY};line-height:1.5">'
                    f'SPUT (Sprott Physical Uranium Trust) tracks spot U₃O₈; the miners/Cameco carry '
                    f'operating leverage to it. A structural supply-deficit and nuclear-demand theme; '
                    f'relevant to Canadian producers (Cameco, NexGen) and the TSX.</div>',
                    unsafe_allow_html=True)

    # ── Ratios ─────────────────────────────────────────────────────────────
    r1, r2 = st.columns(2)
    with r1:
        st.markdown(section_header("COMMODITIES vs EQUITIES — DJP / SPY"), unsafe_allow_html=True)
        rr = cm.commodity_equity_ratio(252).dropna()
        if not rr.empty:
            rr = rr / rr.iloc[0] * 100
            fig = line_chart([{"x": rr.index, "y": rr.values, "name": "DJP/SPY", "color": GOLD}],
                             height=240, showlegend=False)
            st.plotly_chart(fig, width='stretch', config={"displayModeBar": False})
            st.caption("Rising = commodities outperforming equities — typical of late cycle / inflation.")
    with r2:
        st.markdown(section_header("OIL vs GOLD — CL / GC"), unsafe_allow_html=True)
        rr = cm.oil_gold_ratio(252).dropna()
        if not rr.empty:
            rr = rr / rr.iloc[0] * 100
            fig = line_chart([{"x": rr.index, "y": rr.values, "name": "Oil/Gold", "color": GREEN}],
                             height=240, showlegend=False)
            st.plotly_chart(fig, width='stretch', config={"displayModeBar": False})
            st.caption("Oil leading = risk-on / strong global growth. Gold leading = risk-off / "
                       "growth concerns dominating.")

    # ── Oil shock scenario (Scotiabank elasticities) ───────────────────────
    st.markdown(section_header("OIL SHOCK SCENARIO — CANADA vs US IMPACT"), unsafe_allow_html=True)
    from data.scenarios import oil_scenario
    shock = st.slider("Oil price shock (WTI, $/bbl, persistent 2y)", -30, 30, 10, 5, key="oil_shock")
    sc = oil_scenario(shock)

    def _impact_card(name, d, cad=True):
        gdp, cpi, pol = d.get("gdp_pct_yr2"), d.get("cpi_pp"), d.get("policy_bps")
        cadrow = (f'<div style="display:flex;justify-content:space-between;padding:4px 0">'
                  f'<span style="color:{GREY}">CAD</span><span class="mono" style="color:{pct_color(d.get("cad_pct"))}">'
                  f'{fmt_pct(d.get("cad_pct"))}</span></div>') if cad and d.get("cad_pct") is not None else ""
        return (
            f'<div style="flex:1;background:{CARD};border:1px solid {BORDER};border-radius:8px;padding:14px 18px">'
            f'<div style="color:{GOLD};font-size:13px;font-weight:700;margin-bottom:6px">{name}</div>'
            f'<div style="display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid #1e1e1e">'
            f'<span style="color:{GREY}">GDP (yr 2)</span><span class="mono" style="color:{pct_color(gdp)}">{fmt_pct(gdp)}</span></div>'
            f'<div style="display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid #1e1e1e">'
            f'<span style="color:{GREY}">CPI</span><span class="mono" style="color:{WHITE}">{cpi:+.2f} pp</span></div>'
            f'<div style="display:flex;justify-content:space-between;padding:4px 0">'
            f'<span style="color:{GREY}">Policy rate</span><span class="mono" style="color:{WHITE}">{pol:+.0f} bp</span></div>'
            f'{cadrow}</div>')
    st.markdown(f'<div style="display:flex;gap:12px">'
                f'{_impact_card("🇨🇦 Canada", sc["Canada"])}'
                f'{_impact_card("🇺🇸 United States", sc["US"], cad=False)}</div>',
                unsafe_allow_html=True)
    st.caption(f"A {shock:+d}/bbl persistent WTI shock, per Scotiabank's Canada–U.S. Macro Model "
               f"elasticities (scale ~linearly). Oil is a net terms-of-trade gain for Canada (energy "
               f"exporter) but a wash-to-headwind for the US. Direct read-through to TSX energy and CAD.")

    # ── Canadian commodity link ────────────────────────────────────────────
    st.markdown(section_header("CANADIAN COMMODITY LINK"), unsafe_allow_html=True)
    oil_1m = m.get("CL=F", {}).get("return_1m")
    cop_1m = m.get("HG=F", {}).get("return_1m")
    tsx_1m = m.get("^GSPTSE", {}).get("return_1m")
    st.markdown(
        f'<div style="background:{CARD};border:1px solid {GOLD};border-radius:8px;'
        f'padding:16px 20px;font-size:13px;color:{WHITE};line-height:1.6">'
        f'The S&P/TSX Composite is roughly <b style="color:{GOLD}">18% Energy</b> and '
        f'<b style="color:{GOLD}">12% Materials</b>, so commodity trends feed directly into TSX '
        f'performance and the Northstar Fund. Last month: oil '
        f'<span style="color:{pct_color(oil_1m)}">{fmt_pct(oil_1m)}</span>, copper '
        f'<span style="color:{pct_color(cop_1m)}">{fmt_pct(cop_1m)}</span>, '
        f'TSX <span style="color:{pct_color(tsx_1m)}">{fmt_pct(tsx_1m)}</span>.</div>',
        unsafe_allow_html=True)
