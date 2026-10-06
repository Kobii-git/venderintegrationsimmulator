from app.api.deps import get_inbound_mock_service
from app.core.exceptions import NotFoundError
from app.schemas.inbound import InboundRequestDetailResponse, InboundRequestSummaryResponse
from app.services.inbound_mock import InboundMockService
from fastapi import APIRouter, Depends, Query

router = APIRouter(prefix="/inbound-requests", tags=["mock-api"])


@router.get("", response_model=list[InboundRequestSummaryResponse])
def list_all_inbound_requests(
    limit: int = Query(default=100, ge=1, le=500),
    simulation_id: str | None = Query(default=None),
    request_kind: str | None = Query(default=None),
    response_status: int | None = Query(default=None, ge=100, le=599),
    service: InboundMockService = Depends(get_inbound_mock_service),
) -> list[InboundRequestSummaryResponse]:
    return [
        InboundRequestSummaryResponse.model_validate(item)
        for item in service.list_all_requests(
            limit=limit,
            simulation_id=simulation_id,
            request_kind=request_kind,
            response_status=response_status,
        )
    ]


@router.get("/{request_id}", response_model=InboundRequestDetailResponse)
def get_any_inbound_request(
    request_id: str,
    service: InboundMockService = Depends(get_inbound_mock_service),
) -> InboundRequestDetailResponse:
    log = service.get_request_any(request_id)
    if log is None:
        raise NotFoundError(f"Inbound request not found: {request_id}")
    return InboundRequestDetailResponse.model_validate(log)
