"""Contract, isolation and parsing tests for the Docker log lab."""

import asyncio
import csv
import json
import ssl
from datetime import UTC, datetime
from pathlib import Path
from xml.etree import ElementTree as ET

import httpx
import pytest
import respx
from app.api.deps import get_product_registry
from app.core.database import get_session_factory
from app.core.security import SecretEncryptor
from app.domain.enums import FidelityMode
from app.formats.source import encode_cef, render_source
from app.models import DeliveryJob, EventInstance, Simulation
from app.services.delivery_queue import DeliveryQueue
from app.services.simulation_runtime import SimulationRuntimeService
from app.services.transport_delivery import TransportDeliveryService
from app.transports.azure_logs_ingestion import AzureLogsIngestionTransport, json_batches
from app.transports.registry import transport_registry
from app.transports.syslog.engine import SyslogDeliveryEngine
from app.transports.syslog.models import SyslogDestination
from app.transports.syslog.rate_limiter import SyslogRateLimiter
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[2]
CATALOG = json.loads((ROOT / "products/catalog.json").read_text())


def target(name: str, **changes):
    return {
        "id": name,
        "name": name,
        "destination": {
            "transport_id": "http_webhook",
            "url": f"https://{name}.example.test/events",
        },
        "payload_format": "json",
        **changes,
    }


def simulation_body(**changes):
    return {
        "name": "Log lab",
        "product_id": "windows-dc",
        "scenario_ids": ["logon-failure", "account-lockout"],
        "targets": [target("first"), target("second")],
        "random_seed": 42,
        **changes,
    }


def runtime(db: Session) -> SimulationRuntimeService:
    return SimulationRuntimeService(
        db,
        get_product_registry(),
        TransportDeliveryService(transport_registry),
        SecretEncryptor("test-secret-key-for-encryption-only"),
    )


@pytest.mark.parametrize("profile", CATALOG, ids=lambda p: p["id"])
def test_catalog_families_and_wire_fixtures(profile, products_directory):
    registry = get_product_registry()
    manifest = registry.get_manifest(profile["id"])
    assert manifest and manifest.field_references and manifest.schema_version
    families = set()
    for ref in manifest.scenarios:
        scenario = registry.get_scenario(profile["id"], ref.id)
        if (
            not isinstance(scenario.template.body, dict)
            or "_source_event" not in scenario.template.body
        ):
            continue
        payload = registry.renderer.render_scenario(
            scenario,
            fidelity_mode=FidelityMode.VENDOR_ACCURATE,
            correlation_id="11111111-2222-4333-8444-555555555555",
            plugin=registry.get_plugin(profile["id"]),
            random_seed=42,
            render_time=datetime(2026, 10, 4, 12, tzinfo=UTC),
        )
        families.add(payload["_source_event"]["family"])
        for fmt in profile["formats"]:
            body, _ = render_source(payload, fmt)
            fixture = (
                (products_directory / profile["id"] / "fixtures" / f"{ref.id}.{fmt}.txt")
                .read_text()
                .rstrip("\n")
            )
            assert (
                json.dumps(body, indent=2, ensure_ascii=False) if isinstance(body, dict) else body
            ) == fixture
            if fmt == "xml":
                root = ET.fromstring(body)
                ns = {"w": "http://schemas.microsoft.com/win/2004/08/events/event"}
                assert root.find("w:System/w:EventID", ns).text == str(payload["record"]["EventID"])
                assert root.find("w:System/w:Computer", ns).text == "sim-device-01"
                assert root.find("w:EventData", ns) is not None
            elif fmt == "cef":
                assert body.startswith("CEF:0|" + payload["_source_event"]["vendor"] + "|")
                assert "src=198.51.100.20" in body and " dst=203.0.113.10" in body
                assert "dvc=192.0.2.10" in body
            elif fmt == "csv":
                assert len(next(csv.reader([body]))) == len(payload["csv"])
            elif fmt == "json":
                assert isinstance(body, dict)
                if profile["id"] == "aws-cloudtrail":
                    assert body["eventVersion"] == "1.09" and body["eventName"]
                if profile["id"] == "windows-dc":
                    assert body["EventID"] in {4624, 4625, 4769, 4776, 4740, 4720, 4728}
            else:
                assert isinstance(body, str) and body
    assert families == set(profile["families"])


