"""Page II — STYLE & FACTOR ROTATION."""

from __future__ import annotations

import streamlit as st

from dashboard.styles import GOLD, WHITE, GREY, GREEN, RED, CARD, BORDER, BG, section_header
from dashboard.components import (
    perf_heatmap_html, line_chart, pct_color, fmt_pct, fmt_num,
)
from dashboard.page_data import (
    load_metrics, load_signals, load_regime_performance, load_regime_risk,
)
from data import store, backtest as bt

PERIODS = [("return_5d", "1W"), ("return_1m", "1M"), ("return_3m", "3M"),
           ("return_6m", "6M"), ("return_1y", "1Y"), ("return_ytd", "YTD")]

# Split so the visual read is clean: true factors vs market-cap / size buckets.
FACTOR_STYLES = [("IWF", "Growth"), ("IWD", "Value"), ("MTUM", "Momentum"),
                 ("QUAL", "Quality"), ("USMV", "Low Vol")]

MARKET_CAP = [("IWM", "Small Cap"), ("IWB", "Large Cap"),
              ("SPY", "S&P 500 (Cap Wt)"), ("RSP", "Equal Weight")]

# Combined list still drives the "current style read" recommendation box.
STYLES = FACTOR_STYLES + MARKET_CAP

FACTORS = [("MTUM", "Momentum"), ("USMV", "Low Volatility"), ("QUAL", "Quality"),
           ("IWF", "Growth"), ("IWD", "Value"), ("IWM", "Small Cap")]


def _heat_rows(m, items):
    rows = []
    for tk, name in items:
        r = m.get(tk, {})
        row = {"name": name}
        for key, _ in PERIODS:
            row[key] = r.get(key)
        rows.append(row)
    return rows


def _rolling_rel(num, den, window=63):
    """Rolling `window`-day relative return of num minus den, as %."""
    w = store.closes([num, den]).dropna()
    if w.empty:
        return None
    rn = w[num] / w[num].shift(window) - 1
    rd = w[den] / w[den].shift(window) - 1
    return ((rn - rd) * 100).dropna()


