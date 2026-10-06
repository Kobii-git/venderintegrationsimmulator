"""Regression coverage for the 0.2.0 Phase A repair contract."""

from pathlib import Path

import httpx
import respx

from tests.asgi_client import ASGITestClient


def _http_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "name": "Secure HTTP simulation",
        "product_id": "upguard",
        "scenario_id": "data-leak",
        "scenario_ids": ["data-leak"],
        "simulation_mode": "push_webhook",
        "fidelity_mode": "troubleshooting",
        "destination": {
            "transport_id": "http_webhook",
            "url": "https://example.com:8443/hooks/vendor",
            "method": "POST",
            "headers": [
                {
                    "name": "X-Canary-Secret",
                    "value": "header-canary-42",
                    "sensitive": True,
                },
                {"name": "X-Tenant", "value": "engineering", "sensitive": False},
            ],
            "query_params": [
                {
                    "name": "access_token",
                    "value": "query-canary-42",
                    "sensitive": False,
                }
            ],
        },
        "auth_config": {"auth_method_id": "none"},
        "scenario_overrides": {"data-leak": {"affected_domain": "example.org"}},
        "schedule": {"type": "manual"},
    }
    payload.update(overrides)
    return payload


def _pull_payload(**overrides: object) -> dict[str, object]:
    inbound = {
        "auth_method_id": "none",
        "dataset_size": 5,
        "item_interval_seconds": 30,
        "default_page_size": 2,
        "max_page_size": 10,
    }
    payload: dict[str, object] = {
        "name": "Stable pull dataset",
        "product_id": "demo-pull",
        "scenario_id": "security-event",
        "scenario_ids": ["security-event"],
        "simulation_mode": "pull_api",
        "fidelity_mode": "vendor_accurate",
        "destination": {"transport_id": "http_webhook"},
        "auth_config": {"auth_method_id": "none"},
        "scenario_overrides": {"security-event": {"severity": "high"}},
        "schedule": {"type": "manual"},
        "inbound_config": inbound,
    }
    payload.update(overrides)
    return payload


def test_lifecycle_status_is_write_protected(client: ASGITestClient) -> None:
    create = client.post("/api/v1/simulations", json={**_http_payload(), "status": "running"})
    assert create.status_code == 422

    created = client.post("/api/v1/simulations", json=_http_payload()).json()
    update = client.patch(f"/api/v1/simulations/{created['id']}", json={"status": "running"})
    assert update.status_code == 422


def test_destination_url_query_and_bad_nested_overrides_are_rejected(
    client: ASGITestClient,
) -> None:
    bad_url = _http_payload()
    bad_url["destination"] = {
        "transport_id": "http_webhook",
        "url": "https://example.com/hook?access_token=plaintext",
    }
    assert client.post("/api/v1/simulations", json=bad_url).status_code == 422

    credential_url = _http_payload()
    credential_url["destination"] = {
        "transport_id": "http_webhook",
        "url": "https://url-user:url-password-canary@example.com/hook",
    }
    rejected = client.post("/api/v1/simulations", json=credential_url)
    assert rejected.status_code == 422
    assert (
        "URL must not include embedded credentials; configure authentication separately."
        in rejected.text
    )
    assert "url-password-canary" not in rejected.text

    created = client.post("/api/v1/simulations", json=_http_payload()).json()
    rejected_update = client.patch(
        f"/api/v1/simulations/{created['id']}",
        json={
            "destination": {
                "transport_id": "http_webhook",
                "url": "https://url-user:update-password-canary@example.com/hook",
            }
        },
    )
    assert rejected_update.status_code == 422
    assert (
        "URL must not include embedded credentials; configure authentication separately."
        in rejected_update.text
    )
    assert "update-password-canary" not in rejected_update.text

    bad_override = _http_payload(scenario_overrides={"unselected": {"threshold": 550}})
    assert client.post("/api/v1/simulations", json=bad_override).status_code == 422

    wrong_type = _http_payload(scenario_overrides={"data-leak": {"affected_domain": 123}})
    assert client.post("/api/v1/simulations", json=wrong_type).status_code == 422


