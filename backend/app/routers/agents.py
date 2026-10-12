"""Monitored computers: list them (everyone) and add, re-key, or revoke them (admins)."""
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import config
from ..database import get_db
from ..models import Agent, utcnow
from ..schemas import AgentCreate, AgentKeyOut, AgentOut
from ..security import generate_api_key, get_current_user, hash_api_key, require_admin

router = APIRouter(prefix="/api/agents", tags=["agents"], dependencies=[Depends(get_current_user)])


def agent_status(agent: Agent, now: datetime) -> str:
    if agent.revoked_at:
        return "revoked"
    if agent.last_seen is None:
        return "never_reported"
    if agent.last_seen >= now - timedelta(minutes=config.AGENT_OFFLINE_MINUTES):
        return "online"
    return "offline"


def to_out(agent: Agent, now: datetime | None = None) -> AgentOut:
    out = AgentOut.model_validate(agent)
    out.status = agent_status(agent, now or utcnow())
    return out


@router.get("", response_model=list[AgentOut])
def list_agents(db: Session = Depends(get_db)) -> list[AgentOut]:
    now = utcnow()
    return [to_out(a, now) for a in db.scalars(select(Agent).order_by(Agent.name))]


@router.post("", response_model=AgentKeyOut, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_admin)])
def create_agent(body: AgentCreate, db: Session = Depends(get_db)) -> AgentKeyOut:
    """Register a computer. The API key is shown only in this response."""
    name = body.name.strip()
    if db.scalar(select(Agent).where(Agent.name == name)):
        raise HTTPException(status.HTTP_409_CONFLICT, "A computer with that name already exists")
    api_key = generate_api_key()
    agent = Agent(name=name, api_key_hash=hash_api_key(api_key))
    db.add(agent)
    db.commit()
    return AgentKeyOut(agent=to_out(agent), api_key=api_key)


def _get_agent(db: Session, agent_id: int) -> Agent:
    agent = db.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Computer not found")
    return agent


@router.post("/{agent_id}/rotate-key", response_model=AgentKeyOut, dependencies=[Depends(require_admin)])
def rotate_key(agent_id: int, db: Session = Depends(get_db)) -> AgentKeyOut:
    """Issue a new key (the old one stops working). Also re-enables a revoked computer."""
    agent = _get_agent(db, agent_id)
    api_key = generate_api_key()
    agent.api_key_hash = hash_api_key(api_key)
    agent.revoked_at = None
    db.commit()
    return AgentKeyOut(agent=to_out(agent), api_key=api_key)


@router.post("/{agent_id}/revoke", response_model=AgentOut, dependencies=[Depends(require_admin)])
def revoke(agent_id: int, db: Session = Depends(get_db)) -> AgentOut:
    """Stop accepting events from this computer. Its past events are kept."""
    agent = _get_agent(db, agent_id)
    agent.revoked_at = utcnow()
    # Replace the stored hash too, so the old key can never match again.
    agent.api_key_hash = hash_api_key("revoked-" + secrets.token_urlsafe(32))
    db.commit()
    return to_out(agent)
