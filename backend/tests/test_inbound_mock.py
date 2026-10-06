"""Integration tests for inbound mock REST API (pull-based simulation)."""

from tests.asgi_client import ASGITestClient


def _pull_simulation_payload(**overrides) -> dict:
    payload = {
        "name": "Demo Pull Simulation",
        "product_id": "demo-pull",
        "scenario_id": "security-event",
        "scenario_ids": ["security-event", "alert"],
        "simulation_mode": "pull_api",
        "fidelity_mode": "troubleshooting",
        "destination": {"transport_id": "http_webhook"},
        "auth_config": {"auth_method_id": "none"},
        "scenario_overrides": {},
        "schedule": {"type": "manual"},
        "inbound_config": {
            "auth_method_id": "none",
            "default_page_size": 10,
            "max_page_size": 50,
        },
    }
    payload.update(overrides)
    return payload


def test_demo_pull_product_has_mock_routes(client: ASGITestClient) -> None:
    response = client.get("/api/v1/products/demo-pull")
    assert response.status_code == 200
    data = response.json()
    assert data["supported_modes"] == ["pull_api"]
    assert len(data["mock_routes"]) == 2
    route_ids = {route["id"] for route in data["mock_routes"]}
    assert route_ids == {"events", "alerts"}


def test_create_pull_simulation(client: ASGITestClient) -> None:
    response = client.post("/api/v1/simulations", json=_pull_simulation_payload())
    assert response.status_code == 201
    data = response.json()
    assert data["simulation_mode"] == "pull_api"
    assert data["inbound_config"]["auth_method_id"] == "none"


def test_mock_api_returns_404_without_running_simulation(client: ASGITestClient) -> None:
    response = client.get("/api/v1/mock/demo-pull/events")
    assert response.status_code == 404
    assert "No active pull_api simulation" in response.json()["error"]


def test_pull_simulation_lifecycle_and_mock_api(client: ASGITestClient) -> None:
    created = client.post("/api/v1/simulations", json=_pull_simulation_payload()).json()

    start = client.post(f"/api/v1/simulations/{created['id']}/start")
    assert start.status_code == 200
    assert start.json()["status"] == "running"
    assert start.json()["runtime_stats"]["pull_dataset_activation_id"]
    assert start.json()["runtime_stats"]["pull_dataset_item_count"] == 200

    endpoint_info = client.get(f"/api/v1/simulations/{created['id']}/inbound-endpoint")
    assert endpoint_info.status_code == 200
    endpoint = endpoint_info.json()
    routes = endpoint["routes"]
    assert any("/mock/demo-pull/events" in route["path"] for route in routes)
    assert all(route["url"].startswith("http://testserver/") for route in routes)
    assert all(f"simulation_id={created['id']}" in route["url"] for route in routes)
    assert set(endpoint["api_urls"]) == {route["url"] for route in routes}

    events = client.get(f"/api/v1/mock/demo-pull/events?simulation_id={created['id']}&limit=3")
    assert events.status_code == 200
    body = events.json()
    assert "events" in body
    assert len(body["events"]) == 3
    assert body["nextPageToken"]

    missing_required_header = client.get(
        f"/api/v1/mock/demo-pull/alerts?simulation_id={created['id']}&limit=2"
    )
    assert missing_required_header.status_code == 400
    assert "X-Collector-ID" in missing_required_header.text

    alerts = client.get(
        f"/api/v1/mock/demo-pull/alerts?simulation_id={created['id']}&limit=2",
        headers={"X-Collector-ID": "collector-1"},
    )
    assert alerts.status_code == 200
    assert len(alerts.json()["alerts"]) == 2

    history = client.get(f"/api/v1/simulations/{created['id']}/inbound-requests")
    assert history.status_code == 200
    assert len(history.json()) == 3
    first = history.json()[0]
    assert first["auth_result"] == "success"
    assert first["items_returned"] > 0

    detail = client.get(f"/api/v1/simulations/{created['id']}/inbound-requests/{first['id']}")
    assert detail.status_code == 200
    assert detail.json()["request_method"] == "GET"
    assert detail.json()["request_path"].startswith("/api/v1/mock/demo-pull/")

    stop = client.post(f"/api/v1/simulations/{created['id']}/stop")
    assert stop.status_code == 200
    assert stop.json()["status"] == "stopped"

    after_stop = client.get(f"/api/v1/mock/demo-pull/events?simulation_id={created['id']}")
    assert after_stop.status_code == 404


def test_mock_api_api_key_auth(client: ASGITestClient) -> None:
    created = client.post(
        "/api/v1/simulations",
        json=_pull_simulation_payload(
            auth_config={"auth_method_id": "api_key_header", "token": "secret-key-123"},
            inbound_config={
                "auth_method_id": "api_key",
                "api_key_header": "X-Api-Key",
            },
        ),
    ).json()
    client.post(f"/api/v1/simulations/{created['id']}/start")

    unauthorized = client.get(f"/api/v1/mock/demo-pull/events?simulation_id={created['id']}")
    assert unauthorized.status_code == 401

    authorized = client.get(
        f"/api/v1/mock/demo-pull/events?simulation_id={created['id']}",
        headers={"X-Api-Key": "secret-key-123"},
    )
    assert authorized.status_code == 200


def test_mock_api_inbound_fault_delay_and_status(client: ASGITestClient) -> None:
    created = client.post(
        "/api/v1/simulations",
        json=_pull_simulation_payload(
            inbound_config={
                "auth_method_id": "none",
                "fault_config": {"enabled": True, "response_status": 429},
            },
        ),
    ).json()
    client.post(f"/api/v1/simulations/{created['id']}/start")

    response = client.get(f"/api/v1/mock/demo-pull/events?simulation_id={created['id']}")
    assert response.status_code == 429


def test_mock_api_force_empty(client: ASGITestClient) -> None:
    created = client.post(
        "/api/v1/simulations",
        json=_pull_simulation_payload(
            inbound_config={
                "auth_method_id": "none",
                "fault_config": {"enabled": True, "force_empty": True},
            },
        ),
    ).json()
    client.post(f"/api/v1/simulations/{created['id']}/start")

    response = client.get(f"/api/v1/mock/demo-pull/events?simulation_id={created['id']}")
    assert response.status_code == 200
    assert response.json()["events"] == []


def test_mock_api_pagination_cursor(client: ASGITestClient) -> None:
    created = client.post("/api/v1/simulations", json=_pull_simulation_payload()).json()
    client.post(f"/api/v1/simulations/{created['id']}/start")

    page1 = client.get(
        f"/api/v1/mock/demo-pull/events?simulation_id={created['id']}&limit=2"
    ).json()
    page2 = client.get(
        f"/api/v1/mock/demo-pull/events?simulation_id={created['id']}&limit=2"
        f"&pageToken={page1['nextPageToken']}"
    ).json()
    assert len(page1["events"]) == 2
    assert len(page2["events"]) == 2
    assert page1["events"][0]["id"] != page2["events"][0]["id"]
