from app.api.deps import get_http_transport_service, get_transport_delivery_service
from app.schemas.transport import (
    AzureTransportRequest,
    DeliveryResultResponse,
    HttpDeliveryResultResponse,
    HttpSendRequest,
    HttpTestConnectionRequest,
    SyslogTransportRequest,
)
from app.services.transport import HttpTransportService
from app.services.transport_delivery import TransportDeliveryService
from fastapi import APIRouter, Depends

router = APIRouter(prefix="/transport", tags=["transport"])
http_router = APIRouter(prefix="/http", tags=["transport"])
syslog_router = APIRouter(prefix="/syslog", tags=["transport"])


@http_router.post("/test", response_model=HttpDeliveryResultResponse)
async def test_http_connection(
    data: HttpTestConnectionRequest,
    service: HttpTransportService = Depends(get_http_transport_service),
) -> HttpDeliveryResultResponse:
    """Test an HTTP destination and return classified diagnostics."""
    return await service.test_connection(data)


@http_router.post("/send", response_model=HttpDeliveryResultResponse)
async def send_http_request(
    data: HttpSendRequest,
    service: HttpTransportService = Depends(get_http_transport_service),
) -> HttpDeliveryResultResponse:
    """Send a one-off generic HTTP request for diagnostics."""
    return await service.send(data)


@syslog_router.post("/test", response_model=DeliveryResultResponse)
async def test_syslog_connection(
    data: SyslogTransportRequest,
    service: TransportDeliveryService = Depends(get_transport_delivery_service),
) -> DeliveryResultResponse:
    """Test a syslog destination without sending a full scenario payload."""
    destination = data.model_dump(exclude={"message", "content_type"})
    destination["transport_id"] = "syslog"
    result = await service.test_connection("syslog", destination)
    return DeliveryResultResponse.from_delivery_result(result)


@syslog_router.post("/send", response_model=DeliveryResultResponse)
async def send_syslog_message(
    data: SyslogTransportRequest,
    service: TransportDeliveryService = Depends(get_transport_delivery_service),
) -> DeliveryResultResponse:
    """Send a one-off syslog message for diagnostics."""
    destination = data.model_dump(exclude={"message", "content_type"})
    destination["transport_id"] = "syslog"
    result = await service.deliver(
        destination,
        data.message,
        data.content_type,
        {},
    )
    return DeliveryResultResponse.from_delivery_result(result)


router.include_router(http_router)
router.include_router(syslog_router)


@router.post("/azure/test", response_model=DeliveryResultResponse)
async def test_azure_connection(
    data: AzureTransportRequest,
    service: TransportDeliveryService = Depends(get_transport_delivery_service),
) -> DeliveryResultResponse:
    result = await service.test_connection(
        data.destination.transport_id, data.destination.model_dump(), data.auth_config.model_dump()
    )
    return DeliveryResultResponse.from_delivery_result(result)


@router.post("/azure/send", response_model=DeliveryResultResponse)
async def send_azure_test_record(
    data: AzureTransportRequest,
    service: TransportDeliveryService = Depends(get_transport_delivery_service),
) -> DeliveryResultResponse:
    from app.formats.azure_ingestion import validate_record
    from fastapi import HTTPException

    if data.record is None:
        raise HTTPException(status_code=422, detail="An explicit test record is required")
    try:
        validate_record(data.record, data.destination.batch_max_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    result = await service.deliver(
        data.destination.model_dump(),
        [data.record],
        "application/json",
        data.auth_config.model_dump(),
    )
    return DeliveryResultResponse.from_delivery_result(result)
