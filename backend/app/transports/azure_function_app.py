"""Synchronous, function-key protected Azure ingestion relay client."""

import json
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx
from app.core.http_response import InvalidResponseError, ResponseLimitError, bounded_request
from app.transports.azure_logs_ingestion import AzureLogsIngestionTransport
from app.transports.delivery_result import DeliveryResult


class AzureFunctionAppTransport(AzureLogsIngestionTransport):
    transport_id = "azure_function_app"

    def _delivery_url(self, destination: dict[str, Any]) -> str:
        url = str(destination["url"])
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError(
                "Function App requires an HTTPS URL without credentials, query or fragment"
            )
        return url

    async def _token(
        self, destination: dict[str, Any], auth: dict[str, Any], *, force: bool = False
    ) -> str:
        token = auth.get("token")
        if not isinstance(token, str) or not token:
            raise ValueError("Function App requires a function key")
        return token

    def _headers(self, token: str) -> dict[str, str]:
        return {"Content-Type": "application/json", "x-functions-key": token}

    def _accepted(self, response: httpx.Response, batch: bytes) -> bool:
        if response.status_code != 200:
            return False
        try:
            body = response.json()
        except ValueError:
            return False
        return (
            isinstance(body, dict)
            and type(body.get("accepted_records")) is int
            and body["accepted_records"] == len(json.loads(batch))
            and body.get("downstream_status") == 204
            and isinstance(body.get("request_id"), str)
            and bool(body["request_id"])
        )

    async def test_destination(
        self, destination: dict[str, Any], auth_config: dict[str, Any]
    ) -> DeliveryResult:
        start = datetime.now(UTC)
        status = None
        url = ""
        try:
            parsed = urlsplit(self._delivery_url(destination))
            url = urlunsplit(
                (parsed.scheme, parsed.netloc, parsed.path.rsplit("/", 1)[0] + "/health", "", "")
            )
            token = await self._token(destination, auth_config)
            if self._client is None:
                self._client = httpx.AsyncClient(follow_redirects=False)
            response = await bounded_request(
                self._client,
                "GET",
                url,
                headers=self._headers(token),
                timeout=float(destination.get("timeout_seconds", 60)),
            )
            status = response.status_code
            if status != 200 or response.json().get("configured") is not True:
                raise ValueError(f"Function health check rejected (HTTP {status})")
            error = None
            category = None
        except (ValueError, KeyError, TypeError, AttributeError, httpx.HTTPError) as exc:
            category = (
                exc.category
                if isinstance(exc, ResponseLimitError | InvalidResponseError)
                else "auth"
            )
            error = (
                "Function authentication/configuration check failed; "
                "verify URL, function key and relay settings"
            )
        return DeliveryResult(
            success=error is None,
            reached_server=status is not None,
            started_at=start,
            completed_at=datetime.now(UTC),
            latency_ms=0,
            destination=url,
            request_url_redacted=url,
            method="GET",
            response_status_code=status,
            error_message=error,
            error_category=category,
            request_headers_redacted=self._headers("***REDACTED***"),
            delivery_note=(
                "Function authentication and configuration only; "
                "no records uploaded and DCR access not verified."
            ),
        )
