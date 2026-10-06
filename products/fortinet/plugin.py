"""Fortinet FortiGate product plugin — template context enrichment only."""

from __future__ import annotations

import random
import uuid
from datetime import UTC, datetime
from typing import Any

from app.domain.enums import FidelityMode
from app.products.plugin import ProductPlugin


class FortinetPlugin:
    """Adds FortiGate-style timestamps, device identifiers, and session metadata."""

    product_id = "fortinet"

    def enrich_context(
        self,
        scenario_id: str,
        overrides: dict[str, Any],
        *,
        rng: random.Random,
    ) -> dict[str, Any]:
        now = datetime.now(UTC)
        enriched: dict[str, Any] = {
            "fortigate_date": now.strftime("%Y-%m-%d"),
            "fortigate_time": now.strftime("%H:%M:%S"),
            "eventtime": int(now.timestamp()),
            "sessionid": overrides.get("sessionid", rng.randint(10_000, 9_999_999)),
            "poluuid": overrides.get("poluuid", str(uuid.uuid4())),
        }
        return enriched

    def post_render(
        self,
        payload: dict[str, Any],
        fidelity_mode: FidelityMode,
        *,
        scenario_id: str,
        correlation_id: str,
    ) -> dict[str, Any]:
        del scenario_id
        if fidelity_mode == FidelityMode.TROUBLESHOOTING and "_syslog_message" in payload:
            payload["_syslog_message"] = (
                f"{payload['_syslog_message']} simulator_event_id={correlation_id}"
            )
        return payload


def get_plugin() -> ProductPlugin:
    return FortinetPlugin()
