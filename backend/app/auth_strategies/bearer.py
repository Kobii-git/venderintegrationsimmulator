from typing import Any

from app.transports.http.models import OutboundHttpRequest


class BearerAuthStrategy:
    auth_method_id = "bearer"

    def apply(self, request: OutboundHttpRequest) -> None:
        token = request.auth_config.get("token")
        if not token:
            raise ValueError("Bearer auth requires token")
        request.headers["Authorization"] = f"Bearer {token}"
        request.sensitive_header_names.add("authorization")

    def get_sensitive_header_names(self, auth_config: dict[str, Any]) -> set[str]:
        return {"authorization"}
