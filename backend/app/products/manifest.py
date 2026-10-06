import re
from typing import Any, Literal

from app.products.capabilities import (
    KNOWN_AUTH_METHODS,
    KNOWN_INBOUND_AUTH_METHODS,
    KNOWN_SIMULATION_MODES,
    KNOWN_TRANSPORTS,
)
from app.products.exceptions import ManifestValidationError
from jsonschema import Draft202012Validator
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator

PRODUCT_ID_PATTERN = re.compile(r"^[a-z][a-z0-9-]*$")
SCENARIO_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_-]*$")
SECRET_OPTION_PATTERN = re.compile(r"(?:password|passwd|secret|token|api[-_]?key|credential)", re.I)


class RouteResponseProfile(BaseModel):
    """Declarative response and pagination behaviour for an inbound route."""

    model_config = ConfigDict(extra="forbid")

    body_style: Literal["envelope", "array", "static"] = "envelope"
    cursor_request_param: str = "cursor"
    cursor_response_field: str = "nextPageToken"
    limit_request_param: str = "limit"
    since_request_param: str | None = None
    until_request_param: str | None = None
    minimum_limit: int = Field(default=1, ge=1, le=10_000)
    default_limit: int | None = Field(default=None, ge=1, le=10_000)
    maximum_limit: int | None = Field(default=None, ge=1, le=10_000)
    pagination_location: Literal["body", "link_header", "none"] = "body"
    include_self_link: bool = False
    always_include_next_link: bool = False
    required_headers: list[str] = Field(default_factory=list)
    response_headers: dict[str, str] = Field(default_factory=dict)


class DeliveryPolicy(BaseModel):
    """Product-owned outbound delivery defaults."""

    model_config = ConfigDict(extra="forbid")

    timeout_seconds: float | None = Field(default=None, ge=0.1, le=300)
    follow_redirects: bool | None = None
    max_attempts: int = Field(default=1, ge=1, le=5)
    retry_on: list[Literal["timeout", "http_5xx"]] = Field(default_factory=list)


class ActionAssertion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["none", "json_field_equals_context"] = "none"
    field: str | None = None
    context_key: str | None = None


class ProductActionRef(BaseModel):
    """A product-defined, operator-triggered outbound workflow action."""

    model_config = ConfigDict(extra="forbid")

    id: str
    display_name: str
    description: str | None = None
    supported_modes: list[str] = Field(default_factory=lambda: ["push_webhook"])
    method: Literal["GET", "POST", "PUT", "HEAD"] = "POST"
    headers: dict[str, str] = Field(default_factory=dict)
    body: dict[str, Any] | None = None
    content_type: str | None = "application/json"
    accepted_statuses: list[int] = Field(default_factory=lambda: [200])
    delivery_policy: DeliveryPolicy = Field(default_factory=DeliveryPolicy)
    assertion: ActionAssertion = Field(default_factory=ActionAssertion)

    @field_validator("id")
    @classmethod
    def validate_action_id(cls, value: str) -> str:
        if not SCENARIO_ID_PATTERN.match(value):
            raise ValueError(f"Invalid product action id '{value}'")
        return value


class MockRouteRef(BaseModel):
    """Inbound mock API route declared in a product manifest."""

    model_config = ConfigDict(extra="forbid")

    id: str
    path: str
    methods: list[str] = Field(default_factory=lambda: ["GET"])
    scenario_id: str
    scenario_ids: list[str] = Field(default_factory=list)
    description: str | None = None
    response_type: str = "list"
    items_field: str = "items"
    next_token_field: str = "nextPageToken"
    page_field: str = "page"
    total_field: str = "total"
    supports_pagination: bool = True
    supports_time_filter: bool = True
    pagination_style: str = "cursor"
    required_oauth_scopes: list[str] = Field(default_factory=list)
    handler: Literal["dataset_list", "dataset_single", "static", "oauth_token"] | None = None
    response_profile: RouteResponseProfile = Field(default_factory=RouteResponseProfile)

    @field_validator("id")
    @classmethod
    def validate_route_id(cls, value: str) -> str:
        if not SCENARIO_ID_PATTERN.match(value):
            raise ValueError(f"Invalid mock route id '{value}'")
        return value

    @field_validator("path")
    @classmethod
    def normalize_path(cls, value: str) -> str:
        return value.strip("/")

    @model_validator(mode="after")
    def normalize_handler(self) -> "MockRouteRef":
        if self.handler is None:
            self.handler = "dataset_single" if self.response_type == "single" else "dataset_list"
        return self


