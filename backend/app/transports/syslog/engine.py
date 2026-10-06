import asyncio
import socket
import ssl
from datetime import UTC, datetime
from typing import Any

from app.domain.enums import DeliveryErrorCategory
from app.transports.delivery_result import DeliveryResult
from app.transports.syslog.formats import format_syslog_message, frame_message
from app.transports.syslog.models import SyslogDestination
from app.transports.syslog.rate_limiter import SyslogRateLimiter


class SyslogDeliveryEngine:
    """Send syslog messages over UDP, TCP, or TLS."""

    UDP_BEST_EFFORT_NOTE = (
        "UDP delivery is best-effort. A successful send only means the packet was "
        "handed to the local network stack; it does not confirm remote receipt."
    )
    TCP_ACCEPTED_NOTE = (
        "TCP/TLS delivery accepted the message at the transport layer. Remote "
        "application processing is not verified."
    )
    UDP_TEST_NOTE = "Local UDP transport ready; remote receiver not verified."

    def __init__(self, rate_limiter: SyslogRateLimiter | None = None) -> None:
        self._rate_limiter = rate_limiter or SyslogRateLimiter()
        self._writers: dict[tuple[Any, ...], asyncio.StreamWriter] = {}
        self._locks: dict[tuple[Any, ...], asyncio.Lock] = {}

    async def close(self) -> None:
        writers = list(self._writers.values())
        self._writers.clear()
        for writer in writers:
            writer.close()

        async def finish(writer: asyncio.StreamWriter) -> None:
            try:
                await asyncio.wait_for(writer.wait_closed(), 2)
            except (TimeoutError, OSError):
                writer.transport.abort()

        await asyncio.gather(*(finish(writer) for writer in writers), return_exceptions=True)

    def parse_destination(self, destination: dict[str, Any]) -> SyslogDestination:
        return SyslogDestination(
            host=str(destination["host"]),
            port=int(destination.get("port", 514)),
            protocol=destination.get("protocol", "udp"),
            format=destination.get("format", "rfc5424"),
            facility=int(destination.get("facility", 16)),
            severity=int(destination.get("severity", 6)),
            syslog_hostname=destination.get("syslog_hostname"),
            app_name=destination.get("app_name", "integration-simulator"),
            proc_id=destination.get("proc_id", "-"),
            msg_id=destination.get("msg_id", "-"),
            tcp_framing=destination.get("tcp_framing", "newline"),
            rate_limit_per_second=destination.get("rate_limit_per_second"),
            timeout_seconds=float(destination.get("timeout_seconds", 10)),
            verify_tls=destination.get("verify_tls", True),
            ca_file=destination.get("ca_file"),
        )

    async def deliver(
        self,
        destination: dict[str, Any],
        payload: bytes,
        content_type: str,
    ) -> DeliveryResult:
        started_at = datetime.now(UTC)
        config = self.parse_destination(destination)
        message = format_syslog_message(payload, content_type, config)
        framed = frame_message(
            message, config.tcp_framing if config.protocol != "udp" else "newline"
        )
        rate_key = f"{config.protocol}:{config.host}:{config.port}"
        await self._rate_limiter.wait(rate_key, config.rate_limit_per_second)

        metadata = {
            "format": config.format,
            "facility": str(config.facility),
            "severity": str(config.severity),
            "protocol": config.protocol,
            "tcp_framing": config.tcp_framing,
            "bytes_sent": str(len(framed)),
        }

        try:
            if config.protocol == "udp":
                return await self._deliver_udp(config, framed, message, metadata, started_at)
            if config.protocol == "tcp":
                return await self._deliver_tcp(
                    config, framed, message, metadata, started_at, use_tls=False
                )
            return await self._deliver_tcp(
                config, framed, message, metadata, started_at, use_tls=True
            )
        except TimeoutError:
            return self._failure(
                config,
                message,
                metadata,
                started_at,
                reached_server=False,
                error_message="Syslog delivery timed out",
                error_category=DeliveryErrorCategory.CONNECTION_TIMEOUT.value,
                confirmation="best_effort" if config.protocol == "udp" else "transport_accepted",
            )
        except OSError as exc:
            category = self._categorize_os_error(exc)
            return self._failure(
                config,
                message,
                metadata,
                started_at,
                reached_server=False,
                error_message=str(exc),
                error_category=category,
                confirmation="best_effort" if config.protocol == "udp" else "transport_accepted",
            )

    async def test_connection(self, destination: dict[str, Any]) -> DeliveryResult:
        config = self.parse_destination(destination)
        started_at = datetime.now(UTC)
        metadata = {
            "format": config.format,
            "protocol": config.protocol,
            "test": "true",
        }
        try:
            if config.protocol == "udp":
                transport, _protocol = await self._open_udp_endpoint(config)
                transport.close()
                completed_at = datetime.now(UTC)
                return DeliveryResult(
                    success=True,
                    reached_server=False,
                    started_at=started_at,
                    completed_at=completed_at,
                    latency_ms=self._latency_ms(started_at, completed_at),
                    destination=config.summary,
                    method="UDP",
                    request_headers_redacted=metadata,
                    request_body="(connection test — no message sent)",
                    delivery_confirmation="best_effort",
                    delivery_note=self.UDP_TEST_NOTE,
                )
            writer = None
            try:
                async with asyncio.timeout(config.timeout_seconds):
                    _reader, writer = await self._open_tcp_connection(
                        config, use_tls=config.protocol == "tls"
                    )
                    writer.close()
                    await writer.wait_closed()
            except BaseException:
                if writer is not None:
                    writer.close()
                    writer.transport.abort()
                raise
            completed_at = datetime.now(UTC)
            return DeliveryResult(
                success=True,
                reached_server=True,
                started_at=started_at,
                completed_at=completed_at,
                latency_ms=self._latency_ms(started_at, completed_at),
                destination=config.summary,
                method=config.protocol.upper(),
                request_headers_redacted=metadata,
                request_body="(connection test — no message sent)",
                delivery_confirmation="transport_accepted",
                delivery_note=self.TCP_ACCEPTED_NOTE,
            )
        except Exception as exc:
            return self._failure(
                config,
                "(connection test)",
                metadata,
                started_at,
                reached_server=False,
                error_message=str(exc),
                error_category=self._categorize_os_error(exc)
                if isinstance(exc, OSError)
                else DeliveryErrorCategory.CONNECTION.value,
                confirmation="best_effort" if config.protocol == "udp" else "transport_accepted",
            )

    async def _deliver_udp(
        self,
        config: SyslogDestination,
        framed: bytes,
        message: str,
        metadata: dict[str, str],
        started_at: datetime,
    ) -> DeliveryResult:
        transport, _protocol = await self._open_udp_endpoint(config)
        try:
            transport.sendto(framed)
            await asyncio.sleep(0)
        finally:
            transport.close()
        completed_at = datetime.now(UTC)
        return DeliveryResult(
            success=True,
            reached_server=False,
            started_at=started_at,
            completed_at=completed_at,
            latency_ms=self._latency_ms(started_at, completed_at),
            destination=config.summary,
            method="UDP",
            request_headers_redacted=metadata,
            request_body=message,
            delivery_confirmation="best_effort",
            delivery_note=self.UDP_BEST_EFFORT_NOTE,
        )

    async def _deliver_tcp(
        self,
        config: SyslogDestination,
        framed: bytes,
        message: str,
        metadata: dict[str, str],
        started_at: datetime,
        *,
        use_tls: bool,
    ) -> DeliveryResult:
        key = (
            id(asyncio.get_running_loop()),
            config.host,
            config.port,
            use_tls,
            config.verify_tls,
            config.ca_file,
        )
        writer: asyncio.StreamWriter | None = None
        try:
            async with asyncio.timeout(config.timeout_seconds):
                async with self._locks.setdefault(key, asyncio.Lock()):
                    writer = self._writers.get(key)
                    if writer is None or writer.is_closing():
                        _reader, writer = await self._open_tcp_connection(config, use_tls=use_tls)
                        self._writers[key] = writer
                    writer.write(framed)
                    await writer.drain()
        except BaseException:
            if writer:
                self._writers.pop(key, None)
                writer.close()
                writer.transport.abort()
            raise
        completed_at = datetime.now(UTC)
        return DeliveryResult(
            success=True,
            reached_server=True,
            started_at=started_at,
            completed_at=completed_at,
            latency_ms=self._latency_ms(started_at, completed_at),
            destination=config.summary,
            method="TLS" if use_tls else "TCP",
            request_headers_redacted=metadata,
            request_body=message,
            delivery_confirmation="transport_accepted",
            delivery_note=self.TCP_ACCEPTED_NOTE,
        )

    async def _open_udp_endpoint(
        self, config: SyslogDestination
    ) -> tuple[asyncio.DatagramTransport, asyncio.DatagramProtocol]:
        loop = asyncio.get_running_loop()
        transport, protocol = await loop.create_datagram_endpoint(
            asyncio.DatagramProtocol,
            remote_addr=(config.host, config.port),
        )
        return transport, protocol

    async def _open_tcp_connection(
        self,
        config: SyslogDestination,
        *,
        use_tls: bool,
    ) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        ssl_context = None
        if use_tls:
            ssl_context = ssl.create_default_context(cafile=config.ca_file)
            if not config.verify_tls:
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
        return await asyncio.wait_for(
            asyncio.open_connection(
                config.host,
                config.port,
                ssl=ssl_context,
            ),
            timeout=config.timeout_seconds,
        )

    def _failure(
        self,
        config: SyslogDestination,
        message: str,
        metadata: dict[str, str],
        started_at: datetime,
        *,
        reached_server: bool,
        error_message: str,
        error_category: str,
        confirmation: str = "best_effort",
    ) -> DeliveryResult:
        completed_at = datetime.now(UTC)
        return DeliveryResult(
            success=False,
            reached_server=reached_server,
            started_at=started_at,
            completed_at=completed_at,
            latency_ms=self._latency_ms(started_at, completed_at),
            destination=config.summary,
            method=config.protocol.upper(),
            request_headers_redacted=metadata,
            request_body=message,
            error_message=error_message,
            error_category=error_category,
            delivery_confirmation=confirmation,  # type: ignore[arg-type]
            delivery_note=self.UDP_BEST_EFFORT_NOTE
            if config.protocol == "udp"
            else self.TCP_ACCEPTED_NOTE,
        )

    @staticmethod
    def _latency_ms(started_at: datetime, completed_at: datetime) -> int:
        return max(int((completed_at - started_at).total_seconds() * 1000), 0)

    @staticmethod
    def _categorize_os_error(exc: OSError) -> str:
        if isinstance(exc, socket.gaierror):
            return DeliveryErrorCategory.DNS.value
        if "timed out" in str(exc).lower():
            return DeliveryErrorCategory.CONNECTION_TIMEOUT.value
        if isinstance(exc, ssl.SSLError):
            return DeliveryErrorCategory.TLS.value
        return DeliveryErrorCategory.CONNECTION.value
