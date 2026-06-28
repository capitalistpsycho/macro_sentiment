"""
Regime-change alerting.

When the daily refresh produces a market or macro regime different from the last
stored reading, this raises an alert: it always logs loudly, appends to
output/alerts.log, and records a PM-journal entry. If e-mail (SMTP_*) or a Slack
webhook (SLACK_WEBHOOK_URL) are configured it also delivers there. All delivery
is best-effort — a missing channel never breaks the refresh.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime

from config.secrets import get_secret
from data.db import get_db, add_journal_note

logger = logging.getLogger(__name__)

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_ALERT_LOG = os.path.join(_ROOT, "output", "alerts.log")


def _prior_regimes() -> tuple[str | None, str | None]:
    """The most recently stored (market_regime, macro_regime), or (None, None)."""
    try:
        with get_db() as c:
            r = c.execute("SELECT regime, macro_regime FROM macro_signals "
                          "ORDER BY date DESC LIMIT 1").fetchone()
        if r:
            return r["regime"], r["macro_regime"]
    except Exception:
        pass
    return None, None


def detect_regime_change(sig: dict) -> dict | None:
    """Compare the new signal to the last stored regimes. Returns a change or None.

    Call BEFORE persisting the new signal so the comparison is against the prior day.
    """
    prev_mkt, prev_macro = _prior_regimes()
    new_mkt, new_macro = sig.get("regime"), sig.get("macro_regime")
    changes = []
    if prev_mkt and new_mkt and prev_mkt != new_mkt:
        changes.append(("Market regime", prev_mkt, new_mkt))
    if prev_macro and new_macro and prev_macro != new_macro:
        changes.append(("Macro regime", prev_macro, new_macro))
    if not changes:
        return None
    return {"date": sig.get("date"), "changes": changes,
            "compass": sig.get("compass_score"), "risk": sig.get("risk_score")}


def _send_email(subject: str, body: str) -> bool:
    host = get_secret("SMTP_HOST"); user = get_secret("SMTP_USER")
    pw = get_secret("SMTP_PASS"); to = get_secret("ALERT_EMAIL_TO")
    if not (host and user and pw and to):
        return False
    try:
        import smtplib
        from email.mime.text import MIMEText
        msg = MIMEText(body)
        msg["Subject"] = subject; msg["From"] = user; msg["To"] = to
        port = int(get_secret("SMTP_PORT", "587") or 587)
        with smtplib.SMTP(host, port, timeout=20) as s:
            s.starttls(); s.login(user, pw); s.sendmail(user, [to], msg.as_string())
        return True
    except Exception as exc:
        logger.warning("Alert e-mail failed: %s", exc)
        return False


def _send_slack(text: str) -> bool:
    url = get_secret("SLACK_WEBHOOK_URL")
    if not url:
        return False
    try:
        import requests
        requests.post(url, json={"text": text}, timeout=15)
        return True
    except Exception as exc:
        logger.warning("Alert Slack failed: %s", exc)
        return False


def notify_regime_change(change: dict) -> None:
    lines = [f"{label}: {old} → {new}" for label, old, new in change["changes"]]
    summary = "; ".join(lines)
    subject = f"Macro Compass · regime change ({change['date']})"
    body = (f"{subject}\n\n" + "\n".join(lines)
            + f"\n\nMacroCompass {change.get('compass')}/100 · "
              f"Risk-on/off {change.get('risk')}/100\n"
              f"— Taynton Bay Capital · Macro Compass")

    logger.warning("REGIME CHANGE — %s", summary)
    try:
        os.makedirs(os.path.dirname(_ALERT_LOG), exist_ok=True)
        with open(_ALERT_LOG, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now().isoformat(timespec='seconds')}  {summary}\n")
    except Exception:
        pass
    try:
        add_journal_note(change["date"], change["changes"][0][2],
                         "Auto: regime change — " + summary)
    except Exception:
        pass
    sent = []
    if _send_email(subject, body):
        sent.append("email")
    if _send_slack(body):
        sent.append("slack")
    if sent:
        logger.info("Regime alert delivered via: %s", ", ".join(sent))
