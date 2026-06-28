"""Page V — MACRO & FIXED INCOME."""

from __future__ import annotations

import streamlit as st

from dashboard.styles import GOLD, WHITE, GREY, GREEN, RED, AMBER, CARD, BORDER, section_header
from dashboard.components import (
    line_chart, regime_badge, stat_card, pct_color, fmt_pct, fmt_num,
)
from dashboard.page_data import (
    load_metrics, load_signals, load_calendar, load_financial_stress,
)
from data import store, fixed_income as fi

_IMPACT_COL = {"high": RED, "medium": AMBER, "low": GREY}


def _event_strip(events: list) -> str:
    chips = ""
    for e in events[:8]:
        col = _IMPACT_COL.get(e["impact"], GREY)
        du = e["days_until"]
        when = "today" if du == 0 else ("tomorrow" if du == 1 else f"{du}d")
        last = f' · {e["last"]}' if e.get("last") else ""
        chips += (
            f'<span style="display:inline-block;background:#121212;border:1px solid {col};'
            f'border-left:4px solid {col};border-radius:6px;padding:6px 12px;margin:0 8px 8px 0;'
            f'font-size:12px"><b style="color:{col}">{when}</b> '
            f'<span style="color:{WHITE}">{e["label"]}</span>'
            f'<span style="color:{GREY};font-size:11px">{last}</span></span>')
    return f'<div style="margin:4px 0 6px 0">{chips}</div>'


