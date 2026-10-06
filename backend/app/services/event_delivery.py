import json
import uuid
from typing import Any

from jsonschema import Draft202012Validator

from app.core.exceptions import ValidationAppError
from app.core.redaction import collect_http_secret_values, redact_secret_values
from app.domain.enums import FidelityMode
from app.formats.source import render_source
from app.products.registry import ProductRegistry
from app.products.scenario import ScenarioDefinition
from app.schemas.event import (
    ScenarioPreviewRequest,
    ScenarioPreviewResponse,
    ScenarioSendEventResponse,
    ScenarioSendRequest,
    ScenarioSendResponse,
)
from app.schemas.transport import DeliveryResultResponse
from app.services.destination_config import destination_input_for_delivery
from app.services.transport_delivery import TransportDeliveryService


class EventDeliveryService:
    """Generate scenario payloads and deliver one-shot events."""

    def __init__(
        self,
        registry: ProductRegistry,
        transport_service: TransportDeliveryService,
    ) -> None:
        self._registry = registry
        self._transport_service = transport_service

    def preview(
        self,
        product_id: str,
        scenario_id: str,
        request: ScenarioPreviewRequest,
    ) -> ScenarioPreviewResponse | None:
        scenario = self._registry.get_scenario(product_id, scenario_id)
        manifest = self._registry.get_manifest(product_id)
        if scenario is None or manifest is None:
            return None

        correlation_id = request.correlation_id or str(uuid.uuid4())
        self._validate_scenario_overrides(scenario, request.scenario_overrides)
        payload = self._generate_payload(
            scenario,
            fidelity_mode=request.fidelity_mode,
            correlation_id=correlation_id,
            overrides=request.scenario_overrides,
            diagnostic_merge=manifest.diagnostic_merge,
        )

        response_payload = payload if isinstance(payload, dict) else {"_syslog_message": payload}
        return ScenarioPreviewResponse(
            product_id=product_id,
            scenario_id=scenario_id,
            scenario_display_name=scenario.display_name,
            scenario_description=scenario.description,
            correlation_id=correlation_id,
            fidelity_mode=request.fidelity_mode,
            content_type=scenario.template.content_type,
            method=scenario.template.method,
            payload=response_payload,
        )

    async def send(
        self,
        product_id: str,
        scenario_id: str,
        request: ScenarioSendRequest,
    ) -> ScenarioSendResponse | None:
        scenario = self._registry.get_scenario(product_id, scenario_id)
        manifest = self._registry.get_manifest(product_id)
        if scenario is None or manifest is None:
            return None

        correlation_id = request.correlation_id or str(uuid.uuid4())
        self._validate_destination(request, manifest)
        self._validate_auth(product_id, request.auth_config.model_dump(exclude_none=True))
        self._validate_scenario_overrides(scenario, request.scenario_overrides)

        payload_source = "generated"
        payload: dict[str, Any] | str
        if request.payload_override is not None:
            self._validate_payload_override(request.payload_override)
            payload = request.payload_override
            payload_source = "override"
        else:
            payload = self._generate_payload(
                scenario,
                fidelity_mode=request.fidelity_mode,
                correlation_id=correlation_id,
                overrides=request.scenario_overrides,
                diagnostic_merge=manifest.diagnostic_merge,
            )

        destination = destination_input_for_delivery(request.destination)
        auth_config = request.auth_config.model_dump(exclude_none=True)
        wire_payload, content_type = render_source(
            payload if isinstance(payload, dict) else {"_syslog_message": payload}, "default"
        )
        delivery = await self._transport_service.deliver(
            destination,
            wire_payload,
            content_type,
            auth_config,
        )

        secrets = collect_http_secret_values(
            auth_config=auth_config,
            headers=destination.get("headers", {}),
            query_params=destination.get("query_params", {}),
            sensitive_header_names=set(destination.get("_sensitive_header_names", [])),
            sensitive_query_names=set(destination.get("_sensitive_query_names", [])),
        )
        response_payload = redact_secret_values(
            payload if isinstance(payload, dict) else {"_syslog_message": payload},
            secrets,
        )
        if not isinstance(response_payload, dict):
            response_payload = {}

        return ScenarioSendResponse(
            event=ScenarioSendEventResponse(
                correlation_id=correlation_id,
                product_id=product_id,
                scenario_id=scenario_id,
                fidelity_mode=request.fidelity_mode,
                content_type=scenario.template.content_type,
                method=scenario.template.method,
                payload=response_payload,
                payload_source=payload_source,
            ),
            delivery=DeliveryResultResponse.from_delivery_result(delivery),
        )

    def _generate_payload(
        self,
        scenario: ScenarioDefinition,
        *,
        fidelity_mode: FidelityMode,
        correlation_id: str,
        overrides: dict[str, Any],
        diagnostic_merge: str | None,
    ) -> dict[str, Any] | str:
        plugin = self._registry.get_plugin(scenario.product_id)
        payload = self._registry.renderer.render_scenario(
            scenario,
            fidelity_mode=fidelity_mode,
            correlation_id=correlation_id,
            overrides=overrides,
            plugin=plugin,
            diagnostic_merge=diagnostic_merge,
        )
        workflow = self._registry.get_workflow_plugin(scenario.product_id)
        if workflow is not None and isinstance(payload, dict):
            payload = workflow.prepare_outbound_payload(
                scenario.id,
                payload,
                correlation_id=correlation_id,
            )
        return payload

    def _validate_destination(self, request: ScenarioSendRequest, manifest: Any) -> None:
        destination = request.destination
        transport_id = destination.transport_id or "http_webhook"
        if transport_id not in manifest.supported_transports:
            raise ValidationAppError(
                f"Transport '{transport_id}' is not supported by product '{manifest.id}'",
                details={"supported_transports": manifest.supported_transports},
            )
        if transport_id == "syslog":
            if not destination.host or not destination.host.strip():
                raise ValidationAppError("destination.host is required for syslog transport")
            return
        if transport_id != "azure_logs_ingestion" and (
            not destination.url or not destination.url.strip()
        ):
            raise ValidationAppError("destination.url is required for one-shot send")

    def _validate_auth(self, product_id: str, auth_config: dict[str, Any]) -> None:
        manifest = self._registry.get_manifest(product_id)
        if manifest is None:
            return

        auth_method_id = auth_config.get("auth_method_id", "none")
        if auth_method_id not in manifest.supported_auth_methods:
            raise ValidationAppError(
                f"Auth method '{auth_method_id}' is not supported by product '{product_id}'",
                details={"supported_auth_methods": manifest.supported_auth_methods},
            )

        if auth_method_id == "basic" and (
            not auth_config.get("username") or not auth_config.get("password")
        ):
            raise ValidationAppError("Basic auth requires username and password")

    def _validate_scenario_overrides(
        self, scenario: ScenarioDefinition, overrides: dict[str, Any]
    ) -> None:
        validator = Draft202012Validator(scenario.config_schema or {"type": "object"})
        errors = [
            {
                "path": ".".join(str(part) for part in error.absolute_path),
                "message": error.message,
            }
            for error in validator.iter_errors(overrides)
        ]
        if errors:
            raise ValidationAppError(
                "Scenario overrides failed schema validation",
                details={"scenario_id": scenario.id, "errors": errors},
            )

    def _validate_payload_override(self, payload: dict[str, Any]) -> None:
        try:
            json.dumps(payload)
        except (TypeError, ValueError) as exc:
            raise ValidationAppError(f"payload_override must be valid JSON: {exc}") from exc
