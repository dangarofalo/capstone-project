"""Endpoint the collection agents send their events to."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Agent, Event, to_utc_naive, utcnow
from ..schemas import SEVERITY_BY_TYPE, BatchResult, EventBatch
from ..security import get_current_agent

router = APIRouter(prefix="/api/ingest", tags=["ingest"])


@router.post("/events", response_model=BatchResult)
def ingest_events(
    batch: EventBatch,
    agent: Agent = Depends(get_current_agent),
    db: Session = Depends(get_db),
) -> BatchResult:
    """Store a batch of events. An empty batch still counts as a heartbeat."""
    now = utcnow()
    agent.last_seen = now
    agent.hostname = batch.hostname
    agent.os = batch.os

    record_ids = [e.record_id for e in batch.events]
    already_stored: set[str] = set()
    if record_ids:
        already_stored = set(
            db.scalars(
                select(Event.record_id).where(
                    Event.agent_id == agent.id, Event.record_id.in_(record_ids)
                )
            )
        )

    accepted = 0
    for e in batch.events:
        if e.record_id in already_stored:
            continue
        already_stored.add(e.record_id)  # also skips repeats inside this batch
        db.add(
            Event(
                agent_id=agent.id,
                record_id=e.record_id,
                host=batch.hostname,
                event_time=to_utc_naive(e.event_time),
                received_at=now,
                event_type=e.event_type,
                severity=SEVERITY_BY_TYPE[e.event_type],
                username=e.username,
                source_ip=e.source_ip,
                logon_type=e.logon_type,
                source_event_id=e.source_event_id,
                message=e.message,
            )
        )
        accepted += 1

    db.commit()
    return BatchResult(accepted=accepted, duplicates=len(batch.events) - accepted)
