"""
Macro scenario tool — oil-price shock → Canada/US impacts.

Encodes Scotiabank Economics' published elasticities for a persistent $10/bbl WTI
shock (Canada–U.S. Scotiabank Macro Model, Mar 2026), which Scotiabank states
scale approximately linearly with shock size. This turns the Commodities page's
oil chart into a decision tool for the Northstar Fund's energy/CAD exposure.

Source: scotiabank.com/ca/en/about/economics — "Impact of Higher Oil Prices on
Canada and the US" (verified 2026-07).
"""

from __future__ import annotations

# Impact per +$10/bbl WTI, persistent two-year shock.
ELASTICITY = {
    "Canada": {"gdp_pct_yr2": 0.5, "cpi_pp": 0.2, "cad_pct": 3.0, "policy_bps": 30},
    "US":     {"gdp_pct_yr2": 0.1, "cpi_pp": 0.3, "cad_pct": None, "policy_bps": 20},
}


def oil_scenario(oil_shock_usd: float) -> dict:
    """Scale the Scotiabank elasticities to an arbitrary oil shock (±$/bbl)."""
    k = oil_shock_usd / 10.0

    def scale(d):
        return {key: (round(v * k, 2) if v is not None else None) for key, v in d.items()}

    return {
        "shock_usd": oil_shock_usd,
        "Canada": scale(ELASTICITY["Canada"]),
        "US": scale(ELASTICITY["US"]),
        "note": "Scotiabank Canada–U.S. Macro Model elasticities; scale ~linearly with shock size.",
    }