@respx.mock
def test_structured_secrets_are_hidden_in_storage_reads_export_and_curl(
    client: ASGITestClient, test_settings
) -> None:
    respx.post(url__regex=r"https://example\.com:8443/hooks/vendor.*").mock(
        return_value=httpx.Response(202, json={"accepted": True})
    )
    created_response = client.post("/api/v1/simulations", json=_http_payload())
    assert created_response.status_code == 201, created_response.text
    created = created_response.json()

    header = created["destination"]["headers"][0]
    token = created["destination"]["query_params"][0]
    assert header == {
        "name": "X-Canary-Secret",
        "sensitive": True,
        "has_value": True,
    }
    assert token == {
        "name": "access_token",
        "sensitive": True,
        "has_value": True,
    }
    assert created["destination"]["headers"][1]["value"] == "engineering"

    sent = client.post(f"/api/v1/simulations/{created['id']}/send")
    assert sent.status_code == 200, sent.text
    event_id = sent.json()["event_id"]
    detail = client.get(f"/api/v1/simulations/{created['id']}/events/{event_id}").json()
    attempt = detail["delivery_attempts"][0]
    assert attempt["request_url_redacted"].startswith("https://example.com:8443/hooks/vendor?")
    assert "query-canary-42" not in attempt["request_url_redacted"]

    curl = client.get(
        f"/api/v1/simulations/{created['id']}/events/{event_id}/curl",
        params={"attempt_id": attempt["id"]},
    ).json()
    assert curl["attempt_id"] == attempt["id"]
    assert curl["exact"] is True
    assert "header-canary-42" not in curl["command"]
    assert "query-canary-42" not in curl["command"]

    sanitized = client.get(f"/api/v1/simulations/{created['id']}/export").json()
    assert sanitized["format_version"] == "3.0"
    assert "header-canary-42" not in str(sanitized)
    assert "query-canary-42" not in str(sanitized)

    confirmed = client.get(
        f"/api/v1/simulations/{created['id']}/export",
        params={"include_secrets": True, "confirm_secret_export": True},
    ).json()
    assert "header-canary-42" in str(confirmed)
    assert "query-canary-42" in str(confirmed)

    database_path = Path(test_settings.resolved_database_url.removeprefix("sqlite:///"))
    database_bytes = database_path.read_bytes()
    assert b"header-canary-42" not in database_bytes
    assert b"query-canary-42" not in database_bytes


def test_destination_edit_preserves_then_deletes_hidden_secret(client: ASGITestClient) -> None:
    created = client.post("/api/v1/simulations", json=_http_payload()).json()
    destination = {
        "transport_id": "http_webhook",
        "url": "https://example.com:8443/hooks/vendor",
        "method": "PUT",
        "headers": [
            {"name": "X-Canary-Secret", "sensitive": True},
            {"name": "X-Tenant", "value": "engineering", "sensitive": False},
        ],
        "query_params": [
            {"name": "access_token", "sensitive": True},
        ],
    }
    preserved = client.patch(
        f"/api/v1/simulations/{created['id']}", json={"destination": destination}
    ).json()
    assert preserved["destination"]["headers"][0]["has_value"] is True
    assert preserved["destination"]["query_params"][0]["has_value"] is True

    destination["headers"] = [{"name": "X-Tenant", "value": "engineering", "sensitive": False}]
    destination["query_params"] = []
    cleared = client.patch(
        f"/api/v1/simulations/{created['id']}", json={"destination": destination}
    ).json()
    assert cleared["destination"]["headers"] == [
        {
            "name": "X-Tenant",
            "sensitive": False,
            "has_value": True,
            "value": "engineering",
        }
    ]
    assert cleared["destination"]["query_params"] == []


def test_format_2_0_import_remains_backward_compatible(client: ASGITestClient) -> None:
    created = client.post("/api/v1/simulations", json=_pull_payload()).json()
    document = client.get(f"/api/v1/simulations/{created['id']}/export").json()
    document["format_version"] = "2.0"
    document["simulation"]["inbound_config"].pop("vendor_options", None)
    document["simulation"]["inbound_config"].pop("api_key_prefix", None)

    imported = client.post("/api/v1/simulations/import", json={"document": document})
    assert imported.status_code == 201, imported.text
    restored = client.get(f"/api/v1/simulations/{imported.json()['simulation_id']}").json()
    assert restored["inbound_config"]["vendor_options"] == {}
    assert restored["inbound_config"]["api_key_prefix"] == ""