def test_cef_escapes_header_extension_boundaries():
    text = encode_cef("A|B", "P\\Q", "1", "42", "name\nline", 5, {"msg": "x=y\\z\nnext|part"})
    assert "A\\|B|P\\\\Q" in text
    assert "msg=x\\=y\\\\z\\nnext|part" in text
    assert "\n" not in text


@respx.mock
def test_fanout_retry_partial_filters_and_primary_update(client):
    first = respx.post("https://first.example.test/events").mock(
        side_effect=[httpx.Response(503), httpx.Response(204)]
    )
    second = respx.post("https://second.example.test/events").mock(return_value=httpx.Response(400))
    created = client.post(
        "/api/v1/simulations",
        json=simulation_body(fault_config={"enabled": True, "delivery": {"retry_count": 1}}),
    )
    assert created.status_code == 201, created.text
    sim = created.json()
    sid = sim["id"]
    result = client.post(f"/api/v1/simulations/{sid}/send").json()
    assert result["delivery_success"] is False and first.call_count == 2 and second.call_count == 2
    event = client.get(f'/api/v1/simulations/{sid}/events/{result["event_id"]}').json()
    assert event["status"] == "partial"
    assert {a["target_id"] for a in event["delivery_attempts"]} == {"first", "second"}
    assert all(a["delivery_confirmation"] == "api_accepted" for a in event["delivery_attempts"])
    assert len(client.get(f"/api/v1/simulations/{sid}/events?success=false").json()) == 1
    assert not client.get(f"/api/v1/simulations/{sid}/events?success=true").json()
    changed = client.patch(
        f"/api/v1/simulations/{sid}",
        json={"destination": {"url": "https://replacement.example.test/events"}},
    ).json()
    assert changed["targets"][0]["destination"]["url"] == "https://replacement.example.test/events"
    assert changed["targets"][1]["destination"]["url"] == "https://second.example.test/events"
    ambiguous = client.patch(
        f"/api/v1/simulations/{sid}",
        json={
            "targets": simulation_body()["targets"],
            "destination": {"url": "https://example.test"},
        },
    )
    assert ambiguous.status_code == 422


@respx.mock
def test_final_retry_success_and_sanitized_multi_target_export(client):
    respx.post("https://first.example.test/events").mock(
        side_effect=[httpx.Response(503), httpx.Response(204)]
    )
    respx.post("https://second.example.test/events").mock(return_value=httpx.Response(201))
    body = simulation_body(fault_config={"enabled": True, "delivery": {"retry_count": 1}})
    body["targets"][1]["auth_config"] = {
        "auth_method_id": "bearer",
        "token": "secret-target-canary",
    }
    sim = client.post("/api/v1/simulations", json=body).json()
    sid = sim["id"]
    assert "secret-target-canary" not in json.dumps(sim)
    assert client.post(f"/api/v1/simulations/{sid}/send").json()["delivery_success"]
    assert client.get(f"/api/v1/simulations/{sid}/events?success=true").json()[0][
        "delivery_success"
    ]
    assert len(client.get(f"/api/v1/simulations/{sid}/events?http_status=201").json()) == 1
    assert not client.get(f"/api/v1/simulations/{sid}/events?http_status=503").json()
    exported = client.get(f"/api/v1/simulations/{sid}/export").json()
    assert exported["format_version"] == "3.0" and "secret-target-canary" not in json.dumps(
        exported
    )
    imported = client.post("/api/v1/simulations/import", json={"document": exported})
    assert imported.status_code == 201, imported.text
    targets = client.get("/api/v1/simulations/" + imported.json()["simulation_id"]).json()[
        "targets"
    ]
    assert len(targets) == 2 and [t["id"] for t in targets] == ["first", "second"]
    explicit = client.get(
        f"/api/v1/simulations/{sid}/export?include_secrets=true&confirm_secret_export=true"
    ).json()
    assert explicit["simulation"]["targets"][1]["auth_config"]["token"] == "secret-target-canary"
    preview = client.post(f"/api/v1/simulations/{sid}/wire-preview?target_id=first")
    assert preview.status_code == 200, preview.text
    assert preview.json()["bytes"] == len(preview.json()["wire_text"].encode())


