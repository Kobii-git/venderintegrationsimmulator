from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

DeliveryConfirmation = Literal["confirmed", "api_accepted", "transport_accepted", "best_effort"]


class DeliveryResult(BaseModel):
    """Transport-neutral delivery outcome mapped to delivery_attempts."""

    model_config = ConfigDict(extra="forbid")

    success: bool
    reached_server: bool
    started_at: datetime
    completed_at: datetime
    latency_ms: int
    destination: str
    request_url_redacted: str | None = None
    method: str
    request_headers_redacted: dict[str, str] = Field(default_factory=dict)
    request_query_params_redacted: dict[str, Any] = Field(default_factory=dict)
    request_body: str | None = None
    response_status_code: int | None = None
    response_headers_redacted: dict[str, str] = Field(default_factory=dict)
    response_body: str | None = None
    error_message: str | None = None
    error_category: str | None = None
    delivery_confirmation: DeliveryConfirmation = "confirmed"
    delivery_note: str | None = None
