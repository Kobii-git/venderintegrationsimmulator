"""Optional plugin for the demo-http internal product."""

import random
from typing import Any

from app.domain.enums import FidelityMode
from app.products.plugin import ProductPlugin


class DemoHttpPlugin:
    product_id = "demo-http"

    def enrich_context(
        self,
        scenario_id: str,
        overrides: dict[str, Any],
        *,
        rng: random.Random,
    ) -> dict[str, Any]:
        del rng
        if scenario_id != "ping":
            return {}
        return {
            "message": overrides.get("message", "hello-from-plugin"),
            "plugin_marker": "demo-http-plugin-active",
        }

    def post_render(
        self,
        payload: dict[str, Any],
        fidelity_mode: FidelityMode,
        *,
        scenario_id: str,
        correlation_id: str,
    ) -> dict[str, Any]:
        if fidelity_mode == FidelityMode.TROUBLESHOOTING:
            payload["plugin_post_render"] = True
        return payload


def get_plugin() -> ProductPlugin:
    return DemoHttpPlugin()
