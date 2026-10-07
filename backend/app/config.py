"""Application settings, read from environment variables with safe defaults."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# SQLite for local development; set to a PostgreSQL URL in production, e.g.
# postgresql+psycopg://sentinel:password@localhost:5432/sentinelview
DATABASE_URL = os.getenv("SENTINEL_DATABASE_URL", f"sqlite:///{BASE_DIR / 'sentinelview.db'}")

# Largest number of events an agent may send in one request.
MAX_BATCH_SIZE = int(os.getenv("SENTINEL_MAX_BATCH_SIZE", "500"))

# --- Detection rules --------------------------------------------------------
# Brute force: this many failed logins within this many minutes raises an alert.
BRUTE_FORCE_THRESHOLD = int(os.getenv("SENTINEL_BRUTE_FORCE_THRESHOLD", "5"))
BRUTE_FORCE_WINDOW_MINUTES = int(os.getenv("SENTINEL_BRUTE_FORCE_WINDOW_MINUTES", "5"))

# Off-hours logins: business hours are WORK_HOURS_START:00 to WORK_HOURS_END:00.
WORK_HOURS_START = int(os.getenv("SENTINEL_WORK_HOURS_START", "7"))
WORK_HOURS_END = int(os.getenv("SENTINEL_WORK_HOURS_END", "19"))
# IANA time zone for business hours, e.g. "America/New_York". Empty = this server's zone.
TIMEZONE = os.getenv("SENTINEL_TIMEZONE") or None

# Offline agents: an agent that has not reported for this long raises an alert.
AGENT_OFFLINE_MINUTES = int(os.getenv("SENTINEL_AGENT_OFFLINE_MINUTES", "10"))
OFFLINE_CHECK_SECONDS = int(os.getenv("SENTINEL_OFFLINE_CHECK_SECONDS", "60"))

# --- Email alerts (optional; disabled unless SMTP_HOST and ALERT_EMAIL_TO are set) ---
SMTP_HOST = os.getenv("SENTINEL_SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SENTINEL_SMTP_PORT", "587"))
SMTP_USER = os.getenv("SENTINEL_SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SENTINEL_SMTP_PASSWORD", "")
SMTP_STARTTLS = os.getenv("SENTINEL_SMTP_STARTTLS", "true").lower() == "true"
SMTP_FROM = os.getenv("SENTINEL_SMTP_FROM", "sentinelview@localhost")
ALERT_EMAIL_TO = os.getenv("SENTINEL_ALERT_EMAIL_TO", "")  # comma-separated
EMAIL_MIN_SEVERITY = os.getenv("SENTINEL_EMAIL_MIN_SEVERITY", "high")
