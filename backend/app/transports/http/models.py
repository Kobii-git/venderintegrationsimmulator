from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

HttpMethod = Literal["GET", "POST", "PUT", "HEAD"]
DeliveryConfirmation = Literal["confirmed", "transport_accepted", "best_effort"]


class OutboundHttpRequest(BaseModel):
    """Vendor-neutral outbound HTTP request description."""

    model_config = ConfigDict(extra="forbid")

    method: HttpMethod = "POST"
    url: str
    headers: dict[str, str] = Field(default_factory=dict)
    query_params: dict[str, Any] = Field(default_factory=dict)
    body: bytes | None = None
    content_type: str | None = "application/json"
    auth_config: dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: float = Field(default=30.0, ge=0.1, le=300.0)
    verify_tls: bool = True
    ca_file: str | None = None
    follow_redirects: bool = True

    # Populated by auth strategy before send; excluded from serialization.
    httpx_auth: Any = Field(default=None, exclude=True)
    sensitive_header_names: set[str] = Field(default_factory=set, exclude=True)
    sensitive_query_names: set[str] = Field(default_factory=set, exclude=True)

    @field_validator("method")
    @classmethod
    def normalize_method(cls, value: str) -> str:
        return value.upper()


class HttpDeliveryResult(BaseModel):
    """Structured delivery outcome for HTTP transports."""

    model_config = ConfigDict(extra="forbid")

    success: bool
    reached_server: bool
    started_at: datetime
    completed_at: datetime
    latency_ms: int
    destination: str
    request_url_redacted: str | None = None
    method: str
    request_headers_redacted: dict[str, str]
    request_query_params_redacted: dict[str, Any] = Field(default_factory=dict)
    request_body: str | None
    response_status_code: int | None = None
    response_headers_redacted: dict[str, str] = Field(default_factory=dict)
    response_body: str | None = None
    error_message: str | None = None
    error_category: str | None = None
    delivery_confirmation: DeliveryConfirmation = "confirmed"
    delivery_note: str | None = None
