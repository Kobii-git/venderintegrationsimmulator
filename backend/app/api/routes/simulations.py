from datetime import datetime

from app.api.deps import (
    get_inbound_mock_service,
    get_simulation_export_service,
    get_simulation_orchestrator,
    get_simulation_service,
)
from app.core.exceptions import NotFoundError, ValidationAppError
from app.schemas.event_instance import (
    CurlResponse,
    EventInstanceResponse,
    EventInstanceSummaryResponse,
    EventListFilters,
    ReplayEventRequest,
    ReplayEventResponse,
    SimulationSendRequestBody,
    WorkflowActionResponse,
)
from app.schemas.inbound import (
    InboundEndpointInfoResponse,
    InboundRequestDetailResponse,
    InboundRequestSummaryResponse,
    IssuedOAuthTokenResponse,
)
from app.schemas.simulation import (
    SimulationBurstRequest,
    SimulationBurstResponse,
    SimulationCreate,
    SimulationResponse,
    SimulationSendResponse,
    SimulationUpdate,
)
from app.schemas.simulation_export import (
    SimulationExportDocument,
    SimulationImportRequest,
    SimulationImportResponse,
)
from app.services.inbound_mock import InboundMockService
from app.services.simulation import SimulationService
from app.services.simulation_export import SimulationExportService
from app.services.simulation_orchestrator import SimulationOrchestrator
from fastapi import APIRouter, Depends, Query, Request, status

router = APIRouter(prefix="/simulations", tags=["simulations"])


@router.get("", response_model=list[SimulationResponse])
def list_simulations(
    service: SimulationService = Depends(get_simulation_service),
) -> list[SimulationResponse]:
    """List all simulations."""
    return service.list_simulations()


@router.post("", response_model=SimulationResponse, status_code=status.HTTP_201_CREATED)
def create_simulation(
    data: SimulationCreate,
    service: SimulationService = Depends(get_simulation_service),
) -> SimulationResponse:
    """Create a new simulation."""
    return service.create_simulation(data)


@router.get("/{simulation_id}", response_model=SimulationResponse)
def get_simulation(
    simulation_id: str,
    service: SimulationService = Depends(get_simulation_service),
) -> SimulationResponse:
    """Get a simulation by ID including runtime statistics."""
    return service.get_simulation(simulation_id)


@router.patch("/{simulation_id}", response_model=SimulationResponse)
def update_simulation(
    simulation_id: str,
    data: SimulationUpdate,
    service: SimulationService = Depends(get_simulation_service),
) -> SimulationResponse:
    """Update a simulation."""
    return service.update_simulation(simulation_id, data)


@router.delete("/{simulation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_simulation(
    simulation_id: str,
    service: SimulationService = Depends(get_simulation_service),
) -> None:
    """Delete a simulation."""
    service.delete_simulation(simulation_id)


@router.post("/{simulation_id}/start", response_model=SimulationResponse)
def start_simulation(
    simulation_id: str,
    orchestrator: SimulationOrchestrator = Depends(get_simulation_orchestrator),
) -> SimulationResponse:
    """Start a continuous or finite simulation."""
    return orchestrator.start(simulation_id)


@router.post("/{simulation_id}/stop", response_model=SimulationResponse)
def stop_simulation(
    simulation_id: str,
    orchestrator: SimulationOrchestrator = Depends(get_simulation_orchestrator),
) -> SimulationResponse:
    """Stop a running simulation."""
    return orchestrator.stop(simulation_id)


@router.post("/{simulation_id}/send", response_model=SimulationSendResponse)
async def send_simulation_event(
    simulation_id: str,
    body: SimulationSendRequestBody | None = None,
    orchestrator: SimulationOrchestrator = Depends(get_simulation_orchestrator),
) -> SimulationSendResponse:
    """Generate and deliver a single event for this simulation."""
    request = body or SimulationSendRequestBody()
    return await orchestrator.send_once(
        simulation_id,
        payload_override=request.payload_override,
        scenario_id=request.scenario_id,
        preview_correlation_id=request.preview_correlation_id,
        payload_edited=request.payload_edited,
    )


@router.post(
    "/{simulation_id}/actions/{action_id}",
    response_model=WorkflowActionResponse,
)
async def execute_simulation_action(
    simulation_id: str,
    action_id: str,
    orchestrator: SimulationOrchestrator = Depends(get_simulation_orchestrator),
) -> WorkflowActionResponse:
    """Execute a product-defined workflow action against the simulation destination."""
    return await orchestrator.execute_action(simulation_id, action_id)