@pytest.mark.parametrize(
    "fmt,content,count",
    [
        ("text", "one\ntwo\n", 2),
        (
            "ndjson",
            '{"TimeGenerated":"2020-01-01T00:00:00Z","unusual":"2020-01-01T00:00:00Z"}\n',
            1,
        ),
        ("json", '[{"a":1},{"a":2}]', 2),
        ("csv", 'time,user\n2020-01-01T00:00:00Z,"a,b"\n', 1),
    ],
)
def test_dataset_upload_preview_delete(client, test_settings, fmt, content, count):
    response = client.post(
        "/api/v1/datasets",
        params={"name": "../../untrusted.log", "format": fmt},
        content=content.encode(),
    )
    assert response.status_code == 201, response.text
    row = response.json()
    assert row["record_count"] == count
    preview = client.get(f'/api/v1/datasets/{row["id"]}/preview?rewrite=true').json()
    if fmt == "ndjson":
        assert preview["unknown_timestamp_fields"] == ["unusual"]
        assert preview["records"][0]["payload"]["unusual"] == "2020-01-01T00:00:00Z"
        assert preview["records"][0]["payload"]["TimeGenerated"] != "2020-01-01T00:00:00Z"
    files = list((test_settings.resolved_data_dir / "datasets").iterdir())
    assert len(files) == 1 and files[0].name.endswith(".ndjson")
    assert client.delete(f'/api/v1/datasets/{row["id"]}').status_code == 204
    assert not list((test_settings.resolved_data_dir / "datasets").iterdir())


@pytest.mark.parametrize(
    "fmt,content",
    [("ndjson", '{"a":1}\nBAD'), ("json", '[{"a":1},]'), ("csv", "a,b\n1\n"), ("json", "[1,2]")],
)
def test_malformed_upload_cleanup(client, test_settings, fmt, content):
    result = client.post("/api/v1/datasets?name=bad&format=" + fmt, content=content)
    assert result.status_code == 422
    assert client.get("/api/v1/datasets").json() == []
    assert not list((test_settings.resolved_data_dir / "datasets").iterdir())


@respx.mock
def test_uploaded_replay_loop_and_rewrite(client):
    route = respx.post("https://first.example.test/events").mock(return_value=httpx.Response(204))
    dataset = client.post(
        "/api/v1/datasets?name=events&format=ndjson",
        content='{"TimeGenerated":"2020-01-01T00:00:00Z","msg":"sample"}\n',
    ).json()
    sim = client.post(
        "/api/v1/simulations",
        json=simulation_body(
            targets=[target("first")],
            replay_config={"dataset_id": dataset["id"], "loop": True, "rewrite_timestamps": True},
        ),
    ).json()
    for _ in range(2):
        sent = client.post("/api/v1/simulations/" + sim["id"] + "/send")
        assert sent.status_code == 200, sent.text
    assert route.call_count == 2
    assert json.loads(route.calls.last.request.content)["TimeGenerated"] != "2020-01-01T00:00:00Z"
    assert client.delete("/api/v1/datasets/" + dataset["id"]).status_code == 409


@pytest.mark.asyncio
async def test_azure_refresh_batches_throttling_and_204():
    tokens, uploads = [], []

    def handler(req):
        if "login.microsoftonline.com" in str(req.url):
            tokens.append(req)
            return httpx.Response(
                200, json={"access_token": f"token-{len(tokens)}", "expires_in": 3600}
            )
        uploads.append(req)
        if len(uploads) == 1:
            return httpx.Response(401)
        if len(uploads) == 2:
            return httpx.Response(429, headers={"Retry-After": "0"})
        return httpx.Response(204)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = AzureLogsIngestionTransport(client)
    config = {
        "endpoint": "https://lab.ingest.monitor.azure.com",
        "tenant_id": "tenant",
        "dcr_immutable_id": "dcr-123",
        "stream": "Custom-Lab",
        "batch_max_bytes": 1024,
        "max_retries": 2,
    }
    records = [{"msg": "é" * 200} for _ in range(5)]
    result = await adapter.deliver(
        config,
        json.dumps(records).encode(),
        "application/json",
        {"oauth_client_id": "client", "oauth_client_secret": "client-canary"},
    )
    assert result.success and result.response_status_code == 204
    assert result.delivery_confirmation == "api_accepted"
    assert len(tokens) == 2 and len(uploads) == 5
    assert all(len(r.content) <= 1024 for r in uploads)
    assert all(isinstance(json.loads(r.content), list) for r in uploads)
    assert (
        "client-canary" not in result.model_dump_json()
        and "token-2" not in result.model_dump_json()
    )
    assert b"grant_type=client_credentials" in tokens[0].content
    assert uploads[-1].headers["Authorization"] == "Bearer token-2"
    await adapter.close()


