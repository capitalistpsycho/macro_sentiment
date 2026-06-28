"""
Taynton Bay Capital design system for the Streamlit dashboard.

Colours:
  Background  #0A0A0A   Card     #1A1A1A
  Gold        #C9A227   White    #FFFFFF
  Green       #10b981   Red      #ef4444
  Amber       #f59e0b   Grey     #94a3b8
  Border      #333333

Fonts: Inter (body) | JetBrains Mono (numbers/tickers)
"""

import plotly.graph_objects as go

# ── Colour palette ────────────────────────────────────────────────────────────
BG        = "#0A0A0A"
CARD      = "#1A1A1A"
GOLD      = "#C9A227"
WHITE     = "#FFFFFF"
GREEN     = "#10b981"
RED       = "#ef4444"
AMBER     = "#f59e0b"
GREY      = "#94a3b8"
BORDER    = "#333333"
DARK_GOLD = "#8B6914"


def inject_css() -> str:
    """Return global CSS string for st.markdown(unsafe_allow_html=True)."""
    return f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap');

/* Hide Streamlit chrome */
#MainMenu {{visibility: hidden !important;}}
footer {{visibility: hidden !important;}}
.stDeployButton {{display: none !important;}}
header {{visibility: hidden !important;}}
[data-testid="stToolbar"] {{visibility: hidden !important;}}
.st-emotion-cache-zq5wmm {{display: none !important;}}

/* Global */
.stApp {{
    background-color: {BG} !important;
    color: {WHITE} !important;
    font-family: 'Inter', -apple-system, sans-serif !important;
}}
.block-container {{
    padding-top: 1rem !important;
    padding-bottom: 1rem !important;
    max-width: 1440px !important;
}}

/* Scrollbar */
::-webkit-scrollbar {{ width: 6px; background: {BG}; }}
::-webkit-scrollbar-thumb {{ background: {BORDER}; border-radius: 3px; }}

/* Navigation pills */
.nav-container {{
    display: flex;
    gap: 6px;
    padding: 8px 0 16px 0;
    border-bottom: 1px solid {BORDER};
    margin-bottom: 20px;
    flex-wrap: wrap;
}}
.nav-pill {{
    background: {CARD};
    color: {WHITE};
    border: 1px solid {BORDER};
    padding: 7px 14px;
    border-radius: 20px;
    cursor: pointer;
    font-family: 'Inter', sans-serif;
    font-size: 12px;
    font-weight: 500;
    letter-spacing: 0.5px;
    transition: all 0.15s;
    text-decoration: none;
    white-space: nowrap;
}}
.nav-pill:hover {{
    background: #2A2A2A;
    border-color: {GOLD};
}}
.nav-pill.active {{
    background: {GOLD} !important;
    color: #000000 !important;
    border-color: {GOLD};
    font-weight: 600;
}}

/* KPI cards */
.kpi-row {{
    display: flex;
    gap: 12px;
    margin-bottom: 20px;
    flex-wrap: wrap;
}}
.kpi-card {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 14px 18px;
    flex: 1;
    min-width: 140px;
}}
.kpi-label {{
    font-size: 11px;
    color: {GREY};
    text-transform: uppercase;
    letter-spacing: 0.8px;
    margin-bottom: 4px;
    font-family: 'Inter', sans-serif;
}}
.kpi-value {{
    font-size: 22px;
    font-weight: 600;
    color: {WHITE};
    font-family: 'JetBrains Mono', monospace;
    line-height: 1.2;
}}
.kpi-delta {{
    font-size: 12px;
    font-family: 'JetBrains Mono', monospace;
    margin-top: 2px;
}}
.kpi-positive {{ color: {GREEN}; }}
.kpi-negative {{ color: {RED}; }}
.kpi-neutral  {{ color: {GREY}; }}

