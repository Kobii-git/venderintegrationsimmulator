import random
import uuid
from datetime import UTC, datetime
from typing import Any

from app.domain.enums import FidelityMode
from app.products.plugin import ProductPlugin
from app.products.scenario import ScenarioDefinition, ScenarioTemplate
from jinja2 import StrictUndefined
from jinja2.sandbox import SandboxedEnvironment


class SafeTemplateRenderer:
    """Render scenario templates using a restricted Jinja2 sandbox.

    Only simple expressions and an explicit set of helper functions are available.
    No arbitrary Python execution, imports, or attribute traversal beyond templates.
    """

    def __init__(self) -> None:
        self._env = SandboxedEnvironment(
            autoescape=False,
            undefined=StrictUndefined,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def build_context(
        self,
        *,
        product_id: str,
        scenario_id: str,
        correlation_id: str,
        overrides: dict[str, Any] | None = None,
        plugin: ProductPlugin | None = None,
        random_seed: int | None = None,
        event_sequence: int = 0,
        render_time: datetime | None = None,
    ) -> dict[str, Any]:
        rng = (
            random.Random(random_seed + event_sequence)
            if random_seed is not None
            else random.Random()
        )
        effective_time = render_time or datetime.now(UTC)
        context: dict[str, Any] = {
            "product_id": product_id,
            "scenario_id": scenario_id,
            "correlation_id": correlation_id,
            "event_sequence": event_sequence,
            "generated_at_iso": effective_time.isoformat(),
            "uuid4": lambda: str(uuid.uuid4()),
            "now_iso": lambda: effective_time.isoformat(),
            "random_int": rng.randint,
        }
        if overrides:
            context.update(overrides)
        if plugin is not None:
            context.update(plugin.enrich_context(scenario_id, overrides or {}, rng=rng))
        return context

    def render_structure(self, value: Any, context: dict[str, Any]) -> Any:
        if isinstance(value, str):
            return self._render_string(value, context)
        if isinstance(value, dict):
            return {key: self.render_structure(item, context) for key, item in value.items()}
        if isinstance(value, list):
            return [self.render_structure(item, context) for item in value]
        return value

    def render_scenario(
        self,
        scenario: ScenarioDefinition,
        *,
        fidelity_mode: FidelityMode,
        correlation_id: str,
        overrides: dict[str, Any] | None = None,
        plugin: ProductPlugin | None = None,
        diagnostic_merge: str | None = None,
        random_seed: int | None = None,
        event_sequence: int = 0,
        render_time: datetime | None = None,
    ) -> dict[str, Any] | str:
        merged_overrides = {**scenario.default_variable_values(), **(overrides or {})}
        context = self.build_context(
            product_id=scenario.product_id,
            scenario_id=scenario.id,
            correlation_id=correlation_id,
            overrides=merged_overrides,
            plugin=plugin,
            random_seed=random_seed,
            event_sequence=event_sequence,
            render_time=render_time,
        )

        body = self.render_structure(scenario.template.body, context)
        if isinstance(body, str):
            payload: dict[str, Any] | str = body
        else:
            payload = dict(body)

        if (
            isinstance(payload, dict)
            and fidelity_mode == FidelityMode.TROUBLESHOOTING
            and scenario.template.diagnostic_fields
        ):
            diagnostics = self.render_structure(scenario.template.diagnostic_fields, context)
            merge_mode = scenario.template.diagnostic_merge or diagnostic_merge or "nested"
            if merge_mode == "top_level":
                payload.update(diagnostics)
            else:
                payload["_simulator"] = diagnostics

        if plugin is not None:
            if isinstance(payload, str):
                payload = {"_syslog_message": payload}
            payload = plugin.post_render(
                payload,
                fidelity_mode,
                scenario_id=scenario.id,
                correlation_id=correlation_id,
            )

        return payload

    def render_template_metadata(
        self, template: ScenarioTemplate, context: dict[str, Any]
    ) -> dict[str, Any]:
        return {
            "content_type": template.content_type,
            "method": template.method,
            "body": self.render_structure(template.body, context),
        }

    def _render_string(self, template_str: str, context: dict[str, Any]) -> str:
        if "{{" not in template_str and "{%" not in template_str:
            return template_str
        template = self._env.from_string(template_str)
        return template.render(**context)
