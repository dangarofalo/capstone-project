"""Database engine, session factory, and table creation."""
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from . import config

_connect_args = {"check_same_thread": False} if config.DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(config.DATABASE_URL, connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency that yields a database session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Columns added after a table first shipped. create_all() only creates missing tables,
# so older databases get these added with ALTER TABLE on startup.
ADDED_COLUMNS = {
    "agents": {"revoked_at": "TIMESTAMP"},
    "alerts": {"acknowledged_by": "VARCHAR(50)", "resolved_by": "VARCHAR(50)"},
}


def add_missing_columns(target=None) -> None:
    target = target or engine
    inspector = inspect(target)
    with target.begin() as conn:
        for table, columns in ADDED_COLUMNS.items():
            if not inspector.has_table(table):
                continue
            existing = {c["name"] for c in inspector.get_columns(table)}
            for name, sql_type in columns.items():
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {sql_type}"))


def init_db() -> None:
    from . import models  # noqa: F401  (registers the tables on Base)

    Base.metadata.create_all(bind=engine)
    add_missing_columns()
