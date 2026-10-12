"""Authentication for both kinds of callers.

Agents (computers) send an X-API-Key header. Dashboard users sign in with a username
and password and then send "Authorization: Bearer <token>".
"""
import hashlib
import secrets
from datetime import timedelta, timezone
from typing import Annotated

import jwt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import config
from .database import get_db
from .models import Agent, User, utcnow

# --- Agent API keys -------------------------------------------------------------


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
    if agent is None or agent.revoked_at is not None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid API key")
    return agent


# --- Dashboard users ------------------------------------------------------------

_bearer = HTTPBearer(auto_error=False)
_UNAUTHORIZED = HTTPException(
    status.HTTP_401_UNAUTHORIZED,
    "Not signed in or session expired",
    headers={"WWW-Authenticate": "Bearer"},
)


def _password_version(user: User) -> str:
    # Part of the password hash goes into each token, so changing a password
    # signs that user out everywhere.
    return hashlib.sha256(user.password_hash.encode()).hexdigest()[:12]


def create_access_token(user: User) -> str:
    now = utcnow().replace(tzinfo=timezone.utc)
    claims = {
        "sub": str(user.id),
        "role": user.role,
        "pv": _password_version(user),
        "iat": now,
        "exp": now + timedelta(minutes=config.TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(claims, config.get_secret_key(), algorithm="HS256")


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise _UNAUTHORIZED
    try:
        claims = jwt.decode(credentials.credentials, config.get_secret_key(), algorithms=["HS256"])
        user_id = int(claims["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise _UNAUTHORIZED
    # Load the user fresh on every request so disabling an account or changing a
    # role takes effect immediately, not when the token expires.
    user = db.get(User, user_id)
    if user is None or not user.is_active or claims.get("pv") != _password_version(user):
        raise _UNAUTHORIZED
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only administrators can do this")
    return user
