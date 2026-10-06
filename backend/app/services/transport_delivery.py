import json
from typing import Any

from app.core.exceptions import ValidationAppError
from app.core.security import SecretEncryptor
from app.transports.delivery_result import DeliveryResult
from app.transports.http.engine import encode_json_body
from app.transports.registry import TransportRegistry


class TransportDeliveryService:
    """Dispatch outbound delivery to the configured transport."""

    def __init__(
        self,
        registry: TransportRegistry,
        encryptor: SecretEncryptor | None = None,
    ) -> None:
        self._registry = registry
        self._encryptor = encryptor

    async def deliver(
        self,
        destination: dict[str, Any],
        payload: Any | None,
        content_type: str,
        auth_config: dict[str, Any],
    ) -> DeliveryResult:
        transport_id = destination.get("transport_id", "http_webhook")
        transport = self._registry.get(transport_id)
        if transport is None:
            raise ValidationAppError(
                f"Unknown transport '{transport_id}'",
                details={"supported_transports": self._registry.list_ids()},
            )

        body = self._encode_payload(payload, content_type)
        return await transport.deliver(destination, body, content_type, auth_config)

    async def test_connection(
        self,
        transport_id: str,
        destination: dict[str, Any],
        auth_config: dict[str, Any] | None = None,
    ) -> DeliveryResult:
        transport = self._registry.get(transport_id)
        if transport is None:
            raise ValidationAppError(f"Unknown transport '{transport_id}'")

        return await transport.test_destination(destination, auth_config or {})

    def _encode_payload(self, payload: Any | None, content_type: str) -> bytes:
        if payload is None:
            return b""
        if isinstance(payload, bytes):
            return payload
        if isinstance(payload, str):
            return payload.encode("utf-8")
        if isinstance(payload, list):
            return encode_json_body(payload)
        if isinstance(payload, dict):
            if content_type == "application/json":
                return encode_json_body(payload)
            if "_syslog_message" in payload:
                return str(payload["_syslog_message"]).encode("utf-8")
            return json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        raise ValueError("Unsupported payload type for delivery")
