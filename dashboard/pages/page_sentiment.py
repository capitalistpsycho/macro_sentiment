"""Page VI — SENTIMENT INDICATORS."""

from __future__ import annotations

import streamlit as st

from dashboard.styles import GOLD, WHITE, GREY, GREEN, RED, AMBER, CARD, BORDER, section_header
from dashboard.components import mini_gauge, line_chart, stat_card, pct_color, fmt_pct, fmt_num
from dashboard.page_data import (
    load_metrics, load_sentiment, load_put_call, load_crowding, load_iv_skew,
    load_analyst_breadth,
)
from data import store

FG_ZONES = [
    (0, 25,  "rgba(239,68,68,0.55)"),
    (25, 45, "rgba(245,158,11,0.45)"),
    (45, 55, "rgba(148,163,184,0.35)"),
    (55, 75, "rgba(16,185,129,0.40)"),
    (75, 100, "rgba(16,185,129,0.65)"),
]


def render(ctx: dict) -> None:
    m = load_metrics()
    fg = load_sentiment()

    # ── Fear & Greed gauge + components ────────────────────────────────────
    st.markdown(section_header("FEAR & GREED COMPOSITE"), unsafe_allow_html=True)
    g1, g2 = st.columns([1, 1.3])
    with g1:
        st.plotly_chart(mini_gauge(fg["score"], FG_ZONES), width='stretch',
                        config={"displayModeBar": False})
        lbl = fg["label"]
        col = (RED if fg["score"] < 25 else AMBER if fg["score"] < 45 else
               GREY if fg["score"] < 55 else GREEN)
        st.markdown(f'<div style="text-align:center;margin-top:-12px"><span style="color:{col};'
                    f'font-size:18px;font-weight:700">{lbl}</span></div>', unsafe_allow_html=True)
    with g2:
        body = ""
        for name, val in fg["components"].items():
            barcol = (RED if val < 35 else AMBER if val < 50 else GREEN if val > 65 else GREY)
            body += (
                f'<div style="margin-bottom:8px"><div style="display:flex;'
                f'justify-content:space-between;font-size:12px;margin-bottom:2px">'
                f'<span style="color:{WHITE}">{name}</span>'
                f'<span style="color:{barcol};font-family:JetBrains Mono,monospace">{val:.0f}</span></div>'
                f'<div style="background:#0f0f0f;border-radius:4px;height:6px">'
                f'<div style="width:{val}%;background:{barcol};height:6px;border-radius:4px"></div></div></div>')
        st.markdown(f'<div style="background:{CARD};border:1px solid {BORDER};border-radius:8px;'
                    f'padding:16px 20px">{body}</div>', unsafe_allow_html=True)

    st.markdown(f'<div style="color:{GREY};font-size:11px;margin-top:6px">'
                f'Six components (yfinance prices + FRED high-yield credit spreads) approximating '
                f'the CNN Fear & Greed index — VIX weighted once, junk-bond demand from real credit '
                f'data. Readings above 75 (extreme greed) or below 25 (extreme fear) are contrarian.</div>',
                unsafe_allow_html=True)

    # ── Sentiment trend (from signal history) ──────────────────────────────
    st.markdown(section_header("SENTIMENT & COMPASS TREND"), unsafe_allow_html=True)
    hist = store.signal_history("signal_scores")
    if not hist.empty and len(hist) > 1:
        fig = line_chart([{"x": hist["date"], "y": hist["compass_score"],
                           "name": "MacroCompass", "color": GOLD}], height=260,
                         showlegend=False,
                         hlines=[{"y": 75, "label": "Greed", "color": GREEN},
                                 {"y": 25, "label": "Fear", "color": RED}])
        st.plotly_chart(fig, width='stretch', config={"displayModeBar": False})
        st.caption("MacroCompass history accrues one point per daily refresh. "
                   "Extreme readings tend to mean-revert.")
    else:
        st.info("Sentiment trend builds over time — one point is recorded per daily refresh "
                "(run `python run_macro.py --full`). Showing today's reading only so far.")

    # ── Breadth + new highs/lows ───────────────────────────────────────────
    b1, b2 = st.columns(2)
    with b1:
        st.markdown(section_header("MARKET BREADTH"), unsafe_allow_html=True)
        from data import tickers as T
        basket = [t for t, _, _ in T.SECTOR_US]
        above = sum(1 for t in basket
                    if (m.get(t, {}).get("close") or 0) > (m.get(t, {}).get("ma200") or 1e9))
        pct = above / len(basket) * 100 if basket else 0
        col = GREEN if pct >= 60 else AMBER if pct >= 45 else RED
        st.markdown(
            f'<div style="background:{CARD};border:1px solid {BORDER};border-radius:8px;'
            f'padding:18px 20px;text-align:center">'
            f'<div style="font-size:42px;font-weight:700;color:{col};'
            f'font-family:JetBrains Mono,monospace">{pct:.0f}%</div>'
            f'<div style="color:{GREY};font-size:12px">US sectors above their 200-day MA '
            f'({above}/{len(basket)})</div></div>', unsafe_allow_html=True)
        st.caption("Below 50% the rally is narrow and fragile.")
    with b2:
        st.markdown(section_header("NEW HIGHS vs NEW LOWS (PROXY)"), unsafe_allow_html=True)
        from data import tickers as T
        basket = [t for t, _, _ in (T.SECTOR_US + T.EQUITY_BENCHMARKS) if t != "^VIX"]
        nh, nl = 0, 0
        for t in basket:
            s = store.series(t)
            if s.empty or len(s) < 30:
                continue
            last = s["close"].iloc[-1]
            hi52, lo52 = s["close"].max(), s["close"].min()
            if last >= hi52 * 0.98: nh += 1
            elif last <= lo52 * 1.02: nl += 1
        net = nh - nl
        col = GREEN if net > 0 else RED if net < 0 else GREY
        st.markdown(
            f'<div style="background:{CARD};border:1px solid {BORDER};border-radius:8px;'
            f'padding:18px 20px"><div style="display:flex;justify-content:space-around;text-align:center">'
            f'<div><div style="font-size:30px;font-weight:700;color:{GREEN};'
            f'font-family:JetBrains Mono,monospace">{nh}</div>'
            f'<div style="color:{GREY};font-size:11px">near 52w high</div></div>'
            f'<div><div style="font-size:30px;font-weight:700;color:{RED};'
            f'font-family:JetBrains Mono,monospace">{nl}</div>'
            f'<div style="color:{GREY};font-size:11px">near 52w low</div></div>'
            f'<div><div style="font-size:30px;font-weight:700;color:{col};'
            f'font-family:JetBrains Mono,monospace">{net:+d}</div>'
            f'<div style="color:{GREY};font-size:11px">net</div></div></div></div>',
            unsafe_allow_html=True)
        st.caption("Across sector & benchmark ETFs vs their trailing 52-week range.")

    # ── Options put/call + skew ─────────────────────────────────────────────
    st.markdown(section_header("OPTIONS POSITIONING — PUT/CALL & SKEW (SPY)"), unsafe_allow_html=True)
    pc = load_put_call("SPY")
    sk = load_iv_skew("SPY")
    if pc and (pc.get("pc_vol") is not None or pc.get("pc_oi") is not None):
        tcol = {"bullish": GREEN, "bearish": RED}.get(pc.get("tone"), GREY)
        vol = pc.get("pc_vol"); oi = pc.get("pc_oi")
        vcol = GREEN if (vol or 1) >= 1.2 else RED if (vol or 1) <= 0.7 else WHITE
        skew = sk.get("skew") if sk else None
        skcol = RED if (skew or 0) > 8 else GREEN if (skew is not None and skew < 2) else WHITE
        o1, o2, o4, o3 = st.columns([1, 1, 1, 2])
        with o1:
            st.markdown(stat_card("Put/Call · Volume", fmt_num(vol, 2), "today's flow", vcol),
                        unsafe_allow_html=True)
        with o2:
            st.markdown(stat_card("Put/Call · Open Int.", fmt_num(oi, 2), "standing positioning", WHITE),
                        unsafe_allow_html=True)
        with o4:
            skew_sub = (sk.get("tone", "") if sk else "unavailable")
            st.markdown(stat_card("IV Skew (5% OTM)", (f"{skew:+.1f}" if skew is not None else "—"),
                                  skew_sub, skcol), unsafe_allow_html=True)
        with o3:
            st.markdown(
                f'<div style="background:{CARD};border:1px solid {tcol};border-radius:8px;'
                f'padding:14px 18px;height:100%"><div style="color:{tcol};font-size:13px;'
                f'font-weight:600">{pc.get("read","")}</div>'
                f'<div style="color:{GREY};font-size:11px;margin-top:6px">Aggregated across the '
                f'nearest {len(pc.get("expiries",[]))} SPY expiries. A high ratio = heavy put buying '
                f'(fear); extremes are contrarian.</div></div>', unsafe_allow_html=True)
    else:
        st.info("Live options data unavailable right now (yfinance) — check back during market hours.")

    # ── Analyst-sentiment breadth ──────────────────────────────────────────
    ab = load_analyst_breadth()
    if ab.get("net_bull_pct") is not None:
        st.markdown(section_header("ANALYST-SENTIMENT BREADTH (LARGE-CAP BASKET)"),
                    unsafe_allow_html=True)
        nb = ab["net_bull_pct"]
        nbcol = GREEN if nb > 40 else AMBER if nb > 15 else RED
        up = ab.get("avg_upside")
        st.markdown(
            f'<div style="display:flex;gap:12px;margin:6px 0">'
            f'{stat_card("Net Bullish Ratings", f"{nb:+.0f}%", ab.get("label",""), nbcol)}'
            f'{stat_card("Buy Share", f"{ab.get("bull_share",0):.0f}%", "of all ratings", WHITE)}'
            f'{stat_card("Avg Price-Target Upside", (f"{up:+.0f}%" if up is not None else "—"), "consensus target vs price", GREEN if (up or 0) > 0 else RED)}'
            f'</div>', unsafe_allow_html=True)
        st.caption(f"Sell-side rating distribution and price-target upside across {ab.get('n_names',0)} "
                   f"US/Canadian large caps (FMP). Rising net-bullish + target upside is a supportive "
                   f"backdrop; a rolling-over reading often leads price. Analyst sentiment, not EPS revisions.")

    # ── Crowding composite ─────────────────────────────────────────────────
    cw = load_crowding()
    if cw.get("score") is not None:
        st.markdown(section_header("CROWDING / POSITIONING COMPOSITE"), unsafe_allow_html=True)
        cscore = cw["score"]
        ccol = RED if cscore >= 70 else AMBER if cscore >= 55 else GREEN
        k1, k2 = st.columns([1, 1.4])
        with k1:
            st.markdown(
                f'<div style="background:{CARD};border:1px solid {ccol};border-radius:8px;'
                f'padding:16px 20px;text-align:center"><div style="font-size:44px;font-weight:700;'
                f'color:{ccol};font-family:JetBrains Mono,monospace;line-height:1.1">{cscore:.0f}'
                f'<span style="font-size:15px;color:{GREY}">/100</span></div>'
                f'<div style="color:{ccol};font-size:12px;margin-top:4px">{cw.get("label","")}</div></div>',
                unsafe_allow_html=True)
        with k2:
            bars = ""
            for nm, val in cw.get("components", {}).items():
                bc = RED if val >= 70 else AMBER if val >= 55 else GREEN
                bars += (f'<div style="margin-bottom:8px"><div style="display:flex;'
                         f'justify-content:space-between;font-size:12px;margin-bottom:2px">'
                         f'<span style="color:{WHITE}">{nm}</span>'
                         f'<span style="color:{bc};font-family:JetBrains Mono,monospace">{val:.0f}</span></div>'
                         f'<div style="background:#0f0f0f;border-radius:4px;height:6px">'
                         f'<div style="width:{val}%;background:{bc};height:6px;border-radius:4px"></div></div></div>')
            st.markdown(f'<div style="background:{CARD};border:1px solid {BORDER};border-radius:8px;'
                        f'padding:14px 18px">{bars}</div>', unsafe_allow_html=True)
        st.caption("Crowding proxies (0-100, higher = more crowded): mega-cap concentration (RSP/SPY), "
                   "momentum-factor crowding, volatility complacency and extreme CFTC positioning. "
                   "Crowding builds slowly and unwinds all at once — high readings raise tail/unwind risk.")

    # ── Speculative positioning (CFTC COT) ─────────────────────────────────
    st.markdown(section_header("SPECULATIVE POSITIONING — CFTC COMMITMENT OF TRADERS"),
                unsafe_allow_html=True)
    try:
        from data.positioning import positioning_summary
        pos = positioning_summary()
    except Exception:
        pos = []
    if pos:
        head = ("<tr><th>Market</th><th style='text-align:right'>Spec Net</th>"
                "<th style='text-align:right'>&Delta; 1wk</th><th style='text-align:right'>3y %ile</th>"
                "<th>Read</th></tr>")
        body = ""
        for r in pos:
            p = r["percentile"]
            pcol = RED if (p or 50) >= 85 else GREEN if (p or 50) <= 15 else WHITE
            tcol = {"bullish": GREEN, "bearish": RED}.get(r["tone"], GREY)
            net_str = f"{r['net']:+,.0f}"
            wk = r["week_change"]
            wk_str = f"{wk:+,.0f}" if wk is not None else "—"
            p_str = f"{p:.0f}" if p is not None else "—"
            body += (
                f'<tr><td style="font-weight:600">{r["label"]}'
                f'<span style="color:{GREY};font-size:11px"> · {r["group"]}</span></td>'
                f'<td style="text-align:right" class="mono">{net_str}</td>'
                f'<td style="text-align:right;color:{pct_color(wk)}" class="mono">{wk_str}</td>'
                f'<td style="text-align:right;color:{pcol}" class="mono">{p_str}</td>'
                f'<td style="color:{tcol};font-size:12px">{r["read"]}</td></tr>')
        rd = pos[0]["report_date"]
        st.markdown(f'<table class="data-grid" style="width:100%"><thead>{head}</thead>'
                    f'<tbody>{body}</tbody></table>', unsafe_allow_html=True)
        st.caption(f"Net = speculative long − short contracts; percentile vs ~3-year history "
                   f"(CFTC weekly report, as of {rd}). Above the 85th percentile = crowded long "
                   f"(contrarian caution); below the 15th = crowded short (contrarian support).")
    else:
        st.info("Positioning data unavailable — run `python run_macro.py --full` to fetch the "
                "latest CFTC Commitment of Traders report.")
