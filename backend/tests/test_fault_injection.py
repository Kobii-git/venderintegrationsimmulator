"""Tests for Phase 9 fault injection and burst simulation."""

import copy

import httpx
import respx
from app.domain.fault_config import FaultConfig, PayloadFaults, TimestampFault
from app.domain.fault_injection import apply_payload_faults

SAMPLE_PAYLOAD: dict = {
    "notification": {
        "id": "n-1",
        "type": "DataLeakPublished",
        "occurredAt": "2026-01-01T00:00:00Z",
        "context": {"Title": "Leak title", "Domain": "example.com"},
    },
    "_simulator": {"simulator_timestamp": "2026-01-01T00:00:00Z"},
}


def _sample_payload() -> dict:
    return copy.deepcopy(SAMPLE_PAYLOAD)


def _simulation_payload(**overrides) -> dict:
    payload = {
        "name": "Fault Injection Test",
        "product_id": "upguard",
        "scenario_id": "data-leak",
        "simulation_mode": "push_webhook",
        "fidelity_mode": "troubleshooting",
        "destination": {
            "transport_id": "http_webhook",
            "url": "https://example.com/webhook",
            "timeout_seconds": 30,
        },
        "auth_config": {"auth_method_id": "none"},
        "scenario_overrides": {},
        "schedule": {"type": "manual"},
        "fault_config": {"enabled": False},
    }
    payload.update(overrides)
    return payload


def test_remove_timestamp_mutation() -> None:
    payload = _sample_payload()
    original = copy.deepcopy(payload)
    fault = FaultConfig(
        enabled=True,
        payload=PayloadFaults(remove_timestamp=True),
    )
    mutated, applied, _ = apply_payload_faults(payload, fault)
    assert isinstance(mutated, dict)
    assert "occurredAt" not in mutated["notification"]
    assert applied
    assert original["notification"]["occurredAt"]


def test_invalid_timestamp_mutation() -> None:
    payload = _sample_payload()
    fault = FaultConfig(enabled=True, payload=PayloadFaults(invalid_timestamp=True))
    mutated, applied, _ = apply_payload_faults(payload, fault)
    assert mutated["notification"]["occurredAt"] == "NOT-A-VALID-TIMESTAMP"
    assert any("invalid_timestamp" in item for item in applied)


def test_offset_timestamp_past() -> None:
    payload = _sample_payload()
    fault = FaultConfig(
        enabled=True,
        payload=PayloadFaults(
            timestamp=TimestampFault(
                mode="offset",
                offset_amount=7,
                offset_unit="days",
                offset_direction="past",
            )
        ),
    )
    mutated, applied, _ = apply_payload_faults(payload, fault)
    assert any("timestamp_offset" in item for item in applied)
    assert "T" in mutated["notification"]["occurredAt"]


def test_missing_and_null_fields() -> None:
    payload = _sample_payload()
    fault = FaultConfig(
        enabled=True,
        payload=PayloadFaults(
            remove_fields=["notification.context.Title"],
            null_fields=["notification.context.Domain"],
            extra_fields={"notification.context.Injected": "fault-value"},
        ),
    )
    mutated, applied, _ = apply_payload_faults(payload, fault)
    assert "Title" not in mutated["notification"]["context"]
    assert mutated["notification"]["context"]["Domain"] is None
    assert mutated["notification"]["context"]["Injected"] == "fault-value"
    assert len(applied) == 3


def test_large_field_mutation() -> None:
    payload = _sample_payload()
    fault = FaultConfig(
        enabled=True,
        payload=PayloadFaults(large_field_path="notification.context.Bulk", large_field_size_kb=1),
    )
    mutated, applied, _ = apply_payload_faults(payload, fault)
    assert len(mutated["notification"]["context"]["Bulk"]) == 1024
    assert applied[0].startswith("large_field:")


def test_malformed_json_hint() -> None:
    payload = _sample_payload()
    fault = FaultConfig(enabled=True, payload=PayloadFaults(malformed_json=True))
    _, applied, hints = apply_payload_faults(payload, fault)
    assert "malformed_json" in applied
    assert "malformed_body" in hints
    assert "not-valid-json" in hints["malformed_body"]


def test_vendor_template_unchanged_after_fault_application() -> None:
    template_body = {
        "notification": {
            "occurredAt": "{{ generated_at_iso }}",
            "context": {"Title": "{{ leak_title }}"},
        }
    }
    template_snapshot = copy.deepcopy(template_body)
    payload = _sample_payload()
    fault = FaultConfig(
        enabled=True,
        payload=PayloadFaults(remove_fields=["notification.id"], invalid_timestamp=True),
    )
    apply_payload_faults(payload, fault)
    assert template_body == template_snapshot


