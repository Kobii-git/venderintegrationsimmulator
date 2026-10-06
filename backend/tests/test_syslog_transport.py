import asyncio
import socket

import pytest
from app.transports.syslog.engine import SyslogDeliveryEngine


@pytest.fixture
def udp_syslog_server():
    received: list[bytes] = []

    class Server(asyncio.DatagramProtocol):
        def datagram_received(self, data: bytes, _addr) -> None:
            received.append(data)

    async def run_server() -> tuple[asyncio.AbstractServer, int]:
        loop = asyncio.get_running_loop()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        transport, _protocol = await loop.create_datagram_endpoint(
            lambda: Server(),
            sock=sock,
        )
        return transport, port

    return received, run_server


@pytest.mark.asyncio
async def test_syslog_udp_delivery_best_effort(udp_syslog_server) -> None:
    received, run_server = udp_syslog_server
    transport, port = await run_server()
    engine = SyslogDeliveryEngine()

    result = await engine.deliver(
        {
            "host": "127.0.0.1",
            "port": port,
            "protocol": "udp",
            "format": "rfc5424",
            "facility": 16,
            "severity": 6,
        },
        b'{"event":"test"}',
        "application/json",
    )

    await asyncio.sleep(0.05)
    transport.close()

    assert result.success is True
    assert result.reached_server is False
    assert result.delivery_confirmation == "best_effort"
    assert "does not confirm remote receipt" in (result.delivery_note or "")
    assert len(received) == 1
    assert b"test" in received[0]


@pytest.mark.asyncio
async def test_syslog_tcp_delivery_transport_accepted() -> None:
    received: list[bytes] = []

    async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        data = await reader.read(4096)
        received.append(data)
        writer.close()
        await writer.wait_closed()

    server = await asyncio.start_server(handle_client, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    engine = SyslogDeliveryEngine()

    result = await engine.deliver(
        {
            "host": "127.0.0.1",
            "port": port,
            "protocol": "tcp",
            "format": "raw",
            "tcp_framing": "newline",
        },
        b"plain syslog message",
        "text/plain",
    )

    server.close()
    await server.wait_closed()

    assert result.success is True
    assert result.reached_server is True
    assert result.delivery_confirmation == "transport_accepted"
    assert len(received) == 1
    assert received[0].endswith(b"plain syslog message\n")
