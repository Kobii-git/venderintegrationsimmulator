import gzip
import json
import time
from urllib.parse import urlsplit

import httpx
import pytest
import respx
from app.transports.cloudflare_logpush import encode_logpush


def create(client, product, **extra):
    body = {
        "name": "Vendor native test",
        "product_id": product,
        "scenario_id": "http-request" if product == "cloudflare" else "email-receipt",
        "scenario_ids": ["http-request"]
        if product == "cloudflare"
        else ["email-receipt", "email-delivery"],
        "destination": {
            "transport_id": "cloudflare_logpush" if product == "cloudflare" else "http_webhook",
            "url": "https://collector.example.test/logs",
        },
        "schedule": {"type": "manual"},
    }
    body.update(extra)
    response = client.post("/api/v1/simulations", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def mimecast(client):
    sim = create(
        client,
        "mimecast",
        simulation_mode="pull_api",
        auth_config={
            "auth_method_id": "none",
            "oauth_client_id": "lab-client",
            "oauth_client_secret": "lab-client-secret",
        },
        inbound_config={
            "auth_method_id": "oauth2_client_credentials",
            "dataset_size": 5,
            "vendor_options": {"download_ttl_seconds": 60},
        },
    )
    response = client.post(f"/api/v1/simulations/{sim['id']}/start")
    assert response.status_code == 200, response.text
    token = client.post(
        f"/api/v1/mock/mimecast/oauth/token?simulation_id={sim['id']}",
        data={
            "grant_type": "client_credentials",
            "client_id": "lab-client",
            "client_secret": "lab-client-secret",
        },
    )
    assert token.status_code == 200, token.text
    return sim, {"Authorization": "Bearer " + token.json()["access_token"]}


def local_path(url):
    parsed = urlsplit(url)
    return parsed.path + "?" + parsed.query


@respx.mock
def test_cloudflare_raw_native_delivery_action_and_wire_preview(client):
    route = respx.post("https://collector.example.test/logs").mock(return_value=httpx.Response(200))
    sim = create(client, "cloudflare")
    raw = client.post("/api/v1/products/cloudflare/scenarios/http-request/raw", json={})
    assert raw.status_code == 200, raw.text
    assert len(json.loads(raw.json()["raw_log"])["RayID"]) == 16
    sent = client.post(f"/api/v1/simulations/{sim['id']}/send")
    assert sent.status_code == 200, sent.text
    records = gzip.decompress(route.calls.last.request.content).decode().splitlines()
    assert len(records) == 1 and json.loads(records[0])["ClientIP"] == "198.51.100.20"
    preview = client.post(
        f"/api/v1/simulations/{sim['id']}/wire-preview?target_id={sim['targets'][0]['id']}"
    )
    assert preview.status_code == 200, preview.text
    import base64

    wire = preview.json()
    assert wire["compression"] == "gzip" and wire["record_count"] == 1
    assert (
        json.loads(gzip.decompress(base64.b64decode(wire["wire_base64"])))["ClientIP"]
        == "198.51.100.20"
    )
    action = client.post(f"/api/v1/simulations/{sim['id']}/actions/validate-destination")
    assert action.status_code == 200, action.text
    assert json.loads(gzip.decompress(route.calls.last.request.content)) == {"content": "tests"}
    assert "test.txt.gz" in route.calls.last.request.headers["content-disposition"]


@pytest.mark.parametrize(
    "payload",
    [
        b"[]",
        b"[1]",
        b"null",
        b'"text"',
        json.dumps([{}] * 1001).encode(),
        json.dumps({"large": "x" * 950001}).encode(),
    ],
)
def test_logpush_bounds(payload):
    with pytest.raises(ValueError):
        encode_logpush(payload)


def test_logpush_multiple_records():
    records = [{"ClientIP": "192.0.2.1"}, {"Action": "block"}]
    assert [
        json.loads(line)
        for line in gzip.decompress(encode_logpush(json.dumps(records).encode())).splitlines()
    ] == records


def test_mimecast_auth_batch_checkpoints_download_repeat_stop_and_redaction(client):
    sim, auth = mimecast(client)
    base = f"/api/v1/mock/mimecast/siem/v1/batch/events/cg?simulation_id={sim['id']}&pageSize=2"
    assert client.get(base).status_code == 401
    page = client.get(base, headers=auth)
    assert page.status_code == 200, page.text
    download = local_path(page.json()["value"][0]["url"])
    one = client.get(download)
    assert one.status_code == 200, one.text
    records = [json.loads(line) for line in gzip.decompress(one.content).splitlines()]
    assert len(records) == 2 and records[0]["type"] == "receipt"
    assert client.get(download).content == one.content
    cursor = page.json()["@nextPage"]
    page2 = client.get(base, headers=auth, params={"nextPage": cursor})
    assert page2.status_code == 200 and page2.json()["value"]
    # The final checkpoint can be polled repeatedly without replaying earlier logs.
    page3 = client.get(base, headers=auth, params={"nextPage": page2.json()["@nextPage"]})
    end = client.get(base, headers=auth, params={"nextPage": page3.json()["@nextPage"]})
    assert end.json()["value"] == []
    client.post(f"/api/v1/simulations/{sim['id']}/stop")
    assert client.get(download).content == one.content
    assert client.get(download.replace("token=", "token=invalid")).status_code == 403
    history = client.get(f"/api/v1/simulations/{sim['id']}/inbound-requests")
    assert "lab-client-secret" not in history.text
    assert urlsplit(page.json()["value"][0]["url"]).query.split("token=")[1] not in history.text


def test_mimecast_link_expiry(client, monkeypatch):
    sim, auth = mimecast(client)
    page = client.get(
        f"/api/v1/mock/mimecast/siem/v1/batch/events/cg?simulation_id={sim['id']}", headers=auth
    )
    path = local_path(page.json()["value"][0]["url"])
    now = time.time()
    monkeypatch.setattr(time, "time", lambda: now + 61)
    assert client.get(path).status_code == 403


@pytest.mark.parametrize(
    "route,field",
    [
        ("api/audit/get-audit-events", "audit"),
        ("api/ttp/url/get-logs", "clickLogs"),
        ("api/ttp/attachment/get-logs", "attachmentLogs"),
        ("api/ttp/impersonation/get-logs", "impersonationLogs"),
        ("api/dlp/get-logs", "dlpLogs"),
    ],
)
def test_mimecast_post_envelopes_and_paging(client, route, field):
    sim, auth = mimecast(client)
    path = f"/api/v1/mock/mimecast/{route}?simulation_id={sim['id']}"
    body = {"meta": {"pagination": {"pageSize": 2}}, "data": [{}]}
    first = client.post(path, headers=auth, json=body)
    assert first.status_code == 200, first.text
    assert len(first.json()["data"] if field == "audit" else first.json()["data"][0][field]) == 2
    body["meta"]["pagination"]["pageToken"] = first.json()["meta"]["pagination"]["next"]
    second = client.post(path, headers=auth, json=body)
    assert second.status_code == 200 and second.json()["data"] != first.json()["data"]
    assert client.post(path, headers=auth, content="invalid").status_code == 400


@pytest.mark.parametrize(
    "body",
    [
        {"meta": []},
        {"meta": {"pagination": []}},
        {"meta": {"pagination": {"pageSize": None}}, "data": [{}]},
        {"meta": {"pagination": {"pageToken": 2}}, "data": [{}]},
        {"data": []},
        {"data": [None]},
        {"data": [{"from": "bad"}]},
        {"data": [{"from": "2026-10-07T12:00:00Z", "to": "2026-10-06T12:00:00Z"}]},
    ],
)
def test_mimecast_invalid_bodies_are_400(client, body):
    sim, auth = mimecast(client)
    response = client.post(
        f"/api/v1/mock/mimecast/api/ttp/url/get-logs?simulation_id={sim['id']}",
        headers=auth,
        json=body,
    )
    assert response.status_code == 400, response.text


def test_mimecast_type_filter_bad_cursor_scope_and_time_window(client):
    sim, auth = mimecast(client)
    base = f"/api/v1/mock/mimecast/siem/v1/batch/events/cg?simulation_id={sim['id']}"
    receipt = client.get(base, headers=auth, params={"type": "receipt"})
    path = local_path(receipt.json()["value"][0]["url"])
    assert all(
        r["type"] == "receipt"
        for r in map(json.loads, gzip.decompress(client.get(path).content).splitlines())
    )
    assert client.get(base, headers=auth, params={"nextPage": "invalid"}).status_code == 400
    other, other_auth = mimecast(client)
    assert client.get(path.replace(sim["id"], other["id"])).status_code == 403
    assert client.get(base, headers=other_auth).status_code == 401
    audit = client.post(
        f"/api/v1/mock/mimecast/api/audit/get-audit-events?simulation_id={sim['id']}",
        headers=auth,
        json={
            "data": [
                {"startDateTime": "2100-01-01T00:00:00Z", "endDateTime": "2100-01-02T00:00:00Z"}
            ]
        },
    )
    assert audit.status_code == 200 and audit.json()["data"] == []


@pytest.mark.parametrize(
    "fault", [{"force_empty": True}, {"response_status": 429}, {"pagination_inconsistent": True}]
)
def test_mimecast_faults(client, fault):
    sim = create(
        client,
        "mimecast",
        simulation_mode="pull_api",
        auth_config={
            "auth_method_id": "none",
            "oauth_client_id": "lab-client",
            "oauth_client_secret": "lab-client-secret",
        },
        inbound_config={
            "auth_method_id": "oauth2_client_credentials",
            "dataset_size": 3,
            "fault_config": {"enabled": True, **fault},
        },
    )
    client.post(f"/api/v1/simulations/{sim['id']}/start")
    token = client.post(
        f"/api/v1/mock/mimecast/oauth/token?simulation_id={sim['id']}",
        data={
            "grant_type": "client_credentials",
            "client_id": "lab-client",
            "client_secret": "lab-client-secret",
        },
    )
    auth = {"Authorization": "Bearer " + token.json()["access_token"]}
    response = client.get(
        f"/api/v1/mock/mimecast/siem/v1/batch/events/cg?simulation_id={sim['id']}", headers=auth
    )
    if fault.get("response_status"):
        assert response.status_code == 429
    elif fault.get("force_empty"):
        assert response.json()["value"] == []
    else:
        assert response.json()["@nextPage"] == "invalid-cursor-token"


@pytest.mark.parametrize("product", ["cloudflare", "mimecast"])
def test_new_vendor_all_scenarios_editable_raw_and_saved(client, product):
    detail = client.get(f"/api/v1/products/{product}").json()
    assert detail["connection_profiles"]
    for scenario in detail["scenarios"]:
        raw = client.post(
            f"/api/v1/products/{product}/scenarios/{scenario['id']}/raw",
            json={"scenario_overrides": {"src": "192.0.2.123"}},
        )
        assert raw.status_code == 200, raw.text
        assert "192.0.2.123" in raw.json()["raw_log"]
    sim = create(client, product)
    assert client.get(f"/api/v1/simulations/{sim['id']}").status_code == 200


@pytest.mark.asyncio
@respx.mock
async def test_cloudflare_queue_batches_reclaimed_jobs(runtime_client, monkeypatch):
    import asyncio

    from app.api.deps import get_product_registry
    from app.core.database import get_session_factory
    from app.core.security import SecretEncryptor
    from app.models import DeliveryJob, Simulation
    from app.services.delivery_queue import DeliveryQueue
    from app.services.transport_delivery import TransportDeliveryService
    from app.transports.cloudflare_logpush import CloudflareLogpushTransport
    from app.transports.registry import transport_registry

    from tests.test_log_lab import runtime

    client, _ = runtime_client
    sim = create(
        client,
        "cloudflare",
        schedule={"type": "finite", "events_per_second": 100, "event_count": 20},
    )
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200)

    respx.post("https://collector.example.test/logs").mock(side_effect=handler)
    transport = CloudflareLogpushTransport()
    monkeypatch.setitem(transport_registry._transports, "cloudflare_logpush", transport)
    with get_session_factory()() as db:
        service = runtime(db)
        service.start(sim["id"])
        await service.tick(sim["id"])
        await service.tick(sim["id"])
        db.query(DeliveryJob).filter_by(simulation_id=sim["id"]).update({"status": "active"})
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
                    .filter_by(simulation_id=sim["id"], status="delivered")
                    .count()
                    == 20
                ):
                    break
            await asyncio.sleep(0.02)
        assert len(calls) == 1
        records = list(map(json.loads, gzip.decompress(calls[0].content).splitlines()))
        assert len(records) == 20 and all("RayID" in record for record in records)
        with get_session_factory()() as db:
            assert db.get(Simulation, sim["id"]).runtime_state["events_successful"] == 20
    finally:
        await queue.close()
        await transport.close()


