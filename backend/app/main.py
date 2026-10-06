import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI

from app import __version__
from app.api.deps import get_product_registry, set_scheduler
from app.api.error_handlers import register_exception_handlers
from app.api.routes import (
    datasets,
    events,
    health,
    inbound,
    mock,
    oauth,
    products,
    simulations,
    transport,
    version,
)
from app.auth_strategies.registry import register_default_auth_strategies
from app.core.config import get_settings
from app.core.database import get_session_factory
from app.core.logging import setup_logging
from app.core.migrations import run_migrations
from app.core.security import get_secret_encryptor
from app.core.spa_static import SPAStaticFiles
from app.models import Simulation
from app.services.configuration_migration import (
    migrate_legacy_configurations,
    preflight_configuration_upgrade,
)
from app.services.delivery_queue import DeliveryQueue
from app.services.retention_cleanup import RetentionCleanupService
from app.services.simulation_orchestrator import (
    build_simulation_scheduler,
    recover_simulations_on_startup,
)
from app.services.targets import update_primary
from app.services.transport_delivery import TransportDeliveryService
from app.transports.registry import register_default_transports, transport_registry


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application startup and shutdown hooks."""
    settings = get_settings()
    settings.ensure_data_dir()
    encryptor = get_secret_encryptor()
    registry = get_product_registry()
    _ = registry.list_products()
    prepared_backup = None
    if os.getenv("TESTING") != "1":
        prepared_backup = preflight_configuration_upgrade(settings, encryptor, registry)
        run_migrations()
    register_default_auth_strategies()
    register_default_transports()
    transport_service = TransportDeliveryService(transport_registry)
    if os.getenv("TESTING") != "1":
        db = get_session_factory()()
        try:
            migrate_legacy_configurations(
                db,
                registry,
                encryptor,
                settings,
                backup_path=prepared_backup,
            )
            for simulation in db.query(Simulation).all():
                update_primary(simulation)
            db.commit()
        finally:
            db.close()
    scheduler = build_simulation_scheduler(registry, transport_service, encryptor)
    set_scheduler(scheduler)
    app.state.simulation_scheduler = scheduler

    if os.getenv("TESTING") != "1":
        scheduler.start(paused=True)
        interrupted, resumed = recover_simulations_on_startup(
            registry, transport_service, encryptor, scheduler
        )
        if interrupted:
            import logging

            logging.getLogger(__name__).warning(
                "Marked %d running simulation(s) as stopped after restart", interrupted
            )
        if resumed:
            import logging

            logging.getLogger(__name__).info("Resumed %d simulation(s) after restart", resumed)
        if settings.event_retention_cleanup_on_startup:
            db = get_session_factory()()
            try:
                RetentionCleanupService(db, settings).cleanup()
            finally:
                db.close()

        def retention_cleanup_job() -> None:
            maintenance_db = get_session_factory()()
            try:
                RetentionCleanupService(maintenance_db, settings).cleanup()
            finally:
                maintenance_db.close()

        scheduler.register_maintenance(
            "retention",
            retention_cleanup_job,
            interval_seconds=settings.event_retention_cleanup_interval_seconds,
        )

        scheduler.resume()
    else:
        scheduler.start()
    queue = DeliveryQueue(registry, transport_service, encryptor)
    app.state.delivery_queue = queue
    if os.getenv("TESTING") != "1":
        queue.start()
    yield
    scheduler.shutdown()
    await queue.close()
    for transport_id in transport_registry.list_ids():
        adapter = transport_registry.get(transport_id)
        close = getattr(adapter, "close", None)
        if close:
            await close()


def create_app() -> FastAPI:
    """Application factory."""
    setup_logging()
    settings = get_settings()

    docs_url = "/api/v1/docs" if settings.enable_openapi_docs else None
    openapi_url = "/api/v1/openapi.json" if settings.enable_openapi_docs else None

    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        docs_url=docs_url,
        redoc_url=None,
        openapi_url=openapi_url,
        lifespan=lifespan,
    )

    register_exception_handlers(app)

    api_v1 = APIRouter(prefix="/api/v1")
    api_v1.include_router(health.router)
    api_v1.include_router(datasets.router)
    api_v1.include_router(version.router)
    api_v1.include_router(products.router)
    api_v1.include_router(simulations.router)
    api_v1.include_router(events.router)
    api_v1.include_router(transport.router)
    api_v1.include_router(mock.router)
    api_v1.include_router(oauth.router)
    api_v1.include_router(inbound.router)
    app.include_router(api_v1)

    static_dir = settings.resolved_static_dir
    if static_dir.is_dir():
        app.mount("/", SPAStaticFiles(directory=str(static_dir), html=True), name="static")

    return app


app = create_app()
