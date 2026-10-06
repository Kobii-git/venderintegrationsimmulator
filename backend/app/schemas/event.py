from typing import Any

from app.domain.enums import FidelityMode
from app.schemas.simulation import AuthConfigInput, DestinationConfig
from app.schemas.transport import DeliveryResultResponse
from pydantic import BaseModel, ConfigDict, Field


class ScenarioEventRequest(BaseModel):
    """Shared fields for scenario preview and one-shot send."""

    model_config = ConfigDict(extra="forbid")

    fidelity_mode: FidelityMode = FidelityMode.TROUBLESHOOTING
    scenario_overrides: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str | None = None


class ScenarioPreviewRequest(ScenarioEventRequest):
    """Generate a scenario payload without sending."""


class ScenarioRawPreviewRequest(ScenarioPreviewRequest):
    fidelity_mode: FidelityMode = FidelityMode.VENDOR_ACCURATE


class ScenarioRawPreviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: str
    scenario_id: str
    fidelity_mode: FidelityMode
    content_type: str
    raw_log: str


class ScenarioPreviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: str
    scenario_id: str
    scenario_display_name: str
    scenario_description: str | None
    correlation_id: str
    fidelity_mode: FidelityMode
    content_type: str
    method: str
    payload: dict[str, Any]


class ScenarioSendRequest(ScenarioEventRequest):
    """One-shot scenario delivery to a configured destination."""

    destination: DestinationConfig
    auth_config: AuthConfigInput = Field(default_factory=AuthConfigInput)
    payload_override: dict[str, Any] | None = None


class ScenarioSendEventResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    correlation_id: str
    product_id: str
    scenario_id: str
    fidelity_mode: FidelityMode
    content_type: str
    method: str
    payload: dict[str, Any]
    payload_source: str


class ScenarioSendResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event: ScenarioSendEventResponse
    delivery: DeliveryResultResponse
