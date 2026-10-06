from typing import Any, Protocol

from app.transports.http.models import OutboundHttpRequest


class AuthStrategy(Protocol):
    """Protocol for applying authentication to outbound HTTP requests."""

    auth_method_id: str

    def apply(self, request: OutboundHttpRequest) -> None:
        """Modify the request in-place to apply authentication."""
        ...

    def get_sensitive_header_names(self, auth_config: dict[str, Any]) -> set[str]:
        """Return header names that must be redacted for this auth config."""
        ...
