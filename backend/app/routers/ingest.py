"""Endpoint the collection agents send their events to."""
from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..detection import resolve_offline_alert, run_event_rules
from ..models import Agent, Event, to_utc_naive, utcnow
from ..notifications import alert_snapshot, send_alert_email, should_email
from ..schemas import SEVERITY_BY_TYPE, BatchResult, EventBatch
from ..security import get_current_agent

router = APIRouter(prefix="/api/ingest", tags=["ingest"])


@router.post("/events", response_model=BatchResult)
def ingest_events(
    batch: EventBatch,
    background: BackgroundTasks,
    agent: Agent = Depends(get_current_agent),
    db: Session = Depends(get_db),
) -> BatchResult:
    """Store a batch of events and run detection rules on them.

    An empty batch still counts as a heartbeat.
    """
    now = utcnow()
    agent.last_seen = now
    agent.hostname = batch.hostname
    agent.os = batch.os
    resolve_offline_alert(db, agent, now)

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

    new_events: list[Event] = []
    for e in batch.events:
        if e.record_id in already_stored:
            continue
        already_stored.add(e.record_id)  # also skips repeats inside this batch
        event = Event(
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
        db.add(event)
        new_events.append(event)

    db.flush()  # give the new events IDs so detection rules can query them
    alerts = run_event_rules(db, new_events)
    db.commit()

    # Emails go out after the response is sent, so a slow mail server never delays agents.
    for alert in alerts:
        if should_email(alert):
            background.add_task(send_alert_email, alert_snapshot(alert))

    return BatchResult(
        accepted=len(new_events),
        duplicates=len(batch.events) - len(new_events),
        alerts_created=len(alerts),
    )
