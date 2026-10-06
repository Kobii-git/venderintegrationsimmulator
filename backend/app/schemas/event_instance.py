from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class DeliveryAttemptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    target_id: str | None = None
    delivery_confirmation: str | None = None
    delivery_note: str | None = None
    attempt_number: int
    started_at: datetime
    completed_at: datetime | None = None
    transport_id: str
    destination_summary: str
    request_url_redacted: str | None = None
    request_method: str | None = None
    request_headers_redacted: dict[str, str] = Field(default_factory=dict)
    request_query_params_redacted: dict[str, Any] = Field(default_factory=dict)
    request_body: str | None = None
    response_status_code: int | None = None
    response_headers_redacted: dict[str, str] = Field(default_factory=dict)
    response_body: str | None = None
    latency_ms: int | None = None
    success: bool
    error_message: str | None = None
    error_category: str | None = None
    error_explanation: str | None = None


class EventInstanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    simulation_id: str
    product_id: str
    scenario_id: str
    event_kind: str = "scenario"
    action_id: str | None = None
    fidelity_mode: str
    payload: dict[str, Any]
    correlation_id: str
    status: str
    payload_source: str
    replayed_from_event_id: str | None = None
    simulator_metadata: dict[str, Any] = Field(default_factory=dict)
    generated_at: datetime
    delivery_attempts: list[DeliveryAttemptResponse] = Field(default_factory=list)


class EventInstanceSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    simulation_id: str
    product_id: str
    scenario_id: str
    event_kind: str = "scenario"
    action_id: str | None = None
    correlation_id: str
    status: str
    payload_source: str
    generated_at: datetime
    delivery_success: bool | None = None
    response_status_code: int | None = None
    latency_ms: int | None = None
    fault_modified: bool = False


class EventListFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    limit: int = Field(default=100, ge=1, le=500)
    scenario_id: str | None = None
    success: bool | None = None
    http_status: int | None = None
    correlation_id: str | None = None
    since: datetime | None = None
    until: datetime | None = None


class SimulationSendRequestBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    payload_override: dict[str, Any] | None = None
    scenario_id: str | None = None
    preview_correlation_id: str | None = Field(default=None, min_length=1, max_length=255)
    payload_edited: bool = False


class WorkflowActionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    simulation_id: str
    action_id: str
    event_id: str
    assertion_passed: bool
    delivery_success: bool
    response_status_code: int | None = None
    error_message: str | None = None


class ReplayEventRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["exact", "regenerate"]


class CurlResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attempt_id: str
    exact: bool
    command: str
    warnings: list[str] = Field(default_factory=list)
    secrets_redacted: bool = True


class ReplayEventResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    simulation_id: str
    source_event_id: str
    new_event_id: str
    correlation_id: str
    scenario_id: str
    payload_source: str
    payload: dict[str, Any]
    delivery_success: bool
    response_status_code: int | None = None
    latency_ms: int | None = None
    error_message: str | None = None
