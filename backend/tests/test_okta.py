import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx
import respx

from tests.asgi_client import ASGITestClient

API_TOKEN = "okta-api-token-secret"
OAUTH_SECRET = "okta-oauth-client-secret"


def _create_okta_pull(
    client: ASGITestClient,
    *,
    auth_method: str = "api_key",
    dataset_size: int = 12,
) -> dict:
    if auth_method == "oauth2_client_credentials":
        auth_config = {
            "oauth_client_id": "okta-client",
            "oauth_client_secret": OAUTH_SECRET,
        }
        inbound_config = {
            "auth_method_id": auth_method,
            "oauth_allowed_scopes": ["okta.logs.read"],
            "dataset_size": dataset_size,
            "vendor_options": {"org_url": "https://example.okta.com"},
        }
    else:
        auth_config = {"auth_method_id": "bearer", "token": API_TOKEN}
        inbound_config = {
            "auth_method_id": "api_key",
            "api_key_header": "Authorization",
            "api_key_prefix": "SSWS ",
            "dataset_size": dataset_size,
            "vendor_options": {"org_url": "https://example.okta.com"},
        }

    response = client.post(
        "/api/v1/simulations",
        json={
            "name": "Okta System Log workflow",
            "product_id": "okta",
            "scenario_id": "user-session-start",
            "scenario_ids": [
                "user-session-start",
                "user-lifecycle-create",
                "user-lifecycle-deactivate",
                "application-membership-add",
                "user-authentication-sso",
                "application-sign-on-denied",
            ],
            "simulation_mode": "pull_api",
            "auth_config": auth_config,
            "inbound_config": inbound_config,
        },
    )
    assert response.status_code == 201, response.text
    simulation = response.json()
    started = client.post(f"/api/v1/simulations/{simulation['id']}/start")
    assert started.status_code == 200, started.text
    return simulation


def _logs_url(simulation_id: str) -> str:
    return f"/api/v1/mock/okta/api/v1/logs?simulation_id={simulation_id}"


def _ssws_headers() -> dict[str, str]:
    return {"Authorization": f"SSWS {API_TOKEN}"}


