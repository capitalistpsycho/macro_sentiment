"""Page V — MACRO & FIXED INCOME."""

from __future__ import annotations

import streamlit as st

from dashboard.styles import GOLD, WHITE, GREY, GREEN, RED, AMBER, CARD, BORDER, section_header
from dashboard.components import (
    line_chart, regime_badge, stat_card, pct_color, fmt_pct, fmt_num,
)
from dashboard.page_data import (
    load_metrics, load_signals, load_calendar, load_financial_stress,
    load_treasury_curve, load_rates_extras, load_boc, load_regime_probs, load_gs_fci,
    load_correlation, load_regime_transitions, load_allocation, load_rate_paths,
    load_ensemble,
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

    # ── Full US Treasury curve + slopes (FMP) ──────────────────────────────
    _treasury_curve_section()

    # ── Real yields & inflation expectations, funding (FRED) ───────────────
    _rates_conditions_section()

    # ── Credit curve by rating (FRED) ──────────────────────────────────────
    _credit_curve_section()

    # ── Canada — BoC, GoC curve, CAD ───────────────────────────────────────
    _canada_section(m)

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

        # GDP-weighted (GS-style) FCI — a daily, market-based complement to NFCI.
        gsf = load_gs_fci()
        if gsf.get("composite") is not None:
            comp = gsf["composite"]
            gcol = RED if comp > 0.1 else GREEN if comp < -0.1 else AMBER
            parts = " · ".join(f"{k} {v:+.2f}" for k, v in gsf.get("contributions", {}).items())
            st.markdown(
                f'<div style="display:flex;gap:12px;margin:4px 0">'
                f'{stat_card("GDP-weighted FCI (GS-style)", f"{comp:+.2f}", gsf.get("tone", ""), gcol)}'
                f'{stat_card("Implied growth impulse", f"{gsf.get("growth_impulse"):+.2f}", "≈ pp growth over 1y", gcol)}'
                f'</div>', unsafe_allow_html=True)
            st.caption(f"Daily market-based FCI: z-scored short rate, 10Y real yield, HY credit, equity "
                       f"trend and broad USD, weighted by growth contribution (positive = tighter). "
                       f"Contributions: {parts}.")

        # Cross-asset correlation regime.
        cr = load_correlation()
        if cr.get("avg_pairwise") is not None:
            sb = cr.get("stock_bond")
            sbcol = RED if (sb or 0) > 0.1 else GREEN
            acol = RED if cr.get("rising") else GREY
            st.markdown(
                f'<div style="display:flex;gap:12px;margin:4px 0">'
                f'{stat_card("Stock–Bond Correlation", fmt_num(sb, 2), "bonds hedging equities?" , sbcol)}'
                f'{stat_card("Avg Cross-Asset Corr", fmt_num(cr.get("avg_pairwise"), 2), f"prior {fmt_num(cr.get("avg_prior"),2)}", acol)}'
                f'</div>', unsafe_allow_html=True)
            st.caption(cr.get("read", ""))

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
            st.markdown(_conviction_box(sig, nc), unsafe_allow_html=True)
            st.markdown(_regime_prob_bars(), unsafe_allow_html=True)
            st.markdown(_quadrant_grid(sig["macro_regime"]), unsafe_allow_html=True)
    with q2:
        if nc:
            st.markdown(_nowcast_detail(nc), unsafe_allow_html=True)
        st.markdown(_ensemble_box(), unsafe_allow_html=True)
    if sig.get("macro_source") == "FRED":
        st.caption("Growth axis = Chicago Fed National Activity Index (CFNAI, 0 = trend growth) with "
                   "industrial production and jobless-claims confirmation; inflation axis = core CPI "
                   "year-over-year level and acceleration. All from FRED — point-in-time economic data, "
                   "not price proxies.")
    else:
        st.caption("FRED macro data unavailable — showing the ETF-momentum proxy regime. "
                   "Set FRED_API_KEY to enable the real growth × inflation nowcast.")

    # ── Regime → positioning (transitions, All-Weather tilts, vol target) ───
    if sig.get("macro_source") == "FRED":
        _regime_positioning_section()


def _ensemble_box() -> str:
    e = load_ensemble()
    if not e.get("consensus"):
        return ""
    col = GREEN if e.get("unanimous") else AMBER
    def chip(lbl, reg):
        return (f'<div style="display:flex;justify-content:space-between;padding:3px 0;'
                f'border-bottom:1px solid #1e1e1e"><span style="color:{GREY};font-size:12px">{lbl}</span>'
                f'<span style="color:{WHITE};font-size:12px">{_REGIME_SHORT.get(reg, reg or "—")}</span></div>')
    status = ("all three models agree" if e.get("unanimous")
              else f'{e.get("agreement")} agree — models split')
    return (
        f'<div style="background:{CARD};border:1px solid {col};border-radius:8px;padding:12px 16px;'
        f'margin-top:10px"><div style="display:flex;justify-content:space-between;align-items:baseline;'
        f'margin-bottom:6px"><span style="color:{GOLD};font-size:10px;font-weight:600;'
        f'text-transform:uppercase;letter-spacing:1px">Regime ensemble</span>'
        f'<span style="color:{col};font-size:11px">{status}</span></div>'
        f'{chip("FRED nowcast", e.get("fred"))}{chip("ETF-momentum proxy", e.get("proxy"))}'
        f'{chip("Probability model", e.get("model"))}'
        f'<div style="margin-top:6px;color:{GOLD};font-size:12px">Consensus: '
        f'<b>{_REGIME_SHORT.get(e.get("consensus"), e.get("consensus"))}</b></div></div>')


def _regime_positioning_section() -> None:
    tr = load_regime_transitions()
    al = load_allocation()
    if not tr and not al.get("tilts"):
        return
    st.markdown(section_header("REGIME → POSITIONING"), unsafe_allow_html=True)
    p1, p2 = st.columns([1, 1.2])
    with p1:
        if tr:
            nxt = tr.get("next_period", {})
            order = sorted(nxt.items(), key=lambda kv: kv[1], reverse=True)
            bars = ""
            for reg, p in order:
                col = GOLD if reg == tr.get("current") else GREY
                bars += (f'<div style="margin-bottom:6px"><div style="display:flex;'
                         f'justify-content:space-between;font-size:11px;margin-bottom:2px">'
                         f'<span style="color:{WHITE}">{_REGIME_SHORT.get(reg, reg)}</span>'
                         f'<span style="font-family:JetBrains Mono,monospace;color:{col}">{p:.0f}%</span></div>'
                         f'<div style="background:#0f0f0f;border-radius:4px;height:6px">'
                         f'<div style="width:{p}%;background:{col};height:6px;border-radius:4px"></div></div></div>')
            st.markdown(
                f'<div style="background:{CARD};border:1px solid {BORDER};border-radius:8px;padding:12px 16px">'
                f'<div style="color:{GOLD};font-size:10px;font-weight:600;text-transform:uppercase;'
                f'letter-spacing:1px;margin-bottom:2px">Where the regime goes next (~1 month)</div>'
                f'<div style="color:{GREY};font-size:11px;margin-bottom:8px">'
                f'{tr.get("change_prob",0):.0f}% chance of a regime change · expected duration '
                f'~{tr.get("expected_duration_days","?")} trading days</div>{bars}</div>',
                unsafe_allow_html=True)
        vt = al.get("vol") or {}
        if vt.get("exposure") is not None:
            ec = GREEN if vt["exposure"] > 1.05 else RED if vt["exposure"] < 0.95 else WHITE
            st.markdown(
                f'<div style="background:{CARD};border:1px solid {BORDER};border-radius:8px;'
                f'padding:12px 16px;margin-top:10px"><div style="display:flex;justify-content:space-between;'
                f'align-items:baseline"><span style="color:{GOLD};font-size:10px;font-weight:600;'
                f'text-transform:uppercase;letter-spacing:1px">Vol-target exposure</span>'
                f'<span style="font-family:JetBrains Mono,monospace;color:{ec};font-size:20px">'
                f'{vt["exposure"]:.2f}×</span></div>'
                f'<div style="color:{GREY};font-size:11px;margin-top:4px">Realised vol {vt["current_vol"]:.0f}% '
                f'vs {vt["target_vol"]:.0f}% target — {vt.get("read","")}.</div></div>',
                unsafe_allow_html=True)
    with p2:
        tilts = (al.get("tilts") or {}).get("tilts", {})
        if tilts:
            rows = ""
            for asset, tv in tilts.items():
                pct = abs(tv) / 2 * 50  # half-width, ±2 = full
                col = GREEN if tv > 0.1 else RED if tv < -0.1 else GREY
                side = "left:50%" if tv >= 0 else "right:50%"
                rows += (
                    f'<div style="margin-bottom:7px"><div style="display:flex;justify-content:space-between;'
                    f'font-size:12px;margin-bottom:2px"><span style="color:{WHITE}">{asset}</span>'
                    f'<span style="font-family:JetBrains Mono,monospace;color:{col}">{tv:+.1f}</span></div>'
                    f'<div style="position:relative;background:#0f0f0f;border-radius:4px;height:8px">'
                    f'<div style="position:absolute;left:50%;top:0;bottom:0;width:1px;background:{BORDER}"></div>'
                    f'<div style="position:absolute;{side};top:0;height:8px;width:{pct}%;background:{col};'
                    f'border-radius:4px"></div></div></div>')
            st.markdown(
                f'<div style="background:{CARD};border:1px solid {GOLD};border-radius:8px;padding:12px 16px">'
                f'<div style="color:{GOLD};font-size:10px;font-weight:600;text-transform:uppercase;'
                f'letter-spacing:1px;margin-bottom:8px">All-Weather tilts (probability-blended)</div>'
                f'{rows}</div>', unsafe_allow_html=True)
    st.caption("Positioning read, not advice: forward regime distribution from the estimated Markov "
               "transition matrix; asset-class tilts are the All-Weather environment map blended by the "
               "live regime probabilities (−2 strong underweight … +2 strong overweight); vol-target "
               "scales gross exposure toward a ~12% risk budget.")


def _slope_tile(label: str, val, good_positive=True) -> str:
    if val is None:
        col, txt = GREY, "—"
    else:
        col = (GREEN if val > 0 else RED) if good_positive else (RED if val < 0 else GREEN)
        txt = f"{val:+.2f}"
    return (f'<div style="flex:1;background:{CARD};border:1px solid {BORDER};border-radius:8px;'
            f'padding:10px 12px;text-align:center"><div style="color:{GREY};font-size:10px;'
            f'text-transform:uppercase;letter-spacing:0.6px">{label}</div>'
            f'<div style="font-family:JetBrains Mono,monospace;font-size:20px;color:{col}">{txt}</div></div>')


def _treasury_curve_section() -> None:
    curve, an = load_treasury_curve()
    if not curve:
        return
    st.markdown(section_header("US TREASURY CURVE — FULL TERM STRUCTURE (FMP)"), unsafe_allow_html=True)
    c1, c2 = st.columns([1.5, 1])
    with c1:
        xs = [p["tenor"] for p in curve]
        ys = [p["yield"] for p in curve]
        fig = line_chart([{"x": xs, "y": ys, "name": "UST yield", "color": GOLD}], height=280,
                         showlegend=False)
        fig.update_traces(mode="lines+markers")
        st.plotly_chart(fig, width='stretch', config={"displayModeBar": False})
        st.caption("Full daily Treasury curve across 12 tenors (1M→30Y). Shape reads growth/policy "
                   "expectations; a humped/kinked front end flags near-term policy tension.")
    with c2:
        st.markdown(f'<div style="display:flex;flex-direction:column;gap:8px">'
                    f'{_slope_tile("2s10s", an.get("2s10s"))}'
                    f'{_slope_tile("3M–10Y", an.get("3m10y"))}'
                    f'{_slope_tile("5s30s", an.get("5s30s"))}'
                    f'{_slope_tile("Curvature (2·5Y−2Y−10Y)", an.get("curvature"), good_positive=False)}'
                    f'</div>', unsafe_allow_html=True)
        st.caption("Positive slopes = normal/steepening (risk-on, growth). Curvature > 0 = belly "
                   "cheap (policy-tightening pricing).")
    rp = load_rate_paths()
    fed = rp.get("fed") or {}
    gdp = rp.get("gdpnow")
    if fed.get("policy") is not None:
        st.markdown(
            f'<div style="display:flex;gap:12px;margin:6px 0">'
            f'{stat_card("Fed Funds (effective)", _pct(fed.get("policy")), "current policy", WHITE)}'
            f'{stat_card("1Y Treasury", _pct(fed.get("y1")), "≈ avg rate next 12m", GOLD)}'
            f'{stat_card("Market rate path", (f"{fed.get("spread_1y_bp"):+d} bp" if fed.get("spread_1y_bp") is not None else "—"), "1Y vs policy", pct_color(-(fed.get("spread_1y_bp") or 0)))}'
            f'{stat_card("GDPNow", (_pct(gdp) if gdp is not None else "—"), f"Atlanta Fed · {rp.get("gdpnow_asof","—")}", GREEN if (gdp or 0) > 1 else AMBER)}'
            f'</div>', unsafe_allow_html=True)
        st.caption(f"Rate path is curve-implied (Treasuries embed a term premium, so this is a bias, "
                   f"not an OIS-precise cut count): {fed.get('read','')}. GDPNow = the Atlanta Fed's "
                   f"real-time GDP nowcast.")


def _rates_conditions_section() -> None:
    ex = load_rates_extras()
    inf, fund = ex["inflation"], ex["funding"]
    move = load_metrics().get("^MOVE", {}).get("close")
    st.markdown(section_header("REAL YIELDS · INFLATION EXPECTATIONS · FUNDING"), unsafe_allow_html=True)
    ry10 = inf.get("real_yield_10y")
    ry_chg = inf.get("real_yield_10y_1m_chg")
    ry_sub = ("rising — growth headwind" if (ry_chg or 0) > 0.05 else
              "falling — supports gold/growth" if (ry_chg or 0) < -0.05 else "flat")
    tiles = "".join([
        stat_card("10Y Real Yield (TIPS)", _pct(ry10), ry_sub, RED if (ry_chg or 0) > 0 else GREEN),
        stat_card("5Y Breakeven", _pct(inf.get("breakeven_5y")), "market inflation exp.", GOLD),
        stat_card("10Y Breakeven", _pct(inf.get("breakeven_10y")), "market inflation exp.", GOLD),
        stat_card("5y5y Forward", _pct(inf.get("forward_5y5y")), "long-run inflation anchor", GOLD),
    ])
    st.markdown(f'<div style="display:flex;gap:12px;margin:6px 0">{tiles}</div>', unsafe_allow_html=True)
    move_col = RED if (move or 0) > 120 else AMBER if (move or 0) > 100 else GREEN
    tiles2 = "".join([
        stat_card("30-Day SOFR", _pct(fund.get("sofr_30d")), "secured funding rate", WHITE),
        stat_card("MOVE Index", fmt_num(move, 1) if move else "—", "rates volatility (bond VIX)", move_col),
        stat_card("Broad USD", fmt_num(fund.get("usd_broad"), 1), f"1M {fmt_pct(fund.get('usd_broad_1m_chg'))}",
                  pct_color(-(fund.get("usd_broad_1m_chg") or 0))),
    ])
    st.markdown(f'<div style="display:flex;gap:12px;margin:6px 0">{tiles2}</div>', unsafe_allow_html=True)
    st.caption("Real yields (nominal − TIPS) are the true driver behind gold and long-duration growth. "
               "5y5y forward is the market's long-run inflation anchor. MOVE = the bond market's VIX; "
               "rising MOVE + widening credit is the classic stress combination.")


def _credit_curve_section() -> None:
    cc = load_rates_extras()["credit"]
    rows = cc.get("curve") or []
    if not rows:
        return
    st.markdown(section_header("CREDIT CURVE — OAS BY RATING (FRED / ICE BofA)"), unsafe_allow_html=True)
    head = ("<tr><th>Rating</th><th style='text-align:right'>OAS (%)</th>"
            "<th style='text-align:right'>Δ 1M</th><th style='text-align:right'>Percentile (6y)</th>"
            "<th>Positioning</th></tr>")
    body = ""
    for r in rows:
        p = r.get("pct")
        pcol = RED if (p or 50) >= 80 else GREEN if (p or 50) <= 20 else WHITE
        read = ("wide — cheap/stressed" if (p or 50) >= 80 else
                "tight — rich/complacent" if (p or 50) <= 20 else "mid-range")
        body += (f'<tr><td style="font-weight:600">{r["rating"]}</td>'
                 f'<td style="text-align:right" class="mono">{fmt_num(r["oas"],2)}</td>'
                 f'<td style="text-align:right;color:{pct_color(-(r.get("chg_1m") or 0))}" class="mono">{r.get("chg_1m"):+.2f}</td>'
                 f'<td style="text-align:right;color:{pcol}" class="mono">{fmt_num(p,0)}th</td>'
                 f'<td style="color:{pcol};font-size:12px">{read}</td></tr>')
    st.markdown(f'<table class="data-grid" style="width:100%"><thead>{head}</thead>'
                f'<tbody>{body}</tbody></table>', unsafe_allow_html=True)
    st.caption("Spread widening lowest-quality first (CCC) is the early tell of credit-cycle turns. "
               "Percentile vs 6-year history: high = spreads wide/cheap, low = tight/complacent.")


def _canada_section(m: dict) -> None:
    b = load_boc()
    if b.get("policy_rate") is None and b.get("usdcad") is None:
        return
    st.markdown(section_header("CANADA — BoC, GoC CURVE & CAD"), unsafe_allow_html=True)
    spread = b.get("goc_ust_10y_spread")
    cad_read = ("GoC yields below US — a structural CAD headwind" if (spread or 0) < 0
                else "GoC yields above US — CAD-supportive")
    tiles = "".join([
        stat_card("BoC Policy Rate", _pct(b.get("policy_rate")), "target overnight", WHITE),
        stat_card("GoC 2s10s", fmt_num(b.get("goc_2s10s"), 2), "curve slope",
                  GREEN if (b.get("goc_2s10s") or 0) > 0 else RED),
        stat_card("GoC−UST 10Y", fmt_num(spread, 2), "rate differential",
                  GREEN if (spread or 0) > 0 else RED),
        stat_card("USD/CAD", fmt_num(b.get("usdcad"), 4),
                  f"1M {fmt_num(b.get('usdcad_1m_chg'), 3)}", WHITE),
    ])
    st.markdown(f'<div style="display:flex;gap:12px;margin:6px 0">{tiles}</div>', unsafe_allow_html=True)
    bp = (load_rate_paths().get("boc") or {})
    boc_read = f" BoC path: {bp.get('read','')}." if bp.get("read") and bp.get("read") != "—" else ""
    st.caption(f"Government-of-Canada curve (2/5/10Y), CORRA {fmt_num(b.get('corra'),2)}%, and CAD from "
               f"the Bank of Canada. {cad_read}.{boc_read} The BoC–Fed rate gap is the dominant CAD "
               f"driver (as of {b.get('as_of','—')}).")


def _pct(v) -> str:
    return (fmt_num(v, 2) + "%") if v is not None else "—"


_REGIME_SHORT = {"GOLDILOCKS": "Goldilocks", "REFLATION": "Reflation",
                 "STAGFLATION": "Stagflation", "DEFLATION RISK": "Deflation"}


def _regime_prob_bars() -> str:
    rp = load_regime_probs()
    probs = rp.get("probabilities")
    if not probs:
        return ""
    order = sorted(probs.items(), key=lambda kv: kv[1], reverse=True)
    bars = ""
    for reg, p in order:
        col = GOLD if p == order[0][1] else GREY
        bars += (
            f'<div style="margin-bottom:6px"><div style="display:flex;justify-content:space-between;'
            f'font-size:11px;margin-bottom:2px"><span style="color:{WHITE}">{_REGIME_SHORT.get(reg, reg)}</span>'
            f'<span style="font-family:JetBrains Mono,monospace;color:{col}">{p:.0f}%</span></div>'
            f'<div style="background:#0f0f0f;border-radius:4px;height:6px">'
            f'<div style="width:{p}%;background:{col};height:6px;border-radius:4px"></div></div></div>')
    return (
        f'<div style="background:{CARD};border:1px solid {BORDER};border-radius:8px;'
        f'padding:12px 16px;margin-top:10px">'
        f'<div style="color:{GOLD};font-size:10px;font-weight:600;text-transform:uppercase;'
        f'letter-spacing:1px;margin-bottom:6px">Regime probabilities '
        f'<span style="color:{GREY};font-weight:400;text-transform:none">'
        f'(Gaussian-Bayes + persistence, n={rp.get("n_train","?")})</span></div>{bars}</div>')


def _axis_bar(label: str, score: float | None, pos_word: str, neg_word: str) -> str:
    """Bipolar -1..+1 axis bar centred at zero."""
    s = 0.0 if score is None else max(-1.0, min(1.0, score))
    pct = abs(s) * 50  # half-width
    col = GREEN if s > 0 else RED if s < 0 else GREY
    side = "left:50%" if s >= 0 else f"right:50%"
    val = "—" if score is None else f"{score:+.2f}"
    return (
        f'<div style="margin:6px 0"><div style="display:flex;justify-content:space-between;'
        f'font-size:11px;margin-bottom:2px"><span style="color:{GREY}">{label}</span>'
        f'<span style="font-family:JetBrains Mono,monospace;color:{col}">{val}</span></div>'
        f'<div style="position:relative;background:#0f0f0f;border-radius:4px;height:8px">'
        f'<div style="position:absolute;left:50%;top:0;bottom:0;width:1px;background:{BORDER}"></div>'
        f'<div style="position:absolute;{side};top:0;height:8px;width:{pct}%;background:{col};'
        f'border-radius:4px"></div></div>'
        f'<div style="display:flex;justify-content:space-between;color:#555;font-size:9px;'
        f'margin-top:1px"><span>{neg_word}</span><span>{pos_word}</span></div></div>')


def _conviction_box(sig: dict, nc: dict) -> str:
    conv = sig.get("macro_conviction")
    conv_lbl = sig.get("macro_conviction_label") or "—"
    sec = sig.get("macro_regime_secondary")
    pivot = nc.get("pivot_axis", "")
    conv_col = GREEN if (conv or 0) >= 66 else AMBER if (conv or 0) >= 33 else RED
    bar_w = 0 if conv is None else conv
    g = _axis_bar("Growth", nc.get("growth_score"), "above trend", "below trend")
    i = _axis_bar("Inflation", nc.get("inflation_score"), "rising", "easing")
    # Secondary call — surface prominently when the pivotal axis is near its line.
    sec_html = ""
    if sec and sec != sig.get("macro_regime") and (conv or 100) < 66:
        sec_html = (
            f'<div style="margin-top:8px;padding-top:8px;border-top:1px solid #1e1e1e;'
            f'font-size:11px;color:{GREY}">Borderline on the <b style="color:{AMBER}">{pivot}</b> '
            f'axis — if it turns, regime flips to '
            f'<b style="color:{AMBER}">{sec}</b>.</div>')
    return (
        f'<div style="background:{CARD};border:1px solid {BORDER};border-radius:8px;'
        f'padding:12px 16px;margin-top:10px">'
        f'<div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:4px">'
        f'<span style="color:{GOLD};font-size:10px;font-weight:600;text-transform:uppercase;'
        f'letter-spacing:1px">Conviction</span>'
        f'<span style="font-family:JetBrains Mono,monospace;color:{conv_col};font-size:13px">'
        f'{"—" if conv is None else f"{conv:.0f}/100"} · {conv_lbl}</span></div>'
        f'<div style="background:#0f0f0f;border-radius:4px;height:6px;margin-bottom:4px">'
        f'<div style="width:{bar_w}%;background:{conv_col};height:6px;border-radius:4px"></div></div>'
        f'{g}{i}{sec_html}</div>')


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
