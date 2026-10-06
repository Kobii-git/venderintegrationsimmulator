from typing import Any

from app.transports.http.models import OutboundHttpRequest


class ApiKeyHeaderAuthStrategy:
    auth_method_id = "api_key_header"

    def apply(self, request: OutboundHttpRequest) -> None:
        token = request.auth_config.get("token")
        header_name = request.auth_config.get("header_name") or "X-API-Key"
        if not token:
            raise ValueError("API key header auth requires token")
        prefix = request.auth_config.get("header_prefix", "")
        request.headers[header_name] = f"{prefix}{token}"
        request.sensitive_header_names.add(header_name.lower())

    def get_sensitive_header_names(self, auth_config: dict[str, Any]) -> set[str]:
        header_name = auth_config.get("header_name") or "X-API-Key"
        return {header_name.lower()}