def render(ctx: dict) -> None:
    m = load_metrics()
    sig = load_signals()

    # ── Economic event calendar ─────────────────────────────────────────────
    events = load_calendar(21)
    if events:
        st.markdown(section_header("ECONOMIC CALENDAR — NEXT 3 WEEKS"), unsafe_allow_html=True)
        st.markdown(_event_strip(events), unsafe_allow_html=True)
        st.caption("Scheduled US macro releases (FRED). Red = high-impact (FOMC, CPI, jobs, PCE). "
                   "Position size into known event risk.")

    # ── Yield curve ────────────────────────────────────────────────────────
    st.markdown(section_header("US YIELD CURVE — NOW vs 3 MONTHS AGO"), unsafe_allow_html=True)
    curve = fi.current_curve()
    c1, c2 = st.columns([1.4, 1])
    with c1:
        if not curve.empty:
            traces = [{"x": curve["label"].tolist(), "y": curve["yield_now"].tolist(),
                       "name": "Current", "color": GOLD}]
            if curve["yield_3m_ago"].notna().any():
                traces.append({"x": curve["label"].tolist(),
                               "y": curve["yield_3m_ago"].tolist(),
                               "name": "3 months ago", "color": GREY, "dash": "dash"})
            fig = line_chart(traces, height=300)
            fig.update_traces(mode="lines+markers")
            st.plotly_chart(fig, width='stretch', config={"displayModeBar": False})
    with c2:
        spread = sig["summary"].get("yield_curve_spread")
        if spread is None: shape, col = "—", GREY
        elif spread < 0:   shape, col = "INVERTED", RED
        elif spread < 0.5: shape, col = "FLAT", AMBER
        else:              shape, col = "NORMAL", GREEN
        st.markdown(stat_card("10Y − 3M Spread", fmt_num(spread, 2), shape, col),
                    unsafe_allow_html=True)
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        st.markdown(stat_card("US 10Y Yield", fmt_num(m.get("^TNX", {}).get("close"), 2) + "%",
                              "", WHITE), unsafe_allow_html=True)
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        st.markdown(stat_card("US 3M Yield", fmt_num(m.get("^IRX", {}).get("close"), 2) + "%",
                              "", WHITE), unsafe_allow_html=True)

    # ── Curve spread history ───────────────────────────────────────────────
    st.markdown(section_header("YIELD CURVE HISTORY — 10Y−3M SPREAD (2Y)"), unsafe_allow_html=True)
    hist = fi.curve_spread_history(days=504)
    if not hist.empty:
        fig = line_chart([{"x": hist.index, "y": hist.values, "name": "10Y−3M", "color": GOLD}],
                         height=280, showlegend=False,
                         shade=[{"y0": hist.min() - 0.3, "y1": 0, "color": "rgba(239,68,68,0.12)"}],
                         hlines=[{"y": 0, "label": "Inversion", "color": RED}])
        st.plotly_chart(fig, width='stretch', config={"displayModeBar": False})
        st.caption("Red zone = inverted curve (10Y below 3M) — historically a recession lead indicator.")

    # ── VIX + Credit ───────────────────────────────────────────────────────
    v1, v2 = st.columns(2)
    with v1:
        st.markdown(section_header("VIX — 6 MONTHS"), unsafe_allow_html=True)
        vs = store.series("^VIX", days=126)
        if not vs.empty:
            fig = line_chart([{"x": vs["date"], "y": vs["close"], "name": "VIX", "color": GOLD}],
                             height=280, showlegend=False,
                             hlines=[{"y": 15, "label": "Low", "color": GREEN},
                                     {"y": 20, "label": "Elevated", "color": AMBER},
                                     {"y": 25, "label": "High", "color": "#fb923c"},
                                     {"y": 35, "label": "Extreme", "color": RED}])
            st.plotly_chart(fig, width='stretch', config={"displayModeBar": False})
    with v2:
        st.markdown(section_header("CREDIT — HYG vs TLT"), unsafe_allow_html=True)
        rr = store.ratio("HYG", "TLT", days=252).dropna()
        if not rr.empty:
            rr = rr / rr.iloc[0] * 100
            fig = line_chart([{"x": rr.index, "y": rr.values, "name": "HYG/TLT", "color": GREEN}],
                             height=280, showlegend=False)
            st.plotly_chart(fig, width='stretch', config={"displayModeBar": False})
            ce = fi.credit_environment(m)
            st.caption(f"Credit spreads: {ce['direction']}. When HYG underperforms TLT, "
                       f"spreads are widening (risk-off).")

    # ── Real vs nominal / breakeven proxies ────────────────────────────────
    r1, r2 = st.columns(2)
    with r1:
        st.markdown(section_header("REAL vs NOMINAL — TIP / TLT"), unsafe_allow_html=True)
        rr = store.ratio("TIP", "TLT", days=252).dropna()
        if not rr.empty:
            rr = rr / rr.iloc[0] * 100
            fig = line_chart([{"x": rr.index, "y": rr.values, "name": "TIP/TLT", "color": GOLD}],
                             height=240, showlegend=False)
            st.plotly_chart(fig, width='stretch', config={"displayModeBar": False})
            st.caption("TIP/TLT rising ≈ rising inflation expectations; falling ≈ rising real yields "
                       "(a historical headwind for growth stocks).")
    with r2:
        st.markdown(section_header("BoC vs FED"), unsafe_allow_html=True)
        us10 = m.get("^TNX", {}).get("close")
        ca_bond_1m = m.get("ZAG.TO", {}).get("return_1m")
        us_bond_1m = m.get("IEF", {}).get("return_1m")
        diverge = "—"
        if ca_bond_1m is not None and us_bond_1m is not None:
            diverge = ("Canada easing faster (CA bonds outperforming)" if ca_bond_1m > us_bond_1m
                       else "US rates leading (US bonds outperforming)")
        st.markdown(
            f'<div style="background:{CARD};border:1px solid {BORDER};border-radius:8px;'
            f'padding:14px 18px;font-size:13px;line-height:1.7">'
            f'<div style="color:{GREY}">US 10Y proxy: <span style="color:{WHITE};'
            f'font-family:JetBrains Mono,monospace">{fmt_num(us10,2)}%</span></div>'
            f'<div style="color:{GREY}">CA agg bond 1M: <span style="color:{pct_color(ca_bond_1m)};'
            f'font-family:JetBrains Mono,monospace">{fmt_pct(ca_bond_1m)}</span></div>'
            f'<div style="color:{GREY}">US 7-10Y bond 1M: <span style="color:{pct_color(us_bond_1m)};'
            f'font-family:JetBrains Mono,monospace">{fmt_pct(us_bond_1m)}</span></div>'
            f'<div style="margin-top:8px;color:{GOLD};font-size:12px">{diverge}</div>'
            f'<div style="color:{GREY};font-size:11px;margin-top:4px">A wider BoC–Fed policy gap '
            f'typically pressures CAD/USD.</div></div>', unsafe_allow_html=True)

    # ── Financial conditions (FRED NFCI) ───────────────────────────────────
    fci = sig.get("financial_conditions") or {}
    nc = sig.get("macro_nowcast") or {}
    if fci.get("nfci") is not None:
        st.markdown(section_header("FINANCIAL CONDITIONS"), unsafe_allow_html=True)
        nfci = fci["nfci"]
        nfci_col = GREEN if nfci < 0 else RED          # negative NFCI = loose/calm
        ddir = fci.get("nfci_dir")
        dlabel = ("tightening" if (ddir or 0) > 0.02 else
                  "easing" if (ddir or 0) < -0.02 else "stable")
        hy, ig = fci.get("hy_oas"), fci.get("ig_oas")
        be = nc.get("breakeven_10y")
        np_, hp = fci.get("nfci_pct"), fci.get("hy_oas_pct")
        nfci_sub = f"{fci.get('label','')} · {dlabel}"
        if np_ is not None:
            nfci_sub += f" · {np_:.0f}th %ile"
        hy_sub = "credit spread" + (f" · {hp:.0f}th %ile" if hp is not None else "")
        st.markdown(
            f'<div style="display:flex;gap:12px;margin:6px 0">'
            f'{stat_card("Financial Conditions (NFCI)", fmt_num(nfci, 2), nfci_sub, nfci_col)}'
            f'{stat_card("US High-Yield OAS", (fmt_num(hy, 2) + "%") if hy is not None else "—", hy_sub, WHITE)}'
            f'{stat_card("US Inv-Grade OAS", (fmt_num(ig, 2) + "%") if ig is not None else "—", "credit spread", WHITE)}'
            f'{stat_card("10Y Breakeven", (fmt_num(be, 2) + "%") if be is not None else "—", "mkt inflation exp.", GOLD)}'
            f'</div>', unsafe_allow_html=True)
        st.caption(f"Chicago Fed National Financial Conditions Index (FRED, as of {fci.get('as_of','—')}). "
                   f"Negative = looser/calmer than average; positive = tighter/stressed.")

        # Stress decomposition: composite + subindices + components
        fs = load_financial_stress()
        if fs.get("composite") is not None:
            d1, d2 = st.columns([1, 1.4])
            comp = fs["composite"]
            comp_col = GREEN if comp < 35 else AMBER if comp < 65 else RED
            with d1:
                sub_chips = ""
                for nm, val in fs.get("subindices", {}).items():
                    if val is None:
                        continue
                    sc = RED if val > 0 else GREEN
                    sub_chips += (f'<div style="display:flex;justify-content:space-between;'
                                  f'padding:3px 0"><span style="color:{GREY};font-size:12px">{nm}</span>'
                                  f'<span style="font-family:JetBrains Mono,monospace;color:{sc}">'
                                  f'{val:+.2f}</span></div>')
                st.markdown(
                    f'<div style="background:{CARD};border:1px solid {comp_col};border-radius:8px;'
                    f'padding:14px 18px"><div style="color:{GREY};font-size:11px;text-transform:uppercase;'
                    f'letter-spacing:0.8px">Composite Stress</div>'
                    f'<div style="font-size:34px;font-weight:700;color:{comp_col};'
                    f'font-family:JetBrains Mono,monospace;line-height:1.1">{comp:.0f}'
                    f'<span style="font-size:14px;color:{GREY}">/100</span></div>'
                    f'<div style="color:{comp_col};font-size:12px;margin-bottom:8px">'
                    f'{fs.get("composite_label","")}</div>'
                    f'<div style="border-top:1px solid #1e1e1e;padding-top:6px">'
                    f'<div style="color:{GOLD};font-size:10px;text-transform:uppercase;'
                    f'letter-spacing:1px;margin-bottom:4px">NFCI subindices</div>{sub_chips}</div></div>',
                    unsafe_allow_html=True)
            with d2:
                bars = ""
                for nm, val in fs.get("components", {}).items():
                    bc = GREEN if val < 35 else AMBER if val < 65 else RED
                    bars += (
                        f'<div style="margin-bottom:8px"><div style="display:flex;'
                        f'justify-content:space-between;font-size:12px;margin-bottom:2px">'
                        f'<span style="color:{WHITE}">{nm}</span>'
                        f'<span style="color:{bc};font-family:JetBrains Mono,monospace">{val:.0f}th</span></div>'
                        f'<div style="background:#0f0f0f;border-radius:4px;height:6px">'
                        f'<div style="width:{val}%;background:{bc};height:6px;border-radius:4px"></div></div></div>')
                st.markdown(
                    f'<div style="background:{CARD};border:1px solid {BORDER};border-radius:8px;'
                    f'padding:14px 18px"><div style="color:{GOLD};font-size:11px;font-weight:600;'
                    f'text-transform:uppercase;letter-spacing:1px;margin-bottom:8px">'
                    f'Stress components (percentile vs 6y history)</div>{bars}</div>',
                    unsafe_allow_html=True)
            st.caption("Composite = average percentile of NFCI, St. Louis Fed Stress Index, high-yield "
                       "credit spreads and equity volatility. Subindices: positive = above-average risk / "
                       "tighter credit / higher leverage.")

    # ── Macro regime — real growth x inflation quadrant ────────────────────
    st.markdown(section_header("MACRO REGIME — GROWTH × INFLATION"), unsafe_allow_html=True)
    q1, q2 = st.columns([1, 1])
    with q1:
        st.markdown(regime_badge(sig["macro_regime"], sig["macro_regime_desc"]),
                    unsafe_allow_html=True)
        if sig.get("macro_source") == "FRED":
            st.markdown(_quadrant_grid(sig["macro_regime"]), unsafe_allow_html=True)
    with q2:
        if nc:
            st.markdown(_nowcast_detail(nc), unsafe_allow_html=True)
    if sig.get("macro_source") == "FRED":
        st.caption("Growth axis = Chicago Fed National Activity Index (CFNAI, 0 = trend growth) with "
                   "industrial production and jobless-claims confirmation; inflation axis = core CPI "
                   "year-over-year level and acceleration. All from FRED — point-in-time economic data, "
                   "not price proxies.")
    else:
        st.caption("FRED macro data unavailable — showing the ETF-momentum proxy regime. "
                   "Set FRED_API_KEY to enable the real growth × inflation nowcast.")


