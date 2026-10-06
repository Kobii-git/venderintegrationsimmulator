import json
from xml.etree import ElementTree

import pytest
import respx


@pytest.mark.parametrize(
    ("scenario", "notification_type"),
    [
        ("score-threshold", "CustomerCSTARUnderThreshold"),
        ("data-leak", "DataLeakPublished"),
        ("identity-breach", "IdentityBreachPublished"),
        ("vulnerability", "NewVulnerabilityDetected"),
    ],
)
@respx.mock
def test_raw_upguard_generation_without_delivery_or_simulation(
    client, scenario, notification_type
) -> None:
    before = client.get("/api/v1/simulations").json()
    response = client.post(f"/api/v1/products/upguard/scenarios/{scenario}/raw", json={})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["content_type"] == "application/json"
    assert result["fidelity_mode"] == "vendor_accurate"
    body = json.loads(result["raw_log"])
    assert set(body) == {"notification"}
    assert body["notification"]["type"] == notification_type
    assert isinstance(body["notification"]["id"], int)
    if scenario == "score-threshold":
        assert body["notification"]["context"] == {
            "LatestScore": 599,
            "PrevScore": 732,
            "Threshold": 600,
        }
    if scenario == "identity-breach":
        assert body["notification"]["context"]["AffectedEmails"] == 3
    assert client.get("/api/v1/simulations").json() == before
    assert not respx.calls


def test_raw_values_and_diagnostics(client) -> None:
    response = client.post(
        "/api/v1/products/upguard/scenarios/data-leak/raw",
        json={
            "scenario_overrides": {"affected_domain": "custom.example", "leak_title": "éxample"},
            "fidelity_mode": "troubleshooting",
            "correlation_id": "raw-example",
        },
    )
    assert response.status_code == 200
    body = json.loads(response.json()["raw_log"])
    assert body["notification"]["context"]["Domain"] == "custom.example"
    assert body["notification"]["context"]["Title"] == "éxample"
    assert body["_simulator"]["simulator_event_id"] == "raw-example"


def test_raw_native_fortinet(client) -> None:
    response = client.post("/api/v1/products/fortinet/scenarios/forward-traffic-allow/raw", json={})
    assert response.status_code == 200
    raw = response.json()["raw_log"]
    assert "srcip=" in raw
    assert "_syslog_message" not in raw
    assert not raw.startswith("{")
    assert response.json()["content_type"] == "text/plain"


def test_raw_windows_default_format(client) -> None:
    response = client.post("/api/v1/products/windows-dc/scenarios/logon-success/raw", json={})
    assert response.status_code == 200
    raw = response.json()["raw_log"]
    assert "_source_event" not in raw
    root = ElementTree.fromstring(raw)
    assert root.find("{*}System/{*}EventID").text == "4624"
    assert response.json()["content_type"] == "application/xml"


def test_raw_invalid_configuration_and_missing_scenario(client) -> None:
    invalid = client.post(
        "/api/v1/products/upguard/scenarios/score-threshold/raw",
        json={"scenario_overrides": {"latest_score": "invalid"}},
    )
    assert invalid.status_code == 422
    missing = client.post("/api/v1/products/upguard/scenarios/missing/raw", json={})
    assert missing.status_code == 404


def test_raw_okta_source_uses_log_body_without_event_hook_envelope(client) -> None:
    response = client.post("/api/v1/products/okta/scenarios/sim-sign-in/raw", json={})
    assert response.status_code == 200
    body = json.loads(response.json()["raw_log"])
    assert "_source_event" not in body
    assert body["eventType"] != "com.okta.event_hook"