def render(ctx: dict) -> None:
    m = load_metrics()

    # ── Factor/style heatmap ───────────────────────────────────────────────
    st.markdown(section_header("FACTOR / STYLE PERFORMANCE HEATMAP"), unsafe_allow_html=True)
    st.markdown(perf_heatmap_html(_heat_rows(m, FACTOR_STYLES), PERIODS),
                unsafe_allow_html=True)
    st.markdown(f'<div style="color:{GREY};font-size:11px;margin-top:6px">'
                f'Green = stronger return, red = weaker, across each horizon. '
                f'What the market is rewarding at the factor level.</div>',
                unsafe_allow_html=True)

    # ── Market-cap / size heatmap ──────────────────────────────────────────
    st.markdown(section_header("MARKET-CAP / SIZE PERFORMANCE HEATMAP"), unsafe_allow_html=True)
    st.markdown(perf_heatmap_html(_heat_rows(m, MARKET_CAP), PERIODS),
                unsafe_allow_html=True)
    st.markdown(f'<div style="color:{GREY};font-size:11px;margin-top:6px">'
                f'Size leadership: small vs large, and cap-weighted (SPY) vs '
                f'equal-weight (RSP) as a breadth tell.</div>',
                unsafe_allow_html=True)

    # ── Growth vs Value ────────────────────────────────────────────────────
    st.markdown(section_header("GROWTH vs VALUE — ROLLING 3M RELATIVE"), unsafe_allow_html=True)
    gv = _rolling_rel("IWF", "IWD", 63)
    if gv is not None and not gv.empty:
        fig = line_chart([{"x": gv.index, "y": gv.values, "name": "Growth − Value (3m)",
                           "color": GOLD}], height=300,
                         hlines=[{"y": 0, "label": "Value leads ↓ / Growth leads ↑", "color": GREY}])
        st.plotly_chart(fig, width='stretch', config={"displayModeBar": False})
        last = gv.iloc[-1]
        lead = "Growth" if last > 0 else "Value"
        st.markdown(f'<div style="color:{GREY};font-size:12px">Currently '
                    f'<b style="color:{GOLD}">{lead}</b> leading by '
                    f'<span style="color:{pct_color(last)}">{fmt_pct(abs(last))}</span> over 3 months.</div>',
                    unsafe_allow_html=True)
    else:
        st.info("Growth/Value series unavailable.")

    # ── Factor momentum table ──────────────────────────────────────────────
    st.markdown(section_header("FACTOR MOMENTUM"), unsafe_allow_html=True)
    head = ("<tr><th>Factor</th><th style='text-align:right'>Price</th>"
            "<th style='text-align:right'>1M</th><th style='text-align:right'>3M</th>"
            "<th style='text-align:right'>6M</th><th style='text-align:right'>RSI</th>"
            "<th style='text-align:center'>Trend</th></tr>")
    body = ""
    for tk, name in FACTORS:
        r = m.get(tk, {})
        rsi = r.get("rsi14")
        rsi_c = RED if (rsi or 50) > 70 else (GREEN if (rsi or 50) < 30 else WHITE)
        above = (r.get("close") or 0) > (r.get("ma50") or 1e9)
        trend = (f'<span style="color:{GREEN}">▲ above 50d</span>' if above
                 else f'<span style="color:{RED}">▼ below 50d</span>')
        body += (
            f'<tr><td style="font-weight:600">{name} '
            f'<span style="color:{GREY};font-size:11px">{tk}</span></td>'
            f'<td style="text-align:right" class="mono">{fmt_num(r.get("close"))}</td>'
            f'<td style="text-align:right;color:{pct_color(r.get("return_1m"))}" class="mono">{fmt_pct(r.get("return_1m"))}</td>'
            f'<td style="text-align:right;color:{pct_color(r.get("return_3m"))}" class="mono">{fmt_pct(r.get("return_3m"))}</td>'
            f'<td style="text-align:right;color:{pct_color(r.get("return_6m"))}" class="mono">{fmt_pct(r.get("return_6m"))}</td>'
            f'<td style="text-align:right;color:{rsi_c}" class="mono">{fmt_num(rsi, 0)}</td>'
            f'<td style="text-align:center">{trend}</td></tr>')
    st.markdown(f'<table class="data-grid" style="width:100%"><thead>{head}</thead>'
                f'<tbody>{body}</tbody></table>', unsafe_allow_html=True)

    # ── Ratio charts ───────────────────────────────────────────────────────
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(section_header("SMALL vs LARGE — IWM / SPY"), unsafe_allow_html=True)
        rr = store.ratio("IWM", "SPY", days=252).dropna()
        if not rr.empty:
            fig = line_chart([{"x": rr.index, "y": rr.values, "name": "IWM/SPY", "color": GREEN}],
                             height=260, showlegend=False)
            st.plotly_chart(fig, width='stretch', config={"displayModeBar": False})
            st.caption("Rising = small caps leading (early cycle). Falling = large caps dominate (defensive/late).")
    with c2:
        st.markdown(section_header("BREADTH — RSP / SPY"), unsafe_allow_html=True)
        rr2 = store.ratio("RSP", "SPY", days=252).dropna()
        if not rr2.empty:
            fig = line_chart([{"x": rr2.index, "y": rr2.values, "name": "RSP/SPY", "color": GOLD}],
                             height=260, showlegend=False)
            st.plotly_chart(fig, width='stretch', config={"displayModeBar": False})
            st.caption("Rising = broad participation (healthy). Falling = narrow mega-cap leadership (warning).")

    # ── Recommendation box ─────────────────────────────────────────────────
    best, best_v = None, -1e9
    for tk, name in STYLES:
        v = m.get(tk, {}).get("return_1m")
        if v is not None and v > best_v:
            best, best_v = name, v
    gv_last = gv.iloc[-1] if (gv is not None and not gv.empty) else None
    iwm_spy = store.ratio("IWM", "SPY", days=21).dropna()
    breadth_note = ""
    if len(iwm_spy) > 5:
        breadth_note = ("small caps firming" if iwm_spy.iloc[-1] > iwm_spy.iloc[0]
                        else "large caps leading")
    evidence = []
    if best is not None:
        evidence.append(f"{best} strongest over 1M ({fmt_pct(best_v)})")
    if gv_last is not None:
        evidence.append(f"Growth−Value 3m at {fmt_pct(gv_last)}")
    if breadth_note:
        evidence.append(breadth_note)
    st.markdown(
        f'<div style="background:{CARD};border:1px solid {GOLD};border-radius:8px;'
        f'padding:16px 20px;margin-top:14px">'
        f'<div style="color:{GOLD};font-size:11px;font-weight:600;text-transform:uppercase;'
        f'letter-spacing:1px;margin-bottom:6px">Current Style Read</div>'
        f'<div style="font-size:15px;color:{WHITE}">Market currently favouring: '
        f'<b style="color:{GOLD}">{best or "—"}</b></div>'
        f'<div style="color:{GREY};font-size:12px;margin-top:6px">Supporting evidence: '
        f'{" · ".join(evidence) if evidence else "data not available"}.</div></div>',
        unsafe_allow_html=True)

    # ── Regime playbook — how styles/regions have performed by macro regime ──
    _regime_playbook()

    # ── Regime risk profile — tail/shape of forward returns by regime ───────
    _regime_risk_profile()


