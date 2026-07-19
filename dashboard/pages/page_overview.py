"""Page I — OVERVIEW: the market cover page."""

from __future__ import annotations

import streamlit as st

from dashboard.styles import (
    GOLD, WHITE, GREY, GREEN, RED, AMBER, CARD, BORDER, section_header,
)
from dashboard.components import (
    risk_gauge, regime_badge, stat_card, pct_color, fmt_pct, fmt_num, trend_arrow,
)
from dashboard.polaris import render_polaris_bar
from dashboard.page_data import (
    load_metrics, load_signals, load_context_percentiles, load_backtest,
    load_narrative, load_analogues, load_valuation, load_track_record,
)


def _level(m, tk):
    return m.get(tk, {}).get("close")


def _quadrant_equities(m) -> str:
    rows = ""
    for tk, name in (("^GSPTSE", "S&P/TSX"), ("^GSPC", "S&P 500")):
        r = m.get(tk, {})
        px, d1, d1m = r.get("close"), r.get("return_1d"), r.get("return_1m")
        rows += (
            f'<div style="display:flex;justify-content:space-between;align-items:center;'
            f'padding:6px 0;border-bottom:1px solid #1e1e1e">'
            f'<span style="color:{WHITE};font-weight:600">{name}</span>'
            f'<span style="font-family:JetBrains Mono,monospace">'
            f'<span style="color:{WHITE}">{fmt_num(px, 0) if px else "—"}</span> '
            f'<span style="color:{pct_color(d1)}">{fmt_pct(d1)}</span> '
            f'{trend_arrow(d1m)}</span></div>')
    return rows


def _quadrant_macro(sig) -> str:
    s = sig["summary"]
    spread = s.get("yield_curve_spread")
    if spread is None: curve = "—"
    elif spread < 0:   curve = f'<span style="color:{RED}">Inverted ({spread:+.2f})</span>'
    elif spread < 0.5: curve = f'<span style="color:{AMBER}">Flat ({spread:+.2f})</span>'
    else:              curve = f'<span style="color:{GREEN}">Normal ({spread:+.2f})</span>'
    vix = s.get("vix_level")
    vix_c = GREEN if (vix or 99) < 18 else (AMBER if (vix or 99) < 25 else RED)
    credit = s.get("credit_spread_proxy")
    credit_txt = ("Tightening" if (credit or 0) > 0 else "Widening") if credit is not None else "—"
    credit_c = GREEN if (credit or 0) > 0 else RED
    def row(lbl, val):
        return (f'<div style="display:flex;justify-content:space-between;padding:6px 0;'
                f'border-bottom:1px solid #1e1e1e"><span style="color:{GREY}">{lbl}</span>'
                f'<span style="font-family:JetBrains Mono,monospace">{val}</span></div>')
    return (row("Yield curve", curve)
            + row("VIX", f'<span style="color:{vix_c}">{fmt_num(vix, 1)}</span>')
            + row("Credit", f'<span style="color:{credit_c}">{credit_txt}</span>'))


STYLE_MAP = [("IWF", "Growth"), ("IWD", "Value"), ("MTUM", "Momentum"),
             ("USMV", "Low Vol"), ("QUAL", "Quality")]


def _quadrant_style(m) -> str:
    best, best_v = None, -1e9
    for tk, name in STYLE_MAP:
        v = m.get(tk, {}).get("return_1m")
        if v is not None and v > best_v:
            best, best_v = name, v
    leader = f'<span style="color:{GOLD};font-weight:700;font-size:18px">{best or "—"}</span>'
    body = (f'<div style="padding:4px 0 10px 0">Leading style (1m)<br>{leader} '
            f'<span style="color:{pct_color(best_v)};font-family:JetBrains Mono,monospace">'
            f'{fmt_pct(best_v) if best is not None else ""}</span></div>')
    for tk, name in STYLE_MAP:
        v = m.get(tk, {}).get("return_1m")
        body += (f'<div style="display:flex;justify-content:space-between;font-size:12px;'
                 f'padding:3px 0"><span style="color:{GREY}">{name}</span>'
                 f'<span style="color:{pct_color(v)};font-family:JetBrains Mono,monospace">'
                 f'{fmt_pct(v)}</span></div>')
    return body


