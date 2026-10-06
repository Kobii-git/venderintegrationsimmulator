import logging
from typing import Any

from sqlalchemy.orm import Session

from app.core.database import get_session_factory
from app.core.security import SecretEncryptor
from app.domain.enums import SimulationMode, SimulationStatus
from app.domain.runtime_state import utc_now_iso
from app.models import Simulation
from app.products.registry import ProductRegistry
from app.repositories.simulation import SimulationRepository
from app.schemas.event_instance import (
    CurlResponse,
    EventInstanceResponse,
    EventInstanceSummaryResponse,
    EventListFilters,
    ReplayEventResponse,
    WorkflowActionResponse,
)
from app.schemas.simulation import (
    SimulationBurstRequest,
    SimulationBurstResponse,
    SimulationResponse,
    SimulationSendResponse,
)
from app.services.simulation import SimulationService
from app.services.simulation_runtime import SimulationRuntimeService
from app.services.simulation_scheduler import SimulationScheduler
from app.services.transport_delivery import TransportDeliveryService

logger = logging.getLogger(__name__)


class SimulationOrchestrator:
    """Coordinates simulation lifecycle with the in-process scheduler."""

    def __init__(
        self,
        db: Session,
        product_registry: ProductRegistry,
        transport_service: TransportDeliveryService,
        encryptor: SecretEncryptor,
        scheduler: SimulationScheduler,
    ) -> None:
        self._db = db
        self._scheduler = scheduler
        self._runtime = SimulationRuntimeService(db, product_registry, transport_service, encryptor)
        self._catalog = SimulationService(db, product_registry, encryptor)
        self._repo = SimulationRepository(db)

    def start(self, simulation_id: str) -> SimulationResponse:
        simulation = self._runtime.start(simulation_id)
        if simulation.simulation_mode != SimulationMode.PULL_API.value:
            try:
                self._scheduler.register_simulation(simulation)
            except Exception as exc:
                runtime = dict(simulation.runtime_state or {})
                runtime["last_error_message"] = f"Scheduler registration failed: {exc}"
                runtime["last_error_at"] = utc_now_iso()
                runtime["stopped_at"] = runtime["last_error_at"]
                simulation.runtime_state = runtime
                simulation.status = SimulationStatus.ERROR.value
                self._repo.update(simulation)
                raise
        return self._catalog.get_simulation(simulation.id)

    def stop(self, simulation_id: str) -> SimulationResponse:
        simulation = self._repo.get_by_id_or_raise(simulation_id)
        simulation = self._runtime.stop(simulation_id)
        if simulation.simulation_mode != SimulationMode.PULL_API.value:
            self._scheduler.unregister_simulation(simulation_id)
        return self._catalog.get_simulation(simulation.id)

    async def send_once(
        self,
        simulation_id: str,
        *,
        payload_override: dict[str, Any] | None = None,
        scenario_id: str | None = None,
        preview_correlation_id: str | None = None,
        payload_edited: bool = False,
    ) -> SimulationSendResponse:
        return await self._runtime.send_once(
            simulation_id,
            payload_override=payload_override,
            scenario_id=scenario_id,
            preview_correlation_id=preview_correlation_id,
            payload_edited=payload_edited,
        )

    async def burst(
        self,
        simulation_id: str,
        request: SimulationBurstRequest,
    ) -> SimulationBurstResponse:
        return await self._runtime.burst(simulation_id, request)

    async def replay_event(
        self,
        simulation_id: str,
        event_id: str,
        *,
        mode: str,
    ) -> ReplayEventResponse:
        return await self._runtime.replay_event(simulation_id, event_id, mode=mode)  # type: ignore[arg-type]

    async def execute_action(self, simulation_id: str, action_id: str) -> WorkflowActionResponse:
        return await self._runtime.execute_action(simulation_id, action_id)

    def list_events(
        self,
        simulation_id: str,
        filters: EventListFilters | None = None,
    ) -> list[EventInstanceSummaryResponse]:
        return self._runtime.list_events(simulation_id, filters)

    def find_events_by_correlation_id(
        self,
        correlation_id: str,
        *,
        limit: int = 20,
    ) -> list[EventInstanceSummaryResponse]:
        return self._runtime.find_events_by_correlation_id(correlation_id, limit=limit)

    def get_event(self, simulation_id: str, event_id: str) -> EventInstanceResponse:
        return self._runtime.get_event(simulation_id, event_id)

    def get_event_curl(
        self, simulation_id: str, event_id: str, *, attempt_id: str | None = None
    ) -> CurlResponse:
        return self._runtime.get_event_curl(simulation_id, event_id, attempt_id=attempt_id)


def build_simulation_scheduler(
    product_registry: ProductRegistry,
    transport_service: TransportDeliveryService,
    encryptor: SecretEncryptor,
) -> SimulationScheduler:
    session_factory = get_session_factory()

    async def tick_handler(simulation_id: str) -> None:
        db = session_factory()
        try:
            runtime = SimulationRuntimeService(db, product_registry, transport_service, encryptor)
            await runtime.tick(simulation_id)
        except Exception:
            logger.exception("Scheduler tick failed", extra={"simulation_id": simulation_id})
        finally:
            db.close()

    def simulation_provider(simulation_id: str) -> Simulation | None:
        db = session_factory()
        try:
            return SimulationRepository(db).get_by_id(simulation_id)
        finally:
            db.close()

    return SimulationScheduler(tick_handler, simulation_provider)


def recover_simulations_on_startup(
    product_registry: ProductRegistry,
    transport_service: TransportDeliveryService,
    encryptor: SecretEncryptor,
    scheduler: SimulationScheduler,
) -> tuple[int, int]:
    session_factory = get_session_factory()
    db = session_factory()
    try:
        runtime = SimulationRuntimeService(db, product_registry, transport_service, encryptor)
        running_before = len(SimulationRepository(db).list_by_status(SimulationStatus.RUNNING))
        scheduled = runtime.prepare_safe_resume()
        for simulation in scheduled:
            try:
                scheduler.register_simulation(simulation)
            except Exception as exc:
                state = dict(simulation.runtime_state or {})
                state["last_error_message"] = f"Restart scheduler registration failed: {exc}"
                state["last_error_at"] = utc_now_iso()
                state["stopped_at"] = state["last_error_at"]
                simulation.runtime_state = state
                simulation.status = SimulationStatus.ERROR.value
                SimulationRepository(db).update(simulation)
        running_after = len(SimulationRepository(db).list_by_status(SimulationStatus.RUNNING))
        return running_before - running_after, running_after
    finally:
        db.close()
