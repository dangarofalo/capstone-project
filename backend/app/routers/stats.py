"""Numbers for the dashboard overview page, computed in one request."""
from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..detection import ACTIVE_STATUSES
from ..models import Agent, Alert, Event, utcnow
from ..schemas import Overview, Timeline
from ..security import get_current_user
from .agents import agent_status

router = APIRouter(prefix="/api/stats", tags=["stats"], dependencies=[Depends(get_current_user)])

EVENT_TYPES = ["login_success", "login_failure", "account_lockout", "account_created", "admin_group_added"]


def _counts(db: Session, column, *filters) -> dict[str, int]:
    rows = db.execute(select(column, func.count()).where(*filters).group_by(column)).all()
    return {key: count for key, count in rows if key is not None}


def _top(db: Session, column, *filters, limit: int = 5) -> list[dict]:
    count = func.count().label("n")
    rows = db.execute(
        select(column, count)
        .where(column.is_not(None), *filters)
        .group_by(column)
        .order_by(count.desc(), column)
        .limit(limit)
    ).all()
    return [{"name": name, "count": n} for name, n in rows]


def _timeline(db: Session, start: datetime, end: datetime, hours: int) -> Timeline:
    """Events per hour (ranges up to 2 days) or per day, split by event type."""
    step = timedelta(hours=1) if hours <= 48 else timedelta(days=1)
    first = start.replace(minute=0, second=0, microsecond=0)
    if step == timedelta(days=1):
        first = first.replace(hour=0)
    labels = []
    t = first
    while t <= end:
        labels.append(t)
        t += step
    series = {etype: [0] * len(labels) for etype in EVENT_TYPES}

    # Bucketing in Python keeps this portable between SQLite and PostgreSQL.
    rows = db.execute(
        select(Event.event_time, Event.event_type).where(Event.event_time >= start, Event.event_time <= end)
    )
    for event_time, event_type in rows:
        index = int((event_time - first) / step)
        if 0 <= index < len(labels) and event_type in series:
            series[event_type][index] += 1
    return Timeline(bucket="hour" if step == timedelta(hours=1) else "day", labels=labels, series=series)


@router.get("/overview", response_model=Overview)
def overview(
    db: Session = Depends(get_db),
    hours: Annotated[int, Query(ge=1, le=24 * 90, description="How far back to look")] = 24,
) -> Overview:
    end = utcnow()
    start = end - timedelta(hours=hours)
    in_range = (Event.event_time >= start, Event.event_time <= end)
    failures = (*in_range, Event.event_type == "login_failure")

    by_type = _counts(db, Event.event_type, *in_range)
    active_alerts = _counts(db, Alert.severity, Alert.status.in_(ACTIVE_STATUSES))
    agent_statuses = [agent_status(a, end) for a in db.scalars(select(Agent))]

    return Overview(
        range_hours=hours,
        start=start,
        end=end,
        totals={
            "events": sum(by_type.values()),
            "failed_logins": by_type.get("login_failure", 0),
            "successful_logins": by_type.get("login_success", 0),
            "active_alerts": sum(active_alerts.values()),
            "high_alerts": active_alerts.get("high", 0),
            "new_alerts": db.scalar(
                select(func.count()).select_from(Alert).where(Alert.created_at >= start)
            ),
        },
        agents={
            "total": sum(s != "revoked" for s in agent_statuses),
            "online": agent_statuses.count("online"),
            "offline": agent_statuses.count("offline"),
            "never_reported": agent_statuses.count("never_reported"),
        },
        severity_counts={s: c for s, c in _counts(db, Event.severity, *in_range).items()},
        event_type_counts=by_type,
        timeline=_timeline(db, start, end, hours),
        top_failed_users=_top(db, Event.username, *failures),
        top_failed_ips=_top(db, Event.source_ip, *failures),
        top_hosts=_top(db, Event.host, *in_range),
    )
