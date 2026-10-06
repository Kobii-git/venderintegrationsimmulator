from functools import lru_cache

from app.core.config import get_settings, settings
from app.core.database import get_db
from app.core.security import SecretEncryptor, get_secret_encryptor
from app.inbound.oauth import OAuthTokenService
from app.products.registry import ProductRegistry
from app.repositories.simulation import SimulationRepository
from app.services.event_delivery import EventDeliveryService
from app.services.inbound_mock import InboundMockService
from app.services.product import ProductCatalogService
from app.services.simulation import SimulationService
from app.services.simulation_export import SimulationExportService
from app.services.simulation_orchestrator import SimulationOrchestrator, build_simulation_scheduler
from app.services.simulation_runtime import SimulationRuntimeService
from app.services.simulation_scheduler import SimulationScheduler
from app.services.transport import HttpTransportService
from app.services.transport_delivery import TransportDeliveryService
from app.transports.http_webhook import HttpWebhookTransport
from app.transports.registry import transport_registry
from fastapi import Depends, Request
from sqlalchemy.orm import Session

_scheduler: SimulationScheduler | None = None


def get_scheduler() -> SimulationScheduler:
    global _scheduler
    if _scheduler is None:
        registry = get_product_registry()
        transport = get_transport_delivery_service()
        encryptor = get_secret_encryptor()
        _scheduler = build_simulation_scheduler(registry, transport, encryptor)
    return _scheduler


def set_scheduler(scheduler: SimulationScheduler) -> None:
    global _scheduler
    _scheduler = scheduler


@lru_cache
def get_product_registry() -> ProductRegistry:
    """Return singleton product registry (loaded at startup)."""
    registry = ProductRegistry(settings.resolved_products_dir)
    registry.load_all()
    return registry


def get_encryptor() -> SecretEncryptor:
    get_settings().ensure_data_dir()
    return get_secret_encryptor()


def get_simulation_service(
    db: Session = Depends(get_db),
    product_registry: ProductRegistry = Depends(get_product_registry),
    encryptor: SecretEncryptor = Depends(get_encryptor),
) -> SimulationService:
    return SimulationService(db, product_registry, encryptor)


def get_product_catalog_service(
    product_registry: ProductRegistry = Depends(get_product_registry),
) -> ProductCatalogService:
    return ProductCatalogService(product_registry)


def get_http_transport_service() -> HttpTransportService:
    return HttpTransportService(transport=HttpWebhookTransport())


def get_transport_delivery_service() -> TransportDeliveryService:
    return TransportDeliveryService(transport_registry)


def get_event_delivery_service(
    product_registry: ProductRegistry = Depends(get_product_registry),
    transport_service: TransportDeliveryService = Depends(get_transport_delivery_service),
) -> EventDeliveryService:
    return EventDeliveryService(product_registry, transport_service)


def get_simulation_runtime_service(
    db: Session = Depends(get_db),
    product_registry: ProductRegistry = Depends(get_product_registry),
    transport_service: TransportDeliveryService = Depends(get_transport_delivery_service),
    encryptor: SecretEncryptor = Depends(get_encryptor),
) -> SimulationRuntimeService:
    return SimulationRuntimeService(db, product_registry, transport_service, encryptor)


def get_simulation_orchestrator(
    request: Request,
    db: Session = Depends(get_db),
    product_registry: ProductRegistry = Depends(get_product_registry),
    transport_service: TransportDeliveryService = Depends(get_transport_delivery_service),
    encryptor: SecretEncryptor = Depends(get_encryptor),
) -> SimulationOrchestrator:
    scheduler: SimulationScheduler = request.app.state.simulation_scheduler
    return SimulationOrchestrator(db, product_registry, transport_service, encryptor, scheduler)


def get_simulation_export_service(
    db: Session = Depends(get_db),
    catalog: SimulationService = Depends(get_simulation_service),
    encryptor: SecretEncryptor = Depends(get_encryptor),
) -> SimulationExportService:
    return SimulationExportService(SimulationRepository(db), catalog, encryptor)


def get_inbound_mock_service(
    db: Session = Depends(get_db),
    product_registry: ProductRegistry = Depends(get_product_registry),
    encryptor: SecretEncryptor = Depends(get_encryptor),
) -> InboundMockService:
    return InboundMockService(db, product_registry, encryptor)


def get_oauth_token_service(
    db: Session = Depends(get_db),
    encryptor: SecretEncryptor = Depends(get_encryptor),
) -> OAuthTokenService:
    return OAuthTokenService(db, encryptor)
