"""Azure upload contract, preflight, saved secrets and queue completion."""

import json

import httpx
import pytest
from app.core.database import get_session_factory
from app.formats.azure_ingestion import ingestion_record, validate_record
from app.models import DeliveryJob, Simulation
from app.transports.azure_function_app import AzureFunctionAppTransport
from app.transports.azure_logs_ingestion import AzureLogsIngestionTransport, json_batches
from app.transports.registry import transport_registry

from tests.test_log_lab import runtime


def dataset(client, body, fmt="ndjson"):
    result = client.post(f"/api/v1/datasets?name=logs&format={fmt}", content=body)
    assert result.status_code == 201, result.text
    return result.json()


def destination(relay):
    return (
        {
            "transport_id": "azure_function_app",
            "url": "https://relay.example.test/api/ingest",
            "max_retries": 0,
        }
        if relay
        else {
            "transport_id": "azure_logs_ingestion",
            "endpoint": "https://dce.example.test",
            "tenant_id": "tenant",
            "dcr_immutable_id": "dcr-immutable",
            "stream": "Custom-Logs",
            "max_retries": 0,
        }
    )


def auth(relay):
    return (
        {"auth_method_id": "none", "token": "function-key-canary"}
        if relay
        else {
            "auth_method_id": "none",
            "oauth_client_id": "client",
            "oauth_client_secret": "client-secret-canary",
        }
    )


@pytest.mark.parametrize(
    "fmt,body",
    [
        ("text", "first\nsecond\n"),
        ("csv", "timestamp,message\n2020-01-01T00:00:00Z,hello\n"),
        ("json", '[{"Message":"hello"}]'),
        ("ndjson", '{"timestamp":"2020-01-01T00:00:00Z","Message":"é"}\n'),
    ],
)
def test_full_file_preflight_envelope(client, fmt, body):
    uploaded = dataset(client, body, fmt)
    checked = client.post(
        f"/api/v1/datasets/{uploaded['id']}/validate-ingestion", json={"payload_mode": "envelope"}
    )
    assert checked.status_code == 200, checked.text
    preview = checked.json()
    assert preview["record_count"] == uploaded["record_count"]
    assert preview["schema_verified"] is False
    assert set(preview["records"][0]) == {"TimeGenerated", "SourceProfile", "Computer", "RawData"}
    if "timestamp" in body:
        assert preview["records"][0]["TimeGenerated"] == "2020-01-01T00:00:00Z"


def test_preflight_json_preserves_types_and_checks_last_record(client):
    record = {
        "timestamp": "2020-01-01T00:00:00Z",
        "count": 2,
        "active": True,
        "nested": {"x": None},
    }
    uploaded = dataset(client, json.dumps(record) + "\n")
    path = f"/api/v1/datasets/{uploaded['id']}/validate-ingestion"
    assert client.post(path, json={"payload_mode": "json"}).json()["records"] == [record]
    changed = client.post(path, json={"payload_mode": "json", "rewrite_timestamps": True}).json()[
        "records"
    ][0]
    assert changed["timestamp"] != record["timestamp"] and changed["nested"] == record["nested"]
    oversized = dataset(
        client, json.dumps(record) + "\n" + json.dumps({"Message": "é" * 32768}) + "\n"
    )
    rejected = client.post(
        f"/api/v1/datasets/{oversized['id']}/validate-ingestion", json={"payload_mode": "json"}
    )
    assert rejected.status_code == 422 and "Record 2" in rejected.text and "64 KiB" in rejected.text
    text = dataset(client, "hello\n", "text")
    assert (
        client.post(
            f"/api/v1/datasets/{text['id']}/validate-ingestion", json={"payload_mode": "json"}
        ).status_code
        == 422
    )


def test_batch_bounds_are_utf8_and_reject_nonfinite_fields():
    records = [{"value": "é" * 400}, {"value": "é" * 400}]
    batches = json_batches(records, 1024)
    assert len(batches) == 2 and all(len(batch) <= 1024 for batch in batches)
    with pytest.raises(ValueError, match="64 KiB"):
        validate_record({"value": "é" * 32768})
    with pytest.raises(ValueError):
        validate_record({"value": float("nan")})
    envelope = ingestion_record(
        {"_dataset_payload": "hello", "_dataset_content_type": "text/plain"},
        "default",
        "uploaded-logs",
    )
    assert envelope["RawData"] == "hello"


