from tests.asgi_client import ASGITestClient


def _simulation_payload(**overrides) -> dict:
    payload = {
        "name": "Sentinel Webhook Test",
        "product_id": "upguard",
        "scenario_id": "data-leak",
        "simulation_mode": "push_webhook",
        "fidelity_mode": "vendor_accurate",
        "destination": {
            "transport_id": "http_webhook",
            "url": "https://example.com/webhook",
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


def test_create_simulation(client: ASGITestClient) -> None:
    response = client.post("/api/v1/simulations", json=_simulation_payload())
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Sentinel Webhook Test"
    assert data["product_id"] == "upguard"
    assert data["auth_config"]["has_password"] is True
    assert "token" not in data["auth_config"]
    assert "password" not in data["auth_config"]


def test_list_and_get_simulation(client: ASGITestClient) -> None:
    created = client.post("/api/v1/simulations", json=_simulation_payload(name="List Me")).json()

    list_response = client.get("/api/v1/simulations")
    assert list_response.status_code == 200
    assert any(item["id"] == created["id"] for item in list_response.json())

    get_response = client.get(f"/api/v1/simulations/{created['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["name"] == "List Me"


def test_update_simulation_preserves_secret_when_not_provided(client: ASGITestClient) -> None:
    created = client.post("/api/v1/simulations", json=_simulation_payload()).json()

    update_response = client.patch(
        f"/api/v1/simulations/{created['id']}",
        json={"name": "Renamed"},
    )
    assert update_response.status_code == 200
    data = update_response.json()
    assert data["name"] == "Renamed"
    assert data["auth_config"]["has_password"] is True


def test_update_simulation_can_clear_password(client: ASGITestClient) -> None:
    created = client.post("/api/v1/simulations", json=_simulation_payload()).json()

    update_response = client.patch(
        f"/api/v1/simulations/{created['id']}",
        json={"auth_config": {"password": None}},
    )
    assert update_response.status_code == 200
    assert update_response.json()["auth_config"]["has_password"] is False


def test_delete_simulation(client: ASGITestClient) -> None:
    created = client.post("/api/v1/simulations", json=_simulation_payload()).json()

    delete_response = client.delete(f"/api/v1/simulations/{created['id']}")
    assert delete_response.status_code == 204

    get_response = client.get(f"/api/v1/simulations/{created['id']}")
    assert get_response.status_code == 404
    assert get_response.json()["error"]["code"] == "not_found"


def test_create_simulation_unknown_product(client: ASGITestClient) -> None:
    response = client.post(
        "/api/v1/simulations",
        json=_simulation_payload(product_id="unknown-vendor"),
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_create_simulation_invalid_mode(client: ASGITestClient) -> None:
    response = client.post(
        "/api/v1/simulations",
        json=_simulation_payload(simulation_mode="pull_api"),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_create_simulation_missing_name(client: ASGITestClient) -> None:
    payload = _simulation_payload()
    payload["name"] = ""
    response = client.post("/api/v1/simulations", json=payload)
    assert response.status_code == 422


def test_continuous_schedule_requires_interval_seconds(client: ASGITestClient) -> None:
    response = client.post(
        "/api/v1/simulations",
        json=_simulation_payload(schedule={"type": "continuous"}),
    )
    assert response.status_code == 422