_QUAD_CELLS = [  # display order: top-left, top-right, bottom-left, bottom-right
    "GOLDILOCKS", "REFLATION", "DEFLATION RISK", "STAGFLATION",
]


def _quadrant_grid(active: str) -> str:
    cells = ""
    for label in _QUAD_CELLS:
        on = label == active
        bg = "rgba(201,162,39,0.18)" if on else "#121212"
        bd = GOLD if on else BORDER
        txt = GOLD if on else GREY
        cells += (f'<div style="border:1px solid {bd};background:{bg};border-radius:6px;'
                  f'padding:10px 8px;text-align:center;font-size:11px;font-weight:700;'
                  f'color:{txt}">{label}{"  ◀" if on else ""}</div>')
    return (f'<div style="margin-top:10px">'
            f'<div style="display:flex;justify-content:space-between;color:{GREY};'
            f'font-size:10px;margin-bottom:3px"><span>◀ inflation easing</span>'
            f'<span>inflation rising ▶</span></div>'
            f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:6px">{cells}</div>'
            f'<div style="color:{GREY};font-size:10px;margin-top:3px">top row = growth above trend</div>'
            f'</div>')


def _nowcast_detail(nc: dict) -> str:
    def row(lbl, val, col=WHITE):
        return (f'<div style="display:flex;justify-content:space-between;padding:5px 0;'
                f'border-bottom:1px solid #1e1e1e"><span style="color:{GREY};font-size:12px">{lbl}</span>'
                f'<span style="font-family:JetBrains Mono,monospace;color:{col}">{val}</span></div>')
    cfnai = nc.get("cfnai_ma3")
    g_col = GREEN if nc.get("growth_up") else RED
    core, core6 = nc.get("core_cpi_yoy"), nc.get("core_cpi_yoy_6m_ago")
    i_col = RED if nc.get("inflation_up") else GREEN
    accel = ("accelerating" if (core is not None and core6 is not None and core > core6)
             else "decelerating" if (core is not None and core6 is not None) else "—")
    body = (
        f'<div style="color:{GOLD};font-size:11px;font-weight:600;text-transform:uppercase;'
        f'letter-spacing:1px;margin-bottom:6px">Underlying data (FRED)</div>'
        + row("Growth (CFNAI 3m avg)", f"{fmt_num(cfnai,2)} ({'above' if nc.get('growth_up') else 'below'} trend)", g_col)
        + row("Industrial prod. YoY", fmt_pct(nc.get("indpro_yoy")))
        + row("Core CPI YoY", f"{fmt_num(core,2)}% ({accel})", i_col)
        + row("Headline CPI YoY", f"{fmt_num(nc.get('headline_cpi_yoy'),2)}%")
        + row("10Y breakeven", f"{fmt_num(nc.get('breakeven_10y'),2)}%")
        + row("Unemployment", f"{fmt_num(nc.get('unemployment'),1)}%")
    )
    return (f'<div style="background:{CARD};border:1px solid {BORDER};border-radius:8px;'
            f'padding:14px 18px">{body}<div style="color:{GREY};font-size:10px;margin-top:8px">'
            f'As of {nc.get("as_of","—")}</div></div>')