@pytest.mark.asyncio
async def test_azure_bad_auth_and_oversize():
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(403, json={"error": "client-canary"})
        )
    )
    adapter = AzureLogsIngestionTransport(client)
    config = {
        "endpoint": "https://lab.ingest.monitor.azure.com",
        "tenant_id": "t",
        "dcr_immutable_id": "d",
        "stream": "Custom-Lab",
    }
    result = await adapter.deliver(
        config,
        b"{}",
        "application/json",
        {"oauth_client_id": "c", "oauth_client_secret": "client-canary"},
    )
    assert not result.success and result.error_category == "auth"
    assert "client-canary" not in result.model_dump_json()
    with pytest.raises(ValueError):
        json_batches([{"data": "é" * 600}], 1024)
    await adapter.close()


@pytest.mark.asyncio
async def test_rate_limiter_isolates_collectors():
    limiter = SyslogRateLimiter()
    await limiter.wait("slow", 2)
    slow = asyncio.create_task(limiter.wait("slow", 2))
    await asyncio.sleep(0)
    await asyncio.wait_for(limiter.wait("healthy", 100), 0.1)
    slow.cancel()
    await asyncio.gather(slow, return_exceptions=True)


@pytest.mark.parametrize("field", ["syslog_hostname", "app_name", "proc_id", "msg_id"])
def test_syslog_rejects_header_injection(field):
    with pytest.raises(ValueError):
        SyslogDestination(host="localhost", **{field: "header\nnext"})
    with pytest.raises(ValueError):
        SyslogDestination(host="localhost", **{field: "with space"})


@pytest.mark.asyncio
async def test_persistent_queue_rate_and_outage_isolation(runtime_client):
    client, app = runtime_client
    sim = client.post(
        "/api/v1/simulations",
        json=simulation_body(
            schedule={"type": "finite", "events_per_second": 100, "event_count": 20},
            targets=[target("first"), target("second", queue_limit=1)],
        ),
    ).json()

    async def handler(req):
        if req.url.host == "second.example.test":
            await asyncio.sleep(0.5)
            return httpx.Response(503)
        return httpx.Response(204)

    adapter = transport_registry.get("http_webhook")
    adapter.engine._client_for = lambda req: httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    )
    with get_session_factory()() as db:
        service = runtime(db)
        service.start(sim["id"])
        await service.tick(sim["id"])
        await service.tick(sim["id"])
        assert db.get(Simulation, sim["id"]).runtime_state["events_generated"] == 20
        assert db.query(DeliveryJob).filter_by(target_id="second", status="failed").count() == 19
    queue = DeliveryQueue(
        get_product_registry(),
        TransportDeliveryService(transport_registry),
        SecretEncryptor("test-secret-key-for-encryption-only"),
    )
    queue.start()
    try:
        await asyncio.sleep(0.2)
        with get_session_factory()() as db:
            assert (
                db.query(DeliveryJob).filter_by(target_id="first", status="delivered").count() == 20
            )
            assert db.query(DeliveryJob).filter_by(target_id="second", status="active").count() == 1
        await asyncio.sleep(0.5)
        with get_session_factory()() as db:
            assert db.query(EventInstance).filter_by(status="pending").count() == 0
            s = db.get(Simulation, sim["id"])
            assert s.runtime_state["events_attempted"] == 20
            assert s.runtime_state["events_partial"] == 20
    finally:
        await queue.close()


