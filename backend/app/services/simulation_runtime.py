import asyncio
import copy
import json
import logging
import random
import secrets
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.exceptions import ConflictError, NotFoundError, ValidationAppError
from app.core.redaction import redact_mapping, redact_secret_values
from app.core.security import SecretEncryptor
from app.domain.enums import (
    EventInstanceStatus,
    FidelityMode,
    PayloadSource,
    ScheduleType,
    SimulationMode,
    SimulationStatus,
)
from app.domain.fault_config import DuplicateMode, parse_fault_config
from app.domain.fault_injection import apply_payload_faults, build_fault_metadata
from app.domain.inbound import InboundConfig
from app.domain.runtime_state import default_runtime_state, utc_now_iso
from app.domain.schedule import validate_schedule_config
from app.formats.azure_ingestion import AZURE_TRANSPORTS, ingestion_record
from app.formats.source import render_source
from app.models import DeliveryAttempt, DeliveryJob, EventInstance, Simulation
from app.products.registry import ProductRegistry
from app.repositories.simulation import (
    DeliveryAttemptRepository,
    EventInstanceRepository,
    SimulationRepository,
)
from app.schemas.event_instance import (
    CurlResponse,
    DeliveryAttemptResponse,
    EventInstanceResponse,
    EventInstanceSummaryResponse,
    EventListFilters,
    ReplayEventResponse,
    WorkflowActionResponse,
)
from app.schemas.simulation import (
    SimulationBurstRequest,
    SimulationBurstResponse,
    SimulationRuntimeStats,
    SimulationSendResponse,
)
from app.services.curl_generator import build_curl_from_attempt
from app.services.destination_config import destination_for_delivery, missing_destination_secrets
from app.services.error_explanations import explain_error_category
from app.services.inbound_options import validate_inbound_options
from app.services.pull_dataset import PullDatasetService
from app.services.targets import target_configs
from app.services.transport_delivery import TransportDeliveryService
from app.transports.delivery_result import DeliveryResult

logger = logging.getLogger(__name__)


