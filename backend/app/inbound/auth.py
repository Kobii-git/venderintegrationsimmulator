"""Verify inbound authentication for mock API requests."""

from collections.abc import Callable
from typing import Any

from fastapi import Request


class InboundAuthResult:
    def __init__(self, *, success: bool, method_id: str, message: str | None = None) -> None:
        self.success = success
        self.method_id = method_id
        self.message = message


def verify_inbound_auth(
    request: Request,
    auth_config: dict[str, Any],
    *,
    oauth_token_validator: Callable[[str], "InboundAuthResult"] | None = None,
) -> InboundAuthResult:
    method_id = auth_config.get("auth_method_id", "none")

    if method_id == "none":
        return InboundAuthResult(success=True, method_id=method_id)

    if method_id == "oauth2_client_credentials":
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return InboundAuthResult(
                success=False,
                method_id=method_id,
                message="Missing bearer token",
            )
        token = auth_header[7:].strip()
        if not token:
            return InboundAuthResult(
                success=False,
                method_id=method_id,
                message="Missing bearer token",
            )
        if oauth_token_validator is None:
            return InboundAuthResult(
                success=False,
                method_id=method_id,
                message="OAuth token validator not configured",
            )
        return oauth_token_validator(token)

    if method_id == "api_key":
        expected = auth_config.get("token") or auth_config.get("api_key")
        if not expected:
            return InboundAuthResult(
                success=False, method_id=method_id, message="API key not configured on simulation"
            )
        header_name = auth_config.get("api_key_header", "X-Api-Key")
        provided = request.headers.get(header_name)
        query_param = auth_config.get("api_key_query_param")
        if not provided and query_param:
            provided = request.query_params.get(query_param)
        prefix = str(auth_config.get("api_key_prefix") or "")
        if provided != f"{prefix}{expected}":
            return InboundAuthResult(success=False, method_id=method_id, message="Invalid API key")
        return InboundAuthResult(success=True, method_id=method_id)

    if method_id == "bearer":
        expected = auth_config.get("token")
        if not expected:
            return InboundAuthResult(
                success=False, method_id=method_id, message="Bearer token not configured"
            )
        auth_header = request.headers.get("Authorization", "")
        if auth_header != f"Bearer {expected}":
            return InboundAuthResult(
                success=False, method_id=method_id, message="Invalid bearer token"
            )
        return InboundAuthResult(success=True, method_id=method_id)

    if method_id == "basic":
        import base64

        username = auth_config.get("username")
        password = auth_config.get("password")
        if not username or not password:
            return InboundAuthResult(
                success=False, method_id=method_id, message="Basic auth not configured"
            )
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Basic "):
            return InboundAuthResult(
                success=False, method_id=method_id, message="Missing basic auth"
            )
        try:
            decoded = base64.b64decode(auth_header[6:]).decode("utf-8")
            provided_user, _, provided_pass = decoded.partition(":")
        except (ValueError, UnicodeDecodeError):
            return InboundAuthResult(
                success=False, method_id=method_id, message="Malformed basic auth"
            )
        if provided_user != username or provided_pass != password:
            return InboundAuthResult(
                success=False, method_id=method_id, message="Invalid credentials"
            )
        return InboundAuthResult(success=True, method_id=method_id)

    return InboundAuthResult(
        success=False, method_id=method_id, message=f"Unsupported auth method: {method_id}"
    )


def inbound_sensitive_header_names(auth_config: dict[str, Any]) -> set[str]:
    method_id = auth_config.get("auth_method_id", "none")
    names = {"authorization"}
    if method_id == "api_key":
        header = auth_config.get("api_key_header", "X-Api-Key")
        names.add(header.lower())
    return names