@pytest.mark.asyncio
@pytest.mark.parametrize("relay", [False, True])
@pytest.mark.parametrize("accepted", [False, True])
async def test_upload_waits_for_acceptance_and_redacts_secrets(
    runtime_client, monkeypatch, relay, accepted
):
    client, _ = runtime_client
    original = {"TimeGenerated": "2020-01-01T00:00:00Z", "Message": "unchanged", "count": 7}
    uploaded = dataset(client, json.dumps(original) + "\n")
    dest = destination(relay)
    body = {
        "name": "One-off upload",
        "product_id": "uploaded-logs",
        "scenario_ids": ["record"],
        "targets": [
            {
                "id": "azure",
                "name": "Azure",
                "destination": dest,
                "auth_config": auth(relay),
                "payload_format": "json",
            }
        ],
        "replay_config": {"dataset_id": uploaded["id"]},
        "schedule": {"type": "finite", "events_per_second": 10, "event_count": 1},
    }
    saved = client.post("/api/v1/simulations", json=body)
    assert saved.status_code == 201, saved.text
    sim = saved.json()
    assert "function-key-canary" not in saved.text and "client-secret-canary" not in saved.text
    batches = []

    def handler(request):
        if "login.microsoftonline.com" in str(request.url):
            return httpx.Response(200, json={"access_token": "oauth-canary", "expires_in": 3600})
        batches.append(json.loads(request.content))
        if not accepted:
            return httpx.Response(424 if relay else 400)
        if relay:
            assert request.headers["x-functions-key"] == "function-key-canary"
            return httpx.Response(
                200,
                json={
                    "accepted_records": len(batches[-1]),
                    "downstream_status": 204,
                    "request_id": "request-1",
                },
            )
        assert request.headers["Authorization"] == "Bearer oauth-canary"
        return httpx.Response(204)

    transport = (AzureFunctionAppTransport if relay else AzureLogsIngestionTransport)(
        httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )
    monkeypatch.setitem(transport_registry._transports, dest["transport_id"], transport)
    try:
        with get_session_factory()() as db:
            service = runtime(db)
            service.start(sim["id"])
            await service.tick(sim["id"])
            assert db.get(Simulation, sim["id"]).status == "running"
            assert (
                db.query(DeliveryJob).filter_by(simulation_id=sim["id"], status="pending").count()
                == 1
            )
            # Queue remains active: another tick must not mark completion or regenerate.
            await service.tick(sim["id"])
            assert db.get(Simulation, sim["id"]).runtime_state["events_generated"] == 1
        from app.api.deps import get_product_registry
        from app.core.security import SecretEncryptor
        from app.services.delivery_queue import DeliveryQueue
        from app.services.transport_delivery import TransportDeliveryService

        queue = DeliveryQueue(
            get_product_registry(),
            TransportDeliveryService(transport_registry),
            SecretEncryptor("test-secret-key-for-encryption-only"),
        )
        await queue._worker(f"{sim['id']}:azure")
        with get_session_factory()() as db:
            service = runtime(db)
            await service.tick(sim["id"])
            state = db.get(Simulation, sim["id"])
            assert state.status == "completed"
            assert state.runtime_state["events_successful"] == int(accepted)
            assert state.runtime_state["events_failed"] == int(not accepted)
        assert batches == [[original]]
        events = client.get(f"/api/v1/simulations/{sim['id']}/events").json()
        detail = client.get(f"/api/v1/simulations/{sim['id']}/events/{events[0]['id']}")
        assert "function-key-canary" not in detail.text and "oauth-canary" not in detail.text
    finally:
        await transport.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status,ack,success",
    [
        (200, {"accepted_records": 1, "downstream_status": 204, "request_id": "id"}, True),
        (202, {}, False),
        (200, {"accepted_records": 0, "downstream_status": 204, "request_id": "id"}, False),
        (200, {"accepted_records": True, "downstream_status": 204, "request_id": "id"}, False),
        (401, {"secret": "remote-canary"}, False),
        (424, {"secret": "remote-canary"}, False),
        (302, {}, False),
    ],
)
async def test_relay_requires_exact_acknowledgment(status, ack, success):
    transport = AzureFunctionAppTransport(
        httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(status, json=ack)))
    )
    result = await transport.deliver(
        destination(True), b'[{"Message":"hello"}]', "application/json", auth(True)
    )
    assert result.success is success
    assert (
        "remote-canary" not in result.model_dump_json()
        and "function-key-canary" not in result.model_dump_json()
    )
    await transport.close()