def test_four_real_receivers_mixed_udp_tcp_tls_http(client, tmp_path):
    import contextlib
    import socketserver
    import threading
    from datetime import timedelta
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from ipaddress import ip_address

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    captured: dict[str, list[bytes]] = {k: [] for k in ("udp", "tcp", "tls", "http")}
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(UTC) - timedelta(days=1))
        .not_valid_after(datetime.now(UTC) + timedelta(days=1))
        .add_extension(
            x509.SubjectAlternativeName(
                [x509.DNSName("localhost"), x509.IPAddress(ip_address("127.0.0.1"))]
            ),
            critical=False,
        )
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    cert_path, key_path = tmp_path / "ca.pem", tmp_path / "key.pem"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
    )

    class UDP(socketserver.BaseRequestHandler):
        def handle(self):
            captured["udp"].append(self.request[0])

    class TCP(socketserver.StreamRequestHandler):
        def handle(self):
            while line := self.rfile.readline():
                captured["tls" if isinstance(self.request, ssl.SSLSocket) else "tcp"].append(line)

    class HTTP(BaseHTTPRequestHandler):
        def do_POST(self):
            captured["http"].append(self.rfile.read(int(self.headers["Content-Length"])))
            self.send_response(204)
            self.end_headers()

        def log_message(self, *_args):
            pass

    class ThreadedTCP(socketserver.ThreadingTCPServer):
        daemon_threads = True

    servers = [
        socketserver.ThreadingUDPServer(("127.0.0.1", 0), UDP),
        ThreadedTCP(("127.0.0.1", 0), TCP),
        ThreadedTCP(("127.0.0.1", 0), TCP),
        ThreadingHTTPServer(("127.0.0.1", 0), HTTP),
    ]
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert_path, key_path)
    servers[2].socket = context.wrap_socket(servers[2].socket, server_side=True)
    for server in servers:
        threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        targets = []
        for protocol, server in zip(("udp", "tcp", "tls"), servers, strict=False):
            targets.append(
                {
                    "id": protocol,
                    "name": protocol,
                    "payload_format": "xml",
                    "destination": {
                        "transport_id": "syslog",
                        "host": "127.0.0.1",
                        "port": server.server_address[1],
                        "protocol": protocol,
                        "format": "raw",
                        "ca_file": str(cert_path),
                        "timeout_seconds": 2,
                    },
                }
            )
        targets.append(
            {
                "id": "http",
                "name": "http",
                "payload_format": "json",
                "destination": {
                    "transport_id": "http_webhook",
                    "url": f"http://127.0.0.1:{servers[3].server_address[1]}/events",
                },
            }
        )
        sim = client.post(
            "/api/v1/simulations",
            json=simulation_body(
                targets=targets,
                devices=[{"id": "dc01", "hostname": "dc01.lab.test", "ip_address": "192.0.2.50"}],
            ),
        ).json()
        sent = client.post("/api/v1/simulations/" + sim["id"] + "/send")
        assert sent.status_code == 200, sent.text
        assert sent.json()["delivery_success"]
        import time

        until = time.monotonic() + 2
        while not all(captured.values()) and time.monotonic() < until:
            time.sleep(0.01)
        assert all(len(items) == 1 for items in captured.values())
        assert captured["udp"] == captured["tcp"] == captured["tls"]
        for fmt in ("udp", "tcp", "tls"):
            tree = ET.fromstring(captured[fmt][0])
            assert "dc01.lab.test" in captured[fmt][0].decode()
            assert tree.find("{*}System/{*}EventID").text == "4625"
        record = json.loads(captured["http"][0])
        assert record["Computer"] == "dc01.lab.test" and record["EventID"] == 4625
        detail = client.get(
            f'/api/v1/simulations/{sim["id"]}/events/{sent.json()["event_id"]}'
        ).json()
        confirmations = {
            a["target_id"]: a["delivery_confirmation"] for a in detail["delivery_attempts"]
        }
        assert confirmations == {
            "udp": "best_effort",
            "tcp": "transport_accepted",
            "tls": "transport_accepted",
            "http": "api_accepted",
        }
        # The same TLS receiver with an untrusted certificate must fail independently.
        targets[2]["destination"]["ca_file"] = None
        assert (
            client.patch("/api/v1/simulations/" + sim["id"], json={"targets": targets}).status_code
            == 200
        )
        again = client.post("/api/v1/simulations/" + sim["id"] + "/send").json()
        assert not again["delivery_success"]
        assert (
            client.get(f'/api/v1/simulations/{sim["id"]}/events/{again["event_id"]}').json()[
                "status"
            ]
            == "partial"
        )
    finally:
        for server in servers:
            with contextlib.suppress(Exception):
                server.shutdown()
                server.server_close()


