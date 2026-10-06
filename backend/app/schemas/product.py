from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MockRouteSummaryResponse(BaseModel):
    id: str
    path: str
    methods: list[str]
    scenario_id: str
    description: str | None = None
    response_type: str = "list"
    supports_pagination: bool = True
    supports_time_filter: bool = True
    handler: str = "dataset_list"
    required_oauth_scopes: list[str] = Field(default_factory=list)
    response_profile: dict[str, Any] = Field(default_factory=dict)


class ProductActionSummaryResponse(BaseModel):
    id: str
    display_name: str
    description: str | None = None
    supported_modes: list[str] = Field(default_factory=list)


class ProductSummaryResponse(BaseModel):
    id: str
    display_name: str
    version: str
    description: str | None
    supported_modes: list[str]
    supported_transports: list[str]
    supported_auth_methods: list[str]
    supported_inbound_auth_methods: list[str]
    scenario_count: int
    formats: list[str] = Field(default_factory=list)
    field_references: list[str] = Field(default_factory=list)
    schema_version: str | None = None
    compatibility: str | None = None
    has_plugin: bool


class ProductDetailResponse(ProductSummaryResponse):
    diagnostic_merge: str
    inbound_options_schema: dict[str, Any] = Field(default_factory=dict)
    scenarios: list["ScenarioSummaryResponse"]
    mock_routes: list[MockRouteSummaryResponse] = Field(default_factory=list)
    actions: list[ProductActionSummaryResponse] = Field(default_factory=list)


class ScenarioSummaryResponse(BaseModel):
    id: str
    display_name: str
    description: str | None
    default_transport: str
    config_schema: dict[str, Any]
    supported_modes: list[str] = Field(default_factory=list)
    delivery_policy: dict[str, Any] = Field(default_factory=dict)


class ScenarioVariableResponse(BaseModel):
    name: str
    type: str | None = None
    description: str | None = None
    default: Any = None
    required: bool = False


class ScenarioDetailResponse(ScenarioSummaryResponse):
    product_id: str
    template_path: str
    variables: list[ScenarioVariableResponse] = Field(default_factory=list)
    template_metadata: dict[str, Any] = Field(default_factory=dict)


class RenderedScenarioPreviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: str
    scenario_id: str
    fidelity_mode: str
    correlation_id: str
    payload: dict[str, Any]