class ScenarioRef(BaseModel):
    """Scenario entry declared in a product manifest."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str
    display_name: str = Field(validation_alias=AliasChoices("display_name", "name"))
    description: str | None = None
    default_transport: str = "http_webhook"
    template: str
    config_schema: dict[str, Any] = Field(default_factory=dict)
    supported_modes: list[str] = Field(default_factory=list)
    delivery_policy: DeliveryPolicy = Field(default_factory=DeliveryPolicy)

    @field_validator("id")
    @classmethod
    def validate_scenario_id(cls, value: str) -> str:
        if not SCENARIO_ID_PATTERN.match(value):
            raise ValueError(
                f"Invalid scenario id '{value}': "
                "use lowercase letters, digits, hyphens, underscores"
            )
        return value


class ProductManifest(BaseModel):
    """Validated product module manifest (manifest.yaml)."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str
    display_name: str = Field(validation_alias=AliasChoices("display_name", "name"))
    version: str
    description: str | None = None
    supported_modes: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("supported_modes", "simulation_modes"),
    )
    supported_transports: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("supported_transports", "transports"),
    )
    supported_auth_methods: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("supported_auth_methods", "authentication"),
    )
    supported_inbound_auth_methods: list[str] = Field(default_factory=list)
    scenarios: list[ScenarioRef] = Field(default_factory=list)
    mock_routes: list[MockRouteRef] = Field(default_factory=list)
    actions: list[ProductActionRef] = Field(default_factory=list)
    inbound_options_schema: dict[str, Any] = Field(default_factory=dict)
    plugin: bool = False
    diagnostic_merge: str = "nested"
    formats: list[str] = Field(default_factory=list)
    field_references: list[str] = Field(default_factory=list)
    schema_version: str | None = None
    compatibility: str | None = None

    @field_validator("id")
    @classmethod
    def validate_product_id(cls, value: str) -> str:
        if not PRODUCT_ID_PATTERN.match(value):
            raise ValueError(
                f"Invalid product id '{value}': use lowercase letters, digits, hyphens"
            )
        return value

    @field_validator("diagnostic_merge")
    @classmethod
    def validate_diagnostic_merge(cls, value: str) -> str:
        if value not in {"nested", "top_level"}:
            raise ValueError("diagnostic_merge must be 'nested' or 'top_level'")
        return value

    @model_validator(mode="after")
    def validate_capabilities_and_scenarios(self) -> "ProductManifest":
        unknown_modes = set(self.supported_modes) - KNOWN_SIMULATION_MODES
        if unknown_modes:
            raise ValueError(f"Unknown simulation modes: {sorted(unknown_modes)}")

        unknown_transports = set(self.supported_transports) - KNOWN_TRANSPORTS
        if unknown_transports:
            raise ValueError(f"Unknown transports: {sorted(unknown_transports)}")

        unknown_auth = set(self.supported_auth_methods) - KNOWN_AUTH_METHODS
        if unknown_auth:
            raise ValueError(f"Unknown authentication methods: {sorted(unknown_auth)}")

        unknown_inbound_auth = set(self.supported_inbound_auth_methods) - KNOWN_INBOUND_AUTH_METHODS
        if unknown_inbound_auth:
            raise ValueError(
                f"Unknown inbound authentication methods: {sorted(unknown_inbound_auth)}"
            )
        if "pull_api" in self.supported_modes and not self.supported_inbound_auth_methods:
            raise ValueError("pull_api products must declare supported_inbound_auth_methods")

        scenario_ids = [scenario.id for scenario in self.scenarios]
        if len(scenario_ids) != len(set(scenario_ids)):
            duplicates = {sid for sid in scenario_ids if scenario_ids.count(sid) > 1}
            raise ValueError(f"Duplicate scenario ids in manifest: {sorted(duplicates)}")
        for scenario in self.scenarios:
            try:
                Draft202012Validator.check_schema(scenario.config_schema or {"type": "object"})
            except Exception as exc:
                raise ValueError(
                    f"Invalid config_schema for scenario '{scenario.id}': {exc}"
                ) from exc
            unknown_scenario_modes = set(scenario.supported_modes) - set(self.supported_modes)
            if unknown_scenario_modes:
                raise ValueError(
                    f"Scenario '{scenario.id}' has unsupported modes: "
                    f"{sorted(unknown_scenario_modes)}"
                )

        route_ids = [route.id for route in self.mock_routes]
        if len(route_ids) != len(set(route_ids)):
            duplicates = {rid for rid in route_ids if route_ids.count(rid) > 1}
            raise ValueError(f"Duplicate mock route ids in manifest: {sorted(duplicates)}")

        if "pull_api" in self.supported_modes and not self.mock_routes:
            raise ValueError("pull_api products must declare at least one mock_routes entry")

        scenario_id_set = set(scenario_ids)
        for route in self.mock_routes:
            route_scenarios = route.scenario_ids or [route.scenario_id]
            unknown_route_scenarios = set(route_scenarios) - scenario_id_set
            if unknown_route_scenarios:
                raise ValueError(
                    f"Mock route '{route.id}' references unknown scenarios "
                    f"{sorted(unknown_route_scenarios)}"
                )

        action_ids = [action.id for action in self.actions]
        if len(action_ids) != len(set(action_ids)):
            duplicates = {aid for aid in action_ids if action_ids.count(aid) > 1}
            raise ValueError(f"Duplicate product action ids in manifest: {sorted(duplicates)}")
        for action in self.actions:
            unknown_action_modes = set(action.supported_modes) - set(self.supported_modes)
            if unknown_action_modes:
                raise ValueError(
                    f"Action '{action.id}' has unsupported modes: {sorted(unknown_action_modes)}"
                )
            if action.assertion.type == "json_field_equals_context" and (
                not action.assertion.field or not action.assertion.context_key
            ):
                raise ValueError(
                    f"Action '{action.id}' JSON assertion requires field and context_key"
                )

        try:
            Draft202012Validator.check_schema(self.inbound_options_schema or {"type": "object"})
        except Exception as exc:
            raise ValueError(f"Invalid inbound_options_schema: {exc}") from exc
        properties = (self.inbound_options_schema or {}).get("properties", {})
        if isinstance(properties, dict):
            secret_names = sorted(
                name for name in properties if SECRET_OPTION_PATTERN.search(str(name))
            )
            if secret_names:
                raise ValueError(
                    "inbound_options_schema cannot declare secret-like fields; "
                    f"use auth_config instead: {secret_names}"
                )

        return self

    def validate_against_directory(self, product_path: str) -> None:
        """Validate manifest consistency with its on-disk product directory."""
        from pathlib import Path

        root = Path(product_path)
        if self.id != root.name:
            raise ManifestValidationError(
                f"Product id '{self.id}' does not match directory name '{root.name}'",
                product_id=self.id,
                path=str(root),
            )
        for scenario in self.scenarios:
            template_path = root / scenario.template
            if not template_path.is_file():
                raise ManifestValidationError(
                    f"Scenario template not found for {self.id}/{scenario.id}: {scenario.template}",
                    product_id=self.id,
                    path=str(template_path),
                )
