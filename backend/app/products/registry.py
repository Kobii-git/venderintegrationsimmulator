import importlib.util
import json
import logging
from pathlib import Path

import yaml
from app.products.exceptions import (
    ManifestValidationError,
    ProductModuleError,
    ScenarioTemplateError,
)
from app.products.manifest import MockRouteRef, ProductManifest, ScenarioRef
from app.products.plugin import NoOpProductPlugin, ProductPlugin, load_plugin_from_module
from app.products.renderer import SafeTemplateRenderer
from app.products.scenario import ScenarioDefinition, ScenarioTemplate
from app.products.workflow import ProductWorkflowPlugin

logger = logging.getLogger(__name__)


class ProductSummary:
    """Lightweight product catalog entry."""

    def __init__(self, manifest: ProductManifest, *, has_plugin: bool) -> None:
        self.id = manifest.id
        self.display_name = manifest.display_name
        self.version = manifest.version
        self.formats = manifest.formats
        self.field_references = manifest.field_references
        self.schema_version = manifest.schema_version
        self.compatibility = manifest.compatibility
        self.description = manifest.description
        self.supported_modes = manifest.supported_modes
        self.supported_transports = manifest.supported_transports
        self.supported_auth_methods = manifest.supported_auth_methods
        self.supported_inbound_auth_methods = manifest.supported_inbound_auth_methods
        self.scenario_count = len(manifest.scenarios)
        self.has_plugin = has_plugin


