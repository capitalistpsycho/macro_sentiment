"""
Market-implied policy-rate path — what the curve is pricing for the Fed and BoC.

An N-year zero yield ≈ the average expected overnight rate over N years (plus a
term premium), so the front Treasury/GoC curve embeds the market's rate path.
This is a *curve-implied approximation* (not OIS/futures-precise), labelled as
such: it reads the 1Y point against the current policy rate to gauge how much
easing/tightening is priced over the next year.
"""

from __future__ import annotations

from data import fred


def _read(policy, one_year):
    """Spread of the 1Y point over the policy rate (bp) + qualitative read.

    A cleanly negative spread = the market pricing cuts; positive = no cuts / a
    tightening or term-premium bias. We report the spread, not a precise cut
    count, because Treasuries embed a term premium that OIS/futures would strip.
    """
    if policy is None or one_year is None:
        return None, "—"
    spread_bp = round((one_year - policy) * 100)
    if spread_bp <= -30:
        read = f"1Y {abs(spread_bp)}bp below policy — pricing cuts"
    elif spread_bp >= 30:
        read = f"1Y {spread_bp}bp above policy — no cuts priced (tightening/term-premium bias)"
    else:
        read = f"1Y within {abs(spread_bp)}bp of policy — roughly on hold"
    return spread_bp, read


def fed_path() -> dict:
    policy = fred.latest("DFF") or fred.latest("FEDFUNDS")   # daily effective
    y3m, y1, y2 = fred.latest("UST:3M"), fred.latest("UST:1Y"), fred.latest("UST:2Y")
    spread, read = _read(policy, y1)
    return {"policy": policy, "y3m": y3m, "y1": y1, "y2": y2,
            "spread_1y_bp": spread, "read": read}


def boc_path() -> dict:
    from data import boc
    b = boc.boc_snapshot()
    policy = b.get("policy_rate")
    g2 = b.get("goc_2y")
    # No 1Y GoC cached; use the 2Y as the front-end read against policy.
    spread, read = _read(policy, g2)
    if spread is not None:
        read = read.replace("1Y", "2Y")
    return {"policy": policy, "corra": b.get("corra"), "goc_2y": g2,
            "spread_1y_bp": spread, "read": read}
