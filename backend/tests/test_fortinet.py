"""Tests for the Fortinet FortiGate product module."""

import asyncio
import socket

import pytest
from app.domain.enums import FidelityMode
from app.products.registry import ProductRegistry


@pytest.fixture
def fortinet_registry(products_directory) -> ProductRegistry:
    registry = ProductRegistry(str(products_directory))
    registry.load_all()
    return registry


FORTINET_SCENARIOS = [
    "forward-traffic-allow",
    "forward-traffic-deny",
    "local-traffic",
    "vpn-event",
    "user-auth-event",
    "system-event",
    "threat-virus",
]


@pytest.mark.parametrize("scenario_id", FORTINET_SCENARIOS)
def test_fortinet_product_loads_scenarios(fortinet_registry, scenario_id) -> None:
    manifest = fortinet_registry.get_manifest("fortinet")
    assert manifest is not None
    assert "syslog" in manifest.supported_transports
    scenario = fortinet_registry.get_scenario("fortinet", scenario_id)
    assert scenario is not None
    assert scenario.default_transport == "syslog"


@pytest.mark.parametrize(
    ("scenario_id", "required_tokens"),
    [
        ("forward-traffic-allow", ['type="traffic"', 'subtype="forward"', 'logid="0000000013"']),
        ("forward-traffic-deny", ['action="deny"', 'subtype="forward"']),
        ("local-traffic", ['subtype="local"', 'logid="0001000014"']),
        ("vpn-event", ['subtype="vpn"', 'logid="0101037127"']),
        ("user-auth-event", ['subtype="user"', 'logid="0102043008"']),
        ("system-event", ['subtype="system"', 'logid="0100032001"']),
        ("threat-virus", ['type="utm"', 'subtype="virus"', 'logid="0211008192"']),
    ],
)
def test_fortinet_scenario_renders_expected_fields(
    fortinet_registry, scenario_id, required_tokens
) -> None:
    scenario = fortinet_registry.get_scenario("fortinet", scenario_id)
    assert scenario is not None
    plugin = fortinet_registry.get_plugin("fortinet")
    payload = fortinet_registry.renderer.render_scenario(
        scenario,
        fidelity_mode=FidelityMode.TROUBLESHOOTING,
        correlation_id="test-correlation-id",
        overrides={},
        plugin=plugin,
        diagnostic_merge="nested",
    )
    assert isinstance(payload, dict)
    message = payload["_syslog_message"]
    for token in required_tokens:
        assert token in message
    assert "simulator_event_id=test-correlation-id" in message
    assert 'devname="FGT-SIM-01"' in message


def test_fortinet_scenario_overrides_applied(fortinet_registry) -> None:
    scenario = fortinet_registry.get_scenario("fortinet", "forward-traffic-allow")
    assert scenario is not None
    plugin = fortinet_registry.get_plugin("fortinet")
    payload = fortinet_registry.renderer.render_scenario(
        scenario,
        fidelity_mode=FidelityMode.VENDOR_ACCURATE,
        correlation_id="override-test",
        overrides={"srcip": "192.168.1.10", "dstip": "8.8.4.4", "dstport": 53},
        plugin=plugin,
    )
    message = payload["_syslog_message"]
    assert "srcip=192.168.1.10" in message
    assert "dstip=8.8.4.4" in message
    assert "dstport=53" in message


def test_fortinet_listed_in_catalog(client) -> None:
    products = client.get("/api/v1/products").json()
    fortinet = next(item for item in products if item["id"] == "fortinet")
    assert fortinet["scenario_count"] >= 7
    assert "syslog" in fortinet["supported_transports"]


def test_fortinet_preview_api(client) -> None:
    response = client.post(
        "/api/v1/products/fortinet/scenarios/forward-traffic-allow/preview",
        json={"fidelity_mode": "troubleshooting"},
    )
    assert response.status_code == 200
    payload = response.json()["payload"]
    assert "_syslog_message" in payload
    assert 'type="traffic"' in payload["_syslog_message"]


@pytest.mark.asyncio
async def test_fortinet_simulation_syslog_delivery(runtime_client) -> None:
    received: list[bytes] = []

    class Server(asyncio.DatagramProtocol):
        def datagram_received(self, data: bytes, _addr) -> None:
            received.append(data)

    loop = asyncio.get_running_loop()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    transport, _protocol = await loop.create_datagram_endpoint(lambda: Server(), sock=sock)

    client, _app = runtime_client
    created = client.post(
        "/api/v1/simulations",
        json={
            "name": "Fortinet Delivery Test",
            "product_id": "fortinet",
            "scenario_id": "threat-virus",
            "simulation_mode": "push_webhook",
            "fidelity_mode": "troubleshooting",
            "destination": {
                "transport_id": "syslog",
                "host": "127.0.0.1",
                "port": port,
                "protocol": "udp",
                "format": "raw",
                "facility": 16,
                "severity": 6,
            },
            "auth_config": {"auth_method_id": "none"},
            "schedule": {"type": "manual"},
            "fault_config": {"enabled": False},
        },
    )
    assert created.status_code == 201
    sim_id = created.json()["id"]

    send = client.post(f"/api/v1/simulations/{sim_id}/send")
    assert send.status_code == 200
    assert send.json()["delivery_success"] is True

    await asyncio.sleep(0.05)
    transport.close()

    assert len(received) == 1
    message = received[0].decode("utf-8")
    assert 'type="utm"' in message
    assert 'subtype="virus"' in message
    assert "simulator_event_id=" in message

    events = client.get(f"/api/v1/simulations/{sim_id}/events").json()
    assert len(events) == 1
    detail = client.get(f"/api/v1/simulations/{sim_id}/events/{events[0]['id']}").json()
    assert detail["delivery_attempts"][0]["transport_id"] == "syslog"
