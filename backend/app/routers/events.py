"""Event search and CSV export for the dashboard (any signed-in user)."""
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..exports import MAX_EXPORT_ROWS, csv_response
from ..models import Event, to_utc_naive
from ..schemas import EventPage, EventType, Severity
from ..security import get_current_user

router = APIRouter(prefix="/api/events", tags=["events"], dependencies=[Depends(get_current_user)])


def event_filters(
    host: str | None = None,
    username: str | None = None,
    source_ip: str | None = None,
    event_type: EventType | None = None,
    severity: Severity | None = None,
    start: Annotated[datetime | None, Query(description="Earliest event time")] = None,
    end: Annotated[datetime | None, Query(description="Latest event time")] = None,
    q: Annotated[str | None, Query(max_length=100, description="Text search in user, IP, host, message")] = None,
) -> list:
    """Query-string filters shared by the event list and the CSV export."""
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
    if q:
        pattern = f"%{q.lower()}%"
        filters.append(
            func.lower(Event.username).like(pattern)
            | func.lower(Event.source_ip).like(pattern)
            | func.lower(Event.host).like(pattern)
            | func.lower(Event.message).like(pattern)
        )
    return filters


@router.get("", response_model=EventPage)
def list_events(
    filters: list = Depends(event_filters),
    db: Session = Depends(get_db),
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> EventPage:
    """Newest events first, with optional filters."""
    total = db.scalar(select(func.count()).select_from(Event).where(*filters))
    items = db.scalars(
        select(Event)
        .where(*filters)
        .order_by(Event.event_time.desc(), Event.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return EventPage(total=total, items=items)


@router.get("/export.csv")
def export_events(filters: list = Depends(event_filters), db: Session = Depends(get_db)):
    """Download the matching events (newest first, up to 100,000) as a spreadsheet."""
    rows = db.execute(
        select(
            Event.event_time, Event.host, Event.event_type, Event.severity, Event.username,
            Event.source_ip, Event.logon_type, Event.source_event_id, Event.message,
        )
        .where(*filters)
        .order_by(Event.event_time.desc(), Event.id.desc())
        .limit(MAX_EXPORT_ROWS)
    ).all()  # read now: the DB session closes before the response finishes streaming
    header = ["time_utc", "computer", "event_type", "severity", "username", "source_ip",
              "logon_type", "windows_event_id", "message"]
    return csv_response("sentinelview-events.csv", header, rows)
