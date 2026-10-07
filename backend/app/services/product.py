from typing import Any

from app.domain.enums import FidelityMode
from app.products.registry import ProductRegistry, ProductSummary
from app.products.scenario import ScenarioDefinition
from app.schemas.product import (
    MockRouteSummaryResponse,
    ProductActionSummaryResponse,
    ProductDetailResponse,
    ProductSummaryResponse,
    ScenarioDetailResponse,
    ScenarioSummaryResponse,
    ScenarioVariableResponse,
)


class ProductCatalogService:
    """Read-only product catalog operations for API layer."""

    def __init__(self, registry: ProductRegistry) -> None:
        self._registry = registry

    def list_products(self) -> list[ProductSummaryResponse]:
        return [self._to_summary(product) for product in self._registry.list_products()]

    def get_product(self, product_id: str) -> ProductDetailResponse | None:
        manifest = self._registry.get_manifest(product_id)
        if manifest is None:
            return None
        summary = self._registry.get_product(product_id)
        assert summary is not None
        return ProductDetailResponse(
            **self._to_summary(summary).model_dump(),
            diagnostic_merge=manifest.diagnostic_merge,
            inbound_options_schema=manifest.inbound_options_schema,
            connection_profiles=manifest.connection_profiles,
            scenarios=[self._to_scenario_summary(scenario) for scenario in manifest.scenarios],
            mock_routes=[
                MockRouteSummaryResponse(
                    id=route.id,
                    path=route.path,
                    methods=route.methods,
                    scenario_id=route.scenario_id,
                    description=route.description,
                    response_type=route.response_type,
                    supports_pagination=route.supports_pagination,
                    supports_time_filter=route.supports_time_filter,
                    handler=route.handler or "dataset_list",
                    required_oauth_scopes=route.required_oauth_scopes,
                    response_profile=route.response_profile.model_dump(mode="json"),
                )
                for route in manifest.mock_routes
            ],
            actions=[
                ProductActionSummaryResponse(
                    id=action.id,
                    display_name=action.display_name,
                    description=action.description,
                    supported_modes=action.supported_modes,
                )
                for action in manifest.actions
            ],
        )

    def list_scenarios(self, product_id: str) -> list[ScenarioSummaryResponse] | None:
        manifest = self._registry.get_manifest(product_id)
        if manifest is None:
            return None
        return [self._to_scenario_summary(scenario) for scenario in manifest.scenarios]

    def get_scenario(self, product_id: str, scenario_id: str) -> ScenarioDetailResponse | None:
        scenario = self._registry.get_scenario(product_id, scenario_id)
        if scenario is None:
            return None
        return self._to_scenario_detail(scenario)

    def render_scenario_preview(
        self,
        product_id: str,
        scenario_id: str,
        *,
        fidelity_mode: FidelityMode = FidelityMode.TROUBLESHOOTING,
        correlation_id: str = "preview-correlation-id",
        overrides: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        scenario = self._registry.get_scenario(product_id, scenario_id)
        manifest = self._registry.get_manifest(product_id)
        if scenario is None or manifest is None:
            return None
        plugin = self._registry.get_plugin(product_id)
        payload = self._registry.renderer.render_scenario(
            scenario,
            fidelity_mode=fidelity_mode,
            correlation_id=correlation_id,
            overrides=overrides,
            plugin=plugin,
            diagnostic_merge=manifest.diagnostic_merge,
        )
        return payload if isinstance(payload, dict) else {"_syslog_message": payload}

    def _to_summary(self, product: ProductSummary) -> ProductSummaryResponse:
        return ProductSummaryResponse(
            id=product.id,
            display_name=product.display_name,
            version=product.version,
            description=product.description,
            supported_modes=product.supported_modes,
            supported_transports=product.supported_transports,
            supported_auth_methods=product.supported_auth_methods,
            supported_inbound_auth_methods=product.supported_inbound_auth_methods,
            scenario_count=product.scenario_count,
            has_plugin=product.has_plugin,
            formats=product.formats,
            field_references=product.field_references,
            schema_version=product.schema_version,
            compatibility=product.compatibility,
        )

    def _to_scenario_summary(self, scenario: Any) -> ScenarioSummaryResponse:
        return ScenarioSummaryResponse(
            id=scenario.id,
            display_name=scenario.display_name,
            description=scenario.description,
            default_transport=scenario.default_transport,
            config_schema=scenario.config_schema,
            supported_modes=scenario.supported_modes,
            delivery_policy=scenario.delivery_policy.model_dump(mode="json"),
        )

    def _to_scenario_detail(self, scenario: ScenarioDefinition) -> ScenarioDetailResponse:
        variables = self._extract_variables(scenario)
        return ScenarioDetailResponse(
            product_id=scenario.product_id,
            id=scenario.id,
            display_name=scenario.display_name,
            description=scenario.description,
            default_transport=scenario.default_transport,
            config_schema=scenario.config_schema,
            supported_modes=scenario.supported_modes,
            delivery_policy=scenario.delivery_policy.model_dump(mode="json"),
            template_path=scenario.template_path,
            variables=variables,
            template_metadata={
                "content_type": scenario.template.content_type,
                "method": scenario.template.method,
                "diagnostic_merge": scenario.template.diagnostic_merge,
            },
        )

    def _extract_variables(self, scenario: ScenarioDefinition) -> list[ScenarioVariableResponse]:
        properties = scenario.config_schema.get("properties", {})
        required = set(scenario.config_schema.get("required", []))
        variables: list[ScenarioVariableResponse] = []
        for name, schema in properties.items():
            if not isinstance(schema, dict):
                continue
            variables.append(
                ScenarioVariableResponse(
                    name=name,
                    type=schema.get("type"),
                    description=schema.get("description"),
                    default=schema.get("default"),
                    required=name in required,
                    hidden=bool(schema.get("hidden", False)),
                    deprecated=bool(schema.get("deprecated", False)),
                )
            )
        return variables
