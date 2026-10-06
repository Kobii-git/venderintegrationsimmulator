"""UpGuard product plugin — context enrichment and numeric type coercion."""

from __future__ import annotations

import random
from typing import Any

from app.domain.enums import FidelityMode
from app.products.plugin import ProductPlugin

_SCORE_CONTEXT_KEYS = frozenset({"LatestScore", "PrevScore", "Threshold"})
_INTEGER_CONTEXT_KEYS = frozenset({"AffectedEmails"})
_SCORE_SCENARIOS = frozenset({"score-threshold", "vendor-score-change"})


class UpGuardPlugin:
    """Enriches UpGuard webhook payloads with realistic dynamic values."""

    product_id = "upguard"

    def enrich_context(
        self,
        scenario_id: str,
        overrides: dict[str, Any],
        *,
        rng: random.Random,
    ) -> dict[str, Any]:
        enriched = dict(overrides)
        enriched.setdefault("notification_id", rng.randint(10_000, 99_999))

        if scenario_id in _SCORE_SCENARIOS:
            threshold = int(enriched.get("threshold", 600))
            latest = int(enriched.get("latest_score", threshold - rng.randint(1, 25)))
            prev = int(enriched.get("prev_score", latest + rng.randint(5, 50)))
            enriched["latest_score"] = max(0, latest)
            enriched["prev_score"] = max(0, prev)
            enriched["threshold"] = threshold

        return enriched

    def post_render(
        self,
        payload: dict[str, Any],
        fidelity_mode: FidelityMode,
        *,
        scenario_id: str,
        correlation_id: str,
    ) -> dict[str, Any]:
        del fidelity_mode, scenario_id, correlation_id
        notification = payload.get("notification")
        if not isinstance(notification, dict):
            return payload

        if "id" in notification:
            notification["id"] = _coerce_int(notification["id"])

        context = notification.get("context")
        if isinstance(context, dict):
            for key, value in context.items():
                if key in _SCORE_CONTEXT_KEYS or key in _INTEGER_CONTEXT_KEYS:
                    context[key] = _coerce_int(value)

        return payload


def _coerce_int(value: Any) -> int | Any:
    try:
        return int(value)
    except (TypeError, ValueError):
        return value


def get_plugin() -> ProductPlugin:
    return UpGuardPlugin()
