from typing import Any

from app.transports.http.models import OutboundHttpRequest


class NoneAuthStrategy:
    auth_method_id = "none"

    def apply(self, request: OutboundHttpRequest) -> None:
        return None

    def get_sensitive_header_names(self, auth_config: dict[str, Any]) -> set[str]:
        return set()
