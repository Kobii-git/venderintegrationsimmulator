import logging
from collections.abc import Iterable, Mapping
from typing import Any

from app.core.config import AppEnvironment, get_settings
from app.core.exceptions import AppError
from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError as PydanticValidationError

logger = logging.getLogger(__name__)


def _public_validation_errors(
    errors: Iterable[Mapping[str, Any]],
) -> list[dict[str, object]]:
    """Keep actionable validation metadata without echoing request inputs or exception context."""
    return [{key: error[key] for key in ("type", "loc", "msg") if key in error} for error in errors]


def register_exception_handlers(app: FastAPI) -> None:
    settings = get_settings()

    @app.exception_handler(AppError)
    async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": jsonable_encoder(exc.details),
                }
            },
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "Request validation failed",
                    "details": {
                        "errors": jsonable_encoder(_public_validation_errors(exc.errors()))
                    },
                }
            },
        )

    @app.exception_handler(PydanticValidationError)
    async def pydantic_validation_handler(
        _request: Request, exc: PydanticValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "Request validation failed",
                    "details": {
                        "errors": jsonable_encoder(_public_validation_errors(exc.errors()))
                    },
                }
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception")
        if settings.debug or settings.app_environment != AppEnvironment.PRODUCTION:
            message = str(exc)
        else:
            message = "An internal server error occurred"
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_error",
                    "message": message,
                    "details": {},
                }
            },
        )
