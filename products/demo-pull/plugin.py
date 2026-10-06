"""Optional plugin for the demo-pull internal product."""

import random
from typing import Any

from app.domain.enums import FidelityMode
from app.products.plugin import ProductPlugin


class DemoPullPlugin:
    product_id = "demo-pull"

    def enrich_context(
        self,
        scenario_id: str,
        overrides: dict[str, Any],
        *,
        rng: random.Random,
    ) -> dict[str, Any]:
        del rng
        if scenario_id == "security-event":
            return {
                "severity": overrides.get("severity", "medium"),
                "plugin_marker": "demo-pull-plugin-active",
            }
        if scenario_id == "alert":
            return {"alert_type": overrides.get("alert_type", "suspicious_activity")}
        return {}

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
    return DemoPullPlugin()
