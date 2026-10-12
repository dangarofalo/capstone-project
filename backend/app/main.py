"""SentinelView API and dashboard entry point.

Run with:  uvicorn app.main:app --reload
"""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select

from . import config
from .database import SessionLocal, init_db
from .detection import check_offline_agents
from .models import User
from .notifications import alert_snapshot, send_alert_email, should_email
from .passwords import hash_password, password_problem
from .routers import agents, alerts, auth, events, ingest, reports, stats, users

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


def ensure_admin_exists() -> None:
    """Create the first admin from environment variables, or explain how to."""
    with SessionLocal() as db:
        if db.scalar(select(func.count()).select_from(User)):
            return
        name, password = config.BOOTSTRAP_ADMIN_USERNAME, config.BOOTSTRAP_ADMIN_PASSWORD
        if name and password:
            if problem := password_problem(password):
                log.error("SENTINEL_ADMIN_PASSWORD rejected: %s", problem)
                return
            db.add(User(username=name, password_hash=hash_password(password), role="admin"))
            db.commit()
            log.warning("Created first admin user '%s'", name)
        else:
            log.warning("No dashboard users yet. Create one with: python -m app.manage create-user NAME --role admin")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    ensure_admin_exists()
    monitor = asyncio.create_task(offline_monitor())
    yield
    monitor.cancel()


app = FastAPI(title="SentinelView API", version="1.0.0", lifespan=lifespan)

for module in (auth, users, agents, ingest, events, alerts, stats, reports):
    app.include_router(module.router)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    if not request.url.path.startswith(("/docs", "/redoc", "/openapi.json")):
        # The dashboard only loads its own files; this blocks injected scripts.
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
            "object-src 'none'; frame-ancestors 'none'; base-uri 'self'",
        )
    return response


@app.get("/api/health", tags=["health"])
def health() -> dict:
    return {"status": "ok", "version": app.version}


# --- Web dashboard ---------------------------------------------------------------
# In production the built React app is served from here, so one server does everything.
# In development, run `npm run dev` in frontend/ instead (it proxies /api to this server).
if (config.FRONTEND_DIST / "index.html").exists():
    app.mount("/assets", StaticFiles(directory=config.FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def dashboard(path: str):
        if path.startswith("api/"):
            raise HTTPException(404, "Not found")
        file = (config.FRONTEND_DIST / path).resolve()
        # Real files (favicon etc.) are served as-is; every other path is a dashboard page.
        if path and file.is_file() and file.is_relative_to(config.FRONTEND_DIST.resolve()):
            return FileResponse(file)
        return FileResponse(config.FRONTEND_DIST / "index.html")