@router.get("/{simulation_id}/events", response_model=list[EventInstanceSummaryResponse])
def list_simulation_events(
    simulation_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    scenario_id: str | None = None,
    success: bool | None = None,
    http_status: int | None = None,
    correlation_id: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    orchestrator: SimulationOrchestrator = Depends(get_simulation_orchestrator),
) -> list[EventInstanceSummaryResponse]:
    """List generated events for a simulation with optional filters."""
    filters = EventListFilters(
        limit=limit,
        scenario_id=scenario_id,
        success=success,
        http_status=http_status,
        correlation_id=correlation_id,
        since=since,
        until=until,
    )
    return orchestrator.list_events(simulation_id, filters)


@router.get(
    "/{simulation_id}/events/{event_id}",
    response_model=EventInstanceResponse,
)
def get_simulation_event(
    simulation_id: str,
    event_id: str,
    orchestrator: SimulationOrchestrator = Depends(get_simulation_orchestrator),
) -> EventInstanceResponse:
    """Get a generated event with delivery attempt details."""
    return orchestrator.get_event(simulation_id, event_id)


@router.get(
    "/{simulation_id}/events/{event_id}/curl",
    response_model=CurlResponse,
)
def get_simulation_event_curl(
    simulation_id: str,
    event_id: str,
    attempt_id: str | None = Query(default=None),
    orchestrator: SimulationOrchestrator = Depends(get_simulation_orchestrator),
) -> CurlResponse:
    """Get a redacted cURL command for an event's delivery attempt."""
    return orchestrator.get_event_curl(simulation_id, event_id, attempt_id=attempt_id)


@router.post(
    "/{simulation_id}/events/{event_id}/replay",
    response_model=ReplayEventResponse,
)
async def replay_simulation_event(
    simulation_id: str,
    event_id: str,
    body: ReplayEventRequest,
    orchestrator: SimulationOrchestrator = Depends(get_simulation_orchestrator),
) -> ReplayEventResponse:
    """Replay an event using the exact stored payload or regenerate from scenario."""
    return await orchestrator.replay_event(simulation_id, event_id, mode=body.mode)


@router.post("/{simulation_id}/burst", response_model=SimulationBurstResponse)
async def burst_simulation_events(
    simulation_id: str,
    body: SimulationBurstRequest,
    orchestrator: SimulationOrchestrator = Depends(get_simulation_orchestrator),
) -> SimulationBurstResponse:
    """Send a bounded burst of events for integration stress testing."""
    return await orchestrator.burst(simulation_id, body)


@router.get("/{simulation_id}/export", response_model=SimulationExportDocument)
def export_simulation(
    simulation_id: str,
    include_secrets: bool = Query(default=False),
    confirm_secret_export: bool = Query(default=False),
    service: SimulationExportService = Depends(get_simulation_export_service),
) -> SimulationExportDocument:
    """Export a simulation configuration. Secrets are excluded unless explicitly requested."""
    if include_secrets and not confirm_secret_export:
        raise ValidationAppError(
            "Exporting secrets requires confirm_secret_export=true",
            details={"include_secrets": True},
        )
    return service.export_simulation(simulation_id, include_secrets=include_secrets)


@router.post(
    "/import", response_model=SimulationImportResponse, status_code=status.HTTP_201_CREATED
)
def import_simulation(
    body: SimulationImportRequest,
    service: SimulationExportService = Depends(get_simulation_export_service),
) -> SimulationImportResponse:
    """Import a sanitized simulation configuration."""
    return service.import_simulation(body.document)


@router.get(
    "/{simulation_id}/inbound-endpoint",
    response_model=InboundEndpointInfoResponse,
)
def get_inbound_endpoint_info(
    simulation_id: str,
    request: Request,
    catalog: SimulationService = Depends(get_simulation_service),
    service: InboundMockService = Depends(get_inbound_mock_service),
) -> InboundEndpointInfoResponse:
    """Describe mock API routes available for a pull-based simulation."""
    catalog.get_simulation(simulation_id)
    info = service.get_endpoint_info(
        simulation_id,
        public_base_url=str(request.base_url),
    )
    if info is None:
        raise NotFoundError(f"Simulation not found: {simulation_id}")
    return InboundEndpointInfoResponse(**info)


@router.get(
    "/{simulation_id}/inbound-requests",
    response_model=list[InboundRequestSummaryResponse],
)
def list_inbound_requests(
    simulation_id: str,
    limit: int = Query(default=50, ge=1, le=500),
    request_kind: str | None = Query(default=None),
    catalog: SimulationService = Depends(get_simulation_service),
    service: InboundMockService = Depends(get_inbound_mock_service),
) -> list[InboundRequestSummaryResponse]:
    """List inbound mock API request history for a simulation."""
    catalog.get_simulation(simulation_id)
    logs = service.list_requests(simulation_id, limit=limit, request_kind=request_kind)
    return [InboundRequestSummaryResponse.model_validate(log) for log in logs]


