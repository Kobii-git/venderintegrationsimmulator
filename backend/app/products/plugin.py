import random
from typing import Any, Protocol, runtime_checkable

from app.domain.enums import FidelityMode


@runtime_checkable
class ProductPlugin(Protocol):
    """Optional product-specific behaviour beyond manifest configuration."""

    product_id: str

    def enrich_context(
        self,
        scenario_id: str,
        overrides: dict[str, Any],
        *,
        rng: random.Random,
    ) -> dict[str, Any]:
        """Add or transform template variables before rendering."""
        ...

    def post_render(
        self,
        payload: dict[str, Any],
        fidelity_mode: FidelityMode,
        *,
        scenario_id: str,
        correlation_id: str,
    ) -> dict[str, Any]:
        """Rare final payload adjustment after template rendering."""
        ...


class NoOpProductPlugin:
    """Default plugin used when no plugin.py is present."""

    def __init__(self, product_id: str) -> None:
        self.product_id = product_id

    def enrich_context(
        self,
        scenario_id: str,
        overrides: dict[str, Any],
        *,
        rng: random.Random,
    ) -> dict[str, Any]:
        del rng
        return {}

    def post_render(
        self,
        payload: dict[str, Any],
        fidelity_mode: FidelityMode,
        *,
        scenario_id: str,
        correlation_id: str,
    ) -> dict[str, Any]:
        return payload


def load_plugin_from_module(module: object, product_id: str) -> ProductPlugin:
    """Instantiate a plugin from a loaded plugin.py module."""
    instance: object | None = None
    if hasattr(module, "get_plugin") and callable(module.get_plugin):
        instance = module.get_plugin()
    elif hasattr(module, "ProductPlugin"):
        instance = module.ProductPlugin()

    if instance is None:
        raise TypeError(
            f"Plugin module for '{product_id}' must expose get_plugin() or ProductPlugin class"
        )
    if not isinstance(instance, ProductPlugin):
        raise TypeError(f"Plugin for '{product_id}' does not implement ProductPlugin protocol")
    if instance.product_id != product_id:
        raise TypeError(
            f"Plugin product_id '{instance.product_id}' does not match manifest '{product_id}'"
        )
    return instance
