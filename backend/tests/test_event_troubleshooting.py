"""Tests for Phase 8 troubleshooting and delivery inspection features."""

from datetime import UTC, datetime, timedelta

import httpx
import respx
from app.models import EventInstance
from app.services.curl_generator import build_curl_command
from app.services.retention_cleanup import RetentionCleanupService


def _simulation_payload(**overrides) -> dict:
    payload = {
        "name": "Troubleshooting Test",
        "product_id": "upguard",
        "scenario_id": "data-leak",
        "simulation_mode": "push_webhook",
        "fidelity_mode": "vendor_accurate",
        "destination": {
            "transport_id": "http_webhook",
            "url": "https://example.com/webhook",
            "query_params": [
                {
                    "name": "api_key",
                    "value": "super-secret-key",
                    "sensitive": True,
                }
            ],
            "timeout_seconds": 30,
        },
        "auth_config": {
            "auth_method_id": "basic",
            "username": "hook-user",
            "password": "super-secret-password",
        },
        "scenario_overrides": {},
        "schedule": {"type": "manual"},
    }
    payload.update(overrides)
    return payload


@respx.mock
def test_event_list_filters(runtime_client) -> None:
    client, _app = runtime_client
    respx.post("https://example.com/webhook").mock(
        side_effect=[
            httpx.Response(200),
            httpx.Response(500),
            httpx.Response(404),
        ]
    )

    created = client.post("/api/v1/simulations", json=_simulation_payload()).json()
    sim_id = created["id"]

    for _ in range(3):
        client.post(f"/api/v1/simulations/{sim_id}/send")

    all_events = client.get(f"/api/v1/simulations/{sim_id}/events").json()
    assert len(all_events) == 3

    successful = client.get(
        f"/api/v1/simulations/{sim_id}/events",
        params={"success": True},
    ).json()
    assert len(successful) == 1
    assert successful[0]["delivery_success"] is True

    failed = client.get(
        f"/api/v1/simulations/{sim_id}/events",
        params={"success": False},
    ).json()
    assert len(failed) == 2

    by_status = client.get(
        f"/api/v1/simulations/{sim_id}/events",
        params={"http_status": 500},
    ).json()
    assert len(by_status) == 1
    assert by_status[0]["response_status_code"] == 500


@respx.mock
def test_correlation_lookup(runtime_client) -> None:
    client, _app = runtime_client
    respx.post("https://example.com/webhook").mock(return_value=httpx.Response(200))

    created = client.post("/api/v1/simulations", json=_simulation_payload()).json()
    send = client.post(f"/api/v1/simulations/{created['id']}/send").json()
    correlation_id = send["correlation_id"]

    filtered = client.get(
        f"/api/v1/simulations/{created['id']}/events",
        params={"correlation_id": correlation_id},
    ).json()
    assert len(filtered) == 1
    assert filtered[0]["correlation_id"] == correlation_id

    global_search = client.get(
        "/api/v1/events",
        params={"correlation_id": correlation_id},
    ).json()
    assert len(global_search) == 1
    assert global_search[0]["simulation_id"] == created["id"]


@respx.mock
def test_replay_exact_and_regenerate(runtime_client) -> None:
    client, _app = runtime_client
    respx.post("https://example.com/webhook").mock(return_value=httpx.Response(202))

    created = client.post("/api/v1/simulations", json=_simulation_payload()).json()
    sim_id = created["id"]
    original = client.post(f"/api/v1/simulations/{sim_id}/send").json()
    event_id = original["event_id"]
    original_payload = original["payload"]

    exact = client.post(
        f"/api/v1/simulations/{sim_id}/events/{event_id}/replay",
        json={"mode": "exact"},
    ).json()
    assert exact["payload_source"] == "replay_exact"
    assert exact["payload"] == original_payload
    assert exact["source_event_id"] == event_id
    assert exact["new_event_id"] != event_id
    assert exact["delivery_success"] is True

    regenerate = client.post(
        f"/api/v1/simulations/{sim_id}/events/{event_id}/replay",
        json={"mode": "regenerate"},
    ).json()
    assert regenerate["payload_source"] == "replay_regenerate"
    assert regenerate["source_event_id"] == event_id
    assert regenerate["delivery_success"] is True


@respx.mock
def test_manual_json_send(runtime_client) -> None:
    client, _app = runtime_client
    respx.post("https://example.com/webhook").mock(return_value=httpx.Response(200))

    created = client.post("/api/v1/simulations", json=_simulation_payload()).json()
    override = {"custom": "manual-payload", "event": "edited"}
    send = client.post(
        f"/api/v1/simulations/{created['id']}/send",
        json={"payload_override": override},
    ).json()
    assert send["payload"] == override
    assert send["payload_source"] == "manual_override"

    detail = client.get(f"/api/v1/simulations/{created['id']}/events/{send['event_id']}").json()
    assert detail["payload_source"] == "manual_override"
    assert detail["simulator_metadata"].get("manual_edit") is True


