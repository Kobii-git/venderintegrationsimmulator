"""Integration test for the primary V1 operator workflow."""

import httpx
import respx


def _simulation_payload(**overrides) -> dict:
    payload = {
        "name": "V1 Workflow Test",
        "product_id": "upguard",
        "scenario_id": "data-leak",
        "simulation_mode": "push_webhook",
        "fidelity_mode": "troubleshooting",
        "destination": {
            "transport_id": "http_webhook",
            "url": "https://mock-collector.example/webhook",
            "timeout_seconds": 30,
        },
        "auth_config": {"auth_method_id": "none"},
        "scenario_overrides": {},
        "schedule": {"type": "manual"},
        "fault_config": {"enabled": False},
    }
    payload.update(overrides)
    return payload


@respx.mock
def test_v1_end_to_end_workflow(runtime_client) -> None:
    client, _app = runtime_client
    mock = respx.post("https://mock-collector.example/webhook").mock(
        return_value=httpx.Response(200, json={"accepted": True})
    )

    created = client.post("/api/v1/simulations", json=_simulation_payload()).json()
    sim_id = created["id"]

    preview = client.post(
        "/api/v1/products/upguard/scenarios/data-leak/preview",
        json={"fidelity_mode": "troubleshooting"},
    ).json()
    assert preview["payload"]["notification"]["type"] == "DataLeakPublished"

    send = client.post(f"/api/v1/simulations/{sim_id}/send").json()
    assert send["delivery_success"] is True
    assert mock.called

    events = client.get(f"/api/v1/simulations/{sim_id}/events").json()
    assert len(events) == 1
    event_id = events[0]["id"]
    correlation_id = events[0]["correlation_id"]

    detail = client.get(f"/api/v1/simulations/{sim_id}/events/{event_id}").json()
    assert detail["delivery_attempts"][0]["response_status_code"] == 200
    assert detail["delivery_attempts"][0]["latency_ms"] is not None

    filtered = client.get(
        f"/api/v1/simulations/{sim_id}/events",
        params={"correlation_id": correlation_id},
    ).json()
    assert len(filtered) == 1

    curl = client.get(f"/api/v1/simulations/{sim_id}/events/{event_id}/curl").json()
    assert "curl" in curl["command"]
    assert curl["attempt_id"]
    assert "super-secret" not in curl["command"]

    replay = client.post(
        f"/api/v1/simulations/{sim_id}/events/{event_id}/replay",
        json={"mode": "exact"},
    ).json()
    assert replay["delivery_success"] is True

    export_doc = client.get(f"/api/v1/simulations/{sim_id}/export").json()
    assert export_doc["includes_secrets"] is False
    assert export_doc["simulation"]["auth_config"]["password"] is None

    imported = client.post("/api/v1/simulations/import", json={"document": export_doc}).json()
    assert imported["simulation_id"] != sim_id

    manual = client.post(
        f"/api/v1/simulations/{sim_id}/send",
        json={"payload_override": {"custom": "manual-test"}},
    ).json()
    assert manual["payload_source"] == "manual_override"

    client.patch(
        f"/api/v1/simulations/{sim_id}",
        json={
            "fault_config": {
                "enabled": True,
                "payload": {"remove_fields": ["notification.occurredAt"]},
            }
        },
    )
    fault_send = client.post(f"/api/v1/simulations/{sim_id}/send").json()
    fault_detail = client.get(
        f"/api/v1/simulations/{sim_id}/events/{fault_send['event_id']}"
    ).json()
    assert fault_detail["simulator_metadata"]["fault_injection"]["intentionally_modified"]

    client.patch(
        f"/api/v1/simulations/{sim_id}",
        json={"schedule": {"type": "continuous", "interval_seconds": 1}},
    )
    start = client.post(f"/api/v1/simulations/{sim_id}/start")
    assert start.status_code == 200
    stop = client.post(f"/api/v1/simulations/{sim_id}/stop")
    assert stop.status_code == 200
    assert stop.json()["status"] == "stopped"


@respx.mock
def test_export_rejects_secret_export_without_confirmation(runtime_client) -> None:
    client, _app = runtime_client
    created = client.post("/api/v1/simulations", json=_simulation_payload()).json()
    denied = client.get(
        f"/api/v1/simulations/{created['id']}/export",
        params={"include_secrets": True},
    )
    assert denied.status_code == 422


def test_format_1_import_converts_and_sanitizes_legacy_configuration(runtime_client) -> None:
    client, _app = runtime_client
    legacy = {
        "format_version": "1.0",
        "exported_at": "2026-08-25T12:00:00Z",
        "includes_secrets": False,
        "simulation": {
            "name": "Legacy format import",
            "product_id": "upguard",
            "scenario_id": "data-leak",
            "simulation_mode": "push_webhook",
            "fidelity_mode": "vendor_accurate",
            "status": "running",
            "destination": {
                "transport_id": "http_webhook",
                "url": "https://collector.example/hook?access_token=url-secret",
                "headers": {"X-Api-Key": "header-secret"},
            },
            "auth_config": {
                "auth_method_id": "basic",
                "username": "legacy-user",
                "password": "legacy-password",
            },
            "scenario_overrides": {"affected_domain": "legacy.example"},
            "schedule": {"type": "manual"},
            "fault_config": {},
            "inbound_config": {},
        },
    }
    imported = client.post("/api/v1/simulations/import", json={"document": legacy})
    assert imported.status_code == 201, imported.text
    result = imported.json()
    assert set(result["missing_secrets"]) == {
        "auth_config.password",
        "destination.headers.X-Api-Key",
        "destination.query_params.access_token",
    }

    simulation = client.get(f"/api/v1/simulations/{result['simulation_id']}").json()
    assert simulation["status"] == "stopped"
    assert simulation["scenario_overrides"] == {"data-leak": {"affected_domain": "legacy.example"}}
    assert "legacy-password" not in str(simulation)
    assert "header-secret" not in str(simulation)
    assert "url-secret" not in str(simulation)
