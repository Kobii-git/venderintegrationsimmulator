from pathlib import Path
from urllib.parse import urlencode

import httpx
import pytest
import respx
from app.schemas.simulation import ConfiguredValueInput

BASE_URL = "https://logic.example.test/workflows/example/triggers/manual/paths/invoke"
SIGNATURE = "logic-signature-canary+slash/=equal"
PARAMS = {
    "api-version": "2016-10-01",
    "sp": "/triggers/manual/run",
    "sv": "1.0",
    "sig": SIGNATURE,
    "blank": "",
}
FULL_URL = BASE_URL + "?" + urlencode(PARAMS)


def _simulation() -> dict:
    return {
        "name": "Signed webhook regression",
        "product_id": "upguard",
        "scenario_id": "data-leak",
        "scenario_ids": ["data-leak"],
        "simulation_mode": "push_webhook",
        "fidelity_mode": "vendor_accurate",
        "destination": {"url": FULL_URL},
        "schedule": {"type": "manual"},
    }


@respx.mock
def test_signed_url_create_edit_send_preserves_parameters_and_hides_values(
    client, test_settings
) -> None:
    route = respx.post(url__regex=r"https://logic\.example\.test/.*").mock(
        return_value=httpx.Response(200, text=SIGNATURE)
    )
    response = client.post("/api/v1/simulations", json=_simulation())
    assert response.status_code == 201, response.text
    created = response.json()
    destination = created["destination"]
    assert destination["url"] == BASE_URL
    assert destination["query_params"] == [
        {"name": name, "sensitive": True, "has_value": True} for name in PARAMS
    ]
    assert SIGNATURE not in response.text
    # An ordinary edit keeps hidden values without copying them into the UI.
    edited_destination = {
        "url": BASE_URL,
        "query_params": [{"name": name, "sensitive": True} for name in PARAMS],
    }
    edited = client.patch(
        f"/api/v1/simulations/{created['id']}", json={"destination": edited_destination}
    )
    assert edited.status_code == 200, edited.text
    assert all(item["has_value"] for item in edited.json()["destination"]["query_params"])
    sent = client.post(f"/api/v1/simulations/{created['id']}/send")
    assert sent.status_code == 200, sent.text
    assert route.called
    assert dict(route.calls.last.request.url.params) == PARAMS
    detail = client.get(f"/api/v1/simulations/{created['id']}/events/{sent.json()['event_id']}")
    attempt = detail.json()["delivery_attempts"][0]
    assert attempt["request_query_params_redacted"]["sig"] == "***REDACTED***"
    export = client.get(f"/api/v1/simulations/{created['id']}/export")
    curl = client.get(
        f"/api/v1/simulations/{created['id']}/events/{sent.json()['event_id']}/curl",
        params={"attempt_id": attempt["id"]},
    )
    for evidence in (edited, sent, detail, export, curl):
        assert SIGNATURE not in evidence.text
        assert urlencode({"sig": SIGNATURE}) not in evidence.text
    database = Path(test_settings.resolved_database_url.removeprefix("sqlite:///"))
    assert SIGNATURE.encode() not in database.read_bytes()
    assert urlencode({"sig": SIGNATURE}).encode() not in database.read_bytes()


@pytest.mark.parametrize("operation,method", [("test", "HEAD"), ("send", "POST")])
@respx.mock
def test_signed_url_transport_test_and_send_use_all_parameters(client, operation, method) -> None:
    route = respx.request(method, url__regex=r"https://logic\.example\.test/.*").mock(
        return_value=httpx.Response(200, text=SIGNATURE)
    )
    response = client.post(
        f"/api/v1/transport/http/{operation}", json={"url": FULL_URL, "method": method}
    )
    assert response.status_code == 200, response.text
    assert response.json()["success"] is True
    assert dict(route.calls.last.request.url.params) == PARAMS
    assert SIGNATURE not in response.text
    assert urlencode({"sig": SIGNATURE}) not in response.text


@pytest.mark.parametrize("name", ["sig", "SIG", "signature", "X-Signature"])
def test_signature_names_cannot_be_marked_public(name: str) -> None:
    assert ConfiguredValueInput(name=name, value=SIGNATURE, sensitive=False).sensitive


@pytest.mark.parametrize("endpoint", ["/simulations", "/transport/http/test"])
@pytest.mark.parametrize("url", [BASE_URL + "?sig=one&sig=two", BASE_URL + "?=value"])
def test_invalid_inline_query_is_rejected_without_echoing_inputs(client, endpoint, url) -> None:
    payload = _simulation() if endpoint == "/simulations" else {"url": url}
    if endpoint == "/simulations":
        payload["destination"] = {"url": url}
    response = client.post("/api/v1" + endpoint, json=payload)
    assert response.status_code == 422
    assert url not in response.text


@pytest.mark.parametrize("endpoint", ["/simulations", "/transport/http/test"])
def test_inline_and_separate_query_collisions_are_rejected(client, endpoint) -> None:
    if endpoint == "/simulations":
        payload = _simulation()
        payload["destination"] = {
            "url": FULL_URL,
            "query_params": [{"name": "sig", "value": "other-signature"}],
        }
    else:
        payload = {"url": FULL_URL, "query_params": {"sig": "other-signature"}}
    response = client.post("/api/v1" + endpoint, json=payload)
    assert response.status_code == 422
    assert SIGNATURE not in response.text
