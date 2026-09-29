"""Read endpoints used by the dashboard.

Stage 1 note: these are not yet protected by a user login (added in Stage 4),
so the server should only listen on 127.0.0.1 until then.
"""
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Agent, Event, to_utc_naive
from ..schemas import AgentOut, EventPage, EventType, Severity

router = APIRouter(prefix="/api", tags=["events"])


@router.get("/events", response_model=EventPage)
def list_events(
    db: Session = Depends(get_db),
    host: str | None = None,
    username: str | None = None,
    source_ip: str | None = None,
    event_type: EventType | None = None,
    severity: Severity | None = None,
    start: Annotated[datetime | None, Query(description="Earliest event time (UTC)")] = None,
    end: Annotated[datetime | None, Query(description="Latest event time (UTC)")] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> EventPage:
    """Newest events first, with optional filters."""
    filters = []
    if host:
        filters.append(Event.host == host)
    if username:
        filters.append(Event.username == username)
    if source_ip:
        filters.append(Event.source_ip == source_ip)
    if event_type:
        filters.append(Event.event_type == event_type)
    if severity:
        filters.append(Event.severity == severity)
    if start:
        filters.append(Event.event_time >= to_utc_naive(start))
    if end:
        filters.append(Event.event_time <= to_utc_naive(end))

    total = db.scalar(select(func.count()).select_from(Event).where(*filters))
    items = db.scalars(
        select(Event)
        .where(*filters)
        .order_by(Event.event_time.desc(), Event.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return EventPage(total=total, items=items)


@router.get("/agents", response_model=list[AgentOut])
def list_agents(db: Session = Depends(get_db)) -> list[Agent]:
    return db.scalars(select(Agent).order_by(Agent.name)).all()
