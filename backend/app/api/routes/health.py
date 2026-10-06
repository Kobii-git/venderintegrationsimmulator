from app import __version__
from app.api.deps import get_product_registry
from app.core.database import get_db
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict[str, str]:
    """Liveness/readiness probe for container orchestration."""
    return {
        "status": "ok",
        "version": __version__,
    }


@router.get("/ready")
def readiness(request: Request, db: Session = Depends(get_db)) -> dict[str, object]:
    checks = {"database": False, "catalog": False, "runtime": False}
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = True
        checks["catalog"] = bool(get_product_registry().list_products())
        scheduler = getattr(request.app.state, "simulation_scheduler", None)
        checks["runtime"] = bool(scheduler and scheduler.is_running)
    except Exception:
        pass
    if not all(checks.values()):
        raise HTTPException(status_code=503, detail=checks)
    return {"status": "ready", "checks": checks, "version": __version__}


@router.get("/metrics")
def lab_metrics(db: Session = Depends(get_db)) -> dict[str, object]:
    """Small operational snapshot, protected with management routes by the gateway."""
    import resource
    import sys
    from pathlib import Path

    from app.models import DeliveryJob
    from sqlalchemy import func

    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    rss_bytes = int(rss if sys.platform == "darwin" else rss * 1024)
    if sys.platform.startswith("linux"):
        import os

        rss_bytes = int(Path("/proc/self/statm").read_text().split()[1]) * os.sysconf(
            "SC_PAGE_SIZE"
        )
    queues = db.query(DeliveryJob.status, func.count()).group_by(DeliveryJob.status).all()
    return {"rss_bytes": rss_bytes, "delivery_jobs": {status: count for status, count in queues}}
