from app.api.deps import get_event_delivery_service, get_product_catalog_service
from app.core.exceptions import NotFoundError
from app.schemas.event import (
    ScenarioPreviewRequest,
    ScenarioPreviewResponse,
    ScenarioSendRequest,
    ScenarioSendResponse,
)
from app.schemas.product import (
    ProductDetailResponse,
    ProductSummaryResponse,
    ScenarioDetailResponse,
    ScenarioSummaryResponse,
)
from app.services.event_delivery import EventDeliveryService
from app.services.product import ProductCatalogService
from fastapi import APIRouter, Depends

router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=list[ProductSummaryResponse])
def list_products(
    service: ProductCatalogService = Depends(get_product_catalog_service),
) -> list[ProductSummaryResponse]:
    """List all installed product modules."""
    return service.list_products()


@router.get("/{product_id}", response_model=ProductDetailResponse)
def get_product(
    product_id: str,
    service: ProductCatalogService = Depends(get_product_catalog_service),
) -> ProductDetailResponse:
    """Get product metadata including supported capabilities and scenario list."""
    product = service.get_product(product_id)
    if product is None:
        raise NotFoundError(f"Product not found: {product_id}")
    return product


@router.get("/{product_id}/scenarios", response_model=list[ScenarioSummaryResponse])
def list_scenarios(
    product_id: str,
    service: ProductCatalogService = Depends(get_product_catalog_service),
) -> list[ScenarioSummaryResponse]:
    """List scenarios available for a product."""
    scenarios = service.list_scenarios(product_id)
    if scenarios is None:
        raise NotFoundError(f"Product not found: {product_id}")
    return scenarios


@router.get("/{product_id}/scenarios/{scenario_id}", response_model=ScenarioDetailResponse)
def get_scenario(
    product_id: str,
    scenario_id: str,
    service: ProductCatalogService = Depends(get_product_catalog_service),
) -> ScenarioDetailResponse:
    """Get scenario metadata for dynamic UI configuration."""
    scenario = service.get_scenario(product_id, scenario_id)
    if scenario is None:
        raise NotFoundError(f"Scenario not found: {product_id}/{scenario_id}")
    return scenario


@router.post(
    "/{product_id}/scenarios/{scenario_id}/preview",
    response_model=ScenarioPreviewResponse,
)
def preview_scenario(
    product_id: str,
    scenario_id: str,
    request: ScenarioPreviewRequest,
    service: EventDeliveryService = Depends(get_event_delivery_service),
) -> ScenarioPreviewResponse:
    """Generate a scenario payload without sending it."""
    preview = service.preview(product_id, scenario_id, request)
    if preview is None:
        raise NotFoundError(f"Scenario not found: {product_id}/{scenario_id}")
    return preview


@router.post(
    "/{product_id}/scenarios/{scenario_id}/send",
    response_model=ScenarioSendResponse,
)
async def send_scenario(
    product_id: str,
    scenario_id: str,
    request: ScenarioSendRequest,
    service: EventDeliveryService = Depends(get_event_delivery_service),
) -> ScenarioSendResponse:
    """Generate (or override) a scenario payload and deliver it once."""
    result = await service.send(product_id, scenario_id, request)
    if result is None:
        raise NotFoundError(f"Scenario not found: {product_id}/{scenario_id}")
    return result
