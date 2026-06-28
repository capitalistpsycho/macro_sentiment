"""Cached data loaders shared by the dashboard pages."""

from __future__ import annotations

import streamlit as st


@st.cache_data(ttl=900, show_spinner=False)
def load_metrics() -> dict:
    from data.store import latest_metrics
    return latest_metrics()


@st.cache_data(ttl=900, show_spinner=False)
def load_signals() -> dict:
    from data.signals import compute_signals
    return compute_signals(load_metrics())


@st.cache_data(ttl=900, show_spinner=False)
def load_sentiment() -> dict:
    from data.sentiment import fear_greed
    return fear_greed(load_metrics())


@st.cache_data(ttl=3600, show_spinner=False)
def load_calendar(days: int = 21) -> list:
    from data.calendar import upcoming_events
    return upcoming_events(days=days)


@st.cache_data(ttl=900, show_spinner=False)
def load_context_percentiles() -> dict:
    from data.signals import signal_context
    return signal_context()


@st.cache_data(ttl=900, show_spinner=False)
def load_backtest(regime_col: str = "regime") -> dict:
    from data.backtest import regime_backtest
    return regime_backtest(regime_col)


@st.cache_data(ttl=3600, show_spinner=False)
def load_financial_stress() -> dict:
    from data.fred import financial_stress
    return financial_stress()


@st.cache_data(ttl=1800, show_spinner=False)
def load_put_call(ticker: str = "SPY") -> dict:
    from data.options import put_call
    return put_call(ticker)
