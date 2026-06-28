"""
Reusable Macro Compass UI components: gauges, heatmaps, trend arrows, regime
badges and a footer — all on the shared Taynton Bay design system.
"""

from __future__ import annotations

import plotly.graph_objects as go

from dashboard.styles import (
    BG, CARD, GOLD, WHITE, GREEN, RED, AMBER, GREY, BORDER, apply_theme,
)


# ── Colour helpers ────────────────────────────────────────────────────────────

def pct_color(v) -> str:
    if v is None or v != v:
        return GREY
    return GREEN if v >= 0 else RED


def heat_color(v, lo: float = -8, hi: float = 8) -> str:
    """Diverging red→neutral→green background for a percentage value."""
    if v is None or v != v:
        return "#161616"
    x = max(-1.0, min(1.0, (v - 0) / (hi if v >= 0 else -lo)))
    if x >= 0:
        # green scale
        g = (16, 185, 129)
        a = 0.15 + 0.55 * x
        return f"rgba({g[0]},{g[1]},{g[2]},{a:.2f})"
    r = (239, 68, 68)
    a = 0.15 + 0.55 * abs(x)
    return f"rgba({r[0]},{r[1]},{r[2]},{a:.2f})"


def fmt_pct(v, dp: int = 1) -> str:
    if v is None or v != v:
        return "—"
    return f"{v:+.{dp}f}%"


def fmt_num(v, dp: int = 2) -> str:
    if v is None or v != v:
        return "—"
    return f"{v:,.{dp}f}"


def trend_arrow(v) -> str:
    if v is None or v != v:
        return f'<span style="color:{GREY}">→</span>'
    if v > 0.25:
        return f'<span style="color:{GREEN}">▲</span>'
    if v < -0.25:
        return f'<span style="color:{RED}">▼</span>'
    return f'<span style="color:{GREY}">→</span>'


# ── Gauges ────────────────────────────────────────────────────────────────────

def risk_gauge(score: float, title: str = "RISK-ON / RISK-OFF") -> go.Figure:
    """0-100 dial: red (0-30), amber (30-60), green (60-100)."""
    if score is None or score != score:
        score = 50.0
    if score < 30:   number_color = RED
    elif score < 60: number_color = AMBER
    else:            number_color = GREEN

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        number={"font": {"color": number_color, "size": 46,
                         "family": "JetBrains Mono, monospace"}, "suffix": ""},
        gauge={
            "axis": {"range": [0, 100], "tickcolor": GREY,
                     "tickfont": {"color": GREY, "size": 10}},
            "bar": {"color": "rgba(0,0,0,0)"},
            "borderwidth": 0,
            "steps": [
                {"range": [0, 30],  "color": "rgba(239,68,68,0.55)"},
                {"range": [30, 60], "color": "rgba(245,158,11,0.50)"},
                {"range": [60, 100], "color": "rgba(16,185,129,0.55)"},
            ],
            "threshold": {"line": {"color": WHITE, "width": 4},
                          "thickness": 0.85, "value": score},
        },
        domain={"x": [0, 1], "y": [0, 1]},
    ))
    fig.update_layout(
        paper_bgcolor=CARD, height=240, margin=dict(l=20, r=20, t=10, b=10),
        font=dict(color=WHITE),
    )
    return fig


def mini_gauge(score: float, zones: list[tuple], height: int = 230) -> go.Figure:
    """Generic 0-100 dial with custom (lo,hi,color) zones (Fear & Greed)."""
    if score is None or score != score:
        score = 50.0
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        number={"font": {"color": WHITE, "size": 42,
                         "family": "JetBrains Mono, monospace"}},
        gauge={
            "axis": {"range": [0, 100], "tickcolor": GREY,
                     "tickfont": {"color": GREY, "size": 10}},
            "bar": {"color": "rgba(0,0,0,0)"},
            "borderwidth": 0,
            "steps": [{"range": [lo, hi], "color": col} for lo, hi, col in zones],
            "threshold": {"line": {"color": WHITE, "width": 4},
                          "thickness": 0.85, "value": score},
        },
    ))
    fig.update_layout(paper_bgcolor=CARD, height=height,
                      margin=dict(l=20, r=20, t=10, b=10), font=dict(color=WHITE))
    return fig


# ── Heatmap table (styles / sectors / regions) ────────────────────────────────

