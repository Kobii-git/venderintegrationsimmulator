from tests.asgi_client import ASGITestClient


def test_list_products_includes_demo_and_upguard(client: ASGITestClient) -> None:
    response = client.get("/api/v1/products")
    assert response.status_code == 200
    ids = {product["id"] for product in response.json()}
    assert "demo-http" in ids
    assert "upguard" in ids


def test_get_product_detail(client: ASGITestClient) -> None:
    response = client.get("/api/v1/products/demo-http")
    assert response.status_code == 200
    data = response.json()
    assert data["display_name"] == "Demo HTTP Product"
    assert data["has_plugin"] is True
    assert data["supported_modes"] == ["push_webhook"]
    assert len(data["scenarios"]) == 1
    assert data["scenarios"][0]["id"] == "ping"


def test_get_product_not_found(client: ASGITestClient) -> None:
    response = client.get("/api/v1/products/missing-product")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_list_product_scenarios(client: ASGITestClient) -> None:
    response = client.get("/api/v1/products/demo-http/scenarios")
    assert response.status_code == 200
    scenarios = response.json()
    assert len(scenarios) == 1
    assert scenarios[0]["id"] == "ping"
    assert "config_schema" in scenarios[0]


def test_get_scenario_detail(client: ASGITestClient) -> None:
    response = client.get("/api/v1/products/demo-http/scenarios/ping")
    assert response.status_code == 200
    data = response.json()
    assert data["product_id"] == "demo-http"
    assert data["template_path"] == "scenarios/ping.json"
    assert data["template_metadata"]["method"] == "POST"
    assert any(variable["name"] == "message" for variable in data["variables"])


def test_get_scenario_not_found(client: ASGITestClient) -> None:
    response = client.get("/api/v1/products/demo-http/scenarios/missing")
    assert response.status_code == 404
