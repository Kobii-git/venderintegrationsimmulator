"""Centralized secret redaction for logs, delivery history, and API responses."""

from __future__ import annotations

import re
from typing import Any

SENSITIVE_KEY_PATTERN = re.compile(
    r"(password|token|secret|api[_-]?key|authorization|credential)",
    re.IGNORECASE,
)
REDACTED = "***REDACTED***"

DEFAULT_SENSITIVE_HEADERS = frozenset(
    {
        "authorization",
        "proxy-authorization",
        "x-api-key",
        "x-api-key-id",
        "api-key",
        "cookie",
        "set-cookie",
    }
)


def is_sensitive_key(name: str) -> bool:
    return bool(SENSITIVE_KEY_PATTERN.search(name))


def is_sensitive_header(name: str, extra: set[str] | frozenset[str] | None = None) -> bool:
    normalized = name.lower()
    if normalized in DEFAULT_SENSITIVE_HEADERS:
        return True
    if extra and normalized in {item.lower() for item in extra}:
        return True
    return is_sensitive_key(name)


def redact_headers(
    headers: dict[str, str],
    *,
    extra_sensitive: set[str] | frozenset[str] | None = None,
) -> dict[str, str]:
    """Return a copy of headers with secret values masked."""
    return {
        key: REDACTED if is_sensitive_header(key, extra_sensitive) else value
        for key, value in headers.items()
    }


def redact_mapping(value: Any) -> Any:
    """Recursively redact sensitive keys in mappings for logging."""
    if isinstance(value, dict):
        return {
            key: REDACTED if is_sensitive_key(str(key)) else redact_mapping(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_mapping(item) for item in value]
    if isinstance(value, str) and is_sensitive_key(value):
        return REDACTED
    return value


def redact_string(value: str) -> str:
    if is_sensitive_key(value):
        return REDACTED
    return value


def redact_secret_values(value: Any, secrets: set[str]) -> Any:
    """Redact configured secret values from structured or textual history data."""
    active = {secret for secret in secrets if secret}
    if isinstance(value, dict):
        return {
            key: REDACTED if is_sensitive_key(str(key)) else redact_secret_values(item, active)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_secret_values(item, active) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_secret_values(item, active) for item in value)
    if isinstance(value, str):
        redacted = value
        for secret in sorted(active, key=len, reverse=True):
            redacted = redacted.replace(secret, REDACTED)
        return redacted
    return value


def collect_http_secret_values(
    *,
    auth_config: dict[str, Any],
    headers: dict[str, str],
    query_params: dict[str, Any],
    sensitive_header_names: set[str] | frozenset[str] | None = None,
    sensitive_query_names: set[str] | frozenset[str] | None = None,
) -> set[str]:
    """Collect exact configured secret values before request evidence is redacted."""
    secrets = {
        str(auth_config[field])
        for field in ("password", "token", "oauth_client_secret", "api_key")
        if auth_config.get(field)
    }
    for name, value in headers.items():
        if value and is_sensitive_header(name, sensitive_header_names):
            secrets.add(str(value))
    explicit_query_names = set(sensitive_query_names or set())
    for name, value in query_params.items():
        if value is None or (name not in explicit_query_names and not is_sensitive_key(name)):
            continue
        if isinstance(value, list | tuple | set):
            secrets.update(str(item) for item in value if item is not None and str(item))
        elif str(value):
            secrets.add(str(value))
    return secrets


def truncate_body(body: str | None, *, max_length: int = 65536) -> str | None:
    if body is None:
        return None
    if len(body) <= max_length:
        return body
    return body[:max_length] + "...[truncated]"
