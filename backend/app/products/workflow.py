"""Optional vendor workflow contract used by advanced product modules."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field


class VendorWorkflowError(Exception):
    def __init__(self, status_code: int, body: Any, headers: dict[str, str] | None = None) -> None:
        super().__init__(str(body))
        self.status_code = status_code
        self.body = body
        self.headers = headers or {}


class WorkflowResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status_code: int = 200
    body: Any = None
    raw_content: bytes | None = None
    media_type: str = "application/json"
    headers: dict[str, str] = Field(default_factory=dict)


@runtime_checkable
class ProductWorkflowPlugin(Protocol):
    product_id: str

    def validate_inbound_options(self, options: dict[str, Any]) -> None: ...

    def validate_inbound_request(
        self,
        route_id: str,
        *,
        method: str,
        headers: dict[str, str],
        query_params: dict[str, str],
        vendor_options: dict[str, Any],
    ) -> None: ...

    def filter_inbound_items(
        self,
        route_id: str,
        items: list[dict[str, Any]],
        query_params: dict[str, str],
    ) -> list[dict[str, Any]]: ...

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
    ) -> WorkflowResponse | None: ...

    def build_static_response(
        self,
        route_id: str,
        *,
        request_url: str,
        vendor_options: dict[str, Any],
    ) -> WorkflowResponse | None: ...

    def format_oauth_success(
        self,
        route_id: str,
        body: dict[str, Any],
    ) -> dict[str, Any]: ...

    def format_oauth_error(
        self,
        route_id: str,
        body: dict[str, Any],
    ) -> dict[str, Any]: ...

    def format_inbound_error(
        self,
        route_id: str,
        status_code: int,
        message: str,
    ) -> dict[str, Any]: ...

    def prepare_outbound_payload(
        self,
        scenario_id: str,
        payload: dict[str, Any],
        *,
        correlation_id: str,
    ) -> dict[str, Any]: ...


class BaseProductWorkflowPlugin:
    """No-op defaults for product modules that override selected workflow hooks."""

    product_id = ""

    def validate_inbound_options(self, options: dict[str, Any]) -> None:
        del options

    def validate_inbound_request(
        self,
        route_id: str,
        *,
        method: str,
        headers: dict[str, str],
        query_params: dict[str, str],
        vendor_options: dict[str, Any],
    ) -> None:
        del route_id, method, headers, query_params, vendor_options

    def filter_inbound_items(
        self,
        route_id: str,
        items: list[dict[str, Any]],
        query_params: dict[str, str],
    ) -> list[dict[str, Any]]:
        del route_id, query_params
        return items

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
        del (
            route_id,
            items,
            next_cursor,
            terminal_cursor,
            total,
            request_url,
            query_params,
            vendor_options,
            default_body,
        )
        return None

    def build_static_response(
        self,
        route_id: str,
        *,
        request_url: str,
        vendor_options: dict[str, Any],
    ) -> WorkflowResponse | None:
        del route_id, request_url, vendor_options
        return None

    def format_oauth_success(
        self,
        route_id: str,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        del route_id
        return body

    def format_oauth_error(
        self,
        route_id: str,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        del route_id
        return body

    def format_inbound_error(
        self,
        route_id: str,
        status_code: int,
        message: str,
    ) -> dict[str, Any]:
        del route_id, status_code
        return {"error": message}

    def prepare_outbound_payload(
        self,
        scenario_id: str,
        payload: dict[str, Any],
        *,
        correlation_id: str,
    ) -> dict[str, Any]:
        del scenario_id, correlation_id
        return payload
