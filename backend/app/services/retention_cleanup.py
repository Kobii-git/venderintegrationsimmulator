"""Retention cleanup for event and delivery history."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models import EventInstance, InboundRequestLog, OAuthAccessToken

logger = logging.getLogger(__name__)


def _rowcount(result: Any) -> int:
    return int(getattr(result, "rowcount", 0) or 0)


class RetentionCleanupService:
    """Prune old event history to prevent unbounded SQLite growth."""

    def __init__(self, db: Session, settings: Settings | None = None) -> None:
        self._db = db
        self._settings = settings or get_settings()

    def cleanup(self) -> dict[str, int]:
        try:
            deleted_by_age = self._delete_older_than_retention_days()
            deleted_by_count = self._enforce_per_simulation_limits()
            deleted_inbound = self._delete_inbound_logs_older_than_retention_days()
            deleted_oauth = self._delete_expired_oauth_tokens()
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise
        total = deleted_by_age + deleted_by_count + deleted_inbound + deleted_oauth
        if total:
            logger.info(
                "Retention cleanup completed",
                extra={
                    "deleted_by_age": deleted_by_age,
                    "deleted_by_count": deleted_by_count,
                    "deleted_inbound": deleted_inbound,
                    "deleted_oauth": deleted_oauth,
                },
            )
        return {
            "deleted_by_age": deleted_by_age,
            "deleted_by_count": deleted_by_count,
            "deleted_inbound": deleted_inbound,
            "deleted_oauth": deleted_oauth,
            "total": total,
        }

    def _delete_older_than_retention_days(self) -> int:
        cutoff = datetime.now(UTC) - timedelta(days=self._settings.event_retention_days)
        stmt = delete(EventInstance).where(
            EventInstance.generated_at < cutoff, EventInstance.status != "pending"
        )
        result = self._db.execute(stmt, execution_options={"synchronize_session": False})
        return _rowcount(result)

    def _enforce_per_simulation_limits(self) -> int:
        max_per_sim = self._settings.event_retention_max_per_simulation
        simulation_ids = (
            self._db.execute(select(EventInstance.simulation_id).distinct()).scalars().all()
        )

        deleted = 0
        for simulation_id in simulation_ids:
            count = self._db.execute(
                select(func.count())
                .select_from(EventInstance)
                .where(EventInstance.simulation_id == simulation_id)
            ).scalar_one()
            if count <= max_per_sim:
                continue

            overflow = count - max_per_sim
            oldest_ids = (
                self._db.execute(
                    select(EventInstance.id)
                    .where(
                        EventInstance.simulation_id == simulation_id,
                        EventInstance.status != "pending",
                    )
                    .order_by(EventInstance.generated_at.asc())
                    .limit(overflow)
                )
                .scalars()
                .all()
            )
            if not oldest_ids:
                continue
            result = self._db.execute(
                delete(EventInstance).where(EventInstance.id.in_(oldest_ids)),
                execution_options={"synchronize_session": False},
            )
            deleted += _rowcount(result)

        return deleted

    def _delete_inbound_logs_older_than_retention_days(self) -> int:
        cutoff = datetime.now(UTC) - timedelta(days=self._settings.event_retention_days)
        stmt = delete(InboundRequestLog).where(InboundRequestLog.received_at < cutoff)
        result = self._db.execute(stmt, execution_options={"synchronize_session": False})
        return _rowcount(result)

    def _delete_expired_oauth_tokens(self) -> int:
        cutoff = datetime.now(UTC)
        stmt = delete(OAuthAccessToken).where(OAuthAccessToken.expires_at < cutoff)
        result = self._db.execute(stmt, execution_options={"synchronize_session": False})
        return _rowcount(result)