@respx.mock
def test_fault_injected_send_records_metadata(runtime_client) -> None:
    client, _app = runtime_client
    respx.post("https://example.com/webhook").mock(return_value=httpx.Response(200))

    created = client.post(
        "/api/v1/simulations",
        json=_simulation_payload(
            fault_config={
                "enabled": True,
                "payload": {"remove_fields": ["notification.occurredAt"]},
            }
        ),
    ).json()

    send = client.post(f"/api/v1/simulations/{created['id']}/send").json()
    detail = client.get(f"/api/v1/simulations/{created['id']}/events/{send['event_id']}").json()
    assert detail["simulator_metadata"]["fault_injection"]["intentionally_modified"] is True
    assert "notification.occurredAt" in str(
        detail["simulator_metadata"]["fault_injection"]["applied_faults"]
    )


@respx.mock
def test_duplicate_correlation_id(runtime_client) -> None:
    client, _app = runtime_client
    respx.post("https://example.com/webhook").mock(return_value=httpx.Response(200))

    created = client.post("/api/v1/simulations", json=_simulation_payload()).json()
    first = client.post(f"/api/v1/simulations/{created['id']}/send").json()

    client.patch(
        f"/api/v1/simulations/{created['id']}",
        json={
            "fault_config": {
                "enabled": True,
                "duplicate": {
                    "mode": "duplicate_correlation_id",
                    "source_event_id": first["event_id"],
                },
            }
        },
    )
    second = client.post(f"/api/v1/simulations/{created['id']}/send").json()
    assert second["correlation_id"] == first["correlation_id"]
    assert second["payload"] != first["payload"]


@respx.mock
def test_exact_payload_duplicate_mode(runtime_client) -> None:
    client, _app = runtime_client
    respx.post("https://example.com/webhook").mock(return_value=httpx.Response(200))

    created = client.post("/api/v1/simulations", json=_simulation_payload()).json()
    first = client.post(f"/api/v1/simulations/{created['id']}/send").json()

    client.patch(
        f"/api/v1/simulations/{created['id']}",
        json={
            "fault_config": {
                "enabled": True,
                "duplicate": {
                    "mode": "exact_payload",
                    "source_event_id": first["event_id"],
                },
            }
        },
    )
    second = client.post(f"/api/v1/simulations/{created['id']}/send").json()
    assert second["payload"] == first["payload"]
    assert second["correlation_id"] != first["correlation_id"]


@respx.mock
def test_burst_respects_limits(runtime_client) -> None:
    client, _app = runtime_client
    respx.post("https://example.com/webhook").mock(return_value=httpx.Response(200))

    created = client.post("/api/v1/simulations", json=_simulation_payload()).json()
    sim_id = created["id"]

    over_limit = client.post(
        f"/api/v1/simulations/{sim_id}/burst",
        json={"count": 100, "confirm_large_run": True},
    )
    assert over_limit.status_code == 422

    burst = client.post(
        f"/api/v1/simulations/{sim_id}/burst",
        json={"count": 5, "events_per_second": 10},
    )
    assert burst.status_code == 422

    ok = client.post(
        f"/api/v1/simulations/{sim_id}/burst",
        json={"count": 3, "interval_ms": 0},
    )
    assert ok.status_code == 200
    data = ok.json()
    assert data["generated"] == 3
    assert len(data["event_ids"]) == 3


@respx.mock
def test_large_burst_requires_confirmation(runtime_client) -> None:
    client, _app = runtime_client
    respx.post("https://example.com/webhook").mock(return_value=httpx.Response(200))

    created = client.post("/api/v1/simulations", json=_simulation_payload()).json()
    denied = client.post(
        f"/api/v1/simulations/{created['id']}/burst",
        json={"count": 25},
    )
    assert denied.status_code == 422

    allowed = client.post(
        f"/api/v1/simulations/{created['id']}/burst",
        json={"count": 25, "confirm_large_run": True},
    )
    assert allowed.status_code == 200
    assert allowed.json()["generated"] == 25


@respx.mock
def test_delivery_duplicate_send_count(runtime_client) -> None:
    client, _app = runtime_client
    route = respx.post("https://example.com/webhook").mock(return_value=httpx.Response(200))

    created = client.post(
        "/api/v1/simulations",
        json=_simulation_payload(
            fault_config={
                "enabled": True,
                "delivery": {"duplicate_send_count": 2},
            }
        ),
    ).json()

    send = client.post(f"/api/v1/simulations/{created['id']}/send").json()
    detail = client.get(f"/api/v1/simulations/{created['id']}/events/{send['event_id']}").json()
    assert len(detail["delivery_attempts"]) == 2
    assert route.call_count == 2


@respx.mock
def test_manual_malformed_payload_send(runtime_client) -> None:
    client, _app = runtime_client
    route = respx.post("https://example.com/webhook").mock(return_value=httpx.Response(400))

    created = client.post(
        "/api/v1/simulations",
        json=_simulation_payload(
            fault_config={"enabled": True, "payload": {"malformed_json": True}},
        ),
    ).json()

    client.post(f"/api/v1/simulations/{created['id']}/send")
    assert route.called
    sent_body = route.calls.last.request.content.decode("utf-8")
    assert "not-valid-json" in sent_body
