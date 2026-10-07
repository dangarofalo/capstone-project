"""Alert endpoints for the dashboard: list, view, acknowledge, resolve.

Stage 2 note: like the event endpoints, these have no user login until Stage 4,
so keep the server on 127.0.0.1 until then.
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..detection import ACTIVE_STATUSES
from ..models import Alert, utcnow
from ..schemas import AlertAction, AlertDetail, AlertPage, AlertRule, AlertStatus, AlertSummary, Severity

router = APIRouter(prefix="/api/alerts", tags=["alerts"])

MAX_EVENTS_IN_DETAIL = 100


@router.get("", response_model=AlertPage)
def list_alerts(
    db: Session = Depends(get_db),
    status_: Annotated[AlertStatus | None, Query(alias="status")] = None,
    severity: Severity | None = None,
    rule: AlertRule | None = None,
    host: str | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AlertPage:
    """Most recently active alerts first, with optional filters."""
    filters = []
    if status_:
        filters.append(Alert.status == status_)
    if severity:
        filters.append(Alert.severity == severity)
    if rule:
        filters.append(Alert.rule == rule)
    if host:
        filters.append(Alert.host == host)

    total = db.scalar(select(func.count()).select_from(Alert).where(*filters))
    items = db.scalars(
        select(Alert).where(*filters).order_by(Alert.last_seen.desc(), Alert.id.desc()).limit(limit).offset(offset)
    ).all()
    return AlertPage(total=total, items=items)


@router.get("/summary", response_model=AlertSummary)
def alert_summary(db: Session = Depends(get_db)) -> AlertSummary:
    by_status = dict(db.execute(select(Alert.status, func.count()).group_by(Alert.status)).all())
    by_severity = dict(
        db.execute(
            select(Alert.severity, func.count())
            .where(Alert.status.in_(ACTIVE_STATUSES))
            .group_by(Alert.severity)
        ).all()
    )
    return AlertSummary(
        open=by_status.get("open", 0),
        acknowledged=by_status.get("acknowledged", 0),
        resolved=by_status.get("resolved", 0),
        active_by_severity={s: by_severity.get(s, 0) for s in ("high", "medium", "low")},
    )


def _get_alert(db: Session, alert_id: int) -> Alert:
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Alert not found")
    return alert


@router.get("/{alert_id}", response_model=AlertDetail)
def get_alert(alert_id: int, db: Session = Depends(get_db)) -> AlertDetail:
    """One alert plus the events that caused it (latest 100)."""
    alert = _get_alert(db, alert_id)
    detail = AlertDetail.model_validate(alert, from_attributes=True)
    detail.events = detail.events[-MAX_EVENTS_IN_DETAIL:]
    return detail


@router.post("/{alert_id}/acknowledge", response_model=AlertDetail)
def acknowledge_alert(alert_id: int, db: Session = Depends(get_db)) -> AlertDetail:
    """Mark that someone is looking into the alert."""
    alert = _get_alert(db, alert_id)
    if alert.status == "resolved":
        raise HTTPException(status.HTTP_409_CONFLICT, "Alert is already resolved")
    if alert.status == "open":
        alert.status = "acknowledged"
        alert.acknowledged_at = utcnow()
        db.commit()
    return get_alert(alert_id, db)


@router.post("/{alert_id}/resolve", response_model=AlertDetail)
def resolve_alert(
    alert_id: int, action: AlertAction | None = None, db: Session = Depends(get_db)
) -> AlertDetail:
    """Close the alert, optionally with a note about what was done."""
    alert = _get_alert(db, alert_id)
    if alert.status == "resolved":
        raise HTTPException(status.HTTP_409_CONFLICT, "Alert is already resolved")
    alert.status = "resolved"
    alert.resolved_at = utcnow()
    alert.resolution_note = action.note if action else None
    db.commit()
    return get_alert(alert_id, db)
