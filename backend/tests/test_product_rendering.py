from app.domain.enums import FidelityMode
from app.products.registry import ProductRegistry
from app.services.product import ProductCatalogService


def test_catalog_service_render_preview(products_directory) -> None:
    registry = ProductRegistry(str(products_directory))
    registry.load_all()
    service = ProductCatalogService(registry)

    payload = service.render_scenario_preview(
        "demo-http",
        "ping",
        fidelity_mode=FidelityMode.VENDOR_ACCURATE,
        correlation_id="preview-1",
        overrides={"message": "from-test"},
    )
    assert payload is not None
    assert payload["message"] == "from-test"
    assert payload["event_id"] == "preview-1"
