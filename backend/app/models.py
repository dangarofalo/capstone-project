"""Database tables."""
from datetime import datetime, timezone

from sqlalchemy import Column, ForeignKey, Index, String, Table, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    """Current time in UTC without tzinfo; all times are stored as naive UTC."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def to_utc_naive(value: datetime) -> datetime:
    """Convert any datetime to naive UTC. Naive input is assumed to already be UTC."""
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


class Agent(Base):
    """A monitored computer that is allowed to send events."""

    __tablename__ = "agents"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    # Only a SHA-256 hash of the API key is stored, never the key itself.
    api_key_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    hostname: Mapped[str | None] = mapped_column(String(255))
    os: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    last_seen: Mapped[datetime | None]
    # Set when an admin revokes the agent's key; the agent can no longer send events.
    revoked_at: Mapped[datetime | None]

    events: Mapped[list["Event"]] = relationship(back_populates="agent")


class Event(Base):
    """One normalized security event (login, failed login, account change, ...)."""

    __tablename__ = "events"
    __table_args__ = (
        # An agent may resend events after a network error; this stops duplicates.
        UniqueConstraint("agent_id", "record_id", name="uq_event_agent_record"),
        Index("ix_events_event_time", "event_time"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id"), index=True)
    record_id: Mapped[str] = mapped_column(String(64))
    host: Mapped[str] = mapped_column(String(255), index=True)
    event_time: Mapped[datetime]
    received_at: Mapped[datetime] = mapped_column(default=utcnow)
    event_type: Mapped[str] = mapped_column(String(40), index=True)
    severity: Mapped[str] = mapped_column(String(10), index=True)
    username: Mapped[str | None] = mapped_column(String(255), index=True)
    source_ip: Mapped[str | None] = mapped_column(String(45), index=True)
    logon_type: Mapped[str | None] = mapped_column(String(10))
    source_event_id: Mapped[str | None] = mapped_column(String(20))
    message: Mapped[str | None] = mapped_column(Text)

    agent: Mapped[Agent] = relationship(back_populates="events")


# Which events caused which alert (one alert can be built from many events).
alert_events = Table(
    "alert_events",
    Base.metadata,
    Column("alert_id", ForeignKey("alerts.id"), primary_key=True),
    Column("event_id", ForeignKey("events.id"), primary_key=True),
)


class Alert(Base):
    """Something suspicious a detection rule found, written for a non-expert to act on."""

    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    rule: Mapped[str] = mapped_column(String(40), index=True)
    severity: Mapped[str] = mapped_column(String(10), index=True)
    # open -> acknowledged (someone is looking at it) -> resolved
    status: Mapped[str] = mapped_column(String(20), index=True, default="open")
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    recommendation: Mapped[str] = mapped_column(Text)
    # Identifies "the same problem" so repeated attacks update one alert instead of
    # creating hundreds, e.g. "brute_force:PC-01:ip:203.0.113.5".
    dedup_key: Mapped[str] = mapped_column(String(255), index=True)
    host: Mapped[str | None] = mapped_column(String(255), index=True)
    username: Mapped[str | None] = mapped_column(String(255))
    source_ip: Mapped[str | None] = mapped_column(String(45))
    agent_id: Mapped[int | None] = mapped_column(ForeignKey("agents.id"))
    event_count: Mapped[int] = mapped_column(default=0)
    first_seen: Mapped[datetime]
    last_seen: Mapped[datetime]
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)
    acknowledged_at: Mapped[datetime | None]
    acknowledged_by: Mapped[str | None] = mapped_column(String(50))
    resolved_at: Mapped[datetime | None]
    resolved_by: Mapped[str | None] = mapped_column(String(50))
    resolution_note: Mapped[str | None] = mapped_column(Text)

    events: Mapped[list[Event]] = relationship(secondary=alert_events, order_by=Event.event_time)


class User(Base):
    """A person who can sign in to the dashboard.

    admin:  everything, including managing alerts, computers, and users
    viewer: read-only access to dashboards, events, alerts, and reports
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(10), default="viewer")
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    last_login: Mapped[datetime | None]
