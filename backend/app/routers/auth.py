"""Dashboard sign-in, current user, and password change."""
import threading
from collections import defaultdict
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import config
from ..database import get_db
from ..models import User, utcnow
from ..passwords import hash_password, password_problem, verify_password
from ..schemas import LoginIn, PasswordChange, TokenOut, UserOut
from ..security import create_access_token, get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Recent failed sign-ins per username, kept in memory. Enough for a single server;
# a multi-server deployment would keep this in the database or Redis instead.
_failures: dict[str, list[datetime]] = defaultdict(list)
_failures_lock = threading.Lock()

# Used so a wrong username takes as long as a wrong password (no username probing).
_DUMMY_HASH = hash_password("timing-equalizer-not-a-real-password")


def _recent_failures(key: str, now: datetime) -> int:
    cutoff = now - timedelta(minutes=config.LOGIN_LOCKOUT_MINUTES)
    _failures[key] = [t for t in _failures[key] if t > cutoff]
    return len(_failures[key])


def reset_login_failures() -> None:
    with _failures_lock:
        _failures.clear()


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, db: Session = Depends(get_db)) -> TokenOut:
    key = body.username.lower()
    now = utcnow()
    with _failures_lock:
        if _recent_failures(key, now) >= config.LOGIN_MAX_FAILURES:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                f"Too many failed sign-ins. Try again in {config.LOGIN_LOCKOUT_MINUTES} minutes.",
            )

    user = db.scalar(select(User).where(func.lower(User.username) == key))
    valid = verify_password(body.password, user.password_hash if user else _DUMMY_HASH)
    if not (user and valid and user.is_active):
        with _failures_lock:
            _failures[key].append(now)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect username or password")

    with _failures_lock:
        _failures.pop(key, None)
    user.last_login = now
    db.commit()
    return TokenOut(
        access_token=create_access_token(user),
        expires_in=config.TOKEN_EXPIRE_MINUTES * 60,
        user=UserOut.model_validate(user),
    )


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.post("/change-password", response_model=TokenOut)
def change_password(
    body: PasswordChange, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> TokenOut:
    """Change your own password. Returns a fresh token; older tokens stop working."""
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Current password is incorrect")
    if problem := password_problem(body.new_password):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, problem)
    user.password_hash = hash_password(body.new_password)
    db.commit()
    return TokenOut(
        access_token=create_access_token(user),
        expires_in=config.TOKEN_EXPIRE_MINUTES * 60,
        user=UserOut.model_validate(user),
    )
