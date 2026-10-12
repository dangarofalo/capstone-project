import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import config
from app import models  # noqa: F401  (registers tables)
from app.database import Base, get_db
from app.main import app
from app.models import Agent, User
from app.passwords import hash_password
from app.routers.auth import reset_login_failures
from app.security import create_access_token, generate_api_key, hash_api_key

PASSWORD = "Correct-horse-9"


@pytest.fixture(autouse=True)
def test_settings(monkeypatch):
    monkeypatch.setattr(config, "PASSWORD_ITERATIONS", 1_000)  # fast hashing in tests
    monkeypatch.setattr(config, "SECRET_KEY", "test-secret-key-not-for-production-use")
    reset_login_failures()


@pytest.fixture
def db_session():
    """A fresh in-memory database for every test."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False)
    session = TestingSession()
    yield session
    session.close()
    engine.dispose()


def make_user(db, username: str, role: str = "viewer", password: str = PASSWORD) -> User:
    user = User(username=username, password_hash=hash_password(password), role=role)
    db.add(user)
    db.commit()
    return user


@pytest.fixture
def admin_user(db_session) -> User:
    return make_user(db_session, "admin", "admin")


@pytest.fixture
def viewer_user(db_session) -> User:
    return make_user(db_session, "viewer", "viewer")


def _client_for(db_session, user: User | None = None) -> TestClient:
    app.dependency_overrides[get_db] = lambda: db_session
    test_client = TestClient(app)
    if user:
        test_client.headers["Authorization"] = f"Bearer {create_access_token(user)}"
    return test_client


@pytest.fixture
def anon_client(db_session):
    """Not signed in."""
    yield _client_for(db_session)
    app.dependency_overrides.clear()


@pytest.fixture
def client(db_session, admin_user):
    """Signed in as an admin (most tests)."""
    yield _client_for(db_session, admin_user)
    app.dependency_overrides.clear()


@pytest.fixture
def viewer_client(db_session, viewer_user):
    """Signed in as a read-only viewer."""
    yield _client_for(db_session, viewer_user)
    app.dependency_overrides.clear()


@pytest.fixture
def api_key(db_session) -> str:
    key = generate_api_key()
    db_session.add(Agent(name="test-agent", api_key_hash=hash_api_key(key)))
    db_session.commit()
    return key
