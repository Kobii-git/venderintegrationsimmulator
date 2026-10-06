import json
from pathlib import Path

import pytest
import yaml
from app.domain.enums import FidelityMode
from app.products.exceptions import ManifestValidationError, ScenarioTemplateError
from app.products.manifest import ProductManifest
from app.products.registry import ProductRegistry
from app.products.renderer import SafeTemplateRenderer


@pytest.fixture
def products_root(tmp_path) -> Path:
    return tmp_path / "products"


@pytest.fixture
def renderer() -> SafeTemplateRenderer:
    return SafeTemplateRenderer()


def _write_product(
    root: Path,
    product_id: str,
    manifest: dict,
    *,
    scenarios: dict[str, dict] | None = None,
    plugin: str | None = None,
) -> Path:
    product_dir = root / product_id
    product_dir.mkdir(parents=True)
    (product_dir / "manifest.yaml").write_text(yaml.safe_dump(manifest), encoding="utf-8")
    if scenarios:
        scenario_dir = product_dir / "scenarios"
        scenario_dir.mkdir(parents=True)
        for name, content in scenarios.items():
            (scenario_dir / name).write_text(json.dumps(content), encoding="utf-8")
    if plugin is not None:
        (product_dir / "plugin.py").write_text(plugin, encoding="utf-8")
    return product_dir


def _valid_manifest(product_id: str = "demo-http") -> dict:
    return {
        "id": product_id,
        "display_name": "Demo",
        "version": "1.0.0",
        "supported_modes": ["push_webhook"],
        "supported_transports": ["http_webhook"],
        "supported_auth_methods": ["none"],
        "scenarios": [
            {
                "id": "ping",
                "display_name": "Ping",
                "template": "scenarios/ping.json",
            }
        ],
    }


def _valid_template() -> dict:
    return {
        "content_type": "application/json",
        "method": "POST",
        "body": {"message": "{{ message }}", "event_id": "{{ correlation_id }}"},
    }


def test_registry_discovers_valid_product(products_root) -> None:
    _write_product(
        products_root,
        "demo-http",
        _valid_manifest(),
        scenarios={"ping.json": _valid_template()},
    )
    registry = ProductRegistry(str(products_root))
    registry.load_all()
    assert registry.list_installed_product_ids() == ["demo-http"]
    assert registry.get_manifest("demo-http") is not None


def test_registry_rejects_id_directory_mismatch(products_root) -> None:
    _write_product(
        products_root,
        "demo-http",
        _valid_manifest("wrong-id"),
        scenarios={"ping.json": _valid_template()},
    )
    registry = ProductRegistry(str(products_root))
    with pytest.raises(ManifestValidationError, match="does not match directory"):
        registry.load_all()


def test_registry_rejects_missing_template(products_root) -> None:
    _write_product(products_root, "demo-http", _valid_manifest())
    registry = ProductRegistry(str(products_root))
    with pytest.raises(ManifestValidationError, match="template not found"):
        registry.load_all()


def test_registry_rejects_invalid_manifest_capabilities(products_root) -> None:
    manifest = _valid_manifest()
    manifest["supported_transports"] = ["fortinet_syslog"]
    _write_product(
        products_root,
        "demo-http",
        manifest,
        scenarios={"ping.json": _valid_template()},
    )
    registry = ProductRegistry(str(products_root))
    with pytest.raises(ManifestValidationError, match="Failed to parse manifest"):
        registry.load_all()


def test_manifest_rejects_secret_like_vendor_option_fields() -> None:
    manifest = _valid_manifest()
    manifest["inbound_options_schema"] = {
        "type": "object",
        "properties": {"client_secret": {"type": "string"}},
    }
    with pytest.raises(ValueError, match="cannot declare secret-like fields"):
        ProductManifest.model_validate(manifest)


def test_registry_rejects_duplicate_scenario_ids(products_root) -> None:
    manifest = _valid_manifest()
    manifest["scenarios"] = [
        {"id": "ping", "display_name": "One", "template": "scenarios/ping.json"},
        {"id": "ping", "display_name": "Two", "template": "scenarios/ping.json"},
    ]
    _write_product(
        products_root,
        "demo-http",
        manifest,
        scenarios={"ping.json": _valid_template()},
    )
    registry = ProductRegistry(str(products_root))
    with pytest.raises(ManifestValidationError, match="Failed to parse manifest"):
        registry.load_all()


def test_registry_rejects_invalid_scenario_template(products_root) -> None:
    _write_product(
        products_root,
        "demo-http",
        _valid_manifest(),
        scenarios={"ping.json": {"unknown_field": "bad"}},
    )
    registry = ProductRegistry(str(products_root))
    with pytest.raises(ScenarioTemplateError):
        registry.load_all()


def test_renderer_replaces_variables(renderer, products_directory) -> None:
    registry = ProductRegistry(str(products_directory))
    registry.load_all()
    scenario = registry.get_scenario("demo-http", "ping")
    assert scenario is not None
    payload = registry.renderer.render_scenario(
        scenario,
        fidelity_mode=FidelityMode.VENDOR_ACCURATE,
        correlation_id="corr-123",
        overrides={"message": "test-message"},
        plugin=registry.get_plugin("demo-http"),
    )
    assert payload["message"] == "test-message"
    assert payload["event_id"] == "corr-123"
    assert "random_value" in payload


def test_renderer_adds_diagnostics_in_troubleshooting_mode(renderer, products_directory) -> None:
    registry = ProductRegistry(str(products_directory))
    registry.load_all()
    scenario = registry.get_scenario("demo-http", "ping")
    assert scenario is not None
    payload = registry.renderer.render_scenario(
        scenario,
        fidelity_mode=FidelityMode.TROUBLESHOOTING,
        correlation_id="corr-456",
        overrides={"message": "diag"},
        plugin=registry.get_plugin("demo-http"),
    )
    assert "_simulator" in payload
    assert payload["_simulator"]["simulator_event_id"] == "corr-456"
    assert payload["plugin_post_render"] is True


def test_plugin_loader_requires_protocol(products_root) -> None:
    plugin_code = "class BrokenPlugin:\n    product_id = 'demo-http'\n"
    _write_product(
        products_root,
        "demo-http",
        {**_valid_manifest(), "plugin": True},
        scenarios={"ping.json": _valid_template()},
        plugin=plugin_code,
    )
    registry = ProductRegistry(str(products_root))
    with pytest.raises(ManifestValidationError, match="must expose get_plugin"):
        registry.load_all()


def test_manifest_accepts_alias_field_names() -> None:
    data = {
        "id": "demo-http",
        "name": "Alias Demo",
        "version": "1",
        "simulation_modes": ["push_webhook"],
        "transports": ["http_webhook"],
        "authentication": ["none"],
        "scenarios": [],
    }
    manifest = ProductManifest.model_validate(data)
    assert manifest.display_name == "Alias Demo"
    assert manifest.supported_modes == ["push_webhook"]