@router.get(
    "/{simulation_id}/inbound-requests/{request_id}",
    response_model=InboundRequestDetailResponse,
)
def get_inbound_request(
    simulation_id: str,
    request_id: str,
    catalog: SimulationService = Depends(get_simulation_service),
    service: InboundMockService = Depends(get_inbound_mock_service),
) -> InboundRequestDetailResponse:
    """Get a single inbound mock API request log entry."""
    catalog.get_simulation(simulation_id)
    log = service.get_request(simulation_id, request_id)
    if log is None:
        raise NotFoundError(f"Inbound request not found: {request_id}")
    return InboundRequestDetailResponse.model_validate(log)


@router.get(
    "/{simulation_id}/oauth-tokens",
    response_model=list[IssuedOAuthTokenResponse],
)
def list_oauth_tokens(
    simulation_id: str,
    limit: int = Query(default=50, ge=1, le=500),
    catalog: SimulationService = Depends(get_simulation_service),
    service: InboundMockService = Depends(get_inbound_mock_service),
) -> list[IssuedOAuthTokenResponse]:
    """List issued OAuth access token metadata for a pull simulation (no secrets)."""
    catalog.get_simulation(simulation_id)
    tokens = service.list_issued_tokens(simulation_id, limit=limit)
    return [IssuedOAuthTokenResponse.model_validate(token) for token in tokens]


@router.post("/{simulation_id}/wire-preview")
def preview_target_wire(
    simulation_id: str,
    target_id: str,
    orchestrator: SimulationOrchestrator = Depends(get_simulation_orchestrator),
) -> dict[str, object]:
    """Render an unpersisted event and the exact UTF-8 bytes at preview time."""
    import base64
    import json

    from app.core.redaction import redact_secret_values
    from app.domain.enums import FidelityMode
    from app.formats.source import custom_ingestion_record, render_source
    from app.services.targets import target_configs
    from app.transports.syslog.engine import SyslogDeliveryEngine
    from app.transports.syslog.formats import format_syslog_message, frame_message

    runtime = orchestrator._runtime
    simulation = orchestrator._repo.get_by_id_or_raise(simulation_id)
    target = next((t for t in target_configs(simulation) if t["id"] == target_id), None)
    if target is None:
        raise NotFoundError("Target not found")
    scenario_id = runtime._select_scenario_id(simulation)
    scenario = runtime._products.get_scenario(simulation.product_id, scenario_id)
    assert scenario is not None
    sequence = int((simulation.runtime_state or {}).get("events_generated", 0))
    device = (simulation.devices or [{}])[sequence % max(len(simulation.devices or []), 1)]
    payload = runtime._products.renderer.render_scenario(
        scenario,
        fidelity_mode=FidelityMode(simulation.fidelity_mode),
        correlation_id="wire-preview",
        overrides=runtime._event_overrides(simulation, scenario, sequence, device),
        plugin=runtime._products.get_plugin(simulation.product_id),
        random_seed=simulation.random_seed,
        event_sequence=sequence,
    )
    if isinstance(payload, str):
        payload = {"_syslog_message": payload}
    if simulation.replay_config:
        from app.models import UploadedDataset
        from app.services.datasets import dataset_directory

        row = runtime._db.get(UploadedDataset, simulation.replay_config["dataset_id"])
        if row is None:
            raise NotFoundError("Replay dataset not found")
        with (dataset_directory(runtime._settings.resolved_data_dir) / row.filename).open(
            encoding="utf-8"
        ) as handle:
            item = json.loads(handle.readline())
        payload = {
            "_dataset_payload": item.get("raw", item["payload"]),
            "_dataset_content_type": item["content_type"],
        }
    payload = redact_secret_values(payload, runtime._configured_secret_values(simulation))
    body, content_type = render_source(payload, target.get("payload_format", "default"))
    destination = target["destination"]
    transport_id = destination.get("transport_id", "http_webhook")
    if transport_id == "azure_logs_ingestion":
        if (
            target.get("payload_format", "default") == "default"
            or content_type != "application/json"
        ):
            body = custom_ingestion_record(payload, body, simulation.product_id)
        elif isinstance(body, str):
            body = json.loads(body)
        body = [body] if isinstance(body, dict) else body
        content_type = "application/json"
    wire = (
        body.encode("utf-8")
        if isinstance(body, str)
        else json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    )
    if transport_id == "syslog":
        config = SyslogDeliveryEngine().parse_destination(
            {
                **destination,
                "syslog_hostname": device.get("hostname") or destination.get("syslog_hostname"),
            }
        )
        wire = frame_message(
            format_syslog_message(wire, content_type, config),
            "newline" if config.protocol == "udp" else config.tcp_framing,
        )
    return {
        "target_id": target_id,
        "scenario_id": scenario_id,
        "content_type": content_type,
        "bytes": len(wire),
        "wire_text": wire.decode("utf-8"),
        "wire_base64": base64.b64encode(wire).decode(),
        "note": (
            "Exact bytes at preview time. Generation and envelope timestamps advance "
            "during actual sends; secrets are redacted."
        ),
    }