def _quadrant_commodities(m) -> str:
    rows = ""
    for tk, name in (("CL=F", "WTI Oil"), ("GC=F", "Gold"), ("HG=F", "Copper")):
        r = m.get(tk, {})
        px, d1m = r.get("close"), r.get("return_1m")
        rows += (f'<div style="display:flex;justify-content:space-between;padding:6px 0;'
                 f'border-bottom:1px solid #1e1e1e"><span style="color:{WHITE};font-weight:600">{name}</span>'
                 f'<span style="font-family:JetBrains Mono,monospace">'
                 f'<span style="color:{WHITE}">${fmt_num(px, 2) if px else "—"}</span> '
                 f'<span style="color:{pct_color(d1m)}">{fmt_pct(d1m)}</span> {trend_arrow(d1m)}</span></div>')
    return rows


def _quad_card(title, inner) -> str:
    return (f'<div style="background:{CARD};border:1px solid {BORDER};border-radius:8px;'
            f'padding:16px 20px;height:100%">'
            f'<div style="font-size:12px;color:{GOLD};font-weight:600;text-transform:uppercase;'
            f'letter-spacing:1px;margin-bottom:10px">{title}</div>{inner}</div>')


def _ticker_tape(m) -> str:
    items = []
    tape = [("^GSPTSE", "TSX"), ("^GSPC", "S&P500"), ("^IXIC", "NASDAQ"),
            ("^RUT", "RUSSELL"), ("^VIX", "VIX"), ("CL=F", "OIL"),
            ("GC=F", "GOLD"), ("HG=F", "COPPER"), ("CADUSD=X", "CADUSD"),
            ("^TNX", "US10Y")]
    for tk, lbl in tape:
        r = m.get(tk, {})
        px, d = r.get("close"), r.get("return_1d")
        if px is None:
            continue
        col = pct_color(d)
        items.append(
            f'<span style="margin-right:26px;font-family:JetBrains Mono,monospace;font-size:12px">'
            f'<b style="color:{GOLD}">{lbl}</b> '
            f'<span style="color:{WHITE}">{fmt_num(px, 2)}</span> '
            f'<span style="color:{col}">{fmt_pct(d)}</span></span>')
    inner = "".join(items)
    return (
        '<div style="overflow:hidden;white-space:nowrap;border:1px solid #1e1e1e;'
        'border-radius:8px;background:#0f0f0f;padding:8px 0;margin:8px 0">'
        '<div style="display:inline-block;animation:tape 38s linear infinite;padding-left:100%">'
        f'{inner}</div></div>'
        '<style>@keyframes tape{0%{transform:translateX(0)}100%{transform:translateX(-100%)}}</style>')