@respx.mock
def test_preview_send_preserves_correlation_and_generated_source(runtime_client) -> None:
    client, _app = runtime_client
    respx.post("https://example.com/webhook").mock(return_value=httpx.Response(200))

    created = client.post("/api/v1/simulations", json=_simulation_payload()).json()
    preview = client.post(
        "/api/v1/products/upguard/scenarios/data-leak/preview",
        json={"fidelity_mode": "vendor_accurate"},
    ).json()
    send = client.post(
        f"/api/v1/simulations/{created['id']}/send",
        json={
            "payload_override": preview["payload"],
            "scenario_id": preview["scenario_id"],
            "preview_correlation_id": preview["correlation_id"],
            "payload_edited": False,
        },
    ).json()

    assert send["correlation_id"] == preview["correlation_id"]
    assert send["payload"] == preview["payload"]
    assert send["payload_source"] == "generated"
    detail = client.get(f"/api/v1/simulations/{created['id']}/events/{send['event_id']}").json()
    assert detail["correlation_id"] == preview["correlation_id"]
    assert detail["payload_source"] == "generated"
    assert detail["simulator_metadata"]["preview_send"] is True
    attempt = detail["delivery_attempts"][0]
    assert attempt["success"] is True
    assert attempt["error_category"] is None
    assert attempt["error_explanation"] is None


@respx.mock
def test_curl_generation_redacts_secrets(runtime_client) -> None:
    client, _app = runtime_client
    respx.post("https://example.com/webhook").mock(return_value=httpx.Response(200))

    created = client.post("/api/v1/simulations", json=_simulation_payload()).json()
    send = client.post(f"/api/v1/simulations/{created['id']}/send").json()

    curl = client.get(f"/api/v1/simulations/{created['id']}/events/{send['event_id']}/curl").json()
    assert curl["secrets_redacted"] is True
    command = curl["command"]
    assert curl["exact"] is True
    assert curl["attempt_id"]
    assert "super-secret-password" not in command
    assert "super-secret-key" not in command
    assert "<REDACTED>" in command or "Basic auth configured" in command


def test_curl_generator_unit() -> None:
    command = build_curl_command(
        method="POST",
        destination_url="https://example.com/hook",
        query_params={"token": "secret-token"},
        headers={"Authorization": "Bearer real-token", "Content-Type": "application/json"},
        body='{"test": true}',
        auth_method_id="bearer",
        auth_header_present=True,
    )
    assert "real-token" not in command
    assert "secret-token" not in command
    assert "<REDACTED>" in command
    assert "POST" in command


@respx.mock
def test_delivery_detail_includes_query_params_and_error_explanation(runtime_client) -> None:
    client, _app = runtime_client
    respx.post("https://example.com/webhook").mock(return_value=httpx.Response(503))

    created = client.post("/api/v1/simulations", json=_simulation_payload()).json()
    send = client.post(f"/api/v1/simulations/{created['id']}/send").json()

    detail = client.get(f"/api/v1/simulations/{created['id']}/events/{send['event_id']}").json()
    attempt = detail["delivery_attempts"][0]
    assert "api_key" in attempt["request_query_params_redacted"]
    assert attempt["request_query_params_redacted"]["api_key"] == "***REDACTED***"
    assert attempt["error_explanation"] is not None
    assert (
        "5xx" in attempt["error_explanation"].lower()
        or "error" in attempt["error_explanation"].lower()
    )


def test_retention_cleanup(test_settings, db_engine) -> None:
    from app.models import Simulation
    from sqlalchemy.orm import sessionmaker

    Session = sessionmaker(bind=db_engine)
    db = Session()
    try:
        simulation = Simulation(
            id="sim-old",
            name="Old Sim",
            product_id="upguard",
            scenario_id="data-leak",
            scenario_ids=["data-leak"],
        )
        db.add(simulation)
        db.flush()

        old_event = EventInstance(
            simulation_id=simulation.id,
            product_id="upguard",
            scenario_id="data-leak",
            fidelity_mode="vendor_accurate",
            payload={"test": True},
            correlation_id="old-correlation",
            status="delivered",
            generated_at=datetime.now(UTC) - timedelta(days=60),
        )
        db.add(old_event)
        db.commit()
        event_id = old_event.id

        service = RetentionCleanupService(db, test_settings)
        result = service.cleanup()
        assert result["deleted_by_age"] >= 1

        remaining = db.query(EventInstance).filter(EventInstance.id == event_id).count()
        assert remaining == 0
    finally:
        db.close()
