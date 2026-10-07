"""SentinelView API entry point.

Run with:  uvicorn app.main:app --reload
"""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from . import config
from .database import SessionLocal, init_db
from .detection import check_offline_agents
from .notifications import alert_snapshot, send_alert_email, should_email
from .routers import alerts, events, ingest

log = logging.getLogger("sentinelview")


def run_offline_check() -> None:
    with SessionLocal() as db:
        for alert in check_offline_agents(db):
            log.warning("Alert %s: %s", alert.id, alert.title)
            if should_email(alert):
                send_alert_email(alert_snapshot(alert))


async def offline_monitor() -> None:
    """Every OFFLINE_CHECK_SECONDS, look for agents that stopped reporting."""
    while True:
        await asyncio.sleep(config.OFFLINE_CHECK_SECONDS)
        try:
            await asyncio.to_thread(run_offline_check)  # DB work off the event loop
        except Exception:
            log.exception("Offline-agent check failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    monitor = asyncio.create_task(offline_monitor())
    yield
    monitor.cancel()


app = FastAPI(title="SentinelView API", version="0.2.0", lifespan=lifespan)
app.include_router(ingest.router)
app.include_router(events.router)
app.include_router(alerts.router)


@app.get("/api/health", tags=["health"])
def health() -> dict:
    return {"status": "ok"}
