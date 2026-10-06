"""Integration test for demo-syslog product and syslog simulation workflow."""

import asyncio
import contextlib
import socket

import pytest


@pytest.fixture
def syslog_udp_listener():
    received: list[bytes] = []

    class Server(asyncio.DatagramProtocol):
        def datagram_received(self, data: bytes, _addr) -> None:
            received.append(data)

    async def start() -> tuple[asyncio.AbstractEventLoop, asyncio.DatagramTransport, int]:
        loop = asyncio.get_running_loop()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        transport, _protocol = await loop.create_datagram_endpoint(lambda: Server(), sock=sock)
        return loop, transport, port

    return received, start


def _syslog_simulation_payload(host: str, port: int, **overrides) -> dict:
    payload = {
        "name": "Syslog Workflow Test",
        "product_id": "demo-syslog",
        "scenario_id": "ping",
        "simulation_mode": "push_webhook",
        "fidelity_mode": "troubleshooting",
        "destination": {
            "transport_id": "syslog",
            "host": host,
            "port": port,
            "protocol": "udp",
            "format": "raw",
            "facility": 16,
            "severity": 6,
            "app_name": "integration-simulator",
            "timeout_seconds": 5,
        },
        "auth_config": {"auth_method_id": "none"},
        "scenario_overrides": {"ping": {"message": "workflow-test"}},
        "schedule": {"type": "manual"},
        "fault_config": {"enabled": False},
    }
    payload.update(overrides)
    return payload


@pytest.mark.asyncio
async def test_demo_syslog_simulation_send(runtime_client, syslog_udp_listener) -> None:
    received, start = syslog_udp_listener
    _loop, transport, port = await start()
    client, _app = runtime_client

    created = client.post(
        "/api/v1/simulations",
        json=_syslog_simulation_payload("127.0.0.1", port),
    )
    assert created.status_code == 201, created.text
    sim_id = created.json()["id"]

    send = client.post(f"/api/v1/simulations/{sim_id}/send")
    assert send.status_code == 200, send.text
    body = send.json()
    assert body["delivery_success"] is True

    await asyncio.sleep(0.05)
    transport.close()

    assert len(received) == 1
    message = received[0].decode("utf-8", errors="replace")
    assert "workflow-test" in message

    events = client.get(f"/api/v1/simulations/{sim_id}/events").json()
    assert len(events) == 1
    detail = client.get(f"/api/v1/simulations/{sim_id}/events/{events[0]['id']}").json()
    attempt = detail["delivery_attempts"][0]
    assert attempt["transport_id"] == "syslog"
    assert attempt["request_method"] == "UDP"
    assert attempt["success"] is True


def test_demo_syslog_product_lists_syslog_transport(client) -> None:
    products = client.get("/api/v1/products").json()
    demo = next(item for item in products if item["id"] == "demo-syslog")
    assert "syslog" in demo["supported_transports"]

    detail = client.get("/api/v1/products/demo-syslog").json()
    assert detail["supported_transports"] == ["syslog"]


def test_syslog_transport_api_send(client) -> None:
    received: list[bytes] = []
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 0))
    sock.settimeout(2.0)
    port = sock.getsockname()[1]

    response = client.post(
        "/api/v1/transport/syslog/send",
        json={
            "host": "127.0.0.1",
            "port": port,
            "protocol": "udp",
            "format": "rfc5424",
            "message": "api test message",
        },
    )

    with contextlib.suppress(TimeoutError):
        received.append(sock.recvfrom(4096)[0])
    sock.close()

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["delivery_confirmation"] == "best_effort"
    assert len(received) == 1
