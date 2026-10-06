import httpx
import pytest
import respx


@respx.mock
def test_transport_test_endpoint(client) -> None:
    respx.head("https://example.com/hook").mock(return_value=httpx.Response(200))
    response = client.post(
        "/api/v1/transport/http/test",
        json={
            "url": "https://example.com/hook",
            "method": "HEAD",
            "auth_config": {"auth_method_id": "none"},
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["reached_server"] is True
    assert "Authorization" not in data["request_headers_redacted"] or (
        data["request_headers_redacted"].get("Authorization") == "***REDACTED***"
    )


@respx.mock
def test_transport_send_endpoint_redacts_secrets(client) -> None:
    route = respx.post(url__regex=r"https://example\.com/hook.*").mock(
        return_value=httpx.Response(
            201,
            text=("super-secret-token custom-header-canary custom-query-canary"),
            headers={
                "X-Diagnostic": "received super-secret-token",
                "Set-Cookie": "session=response-cookie-canary; HttpOnly",
            },
        )
    )
    response = client.post(
        "/api/v1/transport/http/send",
        json={
            "url": "https://example.com/hook",
            "method": "POST",
            "body": {"hello": "world"},
            "headers": {"X-Partner": "custom-header-canary"},
            "query_params": {"partner": "custom-query-canary"},
            "sensitive_header_names": ["X-Partner"],
            "sensitive_query_names": ["partner"],
            "auth_config": {
                "auth_method_id": "bearer",
                "token": "super-secret-token",
            },
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert route.called
    assert data["request_headers_redacted"]["Authorization"] == "***REDACTED***"
    assert data["request_headers_redacted"]["X-Partner"] == "***REDACTED***"
    assert data["response_headers_redacted"]["set-cookie"] == "***REDACTED***"
    assert data["response_headers_redacted"]["x-diagnostic"] == "received ***REDACTED***"
    assert data["response_body"] == ("***REDACTED*** ***REDACTED*** ***REDACTED***")
    assert "super-secret-token" not in response.text
    assert "custom-header-canary" not in response.text
    assert "custom-query-canary" not in response.text
    assert "response-cookie-canary" not in response.text


@pytest.mark.parametrize(
    "endpoint",
    ["/api/v1/transport/http/test", "/api/v1/transport/http/send"],
)
def test_transport_endpoints_reject_embedded_url_credentials(client, endpoint: str) -> None:
    response = client.post(
        endpoint,
        json={
            "url": "https://url-user:url-password-canary@example.com/hook",
            "method": "POST",
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
def test_transport_endpoint_redacts_secret_from_failure_message(client) -> None:
    secret = "api-failure-message-canary"
    respx.post("https://example.com/hook").mock(
        side_effect=httpx.ConnectError(
            f"connection rejected {secret}",
            request=httpx.Request("POST", "https://example.com/hook"),
        )
    )
    response = client.post(
        "/api/v1/transport/http/send",
        json={
            "url": "https://example.com/hook",
            "method": "POST",
            "auth_config": {"auth_method_id": "bearer", "token": secret},
        },
    )
    assert response.status_code == 200
    assert response.json()["error_message"] == (
        "Connection failed: connection rejected ***REDACTED***"
    )
    assert secret not in response.text
