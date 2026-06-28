"""
Taynton Bay Capital — Macro Compass
Northstar Fund | Market Intelligence

Run: python -m streamlit run dashboard/app.py --server.port 8503
"""

import importlib
import os
import sys
from datetime import datetime, timedelta

import pytz
import streamlit as st

# Project root on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

st.set_page_config(
    page_title="Taynton Bay Capital — Macro Compass",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="collapsed",
)

from dashboard.styles import inject_css, GOLD, WHITE, GREY, AMBER  # noqa: E402


# ── Password gate ─────────────────────────────────────────────────────────────

def check_password() -> bool:
    if st.session_state.get("authenticated"):
        return True

    st.markdown("""
<style>
.stApp { background-color: #0A0A0A !important; }
div[data-testid="stVerticalBlock"] { align-items: center; }
</style>
<div style="display:flex;flex-direction:column;align-items:center;
            justify-content:center;min-height:68vh;font-family:Inter,sans-serif">
  <div style="color:#C9A227;font-size:2.8rem;font-weight:700;margin-bottom:0.4rem">🧭 Macro Compass</div>
  <div style="color:#FFFFFF;font-size:1.05rem;opacity:0.85;margin-bottom:0.2rem">Taynton Bay Capital</div>
  <div style="color:#FFFFFF;font-size:0.9rem;margin-bottom:2.6rem;opacity:0.55">
    Northstar Fund · Market Intelligence · Private Access
  </div>
</div>
""", unsafe_allow_html=True)

    c1, c2, c3 = st.columns([1, 1, 1])
    with c2:
        pw = st.text_input("Access code", type="password",
                           placeholder="Enter your access code", label_visibility="collapsed")
        if st.button("Enter Macro Compass", width='stretch', type="primary"):
            try:
                correct = st.secrets["passwords"]["password"]
                if pw == correct:
                    st.session_state["authenticated"] = True
                    st.rerun()
                else:
                    st.error("Incorrect access code. Please try again.")
            except Exception:
                st.error("Authentication not configured — check Streamlit secrets.")
    return False


if not check_password():
    st.stop()

st.markdown(inject_css(), unsafe_allow_html=True)

# ── Page registry (isolated import so one bad page can't crash the app) ────────

_PAGE_MODULES = {
    "I OVERVIEW":   "dashboard.pages.page_overview",
    "II STYLES":    "dashboard.pages.page_styles",
    "III REGIONS":  "dashboard.pages.page_regions",
    "IV SECTORS":   "dashboard.pages.page_sectors",
    "V MACRO":      "dashboard.pages.page_macro",
    "VI SENTIMENT": "dashboard.pages.page_sentiment",
    "VII COMMODITIES": "dashboard.pages.page_commodities",
}

_LOADED: dict = {}
for _pname, _mpath in _PAGE_MODULES.items():
    try:
        _LOADED[_pname] = importlib.import_module(_mpath)
    except Exception as _e:
        import logging
        logging.getLogger(__name__).error("Page import failed [%s]: %s", _pname, _e, exc_info=True)

        class _Failed:
            _err = str(_e)
            def render(self, ctx):
                st.error(f"This page failed to load: {self._err}")
                st.info("The rest of the dashboard is still available — use the nav bar above.")
        _fp = _Failed(); _fp._err = str(_e)
        _LOADED[_pname] = _fp

PAGES = list(_PAGE_MODULES.keys())
if "page" not in st.session_state:
    st.session_state["page"] = "I OVERVIEW"


def render_nav() -> None:
    st.markdown('<div class="nav-container">', unsafe_allow_html=True)
    cols = st.columns(len(PAGES))
    for col, page in zip(cols, PAGES):
        with col:
            active = st.session_state["page"] == page
            if st.button(page, key=f"nav_{page}", width='stretch',
                         type="primary" if active else "secondary"):
                if not active:
                    st.session_state["page"] = page
                    st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)


# ── Market hours (US/Eastern) ─────────────────────────────────────────────────

US_HOLIDAYS_2026 = {
    "2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03", "2026-05-25",
    "2026-06-19", "2026-07-03", "2026-09-07", "2026-11-26", "2026-12-25",
}


def is_market_hours() -> bool:
    now = datetime.now(pytz.timezone("US/Eastern"))
    if now.weekday() >= 5 or now.strftime("%Y-%m-%d") in US_HOLIDAYS_2026:
        return False
    mo = now.replace(hour=9, minute=30, second=0, microsecond=0)
    mc = now.replace(hour=16, minute=0, second=0, microsecond=0)
    return mo <= now <= mc


