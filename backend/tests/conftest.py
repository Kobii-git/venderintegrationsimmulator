import app.models  # noqa: F401
import pytest
from app.api.deps import get_product_registry
from app.core.config import get_settings
from app.core.database import Base, get_db, reset_database_state
from app.core.migrations import run_migrations
from app.main import create_app
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from tests.asgi_client import ASGITestClient


@pytest.fixture
def test_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("TESTING", "1")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/test.db")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-for-encryption-only")
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    get_settings.cache_clear()
    reset_database_state()
    yield get_settings()
    get_settings.cache_clear()
    reset_database_state()
    get_product_registry.cache_clear()


@pytest.fixture
def db_engine(test_settings):
    run_migrations()
    engine = create_engine(
        test_settings.resolved_database_url,
        connect_args={"check_same_thread": False},
    )
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture
def products_directory(test_settings):
    from pathlib import Path

    return Path(test_settings.resolved_products_dir)


@pytest.fixture
def client(test_settings, db_engine):
    session_factory = sessionmaker(bind=db_engine)

    def override_get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    get_product_registry.cache_clear()
    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    with ASGITestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    get_product_registry.cache_clear()


@pytest.fixture
def runtime_client(test_settings, db_engine):
    session_factory = sessionmaker(bind=db_engine)

    def override_get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    get_product_registry.cache_clear()
    get_settings.cache_clear()
    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    with ASGITestClient(app) as test_client:
        yield test_client, app
    app.dependency_overrides.clear()
    get_product_registry.cache_clear()
