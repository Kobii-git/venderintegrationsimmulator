import httpx
import pytest
import respx
from app.auth_strategies.registry import register_default_auth_strategies
from app.domain.enums import DeliveryErrorCategory
from app.transports.http.engine import HttpDeliveryEngine, encode_json_body
from app.transports.http.models import OutboundHttpRequest


@pytest.fixture(autouse=True)
def _register_auth() -> None:
    from app.auth_strategies.registry import auth_strategy_registry

    auth_strategy_registry._strategies.clear()
    register_default_auth_strategies()


@pytest.fixture
def engine() -> HttpDeliveryEngine:
    return HttpDeliveryEngine()


@pytest.mark.asyncio
@respx.mock
async def test_successful_post_delivery(engine: HttpDeliveryEngine) -> None:
    route = respx.post("https://example.com/webhook").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )
    request = engine.build_request(
        method="POST",
        url="https://example.com/webhook",
        body=encode_json_body({"event": "test"}),
        auth_config={"auth_method_id": "none"},
    )
    result = await engine.execute(request)
    assert result.success is True
    assert result.reached_server is True
    assert result.response_status_code == 200
    assert route.called


@pytest.mark.asyncio
@respx.mock
async def test_basic_auth_applied_and_redacted(engine: HttpDeliveryEngine) -> None:
    route = respx.post("https://example.com/webhook").mock(return_value=httpx.Response(204))
    request = engine.build_request(
        method="POST",
        url="https://example.com/webhook",
        body=b"{}",
        auth_config={
            "auth_method_id": "basic",
            "username": "user",
            "password": "secret-pass",
        },
    )
    result = await engine.execute(request)
    assert result.success is True
    assert route.called
    sent_request = route.calls.last.request
    assert sent_request.headers["Authorization"].startswith("Basic ")
    assert result.request_headers_redacted["Authorization"] == "***REDACTED***"
    assert "secret-pass" not in str(result.request_headers_redacted)


@pytest.mark.asyncio
@respx.mock
async def test_bearer_auth_redacted(engine: HttpDeliveryEngine) -> None:
    route = respx.post("https://example.com/webhook").mock(return_value=httpx.Response(200))
    request = engine.build_request(
        method="POST",
        url="https://example.com/webhook",
        body=b"{}",
        auth_config={"auth_method_id": "bearer", "token": "bearer-secret"},
    )
    result = await engine.execute(request)
    assert route.called
    assert result.request_headers_redacted["Authorization"] == "***REDACTED***"
    assert "bearer-secret" not in str(result)


@pytest.mark.asyncio
@respx.mock
async def test_api_key_header_auth(engine: HttpDeliveryEngine) -> None:
    route = respx.post("https://example.com/webhook").mock(return_value=httpx.Response(200))
    request = engine.build_request(
        method="POST",
        url="https://example.com/webhook",
        body=b"{}",
        auth_config={
            "auth_method_id": "api_key_header",
            "header_name": "X-API-Key",
            "token": "abc123",
        },
    )
    result = await engine.execute(request)
    assert route.called
    assert route.calls.last.request.headers["X-API-Key"] == "abc123"
    assert result.request_headers_redacted["X-API-Key"] == "***REDACTED***"


@pytest.mark.asyncio
@respx.mock
async def test_custom_authorization_header_with_prefix(engine: HttpDeliveryEngine) -> None:
    route = respx.post("https://example.com/webhook").mock(return_value=httpx.Response(200))
    request = engine.build_request(
        method="POST",
        url="https://example.com/webhook",
        body=b"{}",
        auth_config={
            "auth_method_id": "api_key_header",
            "header_name": "Authorization",
            "header_prefix": "",
            "token": "ABC123",
        },
    )
    result = await engine.execute(request)
    assert route.calls.last.request.headers["Authorization"] == "ABC123"
    assert result.request_headers_redacted["Authorization"] == "***REDACTED***"


@pytest.mark.asyncio
@respx.mock
async def test_query_parameters(engine: HttpDeliveryEngine) -> None:
    route = respx.get("https://example.com/webhook").mock(return_value=httpx.Response(200))
    request = engine.build_request(
        method="GET",
        url="https://example.com/webhook",
        query_params={"foo": "bar", "count": 1},
        auth_config={"auth_method_id": "none"},
    )
    result = await engine.execute(request)
    assert result.success is True
    assert route.called
    assert route.calls.last.request.url.params["foo"] == "bar"


@pytest.mark.asyncio
@respx.mock
async def test_http_400_is_reached_but_not_success(engine: HttpDeliveryEngine) -> None:
    respx.post("https://example.com/webhook").mock(
        return_value=httpx.Response(400, text="bad request")
    )
    request = engine.build_request(
        method="POST",
        url="https://example.com/webhook",
        body=b"{}",
        auth_config={"auth_method_id": "none"},
    )
    result = await engine.execute(request)
    assert result.success is False
    assert result.reached_server is True
    assert result.error_category == DeliveryErrorCategory.HTTP_4XX.value


@pytest.mark.asyncio
@respx.mock
@pytest.mark.parametrize("status_code,category", [(401, "auth"), (403, "auth")])
async def test_auth_http_responses(
    engine: HttpDeliveryEngine, status_code: int, category: str
) -> None:
    respx.post("https://example.com/webhook").mock(return_value=httpx.Response(status_code))
    request = engine.build_request(
        method="POST",
        url="https://example.com/webhook",
        body=b"{}",
        auth_config={"auth_method_id": "none"},
    )
    result = await engine.execute(request)
    assert result.reached_server is True
    assert result.error_category == category


