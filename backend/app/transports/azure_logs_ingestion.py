"""Azure Monitor Logs Ingestion API, public cloud, API version 2023-01-01."""

import asyncio
import hashlib
import json
import time
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import quote

import httpx
from app.formats.azure_ingestion import MAX_BATCH_BYTES, validate_record
from app.transports.delivery_result import DeliveryResult


def json_batches(records: list[dict[str, Any]], limit: int = 950_000) -> list[bytes]:
    limit = min(limit, MAX_BATCH_BYTES)
    batches: list[bytes] = []
    parts: list[bytes] = []
    size = 2
    for record in records:
        validate_record(record, limit)
        encoded = json.dumps(record, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        if len(encoded) + 2 > limit:
            raise ValueError("A single JSON record exceeds the batch byte limit")
        if size + len(encoded) + bool(parts) > limit:
            batches.append(b"[" + b",".join(parts) + b"]")
            parts, size = [], 2
        size += len(encoded) + bool(parts)
        parts.append(encoded)
    if parts:
        batches.append(b"[" + b",".join(parts) + b"]")
    return batches


class AzureLogsIngestionTransport:
    transport_id = "azure_logs_ingestion"

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client
        self._tokens: dict[str, tuple[str, float]] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
        self._tokens.clear()

    async def _token(
        self, destination: dict[str, Any], auth: dict[str, Any], *, force: bool = False
    ) -> str:
        tenant = str(destination["tenant_id"])
        client_id, secret = auth.get("oauth_client_id"), auth.get("oauth_client_secret")
        if not client_id or not secret:
            raise ValueError("Azure requires OAuth client ID and client secret")
        key = hashlib.sha256(f"{tenant}:{client_id}:{secret}".encode()).hexdigest()
        async with self._locks.setdefault(key, asyncio.Lock()):
            cached = self._tokens.get(key)
            if not force and cached and cached[1] > time.monotonic():
                return cached[0]
            assert self._client is not None
            response = await self._client.post(
                f'https://login.microsoftonline.com/{quote(tenant, safe="")}/oauth2/v2.0/token',
                data={
                    "grant_type": "client_credentials",
                    "client_id": client_id,
                    "client_secret": secret,
                    "scope": "https://monitor.azure.com/.default",
                },
                timeout=float(destination.get("timeout_seconds", 30)),
                follow_redirects=False,
            )
            if response.status_code != 200:
                raise ValueError(f"OAuth token request rejected (HTTP {response.status_code})")
            data = response.json()
            token = data.get("access_token")
            if not isinstance(token, str) or not token:
                raise ValueError("OAuth response did not include an access token")
            expires = max(float(data.get("expires_in", 3600)), 1)
            self._tokens[key] = token, time.monotonic() + max(expires - min(60, expires / 2), 0)
            return token

    @staticmethod
    def _retry_delay(response: httpx.Response, attempt: int) -> float:
        value = response.headers.get("Retry-After")
        if value:
            try:
                return max(float(value), 0)
            except ValueError:
                try:
                    return max(
                        (parsedate_to_datetime(value) - datetime.now(UTC)).total_seconds(), 0
                    )
                except (TypeError, ValueError):
                    pass
        return float(min(2**attempt, 16))

    def _delivery_url(self, destination: dict[str, Any]) -> str:
        endpoint = str(destination["endpoint"]).rstrip("/")
        if not endpoint.startswith("https://"):
            raise ValueError("Azure ingestion endpoint must use HTTPS")
        dcr = quote(str(destination["dcr_immutable_id"]), safe="")
        stream = quote(str(destination["stream"]), safe="")
        return f"{endpoint}/dataCollectionRules/{dcr}/streams/{stream}?api-version=2023-01-01"

    def _headers(self, token: str) -> dict[str, str]:
        return {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}

    def _accepted(self, response: httpx.Response, batch: bytes) -> bool:
        return response.status_code == 204

    async def deliver(
        self,
        destination: dict[str, Any],
        payload: bytes,
        content_type: str,
        auth_config: dict[str, Any],
    ) -> DeliveryResult:
        start = datetime.now(UTC)
        url = ""
        status: int | None = None
        error: str | None = None
        category: str | None = None
        retries = int(destination.get("max_retries", 3))
        try:
            url = self._delivery_url(destination)
            records = json.loads(payload)
            if isinstance(records, dict):
                records = [records]
            if (
                not isinstance(records, list)
                or not records
                or any(not isinstance(r, dict) for r in records)
            ):
                raise ValueError("Ingestion requires a nonempty JSON object or array of objects")
            batches = json_batches(records, int(destination.get("batch_max_bytes", 950_000)))
            if self._client is None:
                # Certificate overrides use mounted CA support via SSL_CERT_FILE.
                self._client = httpx.AsyncClient(
                    follow_redirects=False, limits=httpx.Limits(max_connections=20)
                )
            token = await self._token(destination, auth_config)
            for batch in batches:
                refreshed = False
                for attempt in range(retries + 1):
                    response = await self._client.post(
                        url,
                        content=batch,
                        headers=self._headers(token),
                        timeout=float(destination.get("timeout_seconds", 30)),
                    )
                    status = response.status_code
                    if (
                        status == 401
                        and not refreshed
                        and self.transport_id == "azure_logs_ingestion"
                    ):
                        token = await self._token(destination, auth_config, force=True)
                        refreshed = True
                        response = await self._client.post(
                            url,
                            content=batch,
                            headers=self._headers(token),
                            timeout=float(destination.get("timeout_seconds", 30)),
                        )
                        status = response.status_code
                    if self._accepted(response, batch):
                        break
                    if status in (429, 500, 502, 503, 504) and attempt < retries:
                        delay = self._retry_delay(response, attempt)
                        if delay > 60:
                            raise ValueError(
                                f"HTTP {status}: Retry-After exceeds bounded retry window"
                            )
                        await asyncio.sleep(delay)
                        continue
                    raise ValueError(f"Ingestion API rejected batch (HTTP {status})")
        except (ValueError, KeyError, httpx.HTTPError, TypeError) as exc:
            # Do not retain remote OAuth/API error bodies or credentials in history.
            error = (
                str(exc)
                if isinstance(exc, ValueError)
                else f"Azure ingestion failed ({type(exc).__name__})"
            )
            category = (
                "auth"
                if status in (401, 403) or "OAuth" in error
                else "rate_limit"
                if status == 429
                else "http_5xx"
                if status and status >= 500
                else "malformed_destination"
                if isinstance(exc, (ValueError | KeyError | TypeError))
                else "connection"
            )
        end = datetime.now(UTC)
        return DeliveryResult(
            success=error is None,
            reached_server=status is not None,
            started_at=start,
            completed_at=end,
            latency_ms=int((end - start).total_seconds() * 1000),
            destination=url,
            request_url_redacted=url,
            method="POST",
            request_headers_redacted=self._headers("***REDACTED***"),
            request_body=payload.decode("utf-8", errors="replace")[:20000],
            response_status_code=status,
            error_message=error,
            error_category=category,
            delivery_confirmation="api_accepted",
            delivery_note=(
                "API acceptance does not confirm table arrival. "
                "Validate records with the supplied KQL smoke test. "
                "Retried batches may be duplicated after an ambiguous response."
            ),
        )

    async def test_destination(
        self, destination: dict[str, Any], auth_config: dict[str, Any]
    ) -> DeliveryResult:
        start = datetime.now(UTC)
        if self._client is None:
            self._client = httpx.AsyncClient(follow_redirects=False)
        try:
            await self._token(destination, auth_config)
            error = None
        except (ValueError, httpx.HTTPError, KeyError) as exc:
            error = str(exc) if isinstance(exc, ValueError) else "OAuth connectivity check failed"
        return DeliveryResult(
            success=error is None,
            reached_server=error is None,
            started_at=start,
            completed_at=datetime.now(UTC),
            latency_ms=0,
            destination=str(destination.get("endpoint", "")),
            method="POST",
            error_message=error,
            error_category="auth" if error else None,
            delivery_confirmation="api_accepted",
            delivery_note=(
                "OAuth token acquisition only; no records uploaded "
                "and DCR permissions not verified."
            ),
        )
