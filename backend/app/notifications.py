"""Optional email notifications for new alerts (configured with SENTINEL_SMTP_* settings)."""
import logging
import smtplib
from email.message import EmailMessage

from . import config
from .models import Alert

log = logging.getLogger("sentinelview.notifications")

SEVERITY_RANK = {"info": 0, "low": 1, "medium": 2, "high": 3}


def should_email(alert: Alert) -> bool:
    if not (config.SMTP_HOST and config.ALERT_EMAIL_TO):
        return False
    return SEVERITY_RANK.get(alert.severity, 0) >= SEVERITY_RANK.get(config.EMAIL_MIN_SEVERITY, 3)


def alert_snapshot(alert: Alert) -> dict:
    """Plain copy of the fields an email needs, safe to use after the DB session closes."""
    return {
        "id": alert.id,
        "severity": alert.severity,
        "title": alert.title,
        "description": alert.description,
        "recommendation": alert.recommendation,
        "host": alert.host,
        "first_seen": alert.first_seen.isoformat(timespec="seconds") + "Z",
    }


def send_alert_email(snapshot: dict) -> None:
    """Send one alert email. Errors are logged, never raised, so ingest is never blocked."""
    msg = EmailMessage()
    msg["Subject"] = f"[SentinelView {snapshot['severity'].upper()}] {snapshot['title']}"
    msg["From"] = config.SMTP_FROM
    msg["To"] = config.ALERT_EMAIL_TO
    msg.set_content(
        f"{snapshot['title']}\n\n"
        f"What happened:\n{snapshot['description']}\n\n"
        f"What to do:\n{snapshot['recommendation']}\n\n"
        f"Computer: {snapshot['host']}\n"
        f"First seen (UTC): {snapshot['first_seen']}\n"
        f"Alert ID: {snapshot['id']}\n"
    )
    try:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=10) as smtp:
            if config.SMTP_STARTTLS:
                smtp.starttls()
            if config.SMTP_USER:
                smtp.login(config.SMTP_USER, config.SMTP_PASSWORD)
            smtp.send_message(msg)
    except Exception:
        log.exception("Could not send email for alert %s", snapshot["id"])
