"""Managing dashboard users (administrators only)."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..passwords import hash_password, password_problem
from ..schemas import UserCreate, UserOut, UserUpdate
from ..security import require_admin

router = APIRouter(prefix="/api/users", tags=["users"], dependencies=[Depends(require_admin)])


def _check_password(password: str) -> None:
    if problem := password_problem(password):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, problem)


def _active_admin_count(db: Session) -> int:
    return db.scalar(
        select(func.count()).select_from(User).where(User.role == "admin", User.is_active.is_(True))
    )


@router.get("", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db)) -> list[User]:
    return db.scalars(select(User).order_by(User.username)).all()


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(body: UserCreate, db: Session = Depends(get_db)) -> User:
    if db.scalar(select(User).where(func.lower(User.username) == body.username.lower())):
        raise HTTPException(status.HTTP_409_CONFLICT, "That username is already taken")
    _check_password(body.password)
    user = User(username=body.username, password_hash=hash_password(body.password), role=body.role)
    db.add(user)
    db.commit()
    return user


def _get_user(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return user


@router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    body: UserUpdate,
    db: Session = Depends(get_db),
    current: User = Depends(require_admin),
) -> User:
    """Change a user's role, enable/disable them, or reset their password."""
    user = _get_user(db, user_id)
    losing_admin = user.role == "admin" and user.is_active and (
        (body.role is not None and body.role != "admin") or body.is_active is False
    )
    if losing_admin:
        if user.id == current.id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "You can't remove your own admin access")
        if _active_admin_count(db) <= 1:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "There must be at least one active admin")

    if body.role is not None:
        user.role = body.role
    if body.is_active is not None:
        user.is_active = body.is_active
    if body.password is not None:
        _check_password(body.password)
        user.password_hash = hash_password(body.password)  # also signs them out
    db.commit()
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int, db: Session = Depends(get_db), current: User = Depends(require_admin)
) -> None:
    user = _get_user(db, user_id)
    if user.id == current.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You can't delete your own account")
    if user.role == "admin" and user.is_active and _active_admin_count(db) <= 1:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "There must be at least one active admin")
    db.delete(user)
    db.commit()