class ProductRegistry:
    """Discovers, validates, and indexes product modules from the filesystem."""

    def __init__(self, products_dir: str) -> None:
        self._products_dir = Path(products_dir)
        self._manifests: dict[str, ProductManifest] = {}
        self._scenarios: dict[str, dict[str, ScenarioDefinition]] = {}
        self._plugins: dict[str, ProductPlugin] = {}
        self._renderer = SafeTemplateRenderer()

    @property
    def products_dir(self) -> Path:
        return self._products_dir

    @property
    def renderer(self) -> SafeTemplateRenderer:
        return self._renderer

    def load_all(self) -> None:
        """Scan products directory and load all valid product modules."""
        self._manifests.clear()
        self._scenarios.clear()
        self._plugins.clear()

        if not self._products_dir.is_dir():
            logger.warning("Products directory does not exist: %s", self._products_dir)
            return

        seen_ids: set[str] = set()
        for product_path in sorted(self._products_dir.iterdir()):
            if not product_path.is_dir():
                continue
            manifest_path = product_path / "manifest.yaml"
            if not manifest_path.is_file():
                logger.debug("Skipping %s: no manifest.yaml", product_path.name)
                continue

            manifest = self._load_manifest(manifest_path)
            manifest.validate_against_directory(str(product_path))
            if manifest.id in seen_ids:
                raise ManifestValidationError(
                    f"Duplicate product id: {manifest.id}",
                    product_id=manifest.id,
                    path=str(product_path),
                )
            seen_ids.add(manifest.id)

            scenarios = self._load_scenarios(manifest, product_path)
            plugin = self._load_plugin(manifest, product_path)

            self._manifests[manifest.id] = manifest
            self._scenarios[manifest.id] = scenarios
            self._plugins[manifest.id] = plugin
            logger.info(
                "Loaded product module: %s (%d scenarios, plugin=%s)",
                manifest.id,
                len(scenarios),
                plugin.__class__.__name__ != "NoOpProductPlugin",
            )

    def list_products(self) -> list[ProductSummary]:
        return [
            ProductSummary(
                manifest,
                has_plugin=self._plugins[manifest.id].__class__.__name__ != "NoOpProductPlugin",
            )
            for manifest in self._manifests.values()
        ]

    def get_manifest(self, product_id: str) -> ProductManifest | None:
        return self._manifests.get(product_id)

    def get_product(self, product_id: str) -> ProductSummary | None:
        manifest = self.get_manifest(product_id)
        if manifest is None:
            return None
        return ProductSummary(
            manifest,
            has_plugin=self._plugins[product_id].__class__.__name__ != "NoOpProductPlugin",
        )

    def get_scenarios(self, product_id: str) -> list[ScenarioRef]:
        manifest = self._manifests.get(product_id)
        if manifest is None:
            return []
        return manifest.scenarios

    def get_scenario(self, product_id: str, scenario_id: str) -> ScenarioDefinition | None:
        return self._scenarios.get(product_id, {}).get(scenario_id)

    def get_mock_routes(self, product_id: str) -> list[MockRouteRef]:
        manifest = self._manifests.get(product_id)
        if manifest is None:
            return []
        return manifest.mock_routes

    def get_mock_route(self, product_id: str, route_path: str) -> MockRouteRef | None:
        normalized = route_path.strip("/")
        for route in self.get_mock_routes(product_id):
            if route.path == normalized:
                return route
        return None

    def get_plugin(self, product_id: str) -> ProductPlugin:
        return self._plugins.get(product_id, NoOpProductPlugin(product_id))

    def get_workflow_plugin(self, product_id: str) -> ProductWorkflowPlugin | None:
        plugin = self._plugins.get(product_id)
        return plugin if isinstance(plugin, ProductWorkflowPlugin) else None

    def list_installed_product_ids(self) -> list[str]:
        return sorted(self._manifests.keys())

    def _load_manifest(self, path: Path) -> ProductManifest:
        try:
            with path.open(encoding="utf-8") as handle:
                data = yaml.safe_load(handle)
            return ProductManifest.model_validate(data)
        except ProductModuleError:
            raise
        except Exception as exc:
            raise ManifestValidationError(
                f"Failed to parse manifest: {exc}",
                path=str(path),
            ) from exc

    def _load_scenarios(
        self, manifest: ProductManifest, product_path: Path
    ) -> dict[str, ScenarioDefinition]:
        scenarios: dict[str, ScenarioDefinition] = {}
        for scenario_ref in manifest.scenarios:
            template_path = product_path / scenario_ref.template
            template = self._load_scenario_template(template_path, manifest.id, scenario_ref.id)
            scenarios[scenario_ref.id] = ScenarioDefinition(
                id=scenario_ref.id,
                product_id=manifest.id,
                display_name=scenario_ref.display_name,
                description=scenario_ref.description,
                default_transport=scenario_ref.default_transport,
                config_schema=scenario_ref.config_schema,
                supported_modes=scenario_ref.supported_modes,
                delivery_policy=scenario_ref.delivery_policy,
                template_path=scenario_ref.template,
                template=template,
            )
        return scenarios

    def _load_scenario_template(
        self, path: Path, product_id: str, scenario_id: str
    ) -> ScenarioTemplate:
        try:
            with path.open(encoding="utf-8") as handle:
                data = json.load(handle)
            return ScenarioTemplate.model_validate(data)
        except Exception as exc:
            raise ScenarioTemplateError(
                f"Invalid scenario template for {product_id}/{scenario_id}: {exc}",
                product_id=product_id,
                path=str(path),
            ) from exc

    def _load_plugin(self, manifest: ProductManifest, product_path: Path) -> ProductPlugin:
        plugin_path = product_path / "plugin.py"
        if not manifest.plugin and not plugin_path.is_file():
            return NoOpProductPlugin(manifest.id)

        if not plugin_path.is_file():
            raise ManifestValidationError(
                f"Manifest declares plugin=true but plugin.py is missing for {manifest.id}",
                product_id=manifest.id,
                path=str(plugin_path),
            )

        spec = importlib.util.spec_from_file_location(
            f"products.{manifest.id}.plugin",
            plugin_path,
        )
        if spec is None or spec.loader is None:
            raise ManifestValidationError(
                f"Cannot load plugin for {manifest.id}",
                product_id=manifest.id,
                path=str(plugin_path),
            )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        try:
            return load_plugin_from_module(module, manifest.id)
        except TypeError as exc:
            raise ManifestValidationError(
                str(exc),
                product_id=manifest.id,
                path=str(plugin_path),
            ) from exc