@pytest.mark.asyncio
async def test_slow_tcp_write_is_bounded_and_cancelled_writer_is_closed(monkeypatch):
    class Transport:
        aborted = False

        def abort(self):
            self.aborted = True

    class Writer:
        closed = False
        transport = Transport()

        def write(self, _data):
            pass

        async def drain(self):
            await asyncio.sleep(10)

        def close(self):
            self.closed = True

        def is_closing(self):
            return self.closed

    engine = SyslogDeliveryEngine()
    writer = Writer()

    async def open_connection(*_args, **_kwargs):
        return object(), writer

    monkeypatch.setattr(engine, "_open_tcp_connection", open_connection)
    config = {"host": "127.0.0.1", "protocol": "tcp", "timeout_seconds": 0.5}
    result = await asyncio.wait_for(engine.deliver(config, b"test", "text/plain"), 1)
    assert not result.success and result.error_category == "connection_timeout"
    assert writer.closed and writer.transport.aborted
    writer = Writer()
    send = asyncio.create_task(engine.deliver(config, b"test", "text/plain"))
    await asyncio.sleep(0.01)
    send.cancel()
    with pytest.raises(asyncio.CancelledError):
        await send
    assert writer.closed and writer.transport.aborted


def test_secondary_missing_credentials_and_filter_update_validation(client):
    response = client.post(
        "/api/v1/simulations",
        json=simulation_body(
            devices=[{"id": "dc", "hostname": "dc.lab", "ip_address": "192.0.2.1"}],
            targets=[
                target("first"),
                target("second", device_ids=["dc"], auth_config={"auth_method_id": "bearer"}),
            ],
        ),
    )
    assert response.status_code == 201, response.text
    simulation = response.json()
    assert "targets.second.auth_config.token" in simulation["missing_secrets"]
    path = f'/api/v1/simulations/{simulation["id"]}'
    assert client.post(path + "/start").status_code == 422
    assert client.patch(path, json={"devices": []}).status_code == 422
    assert client.get(path).json()["devices"][0]["id"] == "dc"


def test_original_timing_persists_cursor_and_csv_rewrite(client, test_settings):
    from app.services.datasets import replay_record

    dataset = client.post(
        "/api/v1/datasets?name=original&format=csv",
        content='timestamp,user,customDate\n2020-01-01T00:00:00Z,"a,b",2020-01-01T00:00:00Z\n2020-01-01T00:00:05Z,second,2020-01-01T00:00:00Z\n',
    ).json()
    simulation = client.post(
        "/api/v1/simulations",
        json=simulation_body(
            replay_config={
                "dataset_id": dataset["id"],
                "timing": "original",
                "rewrite_timestamps": True,
            }
        ),
    ).json()
    with get_session_factory()() as db:
        stored = db.get(Simulation, simulation["id"])
        first, delay = replay_record(db, stored, test_settings.resolved_data_dir)
        assert delay == 0
        row = next(csv.reader([first["_dataset_payload"]]))
        assert row[0] != "2020-01-01T00:00:00Z" and row[1] == "a,b"
        assert row[2] == "2020-01-01T00:00:00Z"
        db.commit()
    with get_session_factory()() as db:
        stored = db.get(Simulation, simulation["id"])
        second, delay = replay_record(db, stored, test_settings.resolved_data_dir)
        assert delay == 5 and "second" in second["_dataset_payload"]
        assert replay_record(db, stored, test_settings.resolved_data_dir)[0] is None


