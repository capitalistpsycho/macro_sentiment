"""
Unified secret resolution: Streamlit Cloud secrets → environment variables.
Import get_secret() everywhere instead of os.getenv() for API keys.

On import we load the project-root .env into the environment (without overriding
anything already set) so every entry point — the Streamlit app, run_macro, and
one-off scripts — resolves the same keys.
"""
import os

try:
    from dotenv import load_dotenv

    _ENV_PATH = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    load_dotenv(_ENV_PATH, override=False)
except Exception:
    pass

try:
    import streamlit as st

    def get_secret(key: str, default: str = "") -> str:
        # Check Streamlit secrets (flat key, then api_keys section), but skip
        # empty-string values so blank secrets.toml entries don't shadow real
        # environment variables set in .env or the OS.
        try:
            val = st.secrets[key]
            if val:
                return val
        except Exception:
            pass
        try:
            val = st.secrets["api_keys"][key]
            if val:
                return val
        except Exception:
            pass
        return os.getenv(key, default)

except ImportError:
    def get_secret(key: str, default: str = "") -> str:
        return os.getenv(key, default)
