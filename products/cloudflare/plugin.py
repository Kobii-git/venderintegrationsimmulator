"""Cloudflare field representations for representative dataset records."""

import re
from typing import Any

from app.domain.enums import FidelityMode
from app.products.plugin import NoOpProductPlugin


class CloudflarePlugin(NoOpProductPlugin):
    def __init__(self) -> None:
        super().__init__("cloudflare")

    def post_render(
        self,
        payload: dict[str, Any],
        fidelity_mode: FidelityMode,
        *,
        scenario_id: str,
        correlation_id: str,
    ) -> dict[str, Any]:
        record = payload.get("record", {})
        if "RayID" in record:
            record["RayID"] = re.sub(r"[^a-f0-9]", "", correlation_id.lower())[
                :16
            ].ljust(16, "0")
        return payload


def get_plugin() -> CloudflarePlugin:
    return CloudflarePlugin()