class SimulationRuntimeService:
    """Generate, deliver, and persist simulation events."""

    def __init__(
        self,
        db: Session,
        product_registry: ProductRegistry,
        transport_service: TransportDeliveryService,
        encryptor: SecretEncryptor,
        settings: Settings | None = None,
    ) -> None:
        self._db = db
        self._products = product_registry
        self._transport = transport_service
        self._encryptor = encryptor
        self._settings = settings or get_settings()
        self._simulations = SimulationRepository(db)
        self._events = EventInstanceRepository(db)
        self._attempts = DeliveryAttemptRepository(db)
        self._pull_datasets = PullDatasetService(db, product_registry)
        self._attempt_buffer: list[DeliveryAttempt] | None = None

    def recover_after_restart(self) -> int:
        """Mark interrupted running simulations as stopped. Returns count updated."""
        if self._settings.scheduler_resume_on_restart:
            return 0

        interrupted = 0
        for simulation in self._simulations.list_by_status(SimulationStatus.RUNNING):
            runtime = self._ensure_runtime_state(simulation)
            runtime["interrupted_on_restart"] = True
            runtime["stopped_at"] = utc_now_iso()
            simulation.runtime_state = runtime
            simulation.status = SimulationStatus.STOPPED.value
            interrupted += 1
            logger.warning(
                "Simulation interrupted by restart; marked stopped",
                extra={"simulation_id": simulation.id},
            )
        if interrupted:
            self._db.commit()
        return interrupted

    def prepare_safe_resume(self) -> list[Simulation]:
        """Validate persisted running simulations and return jobs to register."""
        if not self._settings.scheduler_resume_on_restart:
            self.recover_after_restart()
            return []

        scheduled: list[Simulation] = []
        resumed = 0
        running = list(reversed(self._simulations.list_by_status(SimulationStatus.RUNNING)))
        for simulation in running:
            try:
                if resumed >= self._settings.scheduler_max_concurrent_simulations:
                    raise ValidationAppError("Concurrent simulation limit exceeded during recovery")
                if simulation.simulation_mode == SimulationMode.PULL_API.value:
                    self._validate_pull_auth(simulation)
                    if not self._pull_datasets.has_active_dataset(simulation):
                        raise ValidationAppError("Persisted pull dataset is missing")
                else:
                    schedule_type = self._schedule_type(simulation)
                    if schedule_type == ScheduleType.MANUAL:
                        raise ValidationAppError("Manual simulation cannot be resumed")
                    if schedule_type == ScheduleType.FINITE and self._is_finite_complete(
                        simulation
                    ):
                        runtime = self._ensure_runtime_state(simulation)
                        runtime["stopped_at"] = utc_now_iso()
                        simulation.runtime_state = runtime
                        simulation.status = SimulationStatus.COMPLETED.value
                        self._simulations.update(simulation)
                        continue
                    self._validate_schedule_limits(simulation)
                    self._validate_destination(simulation)
                    self._validate_auth(simulation)
                    scheduled.append(simulation)
                runtime = self._ensure_runtime_state(simulation)
                runtime["interrupted_on_restart"] = False
                runtime["last_error_message"] = None
                simulation.runtime_state = runtime
                self._simulations.update(simulation)
                resumed += 1
            except Exception as exc:
                runtime = self._ensure_runtime_state(simulation)
                runtime["last_error_message"] = f"Restart recovery failed: {exc}"
                runtime["last_error_at"] = utc_now_iso()
                runtime["stopped_at"] = utc_now_iso()
                simulation.runtime_state = runtime
                simulation.status = SimulationStatus.ERROR.value
                self._simulations.update(simulation)
                logger.exception(
                    "Simulation could not be resumed after restart",
                    extra={"simulation_id": simulation.id},
                )
        return scheduled

    def start(self, simulation_id: str) -> Simulation:
        simulation = self._simulations.get_by_id_or_raise(simulation_id)
        if simulation.status == SimulationStatus.RUNNING.value:
            raise ConflictError("Simulation is already running")

        if simulation.simulation_mode == SimulationMode.PULL_API.value:
            self._validate_pull_auth(simulation)
            self._enforce_concurrent_limit(exclude_id=simulation.id)
            activation = self._pull_datasets.materialize(simulation)
            runtime = self._ensure_runtime_state(simulation)
            runtime["started_at"] = utc_now_iso()
            runtime["stopped_at"] = None
            runtime["interrupted_on_restart"] = False
            runtime["pull_dataset_activation_id"] = activation.id
            runtime["pull_dataset_item_count"] = activation.item_count
            simulation.runtime_state = runtime
            simulation.status = SimulationStatus.RUNNING.value
            return self._simulations.update(simulation)

        schedule_type = self._schedule_type(simulation)
        if schedule_type == ScheduleType.MANUAL:
            raise ValidationAppError(
                "Manual simulations cannot be started; use POST /send for one-shot delivery"
            )

        self._validate_schedule_limits(simulation)
        requested_rate = float((simulation.schedule or {}).get("events_per_second") or 0)
        running_rate = sum(
            float((s.schedule or {}).get("events_per_second") or 0)
            for s in self._simulations.list_by_status(SimulationStatus.RUNNING)
        )
        if requested_rate + running_rate > 100:
            raise ValidationAppError(
                "Combined scheduled generation rate exceeds 100 events per second"
            )
        self._validate_destination(simulation)
        self._validate_auth(simulation)
        self._validate_azure_replay(simulation)
        self._enforce_concurrent_limit(exclude_id=simulation.id)

        runtime = self._ensure_runtime_state(simulation)
        runtime["started_at"] = utc_now_iso()
        runtime["stopped_at"] = None
        runtime["interrupted_on_restart"] = False
        runtime["schedule_activation_start_count"] = runtime.get("events_generated", 0)
        for key in (
            "replay_offset",
            "replay_last_timestamp",
            "replay_pending_payload",
            "replay_due_at",
            "replay_last_emit_at",
            "rate_credit",
            "replay_generation_finished",
        ):
            runtime.pop(key, None)

        simulation.runtime_state = runtime
        simulation.status = SimulationStatus.RUNNING.value
        return self._simulations.update(simulation)

    def stop(self, simulation_id: str) -> Simulation:
        simulation = self._simulations.get_by_id_or_raise(simulation_id)
        if simulation.status != SimulationStatus.RUNNING.value:
            raise ConflictError("Simulation is not running")

        runtime = self._ensure_runtime_state(simulation)
        runtime["stopped_at"] = utc_now_iso()
        simulation.runtime_state = runtime
        simulation.status = SimulationStatus.STOPPED.value
        return self._simulations.update(simulation)

    async def burst(
        self,
        simulation_id: str,
        request: SimulationBurstRequest,
    ) -> SimulationBurstResponse:
        simulation = self._simulations.get_by_id_or_raise(simulation_id)
        self._validate_burst_request(request)
        self._validate_destination(simulation)
        self._validate_auth(simulation)

        interval_seconds = request.interval_ms / 1000
        if request.events_per_second:
            if request.events_per_second > self._settings.fault_max_burst_rate_per_second:
                raise ValidationAppError(
                    f"events_per_second exceeds maximum of "
                    f"{self._settings.fault_max_burst_rate_per_second}",
                    details={
                        "max_events_per_second": self._settings.fault_max_burst_rate_per_second
                    },
                )
            interval_seconds = 1.0 / request.events_per_second

        event_ids: list[str] = []
        successful = 0
        failed = 0
        fault = parse_fault_config(simulation.fault_config)

        for index in range(request.count):
            event, delivery = await self._generate_and_deliver(
                simulation,
                scenario_id=request.scenario_id,
            )
            event_ids.append(event.id)
            if delivery.success:
                successful += 1
            else:
                failed += 1
            if index < request.count - 1 and interval_seconds > 0:
                await asyncio.sleep(interval_seconds)

        return SimulationBurstResponse(
            simulation_id=simulation.id,
            requested=request.count,
            generated=len(event_ids),
            successful=successful,
            failed=failed,
            event_ids=event_ids,
            faults_enabled=fault.enabled,
        )

    async def send_once(
        self,
        simulation_id: str,
        *,
        payload_override: dict[str, Any] | None = None,
        scenario_id: str | None = None,
        preview_correlation_id: str | None = None,
        payload_edited: bool = False,
    ) -> SimulationSendResponse:
        simulation = self._simulations.get_by_id_or_raise(simulation_id)
        if simulation.simulation_mode == SimulationMode.PULL_API.value:
            raise ValidationAppError(
                "Pull simulations do not send outbound events; start the mock API instead"
            )
        self._validate_destination(simulation)
        self._validate_auth(simulation)

        is_unchanged_preview = (
            payload_override is not None
            and preview_correlation_id is not None
            and not payload_edited
        )
        payload_source = (
            PayloadSource.GENERATED
            if payload_override is None or is_unchanged_preview
            else PayloadSource.MANUAL_OVERRIDE
        )
        simulator_metadata: dict[str, Any] = {}
        if preview_correlation_id is not None:
            simulator_metadata["preview_send"] = True
        if payload_source == PayloadSource.MANUAL_OVERRIDE:
            simulator_metadata["manual_edit"] = True

        event, delivery = await self._generate_and_deliver(
            simulation,
            scenario_id=scenario_id,
            payload_override=payload_override,
            payload_source=payload_source,
            simulator_metadata=simulator_metadata,
            correlation_id_override=preview_correlation_id,
        )
        return SimulationSendResponse(
            simulation_id=simulation.id,
            event_id=event.id,
            correlation_id=event.correlation_id,
            scenario_id=event.scenario_id,
            payload=event.payload,
            payload_source=event.payload_source,
            delivery_success=delivery.success,
            response_status_code=delivery.response_status_code,
            latency_ms=delivery.latency_ms,
            error_message=delivery.error_message,
        )

    async def replay_event(
        self,
        simulation_id: str,
        event_id: str,
        *,
        mode: Literal["exact", "regenerate"],
    ) -> ReplayEventResponse:
        simulation = self._simulations.get_by_id_or_raise(simulation_id)
        source = self._events.get_by_id(event_id)
        if source is None or source.simulation_id != simulation_id:
            raise NotFoundError(f"Event not found: {event_id}")

        self._validate_destination(simulation)
        self._validate_auth(simulation)

        if mode == "exact":
            event, delivery = await self._deliver_existing_payload(
                simulation,
                source,
                payload_source=PayloadSource.REPLAY_EXACT,
            )
        else:
            event, delivery = await self._generate_and_deliver(
                simulation,
                scenario_id=source.scenario_id,
                payload_source=PayloadSource.REPLAY_REGENERATE,
                replayed_from_event_id=source.id,
            )

        return ReplayEventResponse(
            simulation_id=simulation.id,
            source_event_id=source.id,
            new_event_id=event.id,
            correlation_id=event.correlation_id,
            scenario_id=event.scenario_id,
            payload_source=event.payload_source,
            payload=event.payload,
            delivery_success=delivery.success,
            response_status_code=delivery.response_status_code,
            latency_ms=delivery.latency_ms,
            error_message=delivery.error_message,
        )

    async def execute_action(
        self,
        simulation_id: str,
        action_id: str,
    ) -> WorkflowActionResponse:
        simulation = self._simulations.get_by_id_or_raise(simulation_id)
        manifest = self._products.get_manifest(simulation.product_id)
        if manifest is None:
            raise NotFoundError(f"Product not found: {simulation.product_id}")
        action = next((item for item in manifest.actions if item.id == action_id), None)
        if action is None:
            raise NotFoundError(f"Product action not found: {action_id}")
        if simulation.simulation_mode not in action.supported_modes:
            raise ValidationAppError(
                f"Action '{action_id}' is not available in {simulation.simulation_mode} mode"
            )
        self._validate_destination(simulation)
        self._validate_auth(simulation)

        correlation_id = str(uuid.uuid4())
        action_context: dict[str, Any] = {
            "correlation_id": correlation_id,
            "challenge": secrets.token_urlsafe(24),
            "product_id": simulation.product_id,
            "action_id": action.id,
        }
        headers = {
            name: str(self._products.renderer.render_structure(value, action_context))
            for name, value in action.headers.items()
        }
        body = (
            self._products.renderer.render_structure(action.body, action_context)
            if action.body is not None
            else None
        )

        event = EventInstance(
            simulation_id=simulation.id,
            product_id=simulation.product_id,
            scenario_id=action.id,
            event_kind="workflow_action",
            action_id=action.id,
            fidelity_mode=simulation.fidelity_mode,
            payload=body if isinstance(body, dict) else {},
            correlation_id=correlation_id,
            status=EventInstanceStatus.PENDING.value,
            payload_source=PayloadSource.GENERATED.value,
            simulator_metadata={"workflow_action": True},
        )
        event = self._events.create(event)

        destination = destination_for_delivery(
            simulation.destination or {},
            simulation.destination_secret_values or {},
            self._encryptor,
        )
        destination["method"] = action.method
        destination["headers"] = {**destination.get("headers", {}), **headers}
        if action.delivery_policy.timeout_seconds is not None:
            destination["timeout_seconds"] = action.delivery_policy.timeout_seconds
        if action.delivery_policy.follow_redirects is not None:
            destination["follow_redirects"] = action.delivery_policy.follow_redirects

        auth_config = self._encryptor.decrypt_auth_config(simulation.auth_config)
        last_delivery: DeliveryResult | None = None
        for attempt_number in range(1, action.delivery_policy.max_attempts + 1):
            last_delivery = await self._transport.deliver(
                destination,
                body,
                action.content_type or "application/json",
                auth_config,
            )
            self._persist_attempt(
                event,
                last_delivery,
                str(destination.get("transport_id", "http_webhook")),
                attempt_number=attempt_number,
            )
            if last_delivery.success or not self._action_should_retry(
                last_delivery, action.delivery_policy.retry_on
            ):
                break

        assert last_delivery is not None
        accepted_status = last_delivery.response_status_code in action.accepted_statuses
        assertion_passed = accepted_status and self._evaluate_action_assertion(
            action.assertion.type,
            action.assertion.field,
            action.assertion.context_key,
            last_delivery.response_body,
            action_context,
        )
        effective_success = last_delivery.success and assertion_passed
        if not effective_success:
            last_delivery = last_delivery.model_copy(
                update={
                    "success": False,
                    "error_message": last_delivery.error_message
                    or "Workflow action response assertion failed",
                    "error_category": last_delivery.error_category or "internal",
                }
            )
        self._finalize_delivery(simulation, event, last_delivery)
        return WorkflowActionResponse(
            simulation_id=simulation.id,
            action_id=action.id,
            event_id=event.id,
            assertion_passed=assertion_passed,
            delivery_success=effective_success,
            response_status_code=last_delivery.response_status_code,
            error_message=last_delivery.error_message,
        )

    @staticmethod
    def _action_should_retry(delivery: DeliveryResult, retry_on: Sequence[str]) -> bool:
        category = delivery.error_category or ""
        if "http_5xx" in retry_on and category == "http_5xx":
            return True
        return "timeout" in retry_on and category in {
            "timeout",
            "connection_timeout",
            "read_timeout",
        }

    @staticmethod
    def _evaluate_action_assertion(
        assertion_type: str,
        field: str | None,
        context_key: str | None,
        response_body: str | None,
        context: dict[str, Any],
    ) -> bool:
        if assertion_type == "none":
            return True
        if not field or not context_key or response_body is None:
            return False
        try:
            payload = json.loads(response_body)
        except json.JSONDecodeError:
            return False
        if not isinstance(payload, dict):
            return False
        return payload.get(field) == context.get(context_key)

    async def tick(self, simulation_id: str) -> None:
        simulation = self._simulations.get_by_id_or_raise(simulation_id)
        if simulation.status != SimulationStatus.RUNNING.value:
            return

        try:
            if (simulation.runtime_state or {}).get("replay_generation_finished"):
                self._finish_replay_if_drained(simulation)
                return
            rate = (simulation.schedule or {}).get("events_per_second")
            if rate is None:
                await self._scheduled_event(simulation, enqueue=False)
            else:
                self._db.info["batch_writes"] = True
                state = self._ensure_runtime_state(simulation)
                credit = float(state.get("rate_credit", 0)) + float(rate) * 0.1
                count = int(credit + 1e-9)
                state["rate_credit"] = max(credit - count, 0)
                simulation.runtime_state = state
                self._db.flush()
                for _ in range(count):
                    if self._is_finite_complete(simulation):
                        break
                    if not await self._scheduled_event(simulation, enqueue=True):
                        break
                self._db.commit()
            self._db.commit()
            simulation = self._simulations.get_by_id_or_raise(simulation_id)
            if self._is_finite_complete(simulation):
                if simulation.replay_config:
                    self._finish_replay_if_drained(simulation)
                    return
                runtime = self._ensure_runtime_state(simulation)
                runtime["stopped_at"] = utc_now_iso()
                simulation.runtime_state = runtime
                simulation.status = SimulationStatus.COMPLETED.value
                self._simulations.update(simulation)
        except Exception as exc:
            if isinstance(exc, ValidationAppError) and str(exc) == "Replay dataset is complete":
                self._finish_replay_if_drained(simulation)
                return
            self._db.rollback()
            logger.exception(
                "Simulation tick failed",
                extra={"simulation_id": simulation_id},
            )
            runtime = self._ensure_runtime_state(simulation)
            runtime["last_error_message"] = str(exc)
            runtime["last_error_at"] = utc_now_iso()
            runtime["stopped_at"] = utc_now_iso()
            simulation.runtime_state = runtime
            simulation.status = SimulationStatus.ERROR.value
            self._simulations.update(simulation)

    def _finish_replay_if_drained(self, simulation: Simulation) -> None:
        state = self._ensure_runtime_state(simulation)
        state["replay_generation_finished"] = True
        pending = (
            self._db.query(DeliveryJob)
            .filter(
                DeliveryJob.simulation_id == simulation.id,
                DeliveryJob.status.in_(["pending", "active"]),
            )
            .count()
        )
        if not pending:
            state["stopped_at"] = utc_now_iso()
            simulation.status = SimulationStatus.COMPLETED.value
        simulation.runtime_state = state
        self._simulations.update(simulation)
        self._db.commit()

    def _validate_azure_replay(self, simulation: Simulation) -> None:
        if not simulation.replay_config:
            return
        from app.models import UploadedDataset
        from app.services.datasets import dataset_directory, validate_ingestion_dataset

        dataset = self._db.get(UploadedDataset, simulation.replay_config["dataset_id"])
        if dataset is None:
            raise ValidationAppError("Replay dataset not found")
        for target in target_configs(simulation):
            if (
                target.get("enabled", True)
                and target["destination"].get("transport_id") in AZURE_TRANSPORTS
            ):
                try:
                    fmt = target.get("payload_format", "default")
                    validate_ingestion_dataset(
                        dataset_directory(self._settings.resolved_data_dir) / dataset.filename,
                        dataset.format,
                        "envelope" if fmt == "default" else fmt,
                        simulation.replay_config.get("rewrite_timestamps", False),
                        simulation.product_id,
                        int(target["destination"].get("batch_max_bytes", 950_000)),
                        simulation.replay_config.get("timestamp_fields"),
                    )
                except ValueError as exc:
                    raise ValidationAppError(str(exc)) from None

    async def _scheduled_event(self, simulation: Simulation, *, enqueue: bool) -> bool:
        if not simulation.replay_config:
            await self._generate_and_deliver(simulation, enqueue=enqueue)
            return True
        from app.services.datasets import replay_record

        state = self._ensure_runtime_state(simulation)
        now = datetime.now(UTC)
        pending = state.get("replay_pending_payload")
        due = state.get("replay_due_at")
        if pending is not None and due and datetime.fromisoformat(due) > now:
            return False
        if pending is None:
            pending, delay = replay_record(self._db, simulation, self._settings.resolved_data_dir)
            state = self._ensure_runtime_state(simulation)
            if pending is None:
                raise ValidationAppError("Replay dataset is complete")
            last = state.get("replay_last_emit_at")
            due_at = datetime.fromisoformat(last) + timedelta(seconds=delay) if last else now
            if due_at > now:
                state.update(replay_pending_payload=pending, replay_due_at=due_at.isoformat())
                simulation.runtime_state = state
                self._db.flush()
                return False
        state.pop("replay_pending_payload", None)
        state.pop("replay_due_at", None)
        state["replay_last_emit_at"] = now.isoformat()
        simulation.runtime_state = state
        await self._generate_and_deliver(
            simulation,
            payload_override=pending,
            payload_source=PayloadSource.REPLAY_EXACT,
            enqueue=enqueue,
        )
        return True

    def list_events(
        self,
        simulation_id: str,
        filters: EventListFilters | None = None,
    ) -> list[EventInstanceSummaryResponse]:
        self._simulations.get_by_id_or_raise(simulation_id)
        filters = filters or EventListFilters()
        events = self._events.list_for_simulation(
            simulation_id,
            limit=filters.limit,
            scenario_id=filters.scenario_id,
            success=filters.success,
            http_status=filters.http_status,
            correlation_id=filters.correlation_id,
            since=filters.since,
            until=filters.until,
        )
        return [self._to_event_summary(event) for event in events]

    def find_events_by_correlation_id(
        self,
        correlation_id: str,
        *,
        limit: int = 20,
    ) -> list[EventInstanceSummaryResponse]:
        events = self._events.find_by_correlation_id(correlation_id, limit=limit)
        return [self._to_event_summary(event) for event in events]

    def get_event(self, simulation_id: str, event_id: str) -> EventInstanceResponse:
        self._simulations.get_by_id_or_raise(simulation_id)
        event = self._events.get_by_id(event_id)
        if event is None or event.simulation_id != simulation_id:
            raise NotFoundError(f"Event not found: {event_id}")
        return self._to_event_detail(event)

    def get_event_curl(
        self, simulation_id: str, event_id: str, *, attempt_id: str | None = None
    ) -> CurlResponse:
        simulation = self._simulations.get_by_id_or_raise(simulation_id)
        event = self._events.get_by_id(event_id)
        if event is None or event.simulation_id != simulation_id:
            raise NotFoundError(f"Event not found: {event_id}")
        if not event.delivery_attempts:
            raise ValidationAppError("No delivery attempt available for this event")

        attempt: DeliveryAttempt | None
        if attempt_id is None:
            attempt = event.delivery_attempts[-1]
        else:
            attempt = next(
                (item for item in event.delivery_attempts if item.id == attempt_id), None
            )
            if attempt is None:
                raise NotFoundError(f"Delivery attempt not found: {attempt_id}")
        auth_config = self._encryptor.decrypt_auth_config(simulation.auth_config)
        command, exact, warnings = build_curl_from_attempt(
            attempt,
            auth_method_id=auth_config.get("auth_method_id", "none"),
        )
        return CurlResponse(
            attempt_id=attempt.id,
            exact=exact,
            command=command,
            warnings=warnings,
            secrets_redacted=True,
        )

    def runtime_stats(self, simulation: Simulation) -> SimulationRuntimeStats:
        runtime = self._ensure_runtime_state(simulation)
        return SimulationRuntimeStats(**runtime)

    async def _generate_and_deliver(
        self,
        simulation: Simulation,
        *,
        scenario_id: str | None = None,
        payload_override: dict[str, Any] | None = None,
        payload_source: PayloadSource = PayloadSource.GENERATED,
        replayed_from_event_id: str | None = None,
        simulator_metadata: dict[str, Any] | None = None,
        correlation_id_override: str | None = None,
        enqueue: bool = False,
    ) -> tuple[EventInstance, DeliveryResult]:
        if simulation.replay_config and payload_override is None:
            from app.services.datasets import replay_record

            payload_override, _ = replay_record(
                self._db, simulation, self._settings.resolved_data_dir
            )
            if payload_override is None:
                raise ValidationAppError("Replay dataset is complete")
            payload_source = PayloadSource.REPLAY_EXACT
        selected_scenario_id = scenario_id or self._select_scenario_id(simulation)
        scenario = self._products.get_scenario(simulation.product_id, selected_scenario_id)
        manifest = self._products.get_manifest(simulation.product_id)
        if scenario is None or manifest is None:
            raise ValidationAppError(
                f"Scenario not found: {simulation.product_id}/{selected_scenario_id}"
            )

        runtime = self._ensure_runtime_state(simulation)
        event_sequence = runtime.get("events_generated", 0)
        device = (simulation.devices or [{}])[
            event_sequence % max(len(simulation.devices or []), 1)
        ]
        correlation_id = correlation_id_override or str(uuid.uuid4())
        fidelity_mode = FidelityMode(simulation.fidelity_mode)
        plugin = self._products.get_plugin(simulation.product_id)
        fault = parse_fault_config(simulation.fault_config)
        duplicate_mode = fault.duplicate.mode if fault.enabled else DuplicateMode.NONE
        source_event: EventInstance | None = None
        duplicate_source_id: str | None = None
        payload: dict[str, Any] | str

        if fault.enabled and fault.duplicate.source_event_id:
            source_event = self._events.get_by_id(fault.duplicate.source_event_id)
            if source_event is None or source_event.simulation_id != simulation.id:
                raise NotFoundError(f"Source event not found: {fault.duplicate.source_event_id}")
            duplicate_source_id = source_event.id

        if duplicate_mode == DuplicateMode.EXACT_PAYLOAD and source_event is not None:
            payload = copy.deepcopy(source_event.payload)
        elif payload_override is not None:
            payload = payload_override
        else:
            if duplicate_mode == DuplicateMode.DUPLICATE_CORRELATION_ID:
                if source_event is not None:
                    correlation_id = source_event.correlation_id
                elif fault.duplicate.correlation_id:
                    correlation_id = fault.duplicate.correlation_id
            payload = self._products.renderer.render_scenario(
                scenario,
                fidelity_mode=fidelity_mode,
                correlation_id=correlation_id,
                overrides=self._event_overrides(simulation, scenario, event_sequence, device),
                plugin=plugin,
                diagnostic_merge=manifest.diagnostic_merge,
                random_seed=simulation.random_seed,
                event_sequence=event_sequence,
            )

        if isinstance(payload, str):
            payload = {"_syslog_message": payload}

        workflow_plugin = self._products.get_workflow_plugin(simulation.product_id)
        if workflow_plugin is not None:
            payload = workflow_plugin.prepare_outbound_payload(
                selected_scenario_id,
                payload,
                correlation_id=correlation_id,
            )

        payload, applied_faults, delivery_hints = apply_payload_faults(payload, fault)
        metadata = {**dict(simulator_metadata or {}), "device_id": device.get("id")}
        if fault.enabled:
            metadata["fault_injection"] = build_fault_metadata(
                fault,
                applied_faults,
                duplicate_mode=duplicate_mode.value
                if duplicate_mode != DuplicateMode.NONE
                else None,
                source_event_id=duplicate_source_id,
            )

        stored_payload = redact_secret_values(
            payload if isinstance(payload, dict) else {"_syslog_message": payload},
            self._configured_secret_values(simulation),
        )
        event = EventInstance(
            simulation_id=simulation.id,
            product_id=simulation.product_id,
            scenario_id=selected_scenario_id,
            fidelity_mode=simulation.fidelity_mode,
            payload=stored_payload,
            correlation_id=correlation_id,
            status=EventInstanceStatus.PENDING.value,
            payload_source=payload_source.value,
            replayed_from_event_id=replayed_from_event_id,
            simulator_metadata=metadata,
        )
        event = self._events.create(event)

        runtime["events_generated"] = event_sequence + 1
        if payload_source == PayloadSource.GENERATED:
            runtime["scenario_index"] = (runtime.get("scenario_index", 0) + 1) % max(
                len(self._scenario_ids(simulation)), 1
            )
        simulation.runtime_state = runtime
        self._simulations.update(simulation)

        if enqueue:
            self._enqueue_event(simulation, event)
            now = datetime.now(UTC)
            return event, DeliveryResult(
                success=True,
                reached_server=False,
                started_at=now,
                completed_at=now,
                latency_ms=0,
                destination="persistent delivery queue",
                method="QUEUE",
            )
        delivery = await self._deliver_payload(
            simulation,
            scenario,
            payload,
            event=event,
            delivery_hints=delivery_hints,
        )
        self._finalize_delivery(simulation, event, delivery)
        return event, delivery

    async def _deliver_existing_payload(
        self,
        simulation: Simulation,
        source: EventInstance,
        *,
        payload_source: PayloadSource,
    ) -> tuple[EventInstance, DeliveryResult]:
        scenario = self._products.get_scenario(simulation.product_id, source.scenario_id)
        if scenario is None:
            raise ValidationAppError(
                f"Scenario not found: {simulation.product_id}/{source.scenario_id}"
            )

        correlation_id = str(uuid.uuid4())
        event = EventInstance(
            simulation_id=simulation.id,
            product_id=simulation.product_id,
            scenario_id=source.scenario_id,
            fidelity_mode=simulation.fidelity_mode,
            payload=source.payload,
            correlation_id=correlation_id,
            status=EventInstanceStatus.PENDING.value,
            payload_source=payload_source.value,
            replayed_from_event_id=source.id,
            simulator_metadata={"replayed_from_correlation_id": source.correlation_id},
        )
        event = self._events.create(event)

        runtime = self._ensure_runtime_state(simulation)
        runtime["events_generated"] = runtime.get("events_generated", 0) + 1
        simulation.runtime_state = runtime
        self._simulations.update(simulation)

        delivery = await self._deliver_payload(
            simulation,
            scenario,
            source.payload,
            event=event,
        )
        self._finalize_delivery(simulation, event, delivery)
        return event, delivery

    def _selected_targets(
        self, simulation: Simulation, event: EventInstance
    ) -> list[dict[str, Any]]:
        device_id = (event.simulator_metadata or {}).get("device_id")
        return [
            t
            for t in target_configs(simulation)
            if t.get("enabled", True)
            and (not t.get("scenario_ids") or event.scenario_id in t["scenario_ids"])
            and (not t.get("device_ids") or device_id in t["device_ids"])
        ]

    @staticmethod
    def _failure(message: str) -> DeliveryResult:
        now = datetime.now(UTC)
        return DeliveryResult(
            success=False,
            reached_server=False,
            started_at=now,
            completed_at=now,
            latency_ms=0,
            destination="target",
            method="QUEUE",
            error_message=message,
            error_category="internal",
        )

    async def _deliver_payload(
        self,
        simulation: Simulation,
        scenario: Any,
        payload: dict[str, Any] | str,
        *,
        event: EventInstance,
        delivery_hints: dict[str, Any] | None = None,
    ) -> DeliveryResult:
        targets = self._selected_targets(simulation, event)
        if not targets:
            result = self._failure("No enabled targets matched the event filters")
            self._persist_attempt(event, result, "none")
            return result

        async def deliver_one(target: dict[str, Any]) -> DeliveryResult:
            try:
                return await self._deliver_target(
                    simulation,
                    scenario,
                    payload,
                    event=event,
                    delivery_hints=delivery_hints,
                    target=target,
                )
            except Exception as exc:
                result = self._failure(
                    str(redact_secret_values(str(exc), self._configured_secret_values(simulation)))
                )
                self._persist_attempt(
                    event,
                    result,
                    target["destination"].get("transport_id", "http_webhook"),
                    target_id=target["id"],
                )
                return result

        results = await asyncio.gather(*(deliver_one(t) for t in targets))
        for target, result in zip(targets, results, strict=True):
            self._record_target_result(simulation, event, target, result)
        last = next((r for r in results if not r.success), results[-1])
        return last.model_copy(update={"success": all(r.success for r in results)})

    def _record_target_result(
        self,
        simulation: Simulation,
        event: EventInstance,
        target: dict[str, Any],
        result: DeliveryResult,
    ) -> None:
        outcomes = dict((event.simulator_metadata or {}).get("target_results", {}))
        outcomes[target["id"]] = {
            "success": result.success,
            "confirmation": result.delivery_confirmation,
            "error": result.error_message,
        }
        event.simulator_metadata = {**(event.simulator_metadata or {}), "target_results": outcomes}
        row = next((r for r in simulation.targets if r.target_id == target["id"]), None)
        if row:
            stats = dict(row.stats or {})
            stats["attempted"] = stats.get("attempted", 0) + 1
            key = "successful" if result.success else "failed"
            stats[key] = stats.get(key, 0) + 1
            stats.update(
                last_delivery_at=utc_now_iso(),
                last_error=result.error_message,
                last_latency_ms=result.latency_ms,
                confirmation=result.delivery_confirmation,
            )
            row.stats = stats

    def _enqueue_event(self, simulation: Simulation, event: EventInstance) -> None:
        targets = self._selected_targets(simulation, event)
        for target in targets:
            key = f"{simulation.id}:{target['id']}"
            size = (
                self._db.query(DeliveryJob)
                .filter(
                    DeliveryJob.target_key == key, DeliveryJob.status.in_(["pending", "active"])
                )
                .count()
            )
            if size >= target.get("queue_limit", 10000):
                result = self._failure("Target queue overflow")
                self._persist_attempt(
                    event,
                    result,
                    target["destination"].get("transport_id", "http_webhook"),
                    target_id=target["id"],
                )
                self._record_target_result(simulation, event, target, result)
                status = "failed"
            else:
                status = "pending"
            self._db.add(
                DeliveryJob(
                    simulation_id=simulation.id,
                    event_id=event.id,
                    target_key=key,
                    target_id=target["id"],
                    status=status,
                    config=target,
                )
            )
        self._db.flush()
        if not targets or all(
            j.status == "failed" for j in self._db.query(DeliveryJob).filter_by(event_id=event.id)
        ):
            self._finalize_delivery(
                simulation,
                event,
                self._failure("No targets matched or every target queue overflowed"),
            )

    def _event_overrides(
        self, simulation: Simulation, scenario: Any, sequence: int, device: dict[str, Any]
    ) -> dict[str, Any]:
        values = dict((simulation.scenario_overrides or {}).get(scenario.id, {}))
        properties = scenario.config_schema.get("properties", {})
        if device:
            for key, value in {
                "hostname": device.get("hostname"),
                "device_ip": device.get("ip_address"),
                "devname": device.get("hostname"),
            }.items():
                if key in properties and value is not None:
                    values[key] = value
        pool = (simulation.schedule or {}).get("user_pool", [])
        if pool and "user" in properties:
            values["user"] = random.Random((simulation.random_seed or 0) + sequence).choice(pool)
        preset = (simulation.schedule or {}).get("incident_preset")
        if preset == "password_spray":
            values.update(
                {
                    k: v
                    for k, v in {
                        "src": "198.51.100.99",
                        "user": values.get("user") if pool else f"labuser{sequence % 20:02d}",
                    }.items()
                    if k in properties
                }
            )
        elif preset == "privileged_logon" and "user" in properties:
            values["user"] = "administrator"
        elif preset == "firewall_scan":
            values.update(
                {
                    k: v
                    for k, v in {
                        "src": "198.51.100.99",
                        "dst": f"203.0.113.{sequence % 250 + 1}",
                        "dpt": sequence % 1024 + 1,
                    }.items()
                    if k in properties
                }
            )
        return values

    async def _deliver_target(
        self,
        simulation: Simulation,
        scenario: Any,
        payload: dict[str, Any] | str,
        *,
        event: EventInstance,
        delivery_hints: dict[str, Any] | None = None,
        target: dict[str, Any],
    ) -> DeliveryResult:
        fault = parse_fault_config(simulation.fault_config)
        destination = destination_for_delivery(
            target.get("destination", {}),
            target.get("destination_secret_values", {}),
            self._encryptor,
        )
        destination["syslog_hostname"] = (
            (payload.get("_source_event", {}).get("hostname") or destination.get("syslog_hostname"))
            if isinstance(payload, dict)
            else destination.get("syslog_hostname")
        )
        if fault.enabled and fault.delivery.timeout_seconds:
            destination["timeout_seconds"] = fault.delivery.timeout_seconds

        if fault.enabled and fault.delivery.pre_delay_ms:
            await asyncio.sleep(fault.delivery.pre_delay_ms / 1000)

        body, content_type = render_source(
            payload if isinstance(payload, dict) else {"_syslog_message": payload},
            target.get("payload_format", "default"),
        )
        if destination.get("transport_id") in AZURE_TRANSPORTS:
            body = ingestion_record(
                payload if isinstance(payload, dict) else {"_syslog_message": payload},
                target.get("payload_format", "default"),
                simulation.product_id,
            )
            content_type = "application/json"
        if delivery_hints and delivery_hints.get("malformed_body"):
            body = delivery_hints["malformed_body"]

        auth_config = self._encryptor.decrypt_auth_config(target.get("auth_config", {}))
        transport_id = destination.get("transport_id", "http_webhook")
        send_count = fault.delivery.duplicate_send_count if fault.enabled else 1
        retry_count = fault.delivery.retry_count if fault.enabled else 0
        retry_delay_ms = fault.delivery.retry_delay_ms if fault.enabled else 0

        policy = scenario.delivery_policy
        policy_attempts = max(int(policy.max_attempts), 1)
        if policy.timeout_seconds is not None and not (
            fault.enabled and fault.delivery.timeout_seconds
        ):
            destination["timeout_seconds"] = policy.timeout_seconds
        if policy.follow_redirects is not None:
            destination["follow_redirects"] = policy.follow_redirects

        last_delivery: DeliveryResult | None = None
        attempt_number = 0
        for _send_index in range(send_count):
            max_attempts = max(retry_count + 1, policy_attempts)
            for retry_index in range(max_attempts):
                attempt_number += 1
                last_delivery = await self._transport.deliver(
                    destination,
                    body,
                    content_type,
                    auth_config,
                )
                self._persist_attempt(
                    event,
                    last_delivery,
                    transport_id,
                    attempt_number=attempt_number,
                    target_id=target["id"],
                )
                fault_retry = fault.enabled and retry_index < retry_count
                policy_retry = retry_index + 1 < policy_attempts and self._action_should_retry(
                    last_delivery, policy.retry_on
                )
                if last_delivery.success or not (fault_retry or policy_retry):
                    break
                await asyncio.sleep(retry_delay_ms / 1000)

        assert last_delivery is not None
        return last_delivery

    def _finalize_delivery(
        self,
        simulation: Simulation,
        event: EventInstance,
        delivery: DeliveryResult,
    ) -> None:
        results = (event.simulator_metadata or {}).get("target_results", {})
        partial = not delivery.success and any(r.get("success") for r in results.values())
        event.status = "delivered" if delivery.success else "partial" if partial else "failed"
        self._events.update(event)

        self._db.refresh(simulation)
        runtime = self._ensure_runtime_state(simulation)
        if partial:
            runtime["events_partial"] = runtime.get("events_partial", 0) + 1
        runtime["events_attempted"] = runtime.get("events_attempted", 0) + 1
        if delivery.success:
            runtime["events_successful"] = runtime.get("events_successful", 0) + 1
        else:
            runtime["events_failed"] = runtime.get("events_failed", 0) + 1
        runtime["last_delivery_at"] = utc_now_iso()
        runtime["last_http_status"] = delivery.response_status_code
        runtime["last_latency_ms"] = delivery.latency_ms
        runtime["last_error_message"] = delivery.error_message
        runtime["last_event_id"] = event.id
        simulation.runtime_state = runtime
        self._simulations.update(simulation)

    def _persist_attempt(
        self,
        event: EventInstance,
        delivery: DeliveryResult,
        transport_id: str,
        *,
        attempt_number: int = 1,
        target_id: str | None = None,
    ) -> DeliveryAttempt:
        query_params = delivery.request_query_params_redacted
        if not isinstance(query_params, dict):
            query_params = redact_mapping(query_params) if query_params else {}
            if not isinstance(query_params, dict):
                query_params = {}

        secrets = self._configured_secret_values_for_attempt(event)
        attempt = DeliveryAttempt(
            event_instance_id=event.id,
            target_id=target_id,
            delivery_confirmation=delivery.delivery_confirmation,
            delivery_note=delivery.delivery_note,
            attempt_number=attempt_number,
            started_at=delivery.started_at,
            completed_at=delivery.completed_at,
            transport_id=transport_id,
            destination_summary=delivery.destination,
            request_url_redacted=delivery.request_url_redacted,
            request_method=delivery.method,
            request_headers_redacted=redact_secret_values(
                delivery.request_headers_redacted, secrets
            ),
            request_query_params_redacted=redact_secret_values(query_params, secrets),
            request_body=redact_secret_values(delivery.request_body, secrets),
            response_status_code=delivery.response_status_code,
            response_headers_redacted=redact_secret_values(
                delivery.response_headers_redacted, secrets
            ),
            response_body=redact_secret_values(delivery.response_body, secrets),
            latency_ms=delivery.latency_ms,
            success=delivery.success,
            error_message=delivery.error_message,
            error_category=delivery.error_category,
        )
        if self._attempt_buffer is not None:
            self._attempt_buffer.append(attempt)
            return attempt
        return self._attempts.create(attempt)

    def _configured_secret_values(self, simulation: Simulation) -> set[str]:
        auth = self._encryptor.decrypt_auth_config(simulation.auth_config or {})
        secrets = {
            str(auth[field])
            for field in ("password", "token", "oauth_client_secret", "api_key")
            if auth.get(field)
        }
        for target in target_configs(simulation):
            target_auth = self._encryptor.decrypt_auth_config(target.get("auth_config", {}))
            secrets.update(
                str(target_auth[f])
                for f in ("password", "token", "oauth_client_secret")
                if target_auth.get(f)
            )
            for ciphertext in target.get("destination_secret_values", {}).values():
                secrets.add(self._encryptor.decrypt(str(ciphertext)))
        return secrets

    def _configured_secret_values_for_attempt(self, event: EventInstance) -> set[str]:
        simulation = self._simulations.get_by_id_or_raise(event.simulation_id)
        return self._configured_secret_values(simulation)

    def _select_scenario_id(self, simulation: Simulation) -> str:
        scenario_ids = self._scenario_ids(simulation)
        runtime = self._ensure_runtime_state(simulation)
        weights = (simulation.schedule or {}).get("scenario_weights", {})
        if weights:
            rng = random.Random(
                (simulation.random_seed or 0) + int(runtime.get("events_generated", 0))
            )
            return rng.choices(scenario_ids, weights=[weights.get(sid, 1) for sid in scenario_ids])[
                0
            ]
        preset = (simulation.schedule or {}).get("incident_preset")
        matches = {
            "password_spray": "logon-failure",
            "privileged_logon": "logon-success",
            "firewall_scan": "deny",
            "malware_detection": "malware",
        }
        matching = [sid for sid in scenario_ids if matches.get(str(preset), "\x00") in sid]
        if matching:
            return matching[int(runtime.get("scenario_index", 0)) % len(matching)]
        index = int(runtime.get("scenario_index", 0)) % len(scenario_ids)
        return scenario_ids[index]

    def _scenario_ids(self, simulation: Simulation) -> list[str]:
        if simulation.scenario_ids:
            return list(simulation.scenario_ids)
        return [simulation.scenario_id]

    def _schedule_type(self, simulation: Simulation) -> ScheduleType:
        schedule = simulation.schedule or {}
        raw_type = schedule.get("type", ScheduleType.MANUAL.value)
        if raw_type == "interval":
            return ScheduleType.CONTINUOUS
        return ScheduleType(raw_type)

    def _schedule_config(self, simulation: Simulation) -> dict[str, Any]:
        return simulation.schedule or {}

    def _is_finite_complete(self, simulation: Simulation) -> bool:
        if self._schedule_type(simulation) != ScheduleType.FINITE:
            return False
        schedule = self._schedule_config(simulation)
        target = schedule.get("event_count")
        runtime = self._ensure_runtime_state(simulation)
        activation_start = runtime.get("schedule_activation_start_count", 0)
        activation_count = runtime.get("events_generated", 0) - activation_start
        return target is not None and activation_count >= target

    def _validate_schedule_limits(self, simulation: Simulation) -> None:
        from app.services.datasets import schedule_settings_for_replay

        validate_schedule_config(
            self._schedule_config(simulation),
            schedule_settings_for_replay(self._db, simulation.replay_config or {}, self._settings),
        )

    def _validate_burst_request(self, request: SimulationBurstRequest) -> None:
        if request.count > self._settings.fault_max_burst_count:
            raise ValidationAppError(
                f"Burst count exceeds maximum of {self._settings.fault_max_burst_count}",
                details={"max_burst_count": self._settings.fault_max_burst_count},
            )
        if (
            request.count > self._settings.fault_large_run_confirmation_threshold
            and not request.confirm_large_run
        ):
            raise ValidationAppError(
                "Large burst run requires confirm_large_run=true",
                details={
                    "threshold": self._settings.fault_large_run_confirmation_threshold,
                    "requested": request.count,
                },
            )

    def _validate_destination(self, simulation: Simulation) -> None:
        if simulation.simulation_mode == SimulationMode.PULL_API.value:
            return

        for target in target_configs(simulation):
            if not target.get("enabled", True):
                continue
            missing = missing_destination_secrets(
                target["destination"], target.get("destination_secret_values", {})
            )
            if missing:
                raise ValidationAppError(
                    "Target contains missing secret values",
                    details={"target_id": target["id"], "missing_secrets": missing},
                )
            dest = target["destination"]
            if dest.get("transport_id") == "syslog" and not dest.get("host"):
                raise ValidationAppError("destination.host is required for syslog transport")
            if dest.get("transport_id", "http_webhook") == "http_webhook" and not dest.get("url"):
                raise ValidationAppError("destination.url is required for http_webhook transport")

    def _validate_auth(self, simulation: Simulation) -> None:
        if simulation.simulation_mode == SimulationMode.PULL_API.value:
            self._validate_pull_auth(simulation)
            return

        manifest = self._products.get_manifest(simulation.product_id)
        if manifest is None:
            raise NotFoundError(f"Product not found: {simulation.product_id}")

        for target in target_configs(simulation):
            if not target.get("enabled", True):
                continue
            auth = self._encryptor.decrypt_auth_config(target.get("auth_config", {}))
            method = auth.get("auth_method_id", "none")
            if method not in manifest.supported_auth_methods:
                raise ValidationAppError(
                    f"Auth method '{method}' is not supported by product '{simulation.product_id}'"
                )
            if method == "basic" and (not auth.get("username") or not auth.get("password")):
                raise ValidationAppError("Basic auth requires username and password")
            if method in {"bearer", "api_key_header"} and not auth.get("token"):
                raise ValidationAppError(f"{method} auth requires a token")
            if target["destination"].get("transport_id") == "azure_function_app" and not auth.get(
                "token"
            ):
                raise ValidationAppError("Function App requires a function key")
            if target["destination"].get("transport_id") == "azure_logs_ingestion" and (
                not auth.get("oauth_client_id") or not auth.get("oauth_client_secret")
            ):
                raise ValidationAppError("Azure requires OAuth client ID and client secret")

    def _validate_pull_auth(self, simulation: Simulation) -> None:
        inbound = InboundConfig.model_validate(simulation.inbound_config or {})
        manifest = self._products.get_manifest(simulation.product_id)
        if manifest is None:
            raise NotFoundError(f"Product not found: {simulation.product_id}")
        validate_inbound_options(
            manifest,
            dict(inbound.vendor_options),
            workflow_plugin=self._products.get_workflow_plugin(simulation.product_id),
        )
        auth_config = self._encryptor.decrypt_auth_config(simulation.auth_config)
        method = inbound.auth_method_id
        if method == "api_key" and not (auth_config.get("token") or auth_config.get("api_key")):
            raise ValidationAppError("API key inbound auth requires a token in auth_config")
        if method == "bearer" and not auth_config.get("token"):
            raise ValidationAppError("Bearer inbound auth requires a token in auth_config")
        if method == "basic" and (
            not auth_config.get("username") or not auth_config.get("password")
        ):
            raise ValidationAppError("Basic inbound auth requires username and password")
        if method == "oauth2_client_credentials" and (
            not auth_config.get("oauth_client_id") or not auth_config.get("oauth_client_secret")
        ):
            raise ValidationAppError(
                "OAuth2 client credentials require oauth_client_id and oauth_client_secret"
            )

    def _enforce_concurrent_limit(self, *, exclude_id: str | None = None) -> None:
        running = self._simulations.count_by_status(SimulationStatus.RUNNING)
        if exclude_id:
            simulation = self._simulations.get_by_id(exclude_id)
            if simulation and simulation.status == SimulationStatus.RUNNING.value:
                running -= 1
        if running >= self._settings.scheduler_max_concurrent_simulations:
            raise ValidationAppError(
                "Maximum concurrent running simulations reached",
                details={
                    "max_concurrent_simulations": (
                        self._settings.scheduler_max_concurrent_simulations
                    )
                },
            )

    def _ensure_runtime_state(self, simulation: Simulation) -> dict[str, Any]:
        if not simulation.runtime_state:
            simulation.runtime_state = default_runtime_state()
        return dict(simulation.runtime_state)

    def _to_event_summary(self, event: EventInstance) -> EventInstanceSummaryResponse:
        attempt = event.delivery_attempts[-1] if event.delivery_attempts else None
        fault_meta = (event.simulator_metadata or {}).get("fault_injection", {})
        return EventInstanceSummaryResponse(
            id=event.id,
            simulation_id=event.simulation_id,
            product_id=event.product_id,
            scenario_id=event.scenario_id,
            event_kind=event.event_kind,
            action_id=event.action_id,
            correlation_id=event.correlation_id,
            status=event.status,
            payload_source=event.payload_source,
            generated_at=event.generated_at,
            delivery_success=event.status == EventInstanceStatus.DELIVERED.value
            if attempt
            else None,
            response_status_code=attempt.response_status_code if attempt else None,
            latency_ms=attempt.latency_ms if attempt else None,
            fault_modified=bool(fault_meta.get("intentionally_modified")),
        )

    def _to_event_detail(self, event: EventInstance) -> EventInstanceResponse:
        return EventInstanceResponse(
            id=event.id,
            simulation_id=event.simulation_id,
            product_id=event.product_id,
            scenario_id=event.scenario_id,
            event_kind=event.event_kind,
            action_id=event.action_id,
            fidelity_mode=event.fidelity_mode,
            payload=event.payload,
            correlation_id=event.correlation_id,
            status=event.status,
            payload_source=event.payload_source,
            replayed_from_event_id=event.replayed_from_event_id,
            simulator_metadata=event.simulator_metadata or {},
            generated_at=event.generated_at,
            delivery_attempts=[
                self._to_attempt_response(attempt) for attempt in event.delivery_attempts
            ],
        )

    def _to_attempt_response(self, attempt: DeliveryAttempt) -> DeliveryAttemptResponse:
        response = DeliveryAttemptResponse.model_validate(attempt)
        if attempt.success:
            response.error_category = None
        response.error_explanation = explain_error_category(response.error_category)
        return response
