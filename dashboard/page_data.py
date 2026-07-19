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


@st.cache_data(ttl=900, show_spinner=False)
def load_regime_performance(universe_key: str, horizon: int = 21) -> dict:
    from data.backtest import regime_performance, REGIME_UNIVERSES
    return regime_performance(REGIME_UNIVERSES[universe_key], horizon=horizon)


@st.cache_data(ttl=3600, show_spinner=False)
def load_financial_stress() -> dict:
    from data.fred import financial_stress
    return financial_stress()


@st.cache_data(ttl=1800, show_spinner=False)
def load_treasury_curve() -> tuple:
    from data.fmp import treasury_curve, curve_analytics
    return treasury_curve(), curve_analytics()


@st.cache_data(ttl=1800, show_spinner=False)
def load_rates_extras() -> dict:
    from data.fred import inflation_curve, credit_curve, funding_conditions
    return {"inflation": inflation_curve(), "credit": credit_curve(),
            "funding": funding_conditions()}


@st.cache_data(ttl=1800, show_spinner=False)
def load_boc() -> dict:
    from data.boc import boc_snapshot
    return boc_snapshot()


@st.cache_data(ttl=900, show_spinner=False)
def load_regime_probs() -> dict:
    from data.regime_model import regime_probabilities
    return regime_probabilities()


@st.cache_data(ttl=1800, show_spinner=False)
def load_gs_fci() -> dict:
    from data.conditions import gs_style_fci
    return gs_style_fci()


@st.cache_data(ttl=1800, show_spinner=False)
def load_crowding() -> dict:
    from data.crowding import crowding_score
    return crowding_score()


@st.cache_data(ttl=1800, show_spinner=False)
def load_analogues() -> dict:
    from data.analogues import find_analogues
    return find_analogues()


@st.cache_data(ttl=1800, show_spinner=False)
def load_regime_risk(horizon: int = 21) -> dict:
    from data.backtest import regime_risk_profile
    return regime_risk_profile(horizon=horizon)


@st.cache_data(ttl=900, show_spinner=False)
def load_narrative() -> str:
    from data.narrative import macro_brief
    return macro_brief(load_signals())


@st.cache_data(ttl=1800, show_spinner=False)
def load_correlation() -> dict:
    from data.correlations import correlation_state
    return correlation_state()


@st.cache_data(ttl=1800, show_spinner=False)
def load_iv_skew(ticker: str = "SPY") -> dict:
    from data.options import iv_skew
    return iv_skew(ticker)


@st.cache_data(ttl=1800, show_spinner=False)
def load_put_call(ticker: str = "SPY") -> dict:
    from data.options import put_call
    return put_call(ticker)