@pytest.mark.asyncio
async def test_restarted_azure_queue_batches_pending_jobs(runtime_client, monkeypatch):
    client, _ = runtime_client
    simulation = client.post(
        "/api/v1/simulations",
        json=simulation_body(
            targets=[
                target(
                    "azure",
                    payload_format="default",
                    destination={
                        "transport_id": "azure_logs_ingestion",
                        "endpoint": "https://lab.ingest.monitor.azure.com",
                        "dcr_immutable_id": "dcr-lab",
                        "tenant_id": "tenant",
                        "stream": "Custom-SimulatorEvents",
                    },
                    auth_config={
                        "auth_method_id": "none",
                        "oauth_client_id": "client",
                        "oauth_client_secret": "secret",
                    },
                )
            ],
            schedule={"type": "finite", "events_per_second": 100, "event_count": 20},
        ),
    ).json()
    calls = []

    def handler(request):
        if "login.microsoftonline.com" in str(request.url):
            return httpx.Response(200, json={"access_token": "token", "expires_in": 3600})
        calls.append(json.loads(request.content))
        return httpx.Response(204)

    azure = AzureLogsIngestionTransport(httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    monkeypatch.setitem(transport_registry._transports, "azure_logs_ingestion", azure)
    with get_session_factory()() as db:
        service = runtime(db)
        service.start(simulation["id"])
        await service.tick(simulation["id"])
        await service.tick(simulation["id"])
        db.query(DeliveryJob).filter_by(simulation_id=simulation["id"]).update({"status": "active"})
        db.commit()
    queue = DeliveryQueue(
        get_product_registry(),
        TransportDeliveryService(transport_registry),
        SecretEncryptor("test-secret-key-for-encryption-only"),
    )
    queue.start()
    try:
        for _ in range(100):
            with get_session_factory()() as db:
                if (
                    db.query(DeliveryJob)
                    .filter_by(simulation_id=simulation["id"], status="delivered")
                    .count()
                    == 20
                ):
                    break
            await asyncio.sleep(0.02)
        assert len(calls) == 1 and len(calls[0]) == 20
        assert set(calls[0][0]) == {"TimeGenerated", "Computer", "SourceProfile", "RawData"}
        assert calls[0][0]["RawData"].startswith("<Event")
        with get_session_factory()() as db:
            assert db.get(Simulation, simulation["id"]).runtime_state["events_successful"] == 20
    finally:
        await queue.close()
        await azure.close()


def test_seeded_user_pool_and_invalid_weights(client):
    simulation = client.post(
        "/api/v1/simulations",
        json=simulation_body(
            schedule={
                "type": "manual",
                "user_pool": ["alice", "bob"],
                "incident_preset": "password_spray",
            }
        ),
    ).json()
    with get_session_factory()() as db:
        stored = db.get(Simulation, simulation["id"])
        service = runtime(db)
        scenario = get_product_registry().get_scenario("windows-dc", "logon-failure")
        users = [
            service._event_overrides(stored, scenario, sequence, {})["user"]
            for sequence in range(20)
        ]
        assert set(users) == {"alice", "bob"}
        assert users == [
            service._event_overrides(stored, scenario, sequence, {})["user"]
            for sequence in range(20)
        ]
    invalid = client.post(
        "/api/v1/simulations",
        json=simulation_body(schedule={"type": "manual", "scenario_weights": {"unknown": 1}}),
    )
    assert invalid.status_code == 422


def test_normalized_upload_limit_cleans_output(client, test_settings, monkeypatch):
    import app.services.datasets as datasets

    monkeypatch.setattr(datasets, "MAX_UPLOAD_BYTES", 50)
    response = client.post("/api/v1/datasets?name=overflow&format=text", content="record\n" * 5)
    assert response.status_code == 422
    assert client.get("/api/v1/datasets").json() == []
    assert not list((test_settings.resolved_data_dir / "datasets").iterdir())


def test_legacy_fortinet_builtin_mapping_and_disabled_auth(client):
    payload = {
        "_syslog_message": (
            'logid="0000000013" devname="fg.lab" srcip=198.51.100.20 '
            'dstip=203.0.113.10 srcport=1234 dstport=443 action="accept"'
        )
    }
    body, content_type = render_source(payload, "CommonSecurityLog")
    assert content_type == "application/json"
    assert body["DeviceVendor"] == "Fortinet" and body["DestinationPort"] == 443
    assert body["SourceIP"] == "198.51.100.20"
    response = client.post(
        "/api/v1/simulations",
        json=simulation_body(
            targets=[
                target("first", enabled=False, auth_config={"auth_method_id": "bearer"}),
                target("second"),
            ]
        ),
    )
    assert response.status_code == 201 and response.json()["missing_secrets"] == []


@pytest.mark.asyncio
@pytest.mark.parametrize("family", ["cloudflare", "azure"])
@respx.mock
async def test_stop_edit_backlog_restart_uses_each_complete_snapshot(
    runtime_client, monkeypatch, family
):
    import gzip

    client, app = runtime_client
    client._portal.call(app.state.delivery_queue.close)
    if family == "cloudflare":
        configs = [
            target(
                "retained",
                destination={
                    "transport_id": "cloudflare_logpush",
                    "url": f"https://{i}.collector.test/events",
                    "headers": [{"name": "X-API-Key", "value": f"key-{i}", "sensitive": True}],
                },
                payload_format="default",
            )
            for i in [1, 2]
        ]
        configs.append(
            target(
                "retained",
                destination={
                    "transport_id": "http_webhook",
                    "url": "https://3.collector.test/events",
                    "headers": [{"name": "X-API-Key", "value": "key-3", "sensitive": True}],
                },
                payload_format="json",
            )
        )
        changes = {"product_id": "cloudflare", "scenario_ids": ["http-request"]}
    else:
        configs = [
            target(
                "retained",
                destination={
                    "transport_id": "azure_logs_ingestion",
                    "endpoint": f"https://{i}.ingest.monitor.azure.com",
                    "tenant_id": "tenant",
                    "dcr_immutable_id": f"dcr-{i}",
                    "stream": f"Custom-{i}",
                },
                auth_config={
                    "auth_method_id": "none",
                    "oauth_client_id": f"client-{i}",
                    "oauth_client_secret": f"secret-{i}",
                },
                payload_format="default",
            )
            for i in [1, 2]
        ]
        configs.append(
            target(
                "retained",
                destination={
                    "transport_id": "azure_function_app",
                    "url": "https://3.collector.test/api/ingest",
                },
                auth_config={"auth_method_id": "none", "token": "key-3"},
                payload_format="json",
            )
        )
        changes = {"product_id": "mimecast", "scenario_ids": ["email-receipt"]}
    body = simulation_body(
        **changes,
        targets=[configs[0]],
        schedule={"type": "continuous", "events_per_second": 20},
    )
    saved = client.post("/api/v1/simulations", json=body)
    assert saved.status_code == 201, saved.text
    sid = saved.json()["id"]
    for index, config in enumerate(configs):
        if index:
            changed = client.patch(f"/api/v1/simulations/{sid}", json={"targets": [config]})
            assert changed.status_code == 200, changed.text
        with get_session_factory()() as db:
            service = runtime(db)
            service.start(sid)
            await service.tick(sid)
            service.stop(sid)
            db.commit()
    calls = []
    tokens = []

    def handler(req):
        if req.url.host == "login.microsoftonline.com":
            import urllib.parse

            form = urllib.parse.parse_qs(req.content.decode())
            tokens.append((form["client_id"][0], form["client_secret"][0]))
            return httpx.Response(
                200, json={"access_token": "token-" + form["client_id"][0], "expires_in": 3600}
            )
        calls.append(req)
        if req.url.host == "3.collector.test" and family == "azure":
            return httpx.Response(
                200, json={"accepted_records": 2, "downstream_status": 204, "request_id": "ack"}
            )
        return httpx.Response(204 if family == "azure" else 200)

    respx.route().mock(side_effect=handler)
    # Recover jobs claimed before process exit, with the current saved config already changed.
    with get_session_factory()() as db:
        db.query(DeliveryJob).filter_by(simulation_id=sid).update({"status": "active"})
        db.commit()
        assert db.query(DeliveryJob).filter_by(simulation_id=sid).count() == 6
    queue = DeliveryQueue(
        get_product_registry(),
        TransportDeliveryService(transport_registry),
        SecretEncryptor("test-secret-key-for-encryption-only"),
    )
    queue.start()
    try:
        for _ in range(150):
            with get_session_factory()() as db:
                if (
                    db.query(DeliveryJob).filter_by(simulation_id=sid, status="delivered").count()
                    == 6
                ):
                    break
            await asyncio.sleep(0.02)
        with get_session_factory()() as db:
            assert (
                db.query(DeliveryJob).filter_by(simulation_id=sid, status="delivered").count() == 6
            )
        if family == "cloudflare":
            assert [r.url.host for r in calls] == [
                "1.collector.test",
                "2.collector.test",
                "3.collector.test",
                "3.collector.test",
            ]
            assert [r.headers["X-API-Key"] for r in calls] == ["key-1", "key-2", "key-3", "key-3"]
            assert all(len(gzip.decompress(r.content).splitlines()) == 2 for r in calls[:2])
            assert "RayID" in json.loads(calls[2].content)
        else:
            assert [r.url.host for r in calls] == [
                "1.ingest.monitor.azure.com",
                "2.ingest.monitor.azure.com",
                "3.collector.test",
            ]
            assert tokens == [("client-1", "secret-1"), ("client-2", "secret-2")]
            assert [r.headers.get("Authorization") for r in calls[:2]] == [
                "Bearer token-client-1",
                "Bearer token-client-2",
            ]
            assert calls[2].headers["x-functions-key"] == "key-3"
            assert "RawData" in json.loads(calls[0].content)[0]
            assert "messageId" in json.loads(calls[2].content)[0]
    finally:
        await queue.close()
