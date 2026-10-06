from app.api.deps import get_simulation_orchestrator
from app.schemas.event_instance import (
    EventInstanceSummaryResponse,
)
from app.services.simulation_orchestrator import SimulationOrchestrator
from fastapi import APIRouter, Depends, Query

router = APIRouter(prefix="/events", tags=["events"])


@router.get("", response_model=list[EventInstanceSummaryResponse])
def search_events_by_correlation(
    correlation_id: str = Query(..., min_length=1),
    limit: int = Query(default=20, ge=1, le=100),
    orchestrator: SimulationOrchestrator = Depends(get_simulation_orchestrator),
) -> list[EventInstanceSummaryResponse]:
    """Find events across simulations by simulator correlation ID."""
    return orchestrator.find_events_by_correlation_id(correlation_id, limit=limit)
