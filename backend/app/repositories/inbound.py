from app.models import InboundRequestLog
from sqlalchemy.orm import Session


class InboundRequestRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def create(self, log: InboundRequestLog) -> InboundRequestLog:
        self._db.add(log)
        self._db.flush()
        return log

    def list_requests(
        self,
        simulation_id: str,
        *,
        limit: int = 50,
        request_kind: str | None = None,
    ) -> list[InboundRequestLog]:
        query = self._db.query(InboundRequestLog).filter(
            InboundRequestLog.simulation_id == simulation_id
        )
        if request_kind:
            query = query.filter(InboundRequestLog.request_kind == request_kind)
        return query.order_by(InboundRequestLog.received_at.desc()).limit(limit).all()

    def get_by_id(self, simulation_id: str, request_id: str) -> InboundRequestLog | None:
        return (
            self._db.query(InboundRequestLog)
            .filter(
                InboundRequestLog.simulation_id == simulation_id,
                InboundRequestLog.id == request_id,
            )
            .first()
        )

    def get_by_id_any(self, request_id: str) -> InboundRequestLog | None:
        return self._db.get(InboundRequestLog, request_id)

    def list_all(
        self,
        *,
        limit: int = 100,
        simulation_id: str | None = None,
        request_kind: str | None = None,
        response_status: int | None = None,
    ) -> list[InboundRequestLog]:
        query = self._db.query(InboundRequestLog)
        if simulation_id is not None:
            query = query.filter(InboundRequestLog.simulation_id == simulation_id)
        if request_kind is not None:
            query = query.filter(InboundRequestLog.request_kind == request_kind)
        if response_status is not None:
            query = query.filter(InboundRequestLog.response_status_code == response_status)
        return query.order_by(InboundRequestLog.received_at.desc()).limit(limit).all()