def test_pull_send_is_rejected_and_cursor_dataset_is_stable(client: ASGITestClient) -> None:
    created = client.post("/api/v1/simulations", json=_pull_payload()).json()
    assert client.post(f"/api/v1/simulations/{created['id']}/send").status_code == 422
    started = client.post(f"/api/v1/simulations/{created['id']}/start")
    assert started.status_code == 200, started.text

    path = f"/api/v1/mock/demo-pull/events?simulation_id={created['id']}&limit=2"
    first = client.get(path).json()
    assert client.get(path).json() == first
    old_token = first["nextPageToken"]
    seen = list(first["events"])
    page = first
    while page.get("nextPageToken"):
        page = client.get(path, params={"pageToken": page["nextPageToken"]}).json()
        seen.extend(page["events"])
    assert len(seen) == 5
    assert "nextPageToken" not in page or page["nextPageToken"] == ""

    client.post(f"/api/v1/simulations/{created['id']}/stop")
    client.post(f"/api/v1/simulations/{created['id']}/start")
    stale = client.get(path, params={"pageToken": old_token})
    assert stale.status_code == 422


def test_unmatched_inbound_requests_are_globally_visible_and_redacted(
    client: ASGITestClient,
) -> None:
    response = client.get(
        "/api/v1/mock/not-a-product/events",
        params={"access_token": "unmatched-canary-42"},
    )
    assert response.status_code == 404
    logs = client.get("/api/v1/inbound-requests", params={"response_status": 404}).json()
    assert logs and logs[0]["simulation_id"] is None
    detail = client.get(f"/api/v1/inbound-requests/{logs[0]['id']}").json()
    assert detail["request_query_params"]["access_token"] == "***REDACTED***"
    assert "unmatched-canary-42" not in str(detail)


def test_oauth_responses_disable_caching(client: ASGITestClient) -> None:
    inbound = {
        "auth_method_id": "oauth2_client_credentials",
        "dataset_size": 2,
    }
    payload = _pull_payload(inbound_config=inbound)
    payload["auth_config"] = {
        "auth_method_id": "none",
        "oauth_client_id": "repair-client",
        "oauth_client_secret": "oauth-canary-42",
    }
    created = client.post("/api/v1/simulations", json=payload).json()
    client.post(f"/api/v1/simulations/{created['id']}/start")
    token = client.post(
        "/api/v1/oauth2/token",
        params={"simulation_id": created["id"]},
        data={
            "grant_type": "client_credentials",
            "client_id": "repair-client",
            "client_secret": "oauth-canary-42",
        },
    )
    assert token.status_code == 200, token.text
    assert token.headers["cache-control"] == "no-store"
    assert token.headers["pragma"] == "no-cache"

    history = client.get(
        f"/api/v1/simulations/{created['id']}/inbound-requests",
        params={"request_kind": "token"},
    ).json()
    assert history[0]["token_metadata"]["token_record_id"]
    assert "token_prefix" not in history[0]["token_metadata"]


def test_sanitized_export_import_reports_and_preserves_missing_secrets(
    client: ASGITestClient,
) -> None:
    payload = _http_payload()
    payload["auth_config"] = {
        "auth_method_id": "basic",
        "username": "operator",
        "password": "export-canary-42",
    }
    created = client.post("/api/v1/simulations", json=payload).json()
    document = client.get(f"/api/v1/simulations/{created['id']}/export").json()
    imported = client.post("/api/v1/simulations/import", json={"document": document})
    assert imported.status_code == 201, imported.text
    missing = imported.json()["missing_secrets"]
    assert "auth_config.password" in missing
    assert "destination.headers.X-Canary-Secret" in missing

    imported_simulation = client.get(
        f"/api/v1/simulations/{imported.json()['simulation_id']}"
    ).json()
    assert imported_simulation["status"] == "stopped"
    assert "auth_config.password" in imported_simulation["missing_secrets"]
    blocked = client.post(f"/api/v1/simulations/{imported.json()['simulation_id']}/send")
    assert blocked.status_code == 422


def test_import_rejects_embedded_url_credentials_without_echoing_them(client) -> None:
    created = client.post("/api/v1/simulations", json=_http_payload()).json()
    document = client.get(f"/api/v1/simulations/{created['id']}/export").json()
    document["simulation"]["destination"]["url"] = (
        "https://url-user:import-password-canary@example.com/hook"
    )
    response = client.post("/api/v1/simulations/import", json={"document": document})
    assert response.status_code == 422
    assert (
        "URL must not include embedded credentials; configure authentication separately."
        in response.text
    )
    assert "import-password-canary" not in response.text