def _next_open_label() -> str:
    now = datetime.now(pytz.timezone("US/Eastern"))
    if now.weekday() < 5 and (now.hour < 9 or (now.hour == 9 and now.minute < 30)) \
            and now.strftime("%Y-%m-%d") not in US_HOLIDAYS_2026:
        return now.strftime("%a")
    cand = now.date() + timedelta(days=1)
    for _ in range(10):
        if cand.weekday() < 5 and cand.isoformat() not in US_HOLIDAYS_2026:
            return cand.strftime("%a")
        cand += timedelta(days=1)
    return "Mon"


def market_status_badge() -> str:
    if is_market_hours():
        return ('<span style="background:#10b981;color:#000;padding:3px 10px;'
                'border-radius:12px;font-size:11px;font-weight:600">MARKET OPEN</span>')
    return (f'<span style="background:#333;color:#94a3b8;padding:3px 10px;'
            f'border-radius:12px;font-size:11px">MARKET CLOSED · Opens '
            f'{_next_open_label()} 9:30 AM ET</span>')


def maybe_autorefresh() -> None:
    try:
        from streamlit_autorefresh import st_autorefresh
        interval = 900_000 if is_market_hours() else 3_600_000
        st_autorefresh(interval=interval, key="macro_autorefresh")
    except ImportError:
        pass


# ── Header + freshness ────────────────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)
def load_freshness() -> dict:
    try:
        from dashboard.freshness import get_freshness
        return get_freshness()
    except Exception:
        return {}


def render_header() -> None:
    now_et = datetime.now(pytz.timezone("US/Eastern"))
    c1, c2 = st.columns([3, 1])
    with c1:
        st.markdown(
            f'<div style="font-size:18px;font-weight:700;color:{GOLD};'
            f'font-family:Inter,sans-serif;padding:4px 0 0 0">'
            f'🧭 Taynton Bay Capital · Macro Compass'
            f'<span style="font-size:13px;color:{GREY};font-weight:400"> · Northstar Fund</span>'
            f'</div>', unsafe_allow_html=True)
    with c2:
        st.markdown(
            f'<div style="text-align:right;padding-top:4px">{market_status_badge()}'
            f'<span style="font-family:JetBrains Mono,monospace;font-size:11px;'
            f'color:{GREY};margin-left:8px">{now_et.strftime("%H:%M ET")}</span></div>',
            unsafe_allow_html=True)


def render_freshness_strip() -> None:
    f = load_freshness()
    if not f or not f.get("prices_as_of"):
        return
    if f.get("stale"):
        st.markdown(
            f'<div style="background:rgba(245,158,11,0.12);border:1px solid {AMBER};'
            f'border-radius:6px;padding:6px 12px;margin:-4px 0 8px 0;font-size:11px;'
            f'color:{AMBER}">⚠ Data is more than one trading day old '
            f'(prices as of {f["prices_as_of"]}). Run <code>python run_macro.py --full</code> to refresh.</div>',
            unsafe_allow_html=True)
    else:
        st.markdown(
            f'<div style="text-align:right;color:{GREY};font-size:10px;'
            f'font-family:JetBrains Mono,monospace;margin:-6px 0 6px 0">'
            f'As of · Prices {f["prices_as_of"]}</div>', unsafe_allow_html=True)


# ── Page router ───────────────────────────────────────────────────────────────

@st.cache_data(ttl=900, show_spinner=False)
def load_context() -> dict:
    try:
        from dashboard.polaris import build_macro_context
        return build_macro_context()
    except Exception:
        return {}


def render_page(page: str, ctx: dict) -> None:
    import logging
    module = _LOADED.get(page)
    if module is None:
        st.error("Page not found.")
        return
    try:
        module.render(ctx)
    except Exception as exc:
        st.markdown(
            f'<div style="background:#1a0000;border:1px solid #ef4444;border-radius:8px;'
            f'padding:20px;margin:20px 0"><div style="color:#ef4444;font-weight:600;'
            f'margin-bottom:8px">⚠ Unable to load this page</div>'
            f'<div style="color:#94a3b8;font-size:13px">An unexpected error occurred. '
            f'If it persists, check the application log.</div></div>', unsafe_allow_html=True)
        logging.getLogger(__name__).error("Page render error [%s]: %s", page, exc, exc_info=True)


def main() -> None:
    maybe_autorefresh()
    render_header()
    render_nav()
    render_freshness_strip()
    ctx = load_context()
    render_page(st.session_state["page"], ctx)

    # Footer
    from dashboard.components import footer
    now_et = datetime.now(pytz.timezone("US/Eastern")).strftime("%Y-%m-%d %H:%M")
    st.markdown(footer(now_et), unsafe_allow_html=True)


if __name__ == "__main__":
    main()
