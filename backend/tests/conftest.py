import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401  (registers tables)
from app.database import Base, get_db
from app.main import app
from app.models import Agent
from app.security import generate_api_key, hash_api_key


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


@pytest.fixture
def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def api_key(db_session) -> str:
    key = generate_api_key()
    db_session.add(Agent(name="test-agent", api_key_hash=hash_api_key(key)))
    db_session.commit()
    return key
