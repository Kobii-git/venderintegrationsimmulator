from typing import Any

from app.transports.delivery_result import DeliveryResult
from app.transports.syslog.engine import SyslogDeliveryEngine


class SyslogTransport:
    """Vendor-neutral syslog delivery transport."""

    transport_id = "syslog"

    def __init__(self, engine: SyslogDeliveryEngine | None = None) -> None:
        self._engine = engine or SyslogDeliveryEngine()

    async def close(self) -> None:
        await self._engine.close()

    @property
    def engine(self) -> SyslogDeliveryEngine:
        return self._engine

    async def deliver(
        self,
        destination: dict[str, Any],
        payload: bytes,
        content_type: str,
        auth_config: dict[str, Any],
    ) -> DeliveryResult:
        _ = auth_config
        return await self._engine.deliver(destination, payload, content_type)

    async def test_connection(self, destination: dict[str, Any]) -> DeliveryResult:
        return await self._engine.test_connection(destination)

    async def test_destination(
        self,
        destination: dict[str, Any],
        auth_config: dict[str, Any],
    ) -> DeliveryResult:
        _ = auth_config
        return await self._engine.test_connection(destination)
