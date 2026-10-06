from typing import Any

from app.transports.delivery_result import DeliveryResult
from app.transports.http.engine import HttpDeliveryEngine
from app.transports.http.models import HttpDeliveryResult, OutboundHttpRequest


class HttpWebhookTransport:
    """Transport adapter for HTTP webhook delivery."""

    transport_id = "http_webhook"

    def __init__(self, engine: HttpDeliveryEngine | None = None) -> None:
        self._engine = engine or HttpDeliveryEngine()

    async def close(self) -> None:
        await self._engine.close()

    @property
    def engine(self) -> HttpDeliveryEngine:
        return self._engine

    async def deliver(
        self,
        destination: dict[str, Any],
        payload: bytes,
        content_type: str,
        auth_config: dict[str, Any],
    ) -> DeliveryResult:
        request = self._engine.build_request(
            method=destination.get("method", "POST"),
            url=destination["url"],
            headers=destination.get("headers", {}),
            query_params=destination.get("query_params", {}),
            body=payload,
            content_type=content_type,
            auth_config=auth_config,
            timeout_seconds=float(destination.get("timeout_seconds", 30)),
            verify_tls=destination.get("verify_tls", True),
            ca_file=destination.get("ca_file"),
            follow_redirects=destination.get("follow_redirects", True),
            sensitive_header_names=set(destination.get("_sensitive_header_names", [])),
            sensitive_query_names=set(destination.get("_sensitive_query_names", [])),
        )
        result = await self._engine.execute(request)
        return DeliveryResult(
            **{
                **result.model_dump(),
                "delivery_confirmation": "api_accepted",
                "delivery_note": "HTTP acceptance does not confirm remote application processing.",
            }
        )

    async def execute(self, request: OutboundHttpRequest) -> HttpDeliveryResult:
        return await self._engine.execute(request)

    async def test_connection(self, request: OutboundHttpRequest) -> HttpDeliveryResult:
        return await self._engine.test_connection(request)

    async def test_destination(
        self,
        destination: dict[str, Any],
        auth_config: dict[str, Any],
    ) -> DeliveryResult:
        request = self._engine.build_request(
            method=destination.get("method", "HEAD"),
            url=destination.get("url") or "",
            headers=destination.get("headers", {}),
            query_params=destination.get("query_params", {}),
            body=None,
            content_type=None,
            auth_config=auth_config,
            timeout_seconds=float(destination.get("timeout_seconds", 30)),
            verify_tls=destination.get("verify_tls", True),
            ca_file=destination.get("ca_file"),
            follow_redirects=destination.get("follow_redirects", True),
            sensitive_header_names=set(destination.get("_sensitive_header_names", [])),
            sensitive_query_names=set(destination.get("_sensitive_query_names", [])),
        )
        result = await self._engine.test_connection(request)
        return DeliveryResult(
            **{
                **result.model_dump(),
                "delivery_confirmation": "api_accepted",
                "delivery_note": "HTTP acceptance does not confirm remote application processing.",
            }
        )
