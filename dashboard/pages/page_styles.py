"""Page II — STYLE & FACTOR ROTATION."""

from __future__ import annotations

import streamlit as st

from dashboard.styles import GOLD, WHITE, GREY, GREEN, RED, CARD, BORDER, section_header
from dashboard.components import (
    perf_heatmap_html, line_chart, pct_color, fmt_pct, fmt_num,
)
from dashboard.page_data import load_metrics
from data import store

PERIODS = [("return_5d", "1W"), ("return_1m", "1M"), ("return_3m", "3M"),
           ("return_6m", "6M"), ("return_1y", "1Y")]

STYLES = [("IWF", "Growth"), ("IWD", "Value"), ("MTUM", "Momentum"),
          ("QUAL", "Quality"), ("USMV", "Low Vol"), ("IWM", "Small Cap"),
          ("IWB", "Large Cap"), ("RSP", "Equal Weight")]

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

    # ── Style heatmap ──────────────────────────────────────────────────────
    st.markdown(section_header("STYLE PERFORMANCE HEATMAP"), unsafe_allow_html=True)
    st.markdown(perf_heatmap_html(_heat_rows(m, STYLES), PERIODS),
                unsafe_allow_html=True)
    st.markdown(f'<div style="color:{GREY};font-size:11px;margin-top:6px">'
                f'Green = stronger return, red = weaker, across each horizon. '
                f'The single best read on what the market is rewarding right now.</div>',
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
