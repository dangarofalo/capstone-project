"""Database tables."""
from datetime import datetime, timezone

from sqlalchemy import ForeignKey, Index, String, Text, UniqueConstraint
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
