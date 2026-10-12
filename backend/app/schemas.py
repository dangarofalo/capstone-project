"""Request and response shapes for the API (validated by Pydantic)."""
import ipaddress
from datetime import datetime, timezone
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, field_validator

from . import config



def _as_utc_string(value: datetime) -> str:
    """All times are stored as naive UTC; send them with a "Z" so browsers convert correctly."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


UTCDateTime = Annotated[datetime, PlainSerializer(_as_utc_string, return_type=str)]

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
    event_time: UTCDateTime
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
    alerts_created: int = 0


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    agent_id: int
    host: str
    event_time: UTCDateTime
    received_at: UTCDateTime
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


AlertStatus = Literal["open", "acknowledged", "resolved"]
AlertRule = Literal["brute_force", "admin_added", "off_hours_login", "agent_offline"]


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    rule: str
    severity: str
    status: str
    title: str
    description: str
    recommendation: str
    host: str | None
    username: str | None
    source_ip: str | None
    event_count: int
    first_seen: UTCDateTime
    last_seen: UTCDateTime
    created_at: UTCDateTime
    acknowledged_at: UTCDateTime | None
    acknowledged_by: str | None
    resolved_at: UTCDateTime | None
    resolved_by: str | None
    resolution_note: str | None


class AlertDetail(AlertOut):
    events: list[EventOut]


class AlertPage(BaseModel):
    total: int
    items: list[AlertOut]


class AlertSummary(BaseModel):
    open: int
    acknowledged: int
    resolved: int
    active_by_severity: dict[str, int]  # open + acknowledged, per severity


class AlertAction(BaseModel):
    note: str | None = Field(default=None, max_length=1000)


class AgentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    hostname: str | None
    os: str | None
    created_at: UTCDateTime
    last_seen: UTCDateTime | None
    revoked_at: UTCDateTime | None
    status: Literal["online", "offline", "never_reported", "revoked"] = "never_reported"


class AgentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9 ._-]+$")


class AgentKeyOut(BaseModel):
    """Returned once when a computer is added or its key is replaced."""

    agent: AgentOut
    api_key: str


# --- Users and login ----------------------------------------------------------------

Role = Literal["admin", "viewer"]
USERNAME_PATTERN = r"^[A-Za-z0-9._-]+$"


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=200)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    role: str
    is_active: bool
    created_at: UTCDateTime
    last_login: UTCDateTime | None


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
    user: UserOut


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50, pattern=USERNAME_PATTERN)
    password: str = Field(min_length=1, max_length=200)
    role: Role = "viewer"


class UserUpdate(BaseModel):
    role: Role | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=1, max_length=200)


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=1, max_length=200)


# --- Dashboard statistics -------------------------------------------------------------


class NameCount(BaseModel):
    name: str
    count: int


class Timeline(BaseModel):
    bucket: Literal["hour", "day"]
    labels: list[UTCDateTime]  # start of each bucket, UTC
    series: dict[str, list[int]]  # event type -> count per bucket


class Overview(BaseModel):
    range_hours: int
    start: UTCDateTime
    end: UTCDateTime
    totals: dict[str, int]
    agents: dict[str, int]
    severity_counts: dict[str, int]
    event_type_counts: dict[str, int]
    timeline: Timeline
    top_failed_users: list[NameCount]
    top_failed_ips: list[NameCount]
    top_hosts: list[NameCount]