def render(ctx: dict) -> None:
    m = load_metrics()
    sig = load_signals()
    pctx = load_context_percentiles()

    # ── Polaris ask bar ────────────────────────────────────────────────────
    render_polaris_bar(ctx or {})

    # ── Risk gauge + drivers + regime ──────────────────────────────────────
    st.markdown(section_header("MARKET CONDITIONS"), unsafe_allow_html=True)
    g1, g2 = st.columns([1, 1.3])
    with g1:
        st.plotly_chart(risk_gauge(sig["risk_score"]), width='stretch',
                        config={"displayModeBar": False})
        rp = pctx.get("risk_pct")
        rp_txt = (f' · {rp:.0f}th %ile of past year' if rp is not None else '')
        st.markdown(f'<div style="text-align:center;color:{GREY};font-size:12px;margin-top:-12px">'
                    f'Risk-On / Risk-Off composite{rp_txt}</div>', unsafe_allow_html=True)
    with g2:
        st.markdown(regime_badge(sig["regime"], sig["regime_desc"]), unsafe_allow_html=True)
        drivers = sig.get("risk_drivers", [])
        bullets = "".join(f'<li style="margin-bottom:4px;color:{WHITE}">{d}</li>' for d in drivers)
        st.markdown(
            f'<div style="background:{CARD};border:1px solid {BORDER};border-radius:8px;'
            f'padding:12px 18px;margin-top:8px"><div style="color:{GOLD};font-size:11px;'
            f'font-weight:600;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px">'
            f'Biggest drivers</div><ul style="margin:0;padding-left:18px;font-size:13px;'
            f'line-height:1.5">{bullets}</ul></div>', unsafe_allow_html=True)

    # MacroCompass score chip row
    summ = sig["summary"]
    cs = sig["compass_score"]
    cs_col = GREEN if cs >= 60 else (AMBER if cs >= 40 else RED)
    breadth_txt = fmt_pct(summ.get("breadth"), 0).replace("+", "")
    cp = pctx.get("compass_pct")
    compass_sub = sig["macro_regime"]
    if cp is not None:
        compass_sub = f'{sig["macro_regime"]} · {cp:.0f}th %ile'
    bp = pctx.get("breadth_pct")
    breadth_sub = "ETFs above 200d MA" + (f' · {bp:.0f}th %ile' if bp is not None else "")
    vp = pctx.get("vix_pct")
    vix_sub = f'20d avg {fmt_num(summ.get("vix_20d_avg"), 1)}'
    if vp is not None:
        vix_sub += f' · {vp:.0f}th %ile'
    regime_sub = (sig["macro_regime_desc"][:42] + "…") if sig["macro_regime_desc"] else ""
    st.markdown(
        f'<div style="display:flex;gap:12px;margin:14px 0">'
        f'{stat_card("MacroCompass Score", f"{cs:.0f}/100", compass_sub, cs_col)}'
        f'{stat_card("Market Breadth", breadth_txt, breadth_sub, WHITE)}'
        f'{stat_card("VIX", fmt_num(summ.get("vix_level"), 1), vix_sub, WHITE)}'
        f'{stat_card("Macro Regime", sig["macro_regime"], regime_sub, GOLD)}'
        f'</div>', unsafe_allow_html=True)

    # ── Auto macro brief ───────────────────────────────────────────────────
    brief = load_narrative()
    if brief:
        st.markdown(
            f'<div style="background:{CARD};border:1px solid {GOLD};border-radius:8px;'
            f'padding:14px 20px;margin:6px 0 14px 0"><div style="color:{GOLD};font-size:11px;'
            f'font-weight:600;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px">'
            f'The read</div><div style="color:{WHITE};font-size:14px;line-height:1.7">{brief}</div></div>',
            unsafe_allow_html=True)

    # ── 2x2 quadrants ──────────────────────────────────────────────────────
    st.markdown(section_header("MARKET DASHBOARD"), unsafe_allow_html=True)
    r1c1, r1c2 = st.columns(2)
    with r1c1:
        st.markdown(_quad_card("Equities", _quadrant_equities(m)), unsafe_allow_html=True)
    with r1c2:
        st.markdown(_quad_card("Macro", _quadrant_macro(sig)), unsafe_allow_html=True)
    r2c1, r2c2 = st.columns(2)
    with r2c1:
        st.markdown(_quad_card("Style", _quadrant_style(m)), unsafe_allow_html=True)
    with r2c2:
        st.markdown(_quad_card("Commodities", _quadrant_commodities(m)), unsafe_allow_html=True)

    # ── Regime playbook (historical forward returns) ───────────────────────
    bt = load_backtest("regime")
    if bt and bt.get("_order"):
        st.markdown(section_header("REGIME PLAYBOOK — HISTORICAL FORWARD RETURNS"),
                    unsafe_allow_html=True)
        st.markdown(_backtest_table(bt, sig["regime"]), unsafe_allow_html=True)
        st.caption("Average forward return and hit rate (% positive) of each index following days "
                   "in each market regime, from the dashboard's signal history. Current regime "
                   "highlighted. Overlapping daily windows — descriptive context, not an iid backtest.")

    # ── Signal track record (self-grading) ─────────────────────────────────
    tr = load_track_record()
    rows_tr = {k: v for k, v in tr.items() if not k.startswith("_")}
    if rows_tr:
        st.markdown(section_header("SIGNAL TRACK RECORD — DO OUR SIGNALS PREDICT RETURNS?"),
                    unsafe_allow_html=True)
        head = ("<tr><th>Signal</th><th style='text-align:right'>Info Coef.</th>"
                "<th style='text-align:right'>High-reading fwd</th>"
                "<th style='text-align:right'>Low-reading fwd</th>"
                "<th style='text-align:right'>Spread</th><th style='text-align:right'>n</th></tr>")
        body = ""
        for name, v in rows_tr.items():
            ic = v["ic"]
            iccol = GREEN if ic > 0.1 else RED if ic < -0.1 else GREY
            spcol = GREEN if v["spread"] > 0 else RED
            body += (f'<tr><td style="font-weight:600">{name}</td>'
                     f'<td style="text-align:right;color:{iccol}" class="mono">{ic:+.2f}</td>'
                     f'<td style="text-align:right;color:{pct_color(v["high_mean"])}" class="mono">{fmt_pct(v["high_mean"])} <span style="color:{GREY};font-size:10px">{v["high_hit"]:.0f}%</span></td>'
                     f'<td style="text-align:right;color:{pct_color(v["low_mean"])}" class="mono">{fmt_pct(v["low_mean"])} <span style="color:{GREY};font-size:10px">{v["low_hit"]:.0f}%</span></td>'
                     f'<td style="text-align:right;color:{spcol}" class="mono">{fmt_pct(v["spread"])}</td>'
                     f'<td style="text-align:right;color:{GREY}" class="mono">{v["n"]}</td></tr>')
        st.markdown(f'<table class="data-grid" style="width:100%"><thead>{head}</thead>'
                    f'<tbody>{body}</tbody></table>', unsafe_allow_html=True)
        st.caption(f"Information coefficient = rank correlation of each signal with the S&P's next "
                   f"{tr.get('_horizon',21)}-day return; 'High/Low-reading fwd' = average forward return "
                   f"(+ hit rate) after top- vs bottom-tercile readings. Point-in-time, but a ~15-month "
                   f"overlapping-window sample — read as an honest self-check, not a verdict. A negative "
                   f"IC means the signal has been contrarian over this window.")

    # ── Historical analogues ───────────────────────────────────────────────
    an = load_analogues()
    if an.get("analogues"):
        st.markdown(section_header("HISTORICAL ANALOGUES — WHEN DID NOW LOOK LIKE THIS?"),
                    unsafe_allow_html=True)
        head = ("<tr><th>Analogue date</th><th style='text-align:right'>Similarity</th>"
                "<th>Regime then</th><th style='text-align:right'>S&P next month</th></tr>")
        body = ""
        for a in an["analogues"]:
            fwd = a.get("spy_fwd")
            body += (f'<tr><td class="mono" style="color:{GOLD}">{a["date"]}</td>'
                     f'<td style="text-align:right" class="mono">{a.get("similarity",0):.0f}%</td>'
                     f'<td style="color:{WHITE}">{a.get("regime","—")}</td>'
                     f'<td style="text-align:right;color:{pct_color(fwd)}" class="mono">{fmt_pct(fwd)}</td></tr>')
        st.markdown(f'<table class="data-grid" style="width:100%"><thead>{head}</thead>'
                    f'<tbody>{body}</tbody></table>', unsafe_allow_html=True)
        avg = an.get("avg_fwd")
        st.caption(f"Nearest neighbours to today's standardized macro state (growth/inflation scores, "
                   f"risk, breadth, VIX, curve, credit) over the signal history, excluding the last "
                   f"quarter. Similar states saw the S&P {fmt_pct(avg)} on average over the next month "
                   f"— an analogue read, not a forecast.")

    # ── Strategic valuation (long-run expected return) ─────────────────────
    val = load_valuation()
    if val.get("exp_annual_return") is not None:
        pa = val["pct_from_trend"]
        pcol = RED if pa > 15 else GREEN if pa < -15 else AMBER
        er = val["exp_annual_return"]
        ercol = GREEN if er >= 7 else AMBER if er >= 4 else RED
        st.markdown(section_header("STRATEGIC VALUATION — LONG-RUN EXPECTED RETURN"),
                    unsafe_allow_html=True)
        st.markdown(
            f'<div style="display:flex;gap:12px;margin:6px 0">'
            f'{stat_card("S&P vs 16y Trend", f"{pa:+.1f}%", val.get("read",""), pcol)}'
            f'{stat_card(f"Implied {val.get("horizon_years",5)}y Annual Return", f"{er:+.1f}%", "valuation mean-reversion", ercol)}'
            f'</div>', unsafe_allow_html=True)
        st.caption("Grantham/GMO-style mean-reversion: log-linear trend on ~16 years of the S&P, today's "
                   "deviation mapped to the forward annualized return via its own history. A strategic "
                   "anchor beneath the tactical regime call — not a market-timing signal.")

    # ── Ticker tape ────────────────────────────────────────────────────────
    st.markdown(_ticker_tape(m), unsafe_allow_html=True)

    # ── PM journal — auditable regime log ──────────────────────────────────
    _render_journal(sig)


