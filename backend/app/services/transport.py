from typing import Any

from app.core.security import SecretEncryptor
from app.schemas.transport import (
    HttpDeliveryResultResponse,
    HttpSendRequest,
    HttpTestConnectionRequest,
)
from app.transports.http.engine import encode_json_body
from app.transports.http.models import HttpDeliveryResult, OutboundHttpRequest
from app.transports.http_webhook import HttpWebhookTransport


class HttpTransportService:
    """Service layer for HTTP transport operations."""

    def __init__(
        self,
        transport: HttpWebhookTransport | None = None,
        encryptor: SecretEncryptor | None = None,
    ) -> None:
        self._transport = transport or HttpWebhookTransport()
        self._engine = self._transport.engine
        self._encryptor = encryptor

    async def test_connection(self, data: HttpTestConnectionRequest) -> HttpDeliveryResultResponse:
        request = self._build_request(data)
        result = await self._transport.test_connection(request)
        return self._to_response(result)

    async def send(self, data: HttpSendRequest) -> HttpDeliveryResultResponse:
        result = await self.send_raw(data)
        return self._to_response(result)

    async def send_raw(self, data: HttpSendRequest) -> HttpDeliveryResult:
        request = self._build_request(data)
        return await self._transport.execute(request)

    def _build_request(
        self,
        data: HttpTestConnectionRequest | HttpSendRequest,
    ) -> OutboundHttpRequest:
        body = self._encode_body(data.body, data.content_type, data.method)
        auth_config = self._resolve_auth_config(data.auth_config.model_dump(exclude_none=True))
        return self._engine.build_request(
            method=data.method,
            url=data.url,
            headers=data.headers,
            query_params=data.query_params,
            body=body,
            content_type=data.content_type if body is not None else None,
            auth_config=auth_config,
            timeout_seconds=float(data.timeout_seconds),
            verify_tls=data.verify_tls,
            follow_redirects=data.follow_redirects,
            sensitive_header_names=set(data.sensitive_header_names),
            sensitive_query_names=set(data.sensitive_query_names),
        )

    def _encode_body(self, body: Any, content_type: str, method: str) -> bytes | None:
        if method in {"GET", "HEAD"} or body is None:
            return None
        if isinstance(body, dict | list):
            return encode_json_body(body)
        if isinstance(body, str):
            return body.encode("utf-8")
        if isinstance(body, bytes):
            return body
        raise ValueError("Unsupported body type")

    def _resolve_auth_config(self, auth_config: dict[str, Any]) -> dict[str, Any]:
        return auth_config

    def _to_response(self, result: HttpDeliveryResult) -> HttpDeliveryResultResponse:
        return HttpDeliveryResultResponse(
            success=result.success,
            reached_server=result.reached_server,
            started_at=result.started_at.isoformat(),
            completed_at=result.completed_at.isoformat(),
            latency_ms=result.latency_ms,
            destination=result.destination,
            method=result.method,
            request_headers_redacted=result.request_headers_redacted,
            request_body=result.request_body,
            response_status_code=result.response_status_code,
            response_headers_redacted=result.response_headers_redacted,
            response_body=result.response_body,
            error_message=result.error_message,
            error_category=result.error_category,
            delivery_confirmation=result.delivery_confirmation,
            delivery_note=result.delivery_note,
        )
