"""SQLAlchemy engine + session factory."""

from __future__ import annotations

import os
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from athletiq.db.models import Base

_DEFAULT_URL = "sqlite:///./athletiq.db"


def _make_engine(url: str | None = None) -> Engine:
    url = url or os.getenv("DATABASE_URL", _DEFAULT_URL)
    # SQLite needs check_same_thread=False when used with FastAPI's threadpool.
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, future=True, connect_args=connect_args)


engine: Engine = _make_engine()
SessionLocal: sessionmaker[Session] = sessionmaker(
    bind=engine, autoflush=False, autocommit=False, future=True
)


def init_db() -> None:
    """Create tables if they don't exist. Idempotent."""
    Base.metadata.create_all(bind=engine)


def reset_engine(url: str | None = None) -> None:
    """Swap the engine (used by tests to point at an in-memory SQLite DB)."""
    global engine, SessionLocal
    engine.dispose()
    engine = _make_engine(url)
    SessionLocal.configure(bind=engine)


def get_db() -> Iterator[Session]:
    """FastAPI dependency yielding a per-request session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
