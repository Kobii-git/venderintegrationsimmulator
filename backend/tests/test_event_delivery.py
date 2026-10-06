import httpx
import respx
from app.domain.enums import FidelityMode
from app.products.registry import ProductRegistry
from app.schemas.event import ScenarioPreviewRequest
from app.services.event_delivery import EventDeliveryService
from app.services.transport_delivery import TransportDeliveryService
from app.transports.registry import transport_registry


def _service(products_directory) -> EventDeliveryService:
    from app.transports.registry import register_default_transports

    register_default_transports()
    registry = ProductRegistry(str(products_directory))
    registry.load_all()
    return EventDeliveryService(registry, TransportDeliveryService(transport_registry))


def test_preview_api(client) -> None:
    response = client.post(
        "/api/v1/products/upguard/scenarios/data-leak/preview",
        json={"fidelity_mode": "troubleshooting"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["product_id"] == "upguard"
    assert data["scenario_id"] == "data-leak"
    assert "correlation_id" in data
    assert "payload" in data
    assert "_simulator" in data["payload"]
    assert "notification" in data["payload"]


def test_preview_vendor_accurate_api(client) -> None:
    response = client.post(
        "/api/v1/products/upguard/scenarios/score-threshold/preview",
        json={"fidelity_mode": "vendor_accurate"},
    )
    assert response.status_code == 200
    payload = response.json()["payload"]
    assert "_simulator" not in payload
    assert payload["notification"]["type"] == "CustomerCSTARUnderThreshold"


def test_preview_not_found(client) -> None:
    response = client.post(
        "/api/v1/products/upguard/scenarios/missing/preview",
        json={},
    )
    assert response.status_code == 404


@respx.mock
def test_send_one_shot(client) -> None:
    route = respx.post("https://collector.example/webhook").mock(
        return_value=httpx.Response(200, json={"accepted": True})
    )
    response = client.post(
        "/api/v1/products/upguard/scenarios/identity-breach/send",
        json={
            "fidelity_mode": "vendor_accurate",
            "destination": {
                "url": "https://collector.example/webhook",
                "method": "POST",
            },
            "auth_config": {"auth_method_id": "none"},
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["event"]["payload_source"] == "generated"
    assert data["delivery"]["success"] is True
    assert route.called
    sent = route.calls[0].request
    body = sent.content.decode()
    assert "IdentityBreachPublished" in body
    assert "password" not in response.text.lower() or "***" in response.text


@respx.mock
def test_send_with_basic_auth(client) -> None:
    route = respx.post("https://collector.example/webhook").mock(return_value=httpx.Response(200))
    response = client.post(
        "/api/v1/products/upguard/scenarios/vulnerability/send",
        json={
            "destination": {"url": "https://collector.example/webhook"},
            "auth_config": {
                "auth_method_id": "basic",
                "username": "hook-user",
                "password": "hook-secret",
            },
        },
    )
    assert response.status_code == 200
    assert route.called
    assert response.json()["delivery"]["request_headers_redacted"]["Authorization"] == (
        "***REDACTED***"
    )
    assert "hook-secret" not in response.text


@respx.mock
def test_send_with_payload_override(client) -> None:
    route = respx.post("https://collector.example/webhook").mock(return_value=httpx.Response(204))
    override = {
        "notification": {
            "id": 1,
            "type": "CustomOverride",
            "description": "override",
            "occurredAt": "2026-01-01T00:00:00Z",
            "context": {},
        }
    }
    response = client.post(
        "/api/v1/products/upguard/scenarios/data-leak/send",
        json={
            "destination": {"url": "https://collector.example/webhook"},
            "auth_config": {"auth_method_id": "none"},
            "payload_override": override,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["event"]["payload_source"] == "override"
    assert data["event"]["payload"]["notification"]["type"] == "CustomOverride"
    assert route.called


def test_send_rejects_missing_url(client) -> None:
    response = client.post(
        "/api/v1/products/upguard/scenarios/data-leak/send",
        json={
            "destination": {"url": ""},
            "auth_config": {"auth_method_id": "none"},
        },
    )
    assert response.status_code == 422


def test_send_rejects_embedded_url_credentials(client) -> None:
    response = client.post(
        "/api/v1/products/upguard/scenarios/data-leak/send",
        json={
            "destination": {
                "url": "https://url-user:url-password-canary@collector.example/webhook"
            },
            "auth_config": {"auth_method_id": "none"},
        },
    )
    assert response.status_code == 422
    assert (
        "URL must not include embedded credentials; configure authentication separately."
        in response.text
    )
    assert "url-password-canary" not in response.text


@respx.mock
def test_one_shot_structured_values_are_delivered_and_all_evidence_is_redacted(client) -> None:
    route = respx.post(url__regex=r"https://collector\.example/webhook.*").mock(
        return_value=httpx.Response(
            202,
            text="auth-canary header-canary query-canary",
            headers={"Set-Cookie": "session=response-cookie-canary; HttpOnly"},
        )
    )
    response = client.post(
        "/api/v1/products/upguard/scenarios/data-leak/send",
        json={
            "destination": {
                "url": "https://collector.example/webhook",
                "headers": [{"name": "X-Partner", "value": "header-canary", "sensitive": True}],
                "query_params": [{"name": "partner", "value": "query-canary", "sensitive": True}],
            },
            "auth_config": {
                "auth_method_id": "basic",
                "username": "operator",
                "password": "auth-canary",
            },
            "payload_override": {"notification": {"description": "auth-canary"}},
        },
    )
    assert response.status_code == 200, response.text
    sent = route.calls.last.request
    assert sent.headers["X-Partner"] == "header-canary"
    assert sent.url.params["partner"] == "query-canary"
    assert b"auth-canary" in sent.content
    result = response.json()
    assert result["delivery"]["request_headers_redacted"]["X-Partner"] == "***REDACTED***"
    assert result["delivery"]["response_headers_redacted"]["set-cookie"] == "***REDACTED***"
    assert result["event"]["payload"]["notification"]["description"] == "***REDACTED***"
    for canary in (
        "auth-canary",
        "header-canary",
        "query-canary",
        "response-cookie-canary",
    ):
        assert canary not in response.text


def test_one_shot_sensitive_destination_value_is_required(client) -> None:
    response = client.post(
        "/api/v1/products/upguard/scenarios/data-leak/send",
        json={
            "destination": {
                "url": "https://collector.example/webhook",
                "headers": [{"name": "X-Partner", "sensitive": True}],
            },
            "auth_config": {"auth_method_id": "none"},
        },
    )
    assert response.status_code == 422
    assert "requires a value" in response.text


def test_send_rejects_basic_auth_without_password(client) -> None:
    response = client.post(
        "/api/v1/products/upguard/scenarios/data-leak/send",
        json={
            "destination": {"url": "https://collector.example/webhook"},
            "auth_config": {
                "auth_method_id": "basic",
                "username": "user",
            },
        },
    )
    assert response.status_code == 422


def test_send_rejects_unsupported_auth_method(client) -> None:
    response = client.post(
        "/api/v1/products/upguard/scenarios/data-leak/send",
        json={
            "destination": {"url": "https://collector.example/webhook"},
            "auth_config": {"auth_method_id": "bearer", "token": "secret"},
        },
    )
    assert response.status_code == 422


def test_send_rejects_unknown_scenario_override(client) -> None:
    response = client.post(
        "/api/v1/products/upguard/scenarios/data-leak/send",
        json={
            "destination": {"url": "https://collector.example/webhook"},
            "auth_config": {"auth_method_id": "none"},
            "scenario_overrides": {"not_a_field": "value"},
        },
    )
    assert response.status_code == 422


def test_preview_and_send_reject_schema_invalid_scenario_override(client) -> None:
    invalid = {"scenario_overrides": {"affected_domain": 42}}
    preview = client.post(
        "/api/v1/products/upguard/scenarios/data-leak/preview",
        json=invalid,
    )
    assert preview.status_code == 422

    sent = client.post(
        "/api/v1/products/upguard/scenarios/data-leak/send",
        json={
            **invalid,
            "destination": {"url": "https://collector.example/webhook"},
            "auth_config": {"auth_method_id": "none"},
        },
    )
    assert sent.status_code == 422


def test_preview_service_does_not_expose_secrets(products_directory) -> None:
    service = _service(products_directory)
    preview = service.preview(
        "upguard",
        "data-leak",
        ScenarioPreviewRequest(fidelity_mode=FidelityMode.TROUBLESHOOTING),
    )
    assert preview is not None
    assert "password" not in preview.model_dump_json().lower()