def _render_journal(sig: dict) -> None:
    from data.db import add_journal_note, journal_notes
    st.markdown(section_header("PM JOURNAL — REGIME LOG"), unsafe_allow_html=True)
    c1, c2 = st.columns([4, 1])
    with c1:
        note = st.text_input("journal", key="journal_note",
                             placeholder=f"Log a view or rationale (tagged {sig['date']} · {sig['regime']})…",
                             label_visibility="collapsed")
    with c2:
        save = st.button("Save note", width='stretch')
    if save and note.strip():
        add_journal_note(sig["date"], sig["regime"], note.strip())
        st.rerun()
    notes = journal_notes(12)
    if notes:
        rows = ""
        for n in notes:
            ts = (n.get("ts") or "")[:16].replace("T", " ")
            auto = n["note"].startswith("Auto:")
            ncol = AMBER if auto else WHITE
            rows += (
                f'<div style="padding:8px 0;border-bottom:1px solid #1e1e1e">'
                f'<span style="color:{GOLD};font-family:JetBrains Mono,monospace;font-size:11px">'
                f'{n.get("date","")}</span> '
                f'<span style="background:#1a1a1a;color:{GREY};font-size:10px;padding:1px 6px;'
                f'border-radius:8px;margin-left:6px">{n.get("regime","")}</span>'
                f'<div style="color:{ncol};font-size:13px;margin-top:3px">{n["note"]}</div>'
                f'<div style="color:#555;font-size:10px">{ts}</div></div>')
        st.markdown(f'<div style="background:{CARD};border:1px solid {BORDER};border-radius:8px;'
                    f'padding:6px 16px">{rows}</div>', unsafe_allow_html=True)
    else:
        st.caption("No journal entries yet. Notes are timestamped and tagged with the prevailing "
                   "regime; regime changes are logged automatically.")


