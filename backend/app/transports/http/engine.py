from __future__ import annotations

import asyncio
import json
import logging
import ssl
from datetime import UTC, datetime
from typing import Any

import httpx
from app.auth_strategies.registry import auth_strategy_registry
from app.core.http_url import reject_embedded_url_credentials, strip_embedded_url_credentials
from app.core.redaction import (
    collect_http_secret_values,
    redact_headers,
    redact_mapping,
    redact_secret_values,
    truncate_body,
)
from app.domain.enums import DeliveryErrorCategory
from app.transports.http.errors import categorize_exception, categorize_http_status
from app.transports.http.models import HttpDeliveryResult, OutboundHttpRequest

logger = logging.getLogger(__name__)

DEFAULT_MAX_REDIRECTS = 5


class HttpDeliveryEngine:
    """Vendor-neutral HTTP/HTTPS delivery engine."""

    transport_id = "http_webhook"

    def __init__(self) -> None:
        self._clients: dict[tuple[Any, ...], httpx.AsyncClient] = {}

    async def close(self) -> None:
        await asyncio.gather(
            *(client.aclose() for client in self._clients.values()), return_exceptions=True
        )
        self._clients.clear()

    def _client_for(self, request: OutboundHttpRequest) -> httpx.AsyncClient:
        url = httpx.URL(request.url)
        key = (
            id(asyncio.get_running_loop()),
            url.scheme,
            url.host,
            url.port,
            request.verify_tls,
            request.ca_file,
        )
        if key not in self._clients:
            verify: Any = (
                ssl.create_default_context(cafile=request.ca_file) if request.verify_tls else False
            )
            self._clients[key] = httpx.AsyncClient(
                verify=verify,
                max_redirects=DEFAULT_MAX_REDIRECTS,
                limits=httpx.Limits(max_connections=20, max_keepalive_connections=20),
            )
        return self._clients[key]

    def validate_url(self, url: str) -> str:
        reject_embedded_url_credentials(url)
        try:
            parsed = httpx.URL(url)
        except Exception as exc:
            raise ValueError(f"Malformed destination URL: {exc}") from exc
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("URL scheme must be http or https")
        if not parsed.host:
            raise ValueError("URL must include a host")
        return str(parsed)

    def build_request(
        self,
        *,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        query_params: dict[str, Any] | None = None,
        body: bytes | None = None,
        content_type: str | None = "application/json",
        auth_config: dict[str, Any] | None = None,
        timeout_seconds: float = 30.0,
        verify_tls: bool = True,
        ca_file: str | None = None,
        follow_redirects: bool = True,
        sensitive_header_names: set[str] | None = None,
        sensitive_query_names: set[str] | None = None,
    ) -> OutboundHttpRequest:
        request = OutboundHttpRequest(
            method=method.upper(),  # type: ignore[arg-type]
            url=self.validate_url(url),
            headers=dict(headers or {}),
            query_params=dict(query_params or {}),
            body=body,
            content_type=content_type,
            auth_config=dict(auth_config or {}),
            timeout_seconds=timeout_seconds,
            verify_tls=verify_tls,
            ca_file=ca_file,
            follow_redirects=follow_redirects,
            sensitive_header_names={name.casefold() for name in sensitive_header_names or set()},
            sensitive_query_names=set(sensitive_query_names or set()),
        )
        self._apply_auth(request)
        return request

    def _apply_auth(self, request: OutboundHttpRequest) -> None:
        method_id = request.auth_config.get("auth_method_id", "none")
        strategy = auth_strategy_registry.get(method_id)
        if strategy is None:
            raise ValueError(f"Unknown auth method: {method_id}")
        strategy.apply(request)

    async def execute(self, request: OutboundHttpRequest) -> HttpDeliveryResult:
        started_at = datetime.now(UTC)
        destination = strip_embedded_url_credentials(request.url)
        method = request.method
        secrets = collect_http_secret_values(
            auth_config=request.auth_config,
            headers=request.headers,
            query_params=request.query_params,
            sensitive_header_names=request.sensitive_header_names,
            sensitive_query_names=request.sensitive_query_names,
        )

        try:
            request.url = self.validate_url(request.url)
            self._apply_auth(request)
            secrets.update(
                collect_http_secret_values(
                    auth_config=request.auth_config,
                    headers=request.headers,
                    query_params=request.query_params,
                    sensitive_header_names=request.sensitive_header_names,
                    sensitive_query_names=request.sensitive_query_names,
                )
            )
            destination = str(redact_secret_values(self._redacted_request_url(request), secrets))
        except ValueError as exc:
            completed_at = datetime.now(UTC)
            return self._failure_result(
                started_at=started_at,
                completed_at=completed_at,
                request=request,
                destination=destination,
                method=method,
                category=DeliveryErrorCategory.MALFORMED_DESTINATION,
                message=str(redact_secret_values(str(exc), secrets)),
                secret_values=secrets,
                request_url_redacted=destination,
            )

        headers = dict(request.headers)
        if request.body is not None and request.content_type:
            headers.setdefault("Content-Type", request.content_type)

        redacted_request_headers = redact_secret_values(
            redact_headers(headers, extra_sensitive=request.sensitive_header_names),
            secrets,
        )
        if not isinstance(redacted_request_headers, dict):
            redacted_request_headers = {}
        redacted_query_params = {
            key: "***REDACTED***" if key in request.sensitive_query_names else value
            for key, value in (request.query_params or {}).items()
        }
        generic_redacted = redact_mapping(redacted_query_params)
        redacted_query_params = generic_redacted if isinstance(generic_redacted, dict) else {}
        exact_redacted_query = redact_secret_values(redacted_query_params, secrets)
        redacted_query_params = (
            exact_redacted_query if isinstance(exact_redacted_query, dict) else {}
        )
        request_url_redacted = str(
            redact_secret_values(
                self._redacted_request_url(request, query_params=redacted_query_params),
                secrets,
            )
        )
        if request.httpx_auth is not None:
            redacted_request_headers.setdefault("Authorization", "***REDACTED***")
        for header_name in request.sensitive_header_names:
            if header_name not in {key.lower() for key in redacted_request_headers}:
                # Preserve metadata that auth was applied without leaking value.
                canonical = header_name.title() if header_name == "authorization" else header_name
                redacted_request_headers[canonical] = "***REDACTED***"
        request_body_text = redact_secret_values(self._body_to_text(request.body), secrets)

        try:
            timeout = httpx.Timeout(request.timeout_seconds)
            client = self._client_for(request)
            response = await client.request(
                method=request.method,
                url=request.url,
                headers=headers,
                params=request.query_params or None,
                content=request.body,
                auth=request.httpx_auth,
                timeout=timeout,
                follow_redirects=request.follow_redirects,
            )
            client.cookies.clear()
        except Exception as exc:
            completed_at = datetime.now(UTC)
            category, message = categorize_exception(exc)
            message = str(redact_secret_values(message, secrets))
            logger.info(
                "HTTP delivery failed before response",
                extra={
                    "destination": destination,
                    "method": method,
                    "error_category": category.value,
                },
            )
            return self._failure_result(
                started_at=started_at,
                completed_at=completed_at,
                request=request,
                destination=destination,
                method=method,
                category=category,
                message=message,
                request_headers_redacted=redacted_request_headers,
                request_body=request_body_text,
                request_query_params_redacted=redacted_query_params,
                request_url_redacted=request_url_redacted,
                secret_values=secrets,
            )

        completed_at = datetime.now(UTC)
        latency_ms = int((completed_at - started_at).total_seconds() * 1000)
        response_body = redact_secret_values(truncate_body(response.text), secrets)
        response_headers = redact_secret_values(
            redact_headers(
                dict(response.headers.items()),
                extra_sensitive=request.sensitive_header_names,
            ),
            secrets,
        )
        if not isinstance(response_headers, dict):
            response_headers = {}

        status_category = categorize_http_status(response.status_code)
        success = status_category is None

        error_message = None
        error_category = None
        if not success:
            error_category = (
                status_category.value if status_category else DeliveryErrorCategory.UNKNOWN.value
            )
            error_message = f"HTTP {response.status_code}"

        return HttpDeliveryResult(
            success=success,
            reached_server=True,
            started_at=started_at,
            completed_at=completed_at,
            latency_ms=latency_ms,
            destination=destination,
            request_url_redacted=request_url_redacted,
            method=method,
            request_headers_redacted=redacted_request_headers,
            request_query_params_redacted=redacted_query_params,
            request_body=request_body_text,
            response_status_code=response.status_code,
            response_headers_redacted=response_headers,
            response_body=response_body,
            error_message=error_message,
            error_category=error_category,
        )

    async def test_connection(self, request: OutboundHttpRequest) -> HttpDeliveryResult:
        """Probe a destination using HEAD by default for minimal impact."""
        if request.method == "POST" and request.body:
            return await self.execute(request)
        probe = request.model_copy(
            update={"method": "HEAD", "body": None, "content_type": None},
        )
        return await self.execute(probe)

    def _redacted_request_url(
        self,
        request: OutboundHttpRequest,
        *,
        query_params: dict[str, Any] | None = None,
    ) -> str:
        redacted = query_params
        if redacted is None:
            redacted = {
                key: "***REDACTED***" if key in request.sensitive_query_names else value
                for key, value in (request.query_params or {}).items()
            }
            generic = redact_mapping(redacted)
            redacted = generic if isinstance(generic, dict) else {}
        url = httpx.URL(request.url)
        if redacted:
            url = url.copy_merge_params(redacted)
        return str(url)

    def _body_to_text(self, body: bytes | None) -> str | None:
        if body is None:
            return None
        try:
            return truncate_body(body.decode("utf-8"))
        except UnicodeDecodeError:
            return "[binary body omitted]"

    def _failure_result(
        self,
        *,
        started_at: datetime,
        completed_at: datetime,
        request: OutboundHttpRequest,
        destination: str,
        method: str,
        category: DeliveryErrorCategory,
        message: str,
        request_headers_redacted: dict[str, str] | None = None,
        request_query_params_redacted: dict[str, Any] | None = None,
        request_body: str | None = None,
        request_url_redacted: str | None = None,
        secret_values: set[str] | None = None,
    ) -> HttpDeliveryResult:
        secrets = secret_values or set()
        latency_ms = int((completed_at - started_at).total_seconds() * 1000)
        raw_headers = request_headers_redacted or redact_headers(
            request.headers, extra_sensitive=request.sensitive_header_names
        )
        redacted_headers = redact_secret_values(raw_headers, secrets)
        headers = redacted_headers if isinstance(redacted_headers, dict) else {}
        redacted_query_params = request_query_params_redacted
        if redacted_query_params is None:
            redacted_query_params = redact_mapping(request.query_params or {})
        if not isinstance(redacted_query_params, dict):
            redacted_query_params = {}
        exact_redacted_query = redact_secret_values(redacted_query_params, secrets)
        redacted_query_params = (
            exact_redacted_query if isinstance(exact_redacted_query, dict) else {}
        )
        safe_url = request_url_redacted or self._redacted_request_url(
            request, query_params=redacted_query_params
        )
        return HttpDeliveryResult(
            success=False,
            reached_server=False,
            started_at=started_at,
            completed_at=completed_at,
            latency_ms=latency_ms,
            destination=str(redact_secret_values(destination, secrets)),
            request_url_redacted=str(redact_secret_values(safe_url, secrets)),
            method=method,
            request_headers_redacted=headers,
            request_query_params_redacted=redacted_query_params,
            request_body=redact_secret_values(request_body, secrets),
            error_message=str(redact_secret_values(message, secrets)),
            error_category=category.value,
        )


def encode_json_body(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
