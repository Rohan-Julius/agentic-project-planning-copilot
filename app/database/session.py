"""SQLite engine/session setup, driven by Settings.sqlite_url (spec §15)."""
from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    connect_args = {"check_same_thread": False} if "sqlite" in settings.sqlite_url else {}
    return create_engine(settings.sqlite_url, connect_args=connect_args)


@lru_cache
def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, autocommit=False)


def get_session() -> Iterator[Session]:
    """FastAPI dependency: yields a Session, closes it after the request."""
    session = get_sessionmaker()()
    try:
        yield session
    finally:
        session.close()


def init_db() -> None:
    """Create all tables. Called on app startup / test setup."""
    from app.models.base import Base  # noqa: PLC0415 — avoid import cycle at module load

    Base.metadata.create_all(bind=get_engine())