def test_mimecast_dlp_is_separate_from_cg_batch(client):
    sim = create(
        client,
        "mimecast",
        simulation_mode="pull_api",
        auth_config={
            "auth_method_id": "none",
            "oauth_client_id": "separate-client",
            "oauth_client_secret": "separate-secret",
        },
        inbound_config={"auth_method_id": "oauth2_client_credentials", "dataset_size": 20},
    )
    client.post(f"/api/v1/simulations/{sim['id']}/start")
    token = client.post(
        f"/api/v1/mock/mimecast/oauth/token?simulation_id={sim['id']}",
        data={
            "grant_type": "client_credentials",
            "client_id": "separate-client",
            "client_secret": "separate-secret",
        },
    )
    auth = {"Authorization": "Bearer " + token.json()["access_token"]}
    base = f"/api/v1/mock/mimecast/siem/v1/batch/events/cg?simulation_id={sim['id']}"
    batch = client.get(base, headers=auth, params={"pageSize": 100})
    records = list(
        map(
            json.loads,
            gzip.decompress(
                client.get(local_path(batch.json()["value"][0]["url"])).content
            ).splitlines(),
        )
    )
    assert len(records) == 20 and all(record["type"] != "dlp" for record in records)
    dlp = client.post(
        f"/api/v1/mock/mimecast/api/dlp/get-logs?simulation_id={sim['id']}",
        headers=auth,
        json={"data": [{}]},
    )
    assert len(dlp.json()["data"][0]["dlpLogs"]) == 20
