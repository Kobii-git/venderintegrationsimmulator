from app.api.deps import get_inbound_mock_service
from app.services.inbound_mock import InboundMockService
from fastapi import APIRouter, Depends, Request, Response

router = APIRouter(tags=["mock-api"])


@router.api_route(
    "/mock/{product_id}/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"],
)
async def mock_vendor_api(
    product_id: str,
    path: str,
    request: Request,
    service: InboundMockService = Depends(get_inbound_mock_service),
) -> Response:
    """Product-defined mock REST API for pull-based vendor simulation."""
    return await service.handle_request(product_id, path, request)
