import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from tests.asgi_client import ASGITestClient

TENANT_ID = "57ca9a6b-885f-4e36-95ec-290548c26059"


def _create_sophos(client: ASGITestClient, *, dataset_size: int = 210) -> dict:
    response = client.post(
        "/api/v1/simulations",
        json={
            "name": "Sophos Central workflow",
            "product_id": "sophos-central",
            "scenario_id": "core-malware-detection",
            "scenario_ids": [
                "core-malware-detection",
                "behavioral-detection",
                "pua-detection",
                "ips-inbound-detection",
                "ips-outbound-detection",
            ],
            "simulation_mode": "pull_api",
            "auth_config": {
                "oauth_client_id": "sophos-client",
                "oauth_client_secret": "sophos-secret-canary",
            },
            "inbound_config": {
                "auth_method_id": "oauth2_client_credentials",
                "oauth_allowed_scopes": ["token"],
                "dataset_size": dataset_size,
                "vendor_options": {"tenant_id": TENANT_ID},
            },
        },
    )
    assert response.status_code == 201, response.text
    simulation = response.json()
    started = client.post(f"/api/v1/simulations/{simulation['id']}/start")
    assert started.status_code == 200, started.text
    return simulation


def _token(client: ASGITestClient, simulation_id: str, **overrides: str) -> dict:
    form = {
        "grant_type": "client_credentials",
        "client_id": "sophos-client",
        "client_secret": "sophos-secret-canary",
        "scope": "token",
        **overrides,
    }
    response = client.post(
        f"/api/v1/mock/sophos-central/api/v2/oauth2/token?simulation_id={simulation_id}",
        data=form,
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_sophos_token_whoami_and_cursor_workflow(client: ASGITestClient) -> None:
    simulation = _create_sophos(client)
    token = _token(client, simulation["id"])
    assert token["errorCode"] == "success"
    assert token["token_type"] == "bearer"
    assert token["refresh_token"] == token["access_token"]

    headers = {"Authorization": f"Bearer {token['access_token']}"}
    whoami = client.get(
        f"/api/v1/mock/sophos-central/whoami/v1?simulation_id={simulation['id']}",
        headers=headers,
    )
    assert whoami.status_code == 200, whoami.text
    assert whoami.json()["id"] == TENANT_ID
    assert whoami.json()["apiHosts"]["dataRegion"].endswith("/api/v1/mock/sophos-central")

    event_headers = {**headers, "X-Tenant-ID": TENANT_ID}
    first = client.get(
        f"/api/v1/mock/sophos-central/siem/v1/events?simulation_id={simulation['id']}",
        headers=event_headers,
        params={"limit": 200},
    )
    assert first.status_code == 200, first.text
    body = first.json()
    assert len(body["items"]) == 200
    assert body["has_more"] is True
    assert body["next_cursor"]
    assert {item["type"] for item in body["items"]} == {
        "Event::Endpoint::CoreDetection",
        "Event::Endpoint::CoreBehavioralDetection",
        "Event::Endpoint::CorePuaDetection",
        "Event::Endpoint::Threat::IpsInboundDetection",
        "Event::Endpoint::Threat::IpsOutboundDetection",
    }

    second = client.get(
        f"/api/v1/mock/sophos-central/siem/v1/events?simulation_id={simulation['id']}",
        headers=event_headers,
        params={"limit": 200, "cursor": body["next_cursor"]},
    )
    assert second.status_code == 200, second.text
    assert len(second.json()["items"]) == 10
    assert second.json()["has_more"] is False


def test_sophos_validation_filtering_and_secret_redaction(
    client: ASGITestClient, test_settings
) -> None:
    simulation = _create_sophos(client)
    token = _token(client, simulation["id"])
    bearer = token["access_token"]
    url = f"/api/v1/mock/sophos-central/siem/v1/events?simulation_id={simulation['id']}"

    missing_tenant = client.get(url, headers={"Authorization": f"Bearer {bearer}"})
    assert missing_tenant.status_code == 403
    assert missing_tenant.json()["errorCode"] == "403"

    invalid_bearer = client.get(
        url,
        headers={"Authorization": "Bearer invalid", "X-Tenant-ID": TENANT_ID},
    )
    assert invalid_bearer.status_code == 401
    assert invalid_bearer.json()["errorCode"] == "401"

    wrong_tenant = client.get(
        url,
        headers={"Authorization": f"Bearer {bearer}", "X-Tenant-ID": "wrong"},
    )
    assert wrong_tenant.status_code == 403

    invalid_limit = client.get(
        url,
        headers={"Authorization": f"Bearer {bearer}", "X-Tenant-ID": TENANT_ID},
        params={"limit": 199},
    )
    assert invalid_limit.status_code == 400

    invalid_cursor = client.get(
        url,
        headers={"Authorization": f"Bearer {bearer}", "X-Tenant-ID": TENANT_ID},
        params={"cursor": "stale"},
    )
    assert invalid_cursor.status_code == 400

    old_timestamp = int((datetime.now(UTC) - timedelta(hours=25)).timestamp())
    too_old = client.get(
        url,
        headers={"Authorization": f"Bearer {bearer}", "X-Tenant-ID": TENANT_ID},
        params={"from_date": old_timestamp},
    )
    assert too_old.status_code == 400

    filtered = client.get(
        url,
        headers={"Authorization": f"Bearer {bearer}", "X-Tenant-ID": TENANT_ID},
        params={"exclude_types": "Event::Endpoint::CoreDetection"},
    )
    assert filtered.status_code == 200
    assert all(
        item["type"] != "Event::Endpoint::CoreDetection" for item in filtered.json()["items"]
    )

    history = client.get(
        f"/api/v1/simulations/{simulation['id']}/inbound-requests?limit=100"
    ).json()
    details = [
        client.get(f"/api/v1/simulations/{simulation['id']}/inbound-requests/{row['id']}").json()
        for row in history
    ]
    serialized = json.dumps(details)
    assert bearer not in serialized
    assert "sophos-secret-canary" not in serialized
    assert "***REDACTED***" in serialized

    database_path = Path(test_settings.resolved_database_url.removeprefix("sqlite:///"))
    database_bytes = database_path.read_bytes()
    assert bearer.encode() not in database_bytes
    assert b"sophos-secret-canary" not in database_bytes


def test_sophos_rejects_invalid_scope_and_vendor_options(client: ASGITestClient) -> None:
    bad_options = client.post(
        "/api/v1/simulations",
        json={
            "name": "Bad Sophos",
            "product_id": "sophos-central",
            "scenario_id": "core-malware-detection",
            "simulation_mode": "pull_api",
            "auth_config": {
                "oauth_client_id": "client",
                "oauth_client_secret": "secret",
            },
            "inbound_config": {
                "auth_method_id": "oauth2_client_credentials",
                "vendor_options": {"tenant_id": "not-a-uuid"},
            },
        },
    )
    assert bad_options.status_code == 422

    simulation = _create_sophos(client, dataset_size=5)
    invalid_client = client.post(
        f"/api/v1/mock/sophos-central/api/v2/oauth2/token?simulation_id={simulation['id']}",
        data={
            "grant_type": "client_credentials",
            "client_id": "sophos-client",
            "client_secret": "wrong",
            "scope": "token",
        },
    )
    assert invalid_client.status_code == 401
    assert invalid_client.json()["errorCode"] == "invalid_client"

    invalid_scope = client.post(
        f"/api/v1/mock/sophos-central/api/v2/oauth2/token?simulation_id={simulation['id']}",
        data={
            "grant_type": "client_credentials",
            "client_id": "sophos-client",
            "client_secret": "sophos-secret-canary",
            "scope": "admin",
        },
    )
    assert invalid_scope.status_code == 400
    assert invalid_scope.json()["errorCode"] == "invalid_scope"
