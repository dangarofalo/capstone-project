"""Request and response shapes for the API (validated by Pydantic)."""
import ipaddress
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from . import config

EventType = Literal[
    "login_success",
    "login_failure",
    "account_created",
    "admin_group_added",
    "account_lockout",
]
Severity = Literal["info", "low", "medium", "high"]

# The server decides severity so that agents cannot downplay an event.
SEVERITY_BY_TYPE: dict[str, str] = {
    "login_success": "info",
    "login_failure": "low",
    "account_lockout": "medium",
    "account_created": "medium",
    "admin_group_added": "high",
}


class EventIn(BaseModel):
    record_id: str = Field(min_length=1, max_length=64)
    event_time: datetime
    event_type: EventType
    username: str | None = Field(default=None, max_length=255)
    source_ip: str | None = Field(default=None, max_length=45)
    logon_type: str | None = Field(default=None, max_length=10)
    source_event_id: str | None = Field(default=None, max_length=20)
    message: str | None = Field(default=None, max_length=2000)

    @field_validator("source_ip")
    @classmethod
    def valid_ip_or_none(cls, value: str | None) -> str | None:
        # Logs often contain "-" or a hostname instead of an IP; store those as empty.
        if not value:
            return None
        try:
            return str(ipaddress.ip_address(value))
        except ValueError:
            return None


class EventBatch(BaseModel):
    hostname: str = Field(min_length=1, max_length=255)
    os: str | None = Field(default=None, max_length=100)
    events: list[EventIn] = Field(default_factory=list, max_length=config.MAX_BATCH_SIZE)


class BatchResult(BaseModel):
    accepted: int
    duplicates: int


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    agent_id: int
    host: str
    event_time: datetime
    received_at: datetime
    event_type: str
    severity: str
    username: str | None
    source_ip: str | None
    logon_type: str | None
    source_event_id: str | None
    message: str | None


class EventPage(BaseModel):
    total: int
    items: list[EventOut]


class AgentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    hostname: str | None
    os: str | None
    created_at: datetime
    last_seen: datetime | None
