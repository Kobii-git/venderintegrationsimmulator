from typing import Any

import httpx
from app.transports.http.models import OutboundHttpRequest


class BasicAuthStrategy:
    auth_method_id = "basic"

    def apply(self, request: OutboundHttpRequest) -> None:
        username = request.auth_config.get("username")
        password = request.auth_config.get("password")
        if not username or not password:
            raise ValueError("Basic auth requires username and password")
        request.httpx_auth = httpx.BasicAuth(username=str(username), password=str(password))
        request.sensitive_header_names.add("authorization")

    def get_sensitive_header_names(self, auth_config: dict[str, Any]) -> set[str]:
        return {"authorization"}
