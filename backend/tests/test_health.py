from tests.asgi_client import ASGITestClient


def test_health_returns_ok(client: ASGITestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data


def test_version_endpoint(client: ASGITestClient) -> None:
    response = client.get("/api/v1/version")
    assert response.status_code == 200
    data = response.json()
    assert data["app_name"] == "Integration Simulator"
    assert data["version"] == "0.4.3"
    assert data["environment"] == "development"


def test_list_products_includes_upguard_placeholder(client: ASGITestClient) -> None:
    response = client.get("/api/v1/products")
    assert response.status_code == 200
    products = response.json()
    ids = [p["id"] for p in products]
    assert "upguard" in ids
    assert "demo-http" in ids
