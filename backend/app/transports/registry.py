from app.transports.azure_logs_ingestion import AzureLogsIngestionTransport
from app.transports.base import Transport
from app.transports.http_webhook import HttpWebhookTransport
from app.transports.syslog_transport import SyslogTransport


class TransportRegistry:
    """Registry of available delivery transports."""

    def __init__(self) -> None:
        self._transports: dict[str, Transport] = {}

    def register(self, transport: Transport) -> None:
        self._transports[transport.transport_id] = transport

    def get(self, transport_id: str) -> Transport | None:
        return self._transports.get(transport_id)

    def list_ids(self) -> list[str]:
        return sorted(self._transports.keys())


transport_registry = TransportRegistry()


def register_default_transports() -> None:
    transport_registry.register(HttpWebhookTransport())
    transport_registry.register(SyslogTransport())
    transport_registry.register(AzureLogsIngestionTransport())
