"""Agent API keys: generation, hashing, and request authentication."""
import hashlib
import secrets
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import get_db
from .models import Agent


def generate_api_key() -> str:
    return "sv_" + secrets.token_urlsafe(32)


def hash_api_key(api_key: str) -> str:
    # Keys are long random strings, so a fast hash is enough (unlike user passwords).
    return hashlib.sha256(api_key.encode()).hexdigest()


def get_current_agent(
    x_api_key: Annotated[str | None, Header()] = None,
    db: Session = Depends(get_db),
) -> Agent:
    """Look up the agent that owns the X-API-Key header, or reject the request."""
    if not x_api_key:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing X-API-Key header")
    agent = db.scalar(select(Agent).where(Agent.api_key_hash == hash_api_key(x_api_key)))
    if agent is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid API key")
    return agent
