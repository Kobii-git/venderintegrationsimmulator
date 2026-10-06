from typing import Any, Protocol

from app.transports.delivery_result import DeliveryResult


class Transport(Protocol):
    """Protocol for outbound delivery transports."""

    transport_id: str

    async def deliver(
        self,
        destination: dict[str, Any],
        payload: bytes,
        content_type: str,
        auth_config: dict[str, Any],
    ) -> DeliveryResult:
        """Deliver payload to destination using transport-specific logic."""
        ...

    async def test_destination(
        self,
        destination: dict[str, Any],
        auth_config: dict[str, Any],
    ) -> DeliveryResult:
        """Exercise the transport's own connection-test semantics."""
        ...