def _bt_cell(d: dict) -> str:
    mean, hit, n = d.get("mean"), d.get("hit"), d.get("n")
    if mean is None:
        return f'<span style="color:{GREY}">n/a</span>'
    col = GREEN if mean >= 0 else RED
    return (f'<span style="color:{col}">{mean:+.1f}%</span>'
            f'<span style="color:{GREY};font-size:11px"> {hit:.0f}%</span>')


def _backtest_table(bt: dict, current: str) -> str:
    head = ("<tr><th>Regime</th><th style='text-align:right'>Days</th>"
            "<th style='text-align:right'>SPY 1M</th><th style='text-align:right'>SPY 3M</th>"
            "<th style='text-align:right'>TSX 1M</th><th style='text-align:right'>TSX 3M</th></tr>")
    body = ""
    for rg in bt["_order"]:
        cur = rg == current
        spy, tsx = bt[rg]["S&P 500"], bt[rg]["S&P/TSX"]
        name = (f'<b style="color:{GOLD}">▸ {rg}</b>' if cur else
                f'<span style="color:{WHITE}">{rg}</span>')
        rowbg = "background:rgba(201,162,39,0.10)" if cur else ""
        body += (
            f'<tr style="{rowbg}"><td>{name}</td>'
            f'<td style="text-align:right;color:{GREY}" class="mono">{bt["_days"][rg]}</td>'
            f'<td style="text-align:right" class="mono">{_bt_cell(spy["1M"])}</td>'
            f'<td style="text-align:right" class="mono">{_bt_cell(spy["3M"])}</td>'
            f'<td style="text-align:right" class="mono">{_bt_cell(tsx["1M"])}</td>'
            f'<td style="text-align:right" class="mono">{_bt_cell(tsx["3M"])}</td></tr>')
    return (f'<table class="data-grid" style="width:100%"><thead>{head}</thead>'
            f'<tbody>{body}</tbody></table>'
            f'<div style="color:{GREY};font-size:10px;margin-top:4px">'
            f'Each cell: average forward return · hit rate.</div>')
