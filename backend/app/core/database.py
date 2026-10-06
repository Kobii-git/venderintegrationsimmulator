from collections.abc import Generator
from functools import lru_cache
from typing import Any

from app.core.config import get_settings
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for ORM models."""


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    engine = create_engine(
        settings.resolved_database_url,
        connect_args={"check_same_thread": False},
        echo=settings.debug,
    )
    if engine.dialect.name == "sqlite":

        @event.listens_for(engine, "connect")
        def configure_sqlite(dbapi_connection: Any, _connection_record: Any) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()

    return engine


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(autocommit=False, autoflush=False, bind=get_engine())


def get_db() -> Generator[Session, None, None]:
    """Yield a database session for request scope."""
    session_factory = get_session_factory()
    db = session_factory()
    try:
        yield db
    finally:
        db.close()


def reset_database_state() -> None:
    """Clear cached engine/session (for tests)."""
    if get_engine.cache_info().currsize:
        get_engine().dispose()
    get_engine.cache_clear()
    get_session_factory.cache_clear()