def _regime_risk_profile() -> None:
    sig = load_signals()
    current = sig.get("macro_regime")
    rr = load_regime_risk(21)
    if not rr or not rr.get("_order"):
        return
    st.markdown(section_header("REGIME RISK PROFILE — S&P FORWARD-RETURN SHAPE (1M)"),
                unsafe_allow_html=True)
    head = ("<tr><th>Regime</th><th style='text-align:right'>Mean</th>"
            "<th style='text-align:right'>Vol</th><th style='text-align:right'>CVaR 5%</th>"
            "<th style='text-align:right'>Worst</th><th style='text-align:right'>Skew</th>"
            "<th style='text-align:right'>Hit</th><th style='text-align:right'>n</th></tr>")
    body = ""
    for reg in rr["_order"]:
        d = rr[reg]
        if d.get("mean") is None:
            continue
        hot = reg == current
        name = f'<b style="color:{GOLD}">▸ {reg}</b>' if hot else f'<span style="color:{WHITE}">{reg}</span>'
        rowbg = "background:rgba(201,162,39,0.10)" if hot else ""
        sk = d.get("skew")
        skcol = RED if (sk or 0) < -0.3 else GREEN if (sk or 0) > 0.3 else GREY
        body += (
            f'<tr style="{rowbg}"><td>{name}</td>'
            f'<td style="text-align:right;color:{pct_color(d["mean"])}" class="mono">{fmt_pct(d["mean"])}</td>'
            f'<td style="text-align:right" class="mono">{fmt_num(d["vol"],1)}</td>'
            f'<td style="text-align:right;color:{RED}" class="mono">{fmt_pct(d["cvar5"])}</td>'
            f'<td style="text-align:right;color:{RED}" class="mono">{fmt_pct(d["worst"])}</td>'
            f'<td style="text-align:right;color:{skcol}" class="mono">{fmt_num(sk,2)}</td>'
            f'<td style="text-align:right" class="mono">{fmt_num(d["hit"],0)}%</td>'
            f'<td style="text-align:right;color:{GREY}" class="mono">{d["n"]}</td></tr>')
    st.markdown(f'<table class="data-grid" style="width:100%"><thead>{head}</thead>'
                f'<tbody>{body}</tbody></table>', unsafe_allow_html=True)
    st.caption("Distribution shape of S&P forward 1-month returns conditional on each regime — not just "
               "the average. CVaR 5% = mean of the worst 5% of outcomes; negative skew = fat left tail. "
               "Two regimes with the same mean can carry very different downside.")


