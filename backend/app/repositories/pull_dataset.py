from __future__ import annotations

from datetime import datetime

from app.models import PullDatasetActivation, PullDatasetItem
from sqlalchemy.orm import Session


class PullDatasetRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def replace(
        self,
        activation: PullDatasetActivation,
        items: list[PullDatasetItem],
    ) -> PullDatasetActivation:
        self._db.query(PullDatasetActivation).filter(
            PullDatasetActivation.simulation_id == activation.simulation_id
        ).delete(synchronize_session=False)
        self._db.flush()
        self._db.add(activation)
        self._db.add_all(items)
        self._db.flush()
        return activation

    def get_activation(self, activation_id: str) -> PullDatasetActivation | None:
        return self._db.get(PullDatasetActivation, activation_id)

    def route_size(self, activation_id: str, route_id: str) -> int:
        return (
            self._db.query(PullDatasetItem)
            .filter(
                PullDatasetItem.activation_id == activation_id, PullDatasetItem.route_id == route_id
            )
            .count()
        )

    def page(
        self,
        *,
        activation_id: str,
        route_id: str,
        offset: int,
        limit: int,
        since: datetime | None,
    ) -> tuple[list[PullDatasetItem], int]:
        query = self._db.query(PullDatasetItem).filter(
            PullDatasetItem.activation_id == activation_id,
            PullDatasetItem.route_id == route_id,
        )
        if since is not None:
            query = query.filter(PullDatasetItem.generated_at >= since)
        total = query.count()
        items = query.order_by(PullDatasetItem.sequence).offset(offset).limit(limit).all()
        return items, total

    def first(self, *, activation_id: str, route_id: str) -> PullDatasetItem | None:
        return (
            self._db.query(PullDatasetItem)
            .filter(
                PullDatasetItem.activation_id == activation_id,
                PullDatasetItem.route_id == route_id,
            )
            .order_by(PullDatasetItem.sequence)
            .first()
        )

    def list_route_items(
        self,
        *,
        activation_id: str,
        route_id: str,
        since: datetime | None = None,
    ) -> list[PullDatasetItem]:
        query = self._db.query(PullDatasetItem).filter(
            PullDatasetItem.activation_id == activation_id,
            PullDatasetItem.route_id == route_id,
        )
        if since is not None:
            query = query.filter(PullDatasetItem.generated_at >= since)
        return query.order_by(PullDatasetItem.sequence).all()
