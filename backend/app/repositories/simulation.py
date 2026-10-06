from datetime import datetime

from app.core.exceptions import NotFoundError
from app.domain.enums import SimulationStatus
from app.models import DeliveryAttempt, EventInstance, Simulation
from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased, joinedload


class SimulationRepository:
    """Persistence layer for simulations."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def list_all(self) -> list[Simulation]:
        return self._db.query(Simulation).order_by(Simulation.created_at.desc()).all()

    def list_by_status(self, status: SimulationStatus) -> list[Simulation]:
        return (
            self._db.query(Simulation)
            .filter(Simulation.status == status.value)
            .order_by(Simulation.created_at.desc())
            .all()
        )

    def count_by_status(self, status: SimulationStatus) -> int:
        return self._db.query(Simulation).filter(Simulation.status == status.value).count()

    def list_by_product_and_mode(
        self, product_id: str, simulation_mode: str, status: str
    ) -> list[Simulation]:
        return (
            self._db.query(Simulation)
            .filter(
                Simulation.product_id == product_id,
                Simulation.simulation_mode == simulation_mode,
                Simulation.status == status,
            )
            .order_by(Simulation.updated_at.desc())
            .all()
        )

    def get_by_id(self, simulation_id: str) -> Simulation | None:
        return self._db.get(Simulation, simulation_id)

    def get_by_id_or_raise(self, simulation_id: str) -> Simulation:
        simulation = self.get_by_id(simulation_id)
        if simulation is None:
            raise NotFoundError(f"Simulation not found: {simulation_id}")
        return simulation

    def create(self, simulation: Simulation) -> Simulation:
        self._db.add(simulation)
        if self._db.info.get("batch_writes"):
            self._db.flush()
        else:
            self._db.commit()
        self._db.refresh(simulation)
        return simulation

    def update(self, simulation: Simulation) -> Simulation:
        if self._db.info.get("batch_writes"):
            self._db.flush()
        else:
            self._db.commit()
        self._db.refresh(simulation)
        return simulation

    def delete(self, simulation: Simulation) -> None:
        self._db.delete(simulation)
        self._db.commit()


class EventInstanceRepository:
    """Persistence layer for generated event instances."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def create(self, event: EventInstance) -> EventInstance:
        self._db.add(event)
        if self._db.info.get("batch_writes"):
            self._db.flush()
        else:
            self._db.commit()
        self._db.refresh(event)
        return event

    def update(self, event: EventInstance) -> EventInstance:
        if self._db.info.get("batch_writes"):
            self._db.flush()
        else:
            self._db.commit()
        self._db.refresh(event)
        return event

    def get_by_id(self, event_id: str) -> EventInstance | None:
        return (
            self._db.query(EventInstance)
            .options(joinedload(EventInstance.delivery_attempts))
            .filter(EventInstance.id == event_id)
            .one_or_none()
        )

    def list_for_simulation(
        self,
        simulation_id: str,
        *,
        limit: int = 100,
        scenario_id: str | None = None,
        success: bool | None = None,
        http_status: int | None = None,
        correlation_id: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> list[EventInstance]:
        query = (
            self._db.query(EventInstance)
            .options(joinedload(EventInstance.delivery_attempts))
            .filter(EventInstance.simulation_id == simulation_id)
        )
        if scenario_id:
            query = query.filter(EventInstance.scenario_id == scenario_id)
        if correlation_id:
            query = query.filter(EventInstance.correlation_id == correlation_id)
        if since:
            query = query.filter(EventInstance.generated_at >= since)
        if until:
            query = query.filter(EventInstance.generated_at <= until)
        if success is not None:
            query = query.filter(
                EventInstance.status == "delivered"
                if success
                else EventInstance.status.in_(["failed", "partial"])
            )
        if http_status is not None:
            previous = aliased(DeliveryAttempt)
            latest = (
                select(func.max(previous.attempt_number))
                .where(
                    previous.event_instance_id == EventInstance.id,
                    previous.target_id.is_not_distinct_from(DeliveryAttempt.target_id),
                )
                .correlate(EventInstance, DeliveryAttempt)
                .scalar_subquery()
            )
            query = query.join(DeliveryAttempt).filter(
                DeliveryAttempt.attempt_number == latest,
                DeliveryAttempt.response_status_code == http_status,
            )

        return query.order_by(EventInstance.generated_at.desc()).limit(limit).all()

    def find_by_correlation_id(
        self,
        correlation_id: str,
        *,
        limit: int = 20,
    ) -> list[EventInstance]:
        return (
            self._db.query(EventInstance)
            .options(joinedload(EventInstance.delivery_attempts))
            .filter(EventInstance.correlation_id == correlation_id)
            .order_by(EventInstance.generated_at.desc())
            .limit(limit)
            .all()
        )


class DeliveryAttemptRepository:
    """Persistence layer for delivery attempts."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def create(self, attempt: DeliveryAttempt) -> DeliveryAttempt:
        self._db.add(attempt)
        if self._db.info.get("batch_writes"):
            self._db.flush()
        else:
            self._db.commit()
        self._db.refresh(attempt)
        return attempt