@pytest.mark.asyncio
@respx.mock
async def test_rate_limit_429(engine: HttpDeliveryEngine) -> None:
    respx.post("https://example.com/webhook").mock(return_value=httpx.Response(429))
    request = engine.build_request(
        method="POST",
        url="https://example.com/webhook",
        body=b"{}",
        auth_config={"auth_method_id": "none"},
    )
    result = await engine.execute(request)
    assert result.error_category == DeliveryErrorCategory.RATE_LIMIT.value


@pytest.mark.asyncio
@respx.mock
async def test_server_error_500(engine: HttpDeliveryEngine) -> None:
    respx.post("https://example.com/webhook").mock(return_value=httpx.Response(500, text="fail"))
    request = engine.build_request(
        method="POST",
        url="https://example.com/webhook",
        body=b"{}",
        auth_config={"auth_method_id": "none"},
    )
    result = await engine.execute(request)
    assert result.error_category == DeliveryErrorCategory.HTTP_5XX.value


@pytest.mark.asyncio
@respx.mock
async def test_timeout(engine: HttpDeliveryEngine) -> None:
    respx.post("https://example.com/webhook").mock(side_effect=httpx.ReadTimeout("timed out"))
    request = engine.build_request(
        method="POST",
        url="https://example.com/webhook",
        body=b"{}",
        timeout_seconds=1,
        auth_config={"auth_method_id": "none"},
    )
    result = await engine.execute(request)
    assert result.success is False
    assert result.reached_server is False
    assert result.error_category == DeliveryErrorCategory.READ_TIMEOUT.value


@pytest.mark.asyncio
@respx.mock
async def test_connection_error(engine: HttpDeliveryEngine) -> None:
    respx.post("https://example.com/webhook").mock(
        side_effect=httpx.ConnectError(
            "connection refused", request=httpx.Request("POST", "https://example.com/webhook")
        )
    )
    request = engine.build_request(
        method="POST",
        url="https://example.com/webhook",
        body=b"{}",
        auth_config={"auth_method_id": "none"},
    )
    result = await engine.execute(request)
    assert result.reached_server is False
    assert result.error_category == DeliveryErrorCategory.CONNECTION.value


@pytest.mark.asyncio
async def test_invalid_url(engine: HttpDeliveryEngine) -> None:
    request = OutboundHttpRequest(
        method="POST",
        url="not-a-valid-url",
        auth_config={"auth_method_id": "none"},
    )
    result = await engine.execute(request)
    assert result.error_category == DeliveryErrorCategory.MALFORMED_DESTINATION.value
    assert result.reached_server is False


@pytest.mark.asyncio
async def test_embedded_url_credentials_are_rejected_without_echoing_them(
    engine: HttpDeliveryEngine,
) -> None:
    request = OutboundHttpRequest(
        method="POST",
        url="https://url-user:url-password-canary@example.com/hook",
        auth_config={"auth_method_id": "none"},
    )
    result = await engine.execute(request)
    assert result.error_category == DeliveryErrorCategory.MALFORMED_DESTINATION.value
    assert result.request_url_redacted == "https://example.com/hook"
    assert result.error_message == (
        "URL must not include embedded credentials; configure authentication separately."
    )
    assert "url-password-canary" not in str(result)


@pytest.mark.asyncio
@respx.mock
async def test_response_echoes_and_cookie_headers_are_redacted(
    engine: HttpDeliveryEngine,
) -> None:
    secret = "bearer-response-canary"
    cookie = "session=request-cookie-canary"
    respx.post("https://example.com/webhook").mock(
        return_value=httpx.Response(
            200,
            text=f"echo={secret}; cookie={cookie}",
            headers={
                "X-Diagnostic": f"received {secret}",
                "Set-Cookie": "session=response-cookie-canary; HttpOnly",
            },
        )
    )
    request = engine.build_request(
        method="POST",
        url="https://example.com/webhook",
        headers={"Cookie": cookie},
        body=b"{}",
        auth_config={"auth_method_id": "bearer", "token": secret},
    )
    result = await engine.execute(request)
    assert result.request_headers_redacted["Cookie"] == "***REDACTED***"
    assert result.response_headers_redacted["set-cookie"] == "***REDACTED***"
    assert result.response_headers_redacted["x-diagnostic"] == "received ***REDACTED***"
    assert result.response_body == "echo=***REDACTED***; cookie=***REDACTED***"
    assert secret not in str(result)
    assert "request-cookie-canary" not in str(result)
    assert "response-cookie-canary" not in str(result)


@pytest.mark.asyncio
@respx.mock
async def test_transport_error_message_redacts_configured_secret(
    engine: HttpDeliveryEngine,
) -> None:
    secret = "failure-message-canary"
    respx.post("https://example.com/webhook").mock(
        side_effect=httpx.ConnectError(
            f"connection rejected {secret}",
            request=httpx.Request("POST", "https://example.com/webhook"),
        )
    )
    request = engine.build_request(
        method="POST",
        url="https://example.com/webhook",
        body=b"{}",
        auth_config={"auth_method_id": "bearer", "token": secret},
    )
    result = await engine.execute(request)
    assert result.error_message == "Connection failed: connection rejected ***REDACTED***"
    assert secret not in str(result)


@pytest.mark.asyncio
@respx.mock
async def test_follow_redirects_default(engine: HttpDeliveryEngine) -> None:
    respx.post("https://example.com/webhook").mock(return_value=httpx.Response(200))
    request = engine.build_request(
        method="POST",
        url="https://example.com/webhook",
        body=b"{}",
        auth_config={"auth_method_id": "none"},
        follow_redirects=True,
    )
    result = await engine.execute(request)
    assert result.success is True
