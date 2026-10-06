from app import __version__
from app.core.config import settings
from app.schemas.simulation import VersionResponse
from fastapi import APIRouter

router = APIRouter(tags=["meta"])


@router.get("/version", response_model=VersionResponse)
def get_version() -> VersionResponse:
    """Return application version and environment metadata."""
    return VersionResponse(
        app_name=settings.app_name,
        version=__version__,
        environment=settings.app_environment.value,
    )