@pytest.mark.asyncio
async def test_relay_throttle_and_health_never_uploads(monkeypatch):
    calls = []

    async def sleep(_):
        pass

    monkeypatch.setattr("app.transports.azure_logs_ingestion.asyncio.sleep", sleep)

    def handler(req):
        calls.append(req.method)
        if req.method == "GET":
            assert req.url.path == "/api/health"
            return httpx.Response(200, json={"configured": True})
        if calls.count("POST") == 1:
            return httpx.Response(429, headers={"Retry-After": "0"})
        return httpx.Response(
            200, json={"accepted_records": 1, "downstream_status": 204, "request_id": "id"}
        )

    transport = AzureFunctionAppTransport(httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    checked = await transport.test_destination(destination(True), auth(True))
    assert checked.success and calls == ["GET"]
    sent = await transport.deliver(
        {**destination(True), "max_retries": 1}, b'[{"x":1}]', "application/json", auth(True)
    )
    assert sent.success and calls == ["GET", "POST", "POST"]
    await transport.close()


def test_relay_url_and_missing_key_validation(client):
    body = {
        "name": "Relay",
        "product_id": "uploaded-logs",
        "scenario_ids": ["record"],
        "destination": destination(True),
    }
    for url in [
        "http://relay.test/api/ingest",
        "https://relay.test/api/ingest?code=secret",
        "https://user:password@relay.test/api/ingest",
    ]:
        assert (
            client.post(
                "/api/v1/simulations",
                json={**body, "destination": {**destination(True), "url": url}},
            ).status_code
            == 422
        )
    assert (
        client.post(
            "/api/v1/transport/azure/send",
            json={"destination": destination(True), "auth_config": auth(True)},
        ).status_code
        == 422
    )


def test_csv_rewrite_preflight_and_wire_preview_use_same_rendering(client):
    uploaded = dataset(client, "timestamp,message\n2020-01-01T00:00:00Z,hello\n", "csv")
    body = {
        "name": "CSV upload",
        "product_id": "uploaded-logs",
        "scenario_ids": ["record"],
        "targets": [
            {
                "id": "azure",
                "name": "Azure",
                "destination": destination(True),
                "auth_config": auth(True),
                "payload_format": "default",
            }
        ],
        "replay_config": {"dataset_id": uploaded["id"], "rewrite_timestamps": True},
    }
    saved = client.post("/api/v1/simulations", json=body)
    assert saved.status_code == 201, saved.text
    checked = client.post(
        f"/api/v1/datasets/{uploaded['id']}/validate-ingestion", json={"rewrite_timestamps": True}
    ).json()["records"][0]
    preview = client.post(f"/api/v1/simulations/{saved.json()['id']}/wire-preview?target_id=azure")
    assert preview.status_code == 200, preview.text
    wire = json.loads(preview.json()["wire_text"])[0]
    for record in (checked, wire):
        assert record["RawData"].endswith(",hello")
        assert record["TimeGenerated"] != "2020-01-01T00:00:00Z"
        assert record["RawData"].startswith(record["TimeGenerated"])


def test_finite_uploads_can_cover_large_files_without_relaxing_generated_limits(client):
    uploaded = dataset(client, '{"x":1}\n' * 10001)
    body = {
        "name": "Full file",
        "product_id": "uploaded-logs",
        "scenario_ids": ["record"],
        "destination": destination(True),
        "auth_config": auth(True),
        "replay_config": {"dataset_id": uploaded["id"]},
        "schedule": {"type": "finite", "events_per_second": 10, "event_count": 10001},
    }
    assert client.post("/api/v1/simulations", json=body).status_code == 201
    assert client.post("/api/v1/simulations", json={**body, "replay_config": {}}).status_code == 422
    assert (
        client.post(
            "/api/v1/simulations",
            json={**body, "schedule": {**body["schedule"], "event_count": 10002}},
        ).status_code
        == 422
    )


@pytest.mark.asyncio
async def test_continuous_nonloop_replay_persists_eof_and_drains(client):
    uploaded = dataset(client, '{"x":1}\n{"x":2}\n')
    saved = client.post(
        "/api/v1/simulations",
        json={
            "name": "EOF",
            "product_id": "uploaded-logs",
            "scenario_ids": ["record"],
            "destination": destination(True),
            "auth_config": auth(True),
            "replay_config": {"dataset_id": uploaded["id"]},
            "schedule": {"type": "continuous", "events_per_second": 100},
        },
    )
    assert saved.status_code == 201, saved.text
    sid = saved.json()["id"]
    with get_session_factory()() as db:
        service = runtime(db)
        service.start(sid)
        await service.tick(sid)
    with get_session_factory()() as db:
        state = db.get(Simulation, sid)
        assert state.runtime_state["replay_generation_finished"] is True
        assert state.runtime_state["events_generated"] == 2 and state.status == "running"
        assert db.query(DeliveryJob).filter_by(simulation_id=sid, status="pending").count() == 2
        db.query(DeliveryJob).filter_by(simulation_id=sid).update({"status": "failed"})
        db.commit()
        await runtime(db).tick(sid)
        assert db.get(Simulation, sid).status == "completed"


def test_legacy_batch_limits_normalize_and_remain_readable():
    from app.schemas.simulation import DestinationConfig, DestinationConfigResponse

    legacy = {**destination(False), "batch_max_bytes": 1000000}
    assert DestinationConfig.model_validate(legacy).batch_max_bytes == 950000
    assert DestinationConfigResponse.model_validate(legacy).batch_max_bytes == 1000000
