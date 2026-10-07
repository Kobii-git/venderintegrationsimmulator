"""Generate cURL commands from delivery attempts without exposing secrets."""

from __future__ import annotations

import shlex
from typing import Any
from urllib.parse import urlencode, urlparse, urlunparse

from app.core.redaction import REDACTED, redact_mapping

CURL_REDACTED = "<REDACTED>"


def build_curl_command(
    *,
    method: str,
    destination_url: str,
    query_params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    body: str | None = None,
    auth_method_id: str = "none",
    auth_header_present: bool = False,
) -> str:
    """Build a copy-paste cURL command with secrets replaced by placeholders."""
    url = _build_url(destination_url, query_params or {})
    parts = ["curl", "-X", method.upper(), shlex.quote(url)]

    redacted_headers = redact_mapping(headers or {})
    if isinstance(redacted_headers, dict):
        for key, value in redacted_headers.items():
            header_value = CURL_REDACTED if value == REDACTED else str(value)
            parts.extend(["-H", shlex.quote(f"{key}: {header_value}")])

    if auth_method_id == "basic" and not auth_header_present:
        parts.append("# Note: Basic auth configured on simulation — use -u 'username:<REDACTED>'")
    elif auth_method_id == "bearer" and not auth_header_present:
        parts.append(
            "# Note: Bearer token configured on simulation — use "
            "-H 'Authorization: Bearer <REDACTED>'"
        )

    if body and method.upper() not in {"GET", "HEAD"}:
        parts.extend(["--data-raw", shlex.quote(body)])

    return " \\\n  ".join(parts)


def _build_url(destination_url: str, query_params: dict[str, Any]) -> str:
    if not query_params:
        return destination_url

    redacted_params = redact_mapping(query_params)
    if not isinstance(redacted_params, dict):
        return destination_url

    parsed = urlparse(destination_url)
    existing = parsed.query
    encoded = urlencode(redacted_params, doseq=True)
    query = f"{existing}&{encoded}" if existing else encoded
    return urlunparse(parsed._replace(query=query))


def build_curl_from_attempt(
    attempt: Any,
    *,
    auth_method_id: str = "none",
) -> tuple[str, bool, list[str]]:
    headers = attempt.request_headers_redacted or {}
    auth_header_present = any(k.lower() == "authorization" for k in headers)
    exact_url = getattr(attempt, "request_url_redacted", None)
    warnings: list[str] = []
    if exact_url:
        base_url = exact_url
        query_params: dict[str, Any] = {}
        exact = True
    else:
        parsed = urlparse(attempt.destination_summary)
        base_url = urlunparse(parsed._replace(query=""))
        query_params = getattr(attempt, "request_query_params_redacted", None) or {}
        exact = False
        warnings.append("Legacy attempt does not contain an exact request URL")
    compressed = str(attempt.request_body or "").startswith("[gzip upload:")
    if compressed:
        warnings.append(
            "Compressed upload bytes are not stored in history. "
            "Supply the gzip NDJSON file with --data-binary @logs.ndjson.gz."
        )
        exact = False
    command = build_curl_command(
        method=attempt.request_method or "POST",
        destination_url=base_url,
        query_params=query_params,
        headers=headers,
        body=None if compressed else attempt.request_body,
        auth_method_id=auth_method_id,
        auth_header_present=auth_header_present,
    )
    if compressed:
        command += " \\\n  --data-binary @logs.ndjson.gz"
    return command, exact, warnings