def perf_heatmap_html(rows: list[dict], periods: list[tuple], name_key: str = "name",
                      lo: float = -8, hi: float = 8) -> str:
    """
    rows: list of {name_key: str, <period_key>: float, ...}
    periods: list of (period_key, header_label)
    """
    head = "".join(f"<th style='text-align:right'>{lbl}</th>" for _, lbl in periods)
    body = ""
    for r in rows:
        cells = ""
        for key, _ in periods:
            v = r.get(key)
            bg = heat_color(v, lo, hi)
            txt = fmt_pct(v)
            cells += (f"<td style='text-align:right;background:{bg};"
                      f"font-family:JetBrains Mono,monospace;font-size:12px'>{txt}</td>")
        body += (f"<tr><td style='font-weight:600'>{r.get(name_key,'')}</td>{cells}</tr>")
    return (f"<table class='data-grid' style='width:100%'>"
            f"<thead><tr><th>Name</th>{head}</tr></thead><tbody>{body}</tbody></table>")


# ── Themed line chart ─────────────────────────────────────────────────────────

def line_chart(traces: list[dict], height: int = 320, hlines: list[dict] | None = None,
               shade: list[dict] | None = None, **layout) -> go.Figure:
    """traces: list of {x, y, name, color, dash}. hlines: {y,label,color}."""
    fig = go.Figure()
    for t in traces:
        fig.add_trace(go.Scatter(
            x=t["x"], y=t["y"], name=t.get("name", ""),
            mode="lines", line=dict(color=t.get("color", GOLD), width=t.get("width", 2),
                                    dash=t.get("dash")),
            fill=t.get("fill"), fillcolor=t.get("fillcolor"),
        ))
    for s in (shade or []):
        fig.add_hrect(y0=s["y0"], y1=s["y1"], fillcolor=s.get("color", "rgba(239,68,68,0.12)"),
                      line_width=0, layer="below")
    for h in (hlines or []):
        fig.add_hline(y=h["y"], line_dash="dot", line_color=h.get("color", GREY),
                      annotation_text=h.get("label", ""), annotation_position="right",
                      annotation_font_color=h.get("color", GREY))
    apply_theme(fig, height=height, showlegend=layout.pop("showlegend", True), **layout)
    return fig


# ── Regime / status badges ────────────────────────────────────────────────────

REGIME_COLORS = {
    "RISK-ON BULL":     GREEN,
    "RECOVERY":         GREEN,
    "LATE CYCLE":       AMBER,
    "RISK-OFF":         RED,
    "RECESSION SIGNAL": RED,
    "GOLDILOCKS":       GREEN,
    "REFLATION":        AMBER,
    "STAGFLATION":      RED,
    "DEFLATION RISK":   "#60a5fa",
}


def regime_badge(label: str, desc: str = "") -> str:
    color = REGIME_COLORS.get(label, GREY)
    return (
        f'<div style="background:{CARD};border:1px solid {color};border-left:5px solid {color};'
        f'border-radius:8px;padding:16px 20px;margin:6px 0">'
        f'<div style="font-size:22px;font-weight:700;color:{color};'
        f'font-family:Inter,sans-serif;letter-spacing:0.5px">{label}</div>'
        f'<div style="color:{GREY};font-size:13px;margin-top:6px;line-height:1.5">{desc}</div>'
        f'</div>'
    )


def stat_card(label: str, value: str, sub: str = "", color: str = WHITE) -> str:
    sub_html = f'<div style="font-size:12px;color:{GREY};margin-top:4px">{sub}</div>' if sub else ""
    return (
        f'<div style="background:{CARD};border:1px solid {BORDER};border-radius:8px;'
        f'padding:14px 18px;height:100%">'
        f'<div style="font-size:11px;color:{GREY};text-transform:uppercase;'
        f'letter-spacing:0.8px;margin-bottom:6px">{label}</div>'
        f'<div style="font-size:22px;font-weight:600;color:{color};'
        f'font-family:JetBrains Mono,monospace;line-height:1.2">{value}</div>'
        f'{sub_html}</div>'
    )


def footer(as_of: str | None) -> str:
    stamp = as_of or "—"
    return (
        f'<div style="text-align:center;color:#555;font-size:11px;'
        f'padding:14px 0 4px 0;border-top:1px solid #1e1e1e;margin-top:28px">'
        f'Taynton Bay Capital &nbsp;|&nbsp; Macro Compass &nbsp;|&nbsp; '
        f'Data via yfinance &nbsp;|&nbsp; As of {stamp} ET</div>'
    )
