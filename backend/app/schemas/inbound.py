from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class InboundRequestSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    simulation_id: str | None
    product_id: str
    route_id: str
    received_at: datetime
    request_method: str
    request_path: str
    response_status_code: int
    auth_method_id: str
    auth_result: str
    latency_ms: int
    items_returned: int
    error_message: str | None = None
    request_kind: str = "api"
    token_metadata: dict[str, Any] | None = None


class InboundRequestDetailResponse(InboundRequestSummaryResponse):
    request_query_params: dict[str, Any]
    request_headers_redacted: dict[str, str]
    request_body: str | None = None
    response_headers: dict[str, str]
    response_body: str | None = None


class InboundEndpointRouteResponse(BaseModel):
    id: str
    path: str
    url: str
    methods: list[str]
    handler: str = "dataset_list"


class InboundEndpointInfoResponse(BaseModel):
    simulation_id: str
    product_id: str
    simulation_mode: str
    status: str
    auth_method_id: str
    routes: list[InboundEndpointRouteResponse]
    oauth_token_url: str | None = None
    discovery_urls: list[str] = Field(default_factory=list)
    api_urls: list[str] = Field(default_factory=list)
    oauth_token_ttl_seconds: int | None = None
    oauth_allowed_scopes: list[str] = Field(default_factory=list)
    vendor_options: dict[str, Any] = Field(default_factory=dict)
    query_hint: str = Field(
        default="Pass simulation_id query param when multiple pull simulations share a product"
    )


class IssuedOAuthTokenResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    client_id: str
    scope: str | None
    issued_at: datetime
    expires_at: datetime
    revoked: bool
    is_expired: bool
