import logging
from collections.abc import Awaitable, Callable
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.core.config import get_settings
from app.domain.enums import ScheduleType, SimulationStatus
from app.models import Simulation

logger = logging.getLogger(__name__)

TickHandler = Callable[[str], Awaitable[None]]
SimulationProvider = Callable[[str], Simulation | None]


class SimulationScheduler:
    """In-process scheduler for running simulations using APScheduler."""

    def __init__(
        self,
        tick_handler: TickHandler,
        simulation_provider: SimulationProvider,
    ) -> None:
        self._tick_handler = tick_handler
        self._simulation_provider = simulation_provider
        self._scheduler = AsyncIOScheduler()
        self._settings = get_settings()

    @property
    def is_running(self) -> bool:
        return bool(self._scheduler.running)

    def start(self, *, paused: bool = False) -> None:
        if not self._scheduler.running:
            self._scheduler.start(paused=paused)
            logger.info("Simulation scheduler started")

    def resume(self) -> None:
        if self._scheduler.running:
            self._scheduler.resume()

    def shutdown(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            logger.info("Simulation scheduler stopped")

    def register_simulation(self, simulation: Simulation) -> None:
        schedule = simulation.schedule or {}
        schedule_type = schedule.get("type")
        if schedule_type == "interval":
            schedule_type = ScheduleType.CONTINUOUS.value
        if schedule_type not in {ScheduleType.CONTINUOUS.value, ScheduleType.FINITE.value}:
            return

        interval_seconds = (
            0.1
            if schedule.get("events_per_second") is not None
            else schedule.get("interval_seconds")
        )
        if interval_seconds is None:
            raise ValueError("interval_seconds is required for scheduled simulations")

        job_id = self._job_id(simulation.id)
        if self._scheduler.get_job(job_id):
            logger.debug("Scheduler job already exists", extra={"simulation_id": simulation.id})
            return

        self._scheduler.add_job(
            self._run_tick,
            trigger=IntervalTrigger(seconds=interval_seconds),
            id=job_id,
            args=[simulation.id],
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        logger.info(
            "Registered simulation scheduler job",
            extra={"simulation_id": simulation.id, "interval_seconds": interval_seconds},
        )

    def unregister_simulation(self, simulation_id: str) -> None:
        job_id = self._job_id(simulation_id)
        if self._scheduler.get_job(job_id):
            self._scheduler.remove_job(job_id)
            logger.info(
                "Unregistered simulation scheduler job", extra={"simulation_id": simulation_id}
            )

    def has_job(self, simulation_id: str) -> bool:
        return self._scheduler.get_job(self._job_id(simulation_id)) is not None

    def register_maintenance(
        self, job_id: str, handler: Callable[[], Any], *, interval_seconds: int
    ) -> None:
        self._scheduler.add_job(
            handler,
            trigger=IntervalTrigger(seconds=interval_seconds),
            id=f"maintenance-{job_id}",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )

    async def _run_tick(self, simulation_id: str) -> None:
        simulation = self._simulation_provider(simulation_id)
        if simulation is None or simulation.status != SimulationStatus.RUNNING.value:
            self.unregister_simulation(simulation_id)
            return

        await self._tick_handler(simulation_id)

        simulation = self._simulation_provider(simulation_id)
        if simulation is None:
            return
        if simulation.status != SimulationStatus.RUNNING.value:
            self.unregister_simulation(simulation_id)

    @staticmethod
    def _job_id(simulation_id: str) -> str:
        return f"simulation-{simulation_id}"


def create_db_session_factory() -> Callable[[], Any]:
    from app.core.database import get_session_factory

    return get_session_factory()
