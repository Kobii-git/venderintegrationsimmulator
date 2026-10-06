"""Sophos Central workflow and event-shaping behaviour."""

from __future__ import annotations

import random
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from app.domain.enums import FidelityMode
from app.products.plugin import ProductPlugin
from app.products.workflow import (
    BaseProductWorkflowPlugin,
    VendorWorkflowError,
    WorkflowResponse,
)


class SophosCentralPlugin(BaseProductWorkflowPlugin):
    product_id = "sophos-central"

    def enrich_context(
        self,
        scenario_id: str,
        overrides: dict[str, Any],
        *,
        rng: random.Random,
    ) -> dict[str, Any]:
        del scenario_id
        return {
            "hostname": overrides.get("hostname", "SOPHOS-ENDPOINT-01"),
            "username": overrides.get("username", r"EXAMPLE\analyst"),
            "customer_id": str(uuid.UUID(int=rng.getrandbits(128))),
            "endpoint_id": str(uuid.UUID(int=rng.getrandbits(128))),
        }

    def post_render(
        self,
        payload: dict[str, Any],
        fidelity_mode: FidelityMode,
        *,
        scenario_id: str,
        correlation_id: str,
    ) -> dict[str, Any]:
        del fidelity_mode, scenario_id, correlation_id
        return payload

    def validate_inbound_request(
        self,
        route_id: str,
        *,
        method: str,
        headers: dict[str, str],
        query_params: dict[str, str],
        vendor_options: dict[str, Any],
    ) -> None:
        del method
        if route_id != "siem-events":
            return
        normalized_headers = {name.casefold(): value for name, value in headers.items()}
        tenant = normalized_headers.get("x-tenant-id")
        expected = str(vendor_options.get("tenant_id") or "")
        if not tenant:
            raise VendorWorkflowError(
                403,
                self.format_inbound_error(route_id, 403, "Missing X-Tenant-ID"),
            )
        if tenant != expected:
            raise VendorWorkflowError(
                403,
                self.format_inbound_error(route_id, 403, "Invalid tenant ID"),
            )
        raw_from = query_params.get("from_date")
        if raw_from:
            if not raw_from.isdigit():
                raise VendorWorkflowError(
                    400,
                    self.format_inbound_error(route_id, 400, "from_date must be a Unix timestamp"),
                )
            requested = datetime.fromtimestamp(int(raw_from), tz=UTC)
            if requested < datetime.now(UTC) - timedelta(hours=24) or requested > datetime.now(UTC):
                raise VendorWorkflowError(
                    400,
                    self.format_inbound_error(
                        route_id, 400, "from_date must be within the last 24 hours"
                    ),
                )

    def filter_inbound_items(
        self,
        route_id: str,
        items: list[dict[str, Any]],
        query_params: dict[str, str],
    ) -> list[dict[str, Any]]:
        if route_id != "siem-events":
            return items
        excluded = {
            value.strip()
            for value in query_params.get("exclude_types", "").split(",")
            if value.strip()
        }
        return [item for item in items if str(item.get("type")) not in excluded]

    def build_inbound_response(
        self,
        route_id: str,
        *,
        items: list[dict[str, Any]],
        next_cursor: str | None,
        terminal_cursor: str,
        total: int,
        request_url: str,
        query_params: dict[str, str],
        vendor_options: dict[str, Any],
        default_body: Any,
    ) -> WorkflowResponse | None:
        del terminal_cursor, total, request_url, query_params, vendor_options, default_body
        if route_id != "siem-events":
            return None
        body: dict[str, Any] = {"items": items, "has_more": next_cursor is not None}
        if next_cursor is not None:
            body["next_cursor"] = next_cursor
        return WorkflowResponse(body=body)

    def build_static_response(
        self,
        route_id: str,
        *,
        request_url: str,
        vendor_options: dict[str, Any],
    ) -> WorkflowResponse | None:
        if route_id != "whoami":
            return None
        parsed = urlsplit(request_url)
        marker = "/whoami/v1"
        prefix = parsed.path[: -len(marker)] if parsed.path.endswith(marker) else parsed.path
        base_url = urlunsplit((parsed.scheme, parsed.netloc, prefix.rstrip("/"), "", ""))
        return WorkflowResponse(
            body={
                "id": vendor_options["tenant_id"],
                "idType": "tenant",
                "apiHosts": {"global": base_url, "dataRegion": base_url},
            }
        )

    def format_oauth_success(self, route_id: str, body: dict[str, Any]) -> dict[str, Any]:
        if route_id != "oauth-token":
            return body
        access_token = body["access_token"]
        return {
            "access_token": access_token,
            "errorCode": "success",
            "expires_in": body["expires_in"],
            "message": "OK",
            "refresh_token": access_token,
            "token_type": "bearer",
            **({"scope": body["scope"]} if body.get("scope") else {}),
        }

    def format_oauth_error(self, route_id: str, body: dict[str, Any]) -> dict[str, Any]:
        if route_id != "oauth-token":
            return body
        return {
            "errorCode": body.get("error", "error"),
            "message": body.get("error_description", "Authentication failed"),
            "trackingId": str(uuid.uuid4()),
        }

    def format_inbound_error(self, route_id: str, status_code: int, message: str) -> dict[str, Any]:
        del route_id
        return {
            "error": "request_failed",
            "errorCode": str(status_code),
            "message": message,
            "trackingId": str(uuid.uuid4()),
        }


def get_plugin() -> ProductPlugin:
    return SophosCentralPlugin()
