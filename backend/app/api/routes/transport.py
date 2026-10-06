from app.api.deps import get_http_transport_service, get_transport_delivery_service
from app.schemas.transport import (
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
