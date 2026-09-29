"""Application settings, read from environment variables with safe defaults."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# SQLite for local development; set to a PostgreSQL URL in production, e.g.
# postgresql+psycopg://sentinel:password@localhost:5432/sentinelview
DATABASE_URL = os.getenv("SENTINEL_DATABASE_URL", f"sqlite:///{BASE_DIR / 'sentinelview.db'}")

# Largest number of events an agent may send in one request.
MAX_BATCH_SIZE = int(os.getenv("SENTINEL_MAX_BATCH_SIZE", "500"))
