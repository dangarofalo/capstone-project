"""SentinelView API entry point.

Run with:  uvicorn app.main:app --reload
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .database import init_db
from .routers import events, ingest


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="SentinelView API", version="0.1.0", lifespan=lifespan)
app.include_router(ingest.router)
app.include_router(events.router)


@app.get("/api/health", tags=["health"])
def health() -> dict:
    return {"status": "ok"}