def _excess_color(x: float | None) -> str:
    """Diverging shade for excess-return cells (green outperform / red underperform)."""
    if x is None:
        return "#141414"
    v = max(-3.0, min(3.0, x)) / 3.0  # scale ±3pp to full intensity
    if v >= 0:
        return f"rgba(34,197,94,{0.12 + 0.45 * v:.2f})"
    return f"rgba(239,68,68,{0.12 + 0.45 * abs(v):.2f})"


def _regime_playbook() -> None:
    st.markdown(section_header("REGIME PLAYBOOK — PERFORMANCE BY MACRO REGIME"),
                unsafe_allow_html=True)
    sig = load_signals()
    current = sig.get("macro_regime")
    c1, c2 = st.columns([1.3, 1])
    with c1:
        universe = st.radio("Universe", ["Styles / Factors", "Regions"],
                            horizontal=True, key="rp_uni", label_visibility="collapsed")
    with c2:
        hlabel = st.radio("Horizon", ["1M", "3M"], horizontal=True, key="rp_h",
                          label_visibility="collapsed")
    horizon = 21 if hlabel == "1M" else 63
    data = load_regime_performance(universe, horizon)
    if not data or not data.get("_order"):
        st.info("Not enough regime history yet to build the playbook.")
        return

    regimes = data["_order"]
    days = data.get("_days", {})
    labels = [lbl for _, lbl in bt.REGIME_UNIVERSES[universe]]

    # Header row: one column per regime, current regime highlighted.
    head = '<tr><th style="text-align:left">Instrument</th>'
    for reg in regimes:
        hot = reg == current
        bd = GOLD if hot else BORDER
        tag = ' ◀ now' if hot else ''
        head += (f'<th style="text-align:center;border-bottom:2px solid {bd};'
                 f'color:{GOLD if hot else GREY};font-size:10px;min-width:96px">'
                 f'{reg}{tag}<br><span style="color:#555;font-weight:400">n={days.get(reg,0)}d</span></th>')
    head += '</tr>'

    body = ""
    for lbl in labels:
        body += f'<tr><td style="font-weight:600;white-space:nowrap">{lbl}</td>'
        for reg in regimes:
            d = data[reg].get(lbl, {})
            ex, mean, hit = d.get("excess"), d.get("mean"), d.get("hit")
            bg = _excess_color(ex)
            border = f"2px solid {GOLD}" if reg == current else f"1px solid {BG}"
            ex_txt = "—" if ex is None else f"{ex:+.1f}"
            sub = "" if mean is None else f'<span style="color:{GREY};font-size:9px">{fmt_pct(mean)} · {hit:.0f}% up</span>'
            body += (f'<td style="text-align:center;background:{bg};border:{border};'
                     f'padding:5px 4px"><span class="mono" style="color:{WHITE};font-size:12px">'
                     f'{ex_txt}</span><br>{sub}</td>')
        body += '</tr>'

    st.markdown(f'<table class="data-grid" style="width:100%"><thead>{head}</thead>'
                f'<tbody>{body}</tbody></table>', unsafe_allow_html=True)
    hist = store.signal_history("macro_signals")
    since = hist["date"].min().date() if not hist.empty else "—"
    st.caption(f"Cells = average excess {hlabel} forward return vs SPY when the macro regime was "
               f"active (small text = absolute return · % of windows positive). Green = outperformed, "
               f"red = lagged. Gold column = today's regime ({current or '—'}). History since {since}. "
               f"Forward windows overlap → read as descriptive tendencies, not an iid backtest.")