def _parse_links(header: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for part in header.split(","):
        url, relation = part.strip().split(";", 1)
        result[relation.split('"')[1]] = url.strip()[1:-1]
    return result


def test_okta_ssws_raw_array_filters_and_bounded_pagination(client: ASGITestClient) -> None:
    simulation = _create_okta_pull(client)
    first = client.get(
        _logs_url(simulation["id"]),
        headers=_ssws_headers(),
        params={"limit": 5, "sortOrder": "ASCENDING"},
    )
    assert first.status_code == 200, first.text
    assert isinstance(first.json(), list)
    assert len(first.json()) == 5
    links = _parse_links(first.headers["Link"])
    assert set(links) == {"self", "next"}

    next_query = parse_qs(urlsplit(links["next"]).query)
    assert "after" in next_query
    assert "since" not in next_query
    second = client.get(links["next"], headers=_ssws_headers())
    assert second.status_code == 200, second.text
    assert len(second.json()) == 5

    filtered = client.get(
        _logs_url(simulation["id"]),
        headers=_ssws_headers(),
        params={"filter": 'eventType eq "user.session.start"'},
    )
    assert filtered.status_code == 200, filtered.text
    assert filtered.json()
    assert {event["eventType"] for event in filtered.json()} == {"user.session.start"}

    actor_id = first.json()[0]["actor"]["id"]
    actor_filtered = client.get(
        _logs_url(simulation["id"]),
        headers=_ssws_headers(),
        params={"filter": f'actor.id eq "{actor_id}"'},
    )
    assert actor_filtered.status_code == 200
    assert all(event["actor"]["id"] == actor_id for event in actor_filtered.json())

    target_id = first.json()[0]["target"][0]["id"]
    target_filtered = client.get(
        _logs_url(simulation["id"]),
        headers=_ssws_headers(),
        params={"filter": f'target.id eq "{target_id}"'},
    )
    assert target_filtered.status_code == 200
    assert all(
        any(target["id"] == target_id for target in event["target"])
        for event in target_filtered.json()
    )

    searched = client.get(
        _logs_url(simulation["id"]),
        headers=_ssws_headers(),
        params={"q": "analyst@example.com"},
    )
    assert searched.status_code == 200
    assert searched.json()


def test_okta_polling_cursor_validation_and_empty_next_page(client: ASGITestClient) -> None:
    simulation = _create_okta_pull(client, dataset_size=2)
    url = _logs_url(simulation["id"])

    conflict = client.get(
        url,
        headers=_ssws_headers(),
        params={"since": "2026-08-26T00:00:00Z", "after": "cursor"},
    )
    assert conflict.status_code == 400
    assert conflict.json()["errorCode"] == "E0000001"

    bad_filter = client.get(
        url,
        headers=_ssws_headers(),
        params={"filter": 'outcome.result eq "FAILURE"'},
    )
    assert bad_filter.status_code == 400

    first = client.get(
        url,
        headers=_ssws_headers(),
        params={"limit": 2, "sortOrder": "ASCENDING"},
    )
    next_url = _parse_links(first.headers["Link"])["next"]
    empty = client.get(next_url, headers=_ssws_headers())
    assert empty.status_code == 200, empty.text
    assert empty.json() == []
    assert "next" in _parse_links(empty.headers["Link"])

    stale = client.get(
        url,
        headers=_ssws_headers(),
        params={"after": "invalid-cursor"},
    )
    assert stale.status_code == 400
    assert stale.json()["errorCode"] == "E0000001"


def test_okta_oauth_system_log_and_secret_redaction(client: ASGITestClient, test_settings) -> None:
    simulation = _create_okta_pull(client, auth_method="oauth2_client_credentials")
    token_response = client.post(
        f"/api/v1/mock/okta/oauth2/v1/token?simulation_id={simulation['id']}",
        data={
            "grant_type": "client_credentials",
            "client_id": "okta-client",
            "client_secret": OAUTH_SECRET,
            "scope": "okta.logs.read",
        },
    )
    assert token_response.status_code == 200, token_response.text
    access_token = token_response.json()["access_token"]

    logs = client.get(
        _logs_url(simulation["id"]),
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert logs.status_code == 200, logs.text
    assert isinstance(logs.json(), list)

    history = client.get(
        f"/api/v1/simulations/{simulation['id']}/inbound-requests?limit=100"
    ).json()
    details = [
        client.get(f"/api/v1/simulations/{simulation['id']}/inbound-requests/{row['id']}").json()
        for row in history
    ]
    serialized = json.dumps(details)
    assert access_token not in serialized
    assert OAUTH_SECRET not in serialized
    assert "***REDACTED***" in serialized

    database_path = Path(test_settings.resolved_database_url.removeprefix("sqlite:///"))
    database_bytes = database_path.read_bytes()
    assert access_token.encode() not in database_bytes
    assert OAUTH_SECRET.encode() not in database_bytes


def test_okta_oauth_requires_logs_read_scope(client: ASGITestClient) -> None:
    simulation = _create_okta_pull(client, auth_method="oauth2_client_credentials")
    missing_scope = client.post(
        f"/api/v1/mock/okta/oauth2/v1/token?simulation_id={simulation['id']}",
        data={
            "grant_type": "client_credentials",
            "client_id": "okta-client",
            "client_secret": OAUTH_SECRET,
        },
    )
    assert missing_scope.status_code == 400
    assert missing_scope.json()["error"] == "invalid_scope"


def _okta_hook_payload() -> dict:
    return {
        "name": "Okta event hook",
        "product_id": "okta",
        "scenario_id": "user-session-start",
        "simulation_mode": "push_webhook",
        "destination": {
            "transport_id": "http_webhook",
            "url": "https://receiver.example/okta-hook",
        },
        "auth_config": {
            "auth_method_id": "api_key_header",
            "token": API_TOKEN,
            "header_name": "Authorization",
            "header_prefix": "SSWS ",
        },
        "schedule": {"type": "manual"},
    }


@respx.mock
def test_okta_hook_envelope_action_and_action_history(client: ASGITestClient) -> None:
    delivered_bodies: list[dict] = []

    def receive_hook(request: httpx.Request) -> httpx.Response:
        delivered_bodies.append(json.loads(request.content))
        return httpx.Response(200)

    def echo_challenge(request: httpx.Request) -> httpx.Response:
        challenge = request.headers["x-okta-verification-challenge"]
        return httpx.Response(200, json={"verification": challenge})

    post_route = respx.post("https://receiver.example/okta-hook").mock(side_effect=receive_hook)
    get_route = respx.get("https://receiver.example/okta-hook").mock(side_effect=echo_challenge)
    simulation = client.post("/api/v1/simulations", json=_okta_hook_payload()).json()

    sent = client.post(f"/api/v1/simulations/{simulation['id']}/send")
    assert sent.status_code == 200, sent.text
    assert post_route.call_count == 1
    envelope = delivered_bodies[0]
    assert envelope["eventType"] == "com.okta.event_hook"
    assert len(envelope["data"]["events"]) == 1
    assert sent.json()["payload"] == envelope

    action = client.post(f"/api/v1/simulations/{simulation['id']}/actions/verify-event-hook")
    assert action.status_code == 200, action.text
    assert action.json()["assertion_passed"] is True
    assert action.json()["delivery_success"] is True
    assert get_route.call_count == 1

    event = client.get(f"/api/v1/simulations/{simulation['id']}/events/{action.json()['event_id']}")
    assert event.status_code == 200
    assert event.json()["event_kind"] == "workflow_action"
    assert event.json()["action_id"] == "verify-event-hook"
    serialized = json.dumps(event.json())
    assert API_TOKEN not in serialized
    assert "***REDACTED***" in serialized


@respx.mock
def test_okta_hook_retry_policy_retries_5xx_but_not_4xx(client: ASGITestClient) -> None:
    route = respx.post("https://receiver.example/okta-hook").mock(
        side_effect=[httpx.Response(500), httpx.Response(202)]
    )
    simulation = client.post("/api/v1/simulations", json=_okta_hook_payload()).json()
    retried = client.post(f"/api/v1/simulations/{simulation['id']}/send")
    assert retried.status_code == 200
    assert retried.json()["delivery_success"] is True
    assert route.call_count == 2

    route.reset()
    route.mock(return_value=httpx.Response(400))
    not_retried = client.post(f"/api/v1/simulations/{simulation['id']}/send")
    assert not_retried.status_code == 200
    assert not_retried.json()["delivery_success"] is False
    assert route.call_count == 1


@respx.mock
def test_okta_hook_verification_rejects_bad_echo_and_timeout(client: ASGITestClient) -> None:
    route = respx.get("https://receiver.example/okta-hook").mock(
        return_value=httpx.Response(200, json={"verification": "wrong"})
    )
    simulation = client.post("/api/v1/simulations", json=_okta_hook_payload()).json()
    malformed = client.post(f"/api/v1/simulations/{simulation['id']}/actions/verify-event-hook")
    assert malformed.status_code == 200
    assert malformed.json()["assertion_passed"] is False
    assert malformed.json()["delivery_success"] is False

    route.reset()
    route.mock(side_effect=httpx.ReadTimeout("receiver timed out"))
    timed_out = client.post(f"/api/v1/simulations/{simulation['id']}/actions/verify-event-hook")
    assert timed_out.status_code == 200
    assert timed_out.json()["assertion_passed"] is False
    assert timed_out.json()["delivery_success"] is False
    assert route.call_count == 1


@respx.mock
def test_okta_hook_duplicate_and_out_of_order_faults_are_retained(
    client: ASGITestClient,
) -> None:
    delivered: list[dict] = []

    def receive(request: httpx.Request) -> httpx.Response:
        delivered.append(json.loads(request.content))
        return httpx.Response(202)

    route = respx.post("https://receiver.example/okta-hook").mock(side_effect=receive)
    payload = _okta_hook_payload()
    payload["fault_config"] = {
        "enabled": True,
        "payload": {
            "timestamp": {
                "mode": "fixed",
                "fixed_value": "2020-01-01T00:00:00Z",
                "field_paths": ["data.events.0.published"],
            }
        },
        "delivery": {"duplicate_send_count": 2},
    }
    simulation = client.post("/api/v1/simulations", json=payload).json()
    sent = client.post(f"/api/v1/simulations/{simulation['id']}/send")
    assert sent.status_code == 200
    assert route.call_count == 2
    assert len(delivered) == 2
    assert all(len(envelope["data"]["events"]) == 1 for envelope in delivered)
    assert all(
        envelope["data"]["events"][0]["published"] == "2020-01-01T00:00:00Z"
        for envelope in delivered
    )


def test_okta_rejects_invalid_vendor_options_and_exposes_contract(client: ASGITestClient) -> None:
    bad = client.post(
        "/api/v1/simulations",
        json={
            "name": "Invalid Okta org",
            "product_id": "okta",
            "scenario_id": "user-session-start",
            "simulation_mode": "pull_api",
            "auth_config": {"token": API_TOKEN},
            "inbound_config": {
                "auth_method_id": "api_key",
                "vendor_options": {"org_url": "http://not-okta.example"},
            },
        },
    )
    assert bad.status_code == 422

    product = client.get("/api/v1/products/okta")
    assert product.status_code == 200
    body = product.json()
    assert body["inbound_options_schema"]["properties"]["org_url"]
    assert {action["id"] for action in body["actions"]} == {"verify-event-hook"}
    assert (
        next(route for route in body["mock_routes"] if route["id"] == "system-log")[
            "response_profile"
        ]["body_style"]
        == "array"
    )


def test_okta_export_2_1_round_trip_preserves_additive_inbound_fields(
    client: ASGITestClient,
) -> None:
    simulation = _create_okta_pull(client, dataset_size=3)
    document = client.get(f"/api/v1/simulations/{simulation['id']}/export").json()
    assert document["format_version"] == "3.0"
    assert document["simulation"]["inbound_config"]["api_key_prefix"] == "SSWS "
    assert document["simulation"]["inbound_config"]["vendor_options"] == {
        "org_url": "https://example.okta.com"
    }

    imported = client.post("/api/v1/simulations/import", json={"document": document})
    assert imported.status_code == 201, imported.text
    restored = client.get(f"/api/v1/simulations/{imported.json()['simulation_id']}").json()
    assert restored["inbound_config"]["api_key_prefix"] == "SSWS "
    assert restored["inbound_config"]["vendor_options"] == {"org_url": "https://example.okta.com"}