/* Status badges */
.badge {{
    display: inline-block;
    padding: 3px 10px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 600;
    font-family: 'Inter', sans-serif;
    letter-spacing: 0.3px;
    white-space: nowrap;
}}
.badge-green  {{ background: {GREEN};  color: #000; }}
.badge-red    {{ background: {RED};    color: #fff; }}
.badge-amber  {{ background: {AMBER};  color: #000; }}
.badge-gold   {{ background: {GOLD};   color: #000; }}
.badge-grey   {{ background: #2a2a2a;  color: {GREY}; border: 1px solid {BORDER}; }}
.badge-polaris{{ background: #1e3a5f;  color: #60a5fa; border: 1px solid #3b6cb0; font-size: 10px; }}

/* Section headers */
.section-header {{
    font-size: 13px;
    font-weight: 600;
    color: {GOLD};
    text-transform: uppercase;
    letter-spacing: 1px;
    margin: 20px 0 12px 0;
    padding-bottom: 6px;
    border-bottom: 1px solid {BORDER};
}}

/* Data grid tables */
.data-grid {{
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
    font-family: 'Inter', sans-serif;
}}
.data-grid th {{
    background: #111111;
    color: {GREY};
    padding: 8px 12px;
    text-align: left;
    font-size: 11px;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    border-bottom: 1px solid {BORDER};
}}
.data-grid td {{
    padding: 9px 12px;
    border-bottom: 1px solid #1e1e1e;
    color: {WHITE};
    vertical-align: middle;
}}
.data-grid tr:hover td {{
    background: #1e1e1e;
}}
.data-grid .mono {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px;
}}
.data-grid .ticker {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px;
    color: {GOLD};
    font-weight: 600;
}}

/* Polaris ask bar */
.polaris-bar {{
    background: {CARD};
    border: 1px solid {GOLD};
    border-radius: 12px;
    padding: 16px 20px;
    margin-bottom: 20px;
}}
.polaris-label {{
    font-size: 11px;
    color: {GOLD};
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 8px;
    display: flex;
    align-items: center;
    gap: 6px;
}}
.polaris-response {{
    background: #0f1419;
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 14px 16px;
    font-size: 14px;
    line-height: 1.6;
    color: {WHITE};
    margin-top: 12px;
    white-space: pre-wrap;
}}

/* Buttons */
.btn-gold {{
    background: {GOLD};
    color: #000 !important;
    border: none;
    padding: 10px 22px;
    border-radius: 8px;
    font-weight: 600;
    font-size: 13px;
    cursor: pointer;
    font-family: 'Inter', sans-serif;
}}
.btn-ghost {{
    background: transparent;
    color: {GREY};
    border: 1px solid {BORDER};
    padding: 8px 16px;
    border-radius: 6px;
    font-size: 12px;
    cursor: pointer;
}}

/* Streamlit widget overrides */
.stTextInput > div > div > input {{
    background: {CARD} !important;
    border: 1px solid {BORDER} !important;
    color: {WHITE} !important;
    border-radius: 8px !important;
    font-family: 'Inter', sans-serif !important;
}}
.stTextInput > div > div > input:focus {{
    border-color: {GOLD} !important;
    box-shadow: 0 0 0 1px {GOLD} !important;
}}
.stSelectbox > div > div {{
    background: {CARD} !important;
    border-color: {BORDER} !important;
    color: {WHITE} !important;
}}
div[data-baseweb="select"] > div {{
    background: {CARD} !important;
    border-color: {BORDER} !important;
    color: {WHITE} !important;
}}
.stButton > button {{
    background: {CARD} !important;
    color: {WHITE} !important;
    border: 1px solid {BORDER} !important;
    border-radius: 8px !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 13px !important;
    transition: all 0.15s !important;
}}
.stButton > button:hover {{
    border-color: {GOLD} !important;
    color: {GOLD} !important;
}}
.stButton > button[kind="primary"] {{
    background: {GOLD} !important;
    color: #000 !important;
    border-color: {GOLD} !important;
    font-weight: 600 !important;
}}
[data-testid="stMetric"] {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 14px 18px;
}}
[data-testid="stMetricLabel"] {{
    color: {GREY} !important;
    font-size: 11px !important;
    text-transform: uppercase;
    letter-spacing: 0.8px;
}}
[data-testid="stMetricValue"] {{
    color: {WHITE} !important;
    font-family: 'JetBrains Mono', monospace !important;
}}
</style>
"""


# ── Plotly theme ──────────────────────────────────────────────────────────────

def chart_layout(**kwargs) -> dict:
    """Base Plotly layout dict with Taynton Bay theme."""
    base = dict(
        paper_bgcolor=BG,
        plot_bgcolor=CARD,
        font=dict(color=WHITE, family="Inter, sans-serif", size=12),
        title=dict(text="", font=dict(color=GOLD, size=14, family="Inter, sans-serif")),
        xaxis=dict(gridcolor=BORDER, zerolinecolor=BORDER, tickfont=dict(color=GREY, size=11)),
        yaxis=dict(gridcolor=BORDER, zerolinecolor=BORDER, tickfont=dict(color=GREY, size=11)),
        legend=dict(bgcolor=CARD, bordercolor=BORDER, borderwidth=1, font=dict(color=WHITE, size=11)),
        hoverlabel=dict(bgcolor="#1e1e1e", bordercolor=GOLD, font=dict(color=WHITE, size=12)),
        margin=dict(l=50, r=20, t=40, b=40),
    )
    base.update(kwargs)
    return base


def apply_theme(fig: go.Figure, **kwargs) -> go.Figure:
    fig.update_layout(**chart_layout(**kwargs))
    return fig


CHART_COLORS = [GOLD, WHITE, GREEN, RED, AMBER, GREY, "#60a5fa", "#a78bfa"]


# ── HTML helpers ──────────────────────────────────────────────────────────────

def kpi_card(label: str, value: str, delta: str | None = None,
             delta_positive: bool | None = None, color: str = WHITE) -> str:
    delta_class = ""
    delta_html  = ""
    if delta is not None:
        if delta_positive is True:
            delta_class = "kpi-positive"
        elif delta_positive is False:
            delta_class = "kpi-negative"
        else:
            delta_class = "kpi-neutral"
        delta_html = f'<div class="kpi-delta {delta_class}">{delta}</div>'
    return f"""
<div class="kpi-card">
  <div class="kpi-label">{label}</div>
  <div class="kpi-value" style="color:{color}">{value}</div>
  {delta_html}
</div>"""


def badge(text: str, color: str = "grey") -> str:
    return f'<span class="badge badge-{color}">{text}</span>'


def section_header(text: str) -> str:
    return f'<div class="section-header">{text}</div>'


def _color_for_pnl(val: float | None) -> str:
    if val is None or val != val: return GREY
    return GREEN if val >= 0 else RED


def format_market_cap(val) -> str:
    """Format a CAD market cap value as $14.2B / $847M / $45M / —."""
    try:
        v = float(val)
        if v != v or v <= 0:
            return "—"
    except (TypeError, ValueError):
        return "—"
    if v >= 100e9:  return f"${v/1e9:.0f}B"
    if v >= 10e9:   return f"${v/1e9:.1f}B"
    if v >= 1e9:    return f"${v/1e9:.2f}B"
    if v >= 1e6:    return f"${v/1e6:.0f}M"
    return f"${v:,.0f}"


def market_cap_tier_badge(tier: str) -> str:
    """Colour-coded HTML badge for a market cap tier label."""
    colours = {
        "Mega":    ("#C9A227", "#0A0A0A"),   # gold bg, dark text
        "Large":   ("#FFFFFF", "#1A1A1A"),   # white bg
        "Mid":     ("#94a3b8", "#0A0A0A"),   # grey bg
        "Small":   ("#f59e0b", "#0A0A0A"),   # amber bg
        "Micro":   ("#ef4444", "#FFFFFF"),   # red bg
        "Unknown": ("#333333", "#94a3b8"),   # dark bg, muted text
    }
    bg, fg = colours.get(tier, colours["Unknown"])
    return (
        f'<span style="background:{bg};color:{fg};padding:1px 6px;'
        f'border-radius:3px;font-size:0.7rem;font-weight:600;'
        f'font-family:\'JetBrains Mono\',monospace;">{tier}</span>'
    )


def fmt_pct(val: float | None, decimals: int = 1) -> str:
    if val is None or val != val: return "—"
    return f"{val:+.{decimals}f}%"


def fmt_cad(val: float | None, decimals: int = 0) -> str:
    if val is None or val != val: return "—"
    return f"${val:,.{decimals}f}"


def fmt_num(val: float | None, decimals: int = 2) -> str:
    if val is None or val != val: return "—"
    return f"{val:.{decimals}f}"


def score_color(score: float | None) -> str:
    if score is None or score != score: return GREY
    if score >= 80: return GOLD
    if score >= 60: return WHITE
    if score < 40:  return RED
    return GREY


def status_to_badge(status: str) -> str:
    mapping = {
        "ON_THESIS":   ("ON THESIS",    "green"),
        "REVIEW_DUE":  ("REVIEW DUE",   "amber"),
        "NO_THESIS":   ("NO THESIS",    "red"),
        "TIME_STOP":   ("TIME STOP",    "amber"),
        "STOP_HIT":    ("STOP HIT",     "red"),
        "TARGET_HIT":  ("TARGET HIT",   "gold"),
        "PASS":        ("PASS",         "green"),
        "CONDITIONAL": ("CONDITIONAL",  "amber"),
        "FAIL":        ("FAIL",         "red"),
        "BREACH":      ("BREACH",       "red"),
        "WARNING":     ("WARNING",      "amber"),
        "OK":          ("OK",           "green"),
    }
    label, color = mapping.get(status, (status, "grey"))
    return badge(label, color)
