import logging
from typing import Any

from app.core.config import AppEnvironment, get_settings
from app.core.redaction import REDACTED, redact_headers, redact_mapping, redact_string

logger = logging.getLogger(__name__)


class RedactingFilter(logging.Filter):
    """Remove or mask sensitive values from log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, dict):
            record.msg = redact_mapping(record.msg)
        elif isinstance(record.msg, str):
            record.msg = redact_string(record.msg)
        if record.args:
            record.args = tuple(
                redact_mapping(arg) if isinstance(arg, dict | list) else arg for arg in record.args
            )
        return True


class JsonFormatter(logging.Formatter):
    """Structured JSON log formatter."""

    def format(self, record: logging.LogRecord) -> str:
        import json

        payload: dict[str, Any] = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        for key in ("correlation_id", "simulation_id", "event_id"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        return json.dumps(payload, default=str)


def setup_logging() -> None:
    """Configure application logging with redaction."""
    settings = get_settings()
    level = getattr(logging, settings.log_level, logging.INFO)

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)

    handler = logging.StreamHandler()
    if settings.app_environment == AppEnvironment.PRODUCTION:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"))
    handler.addFilter(RedactingFilter())
    root.addHandler(handler)

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if settings.debug else logging.WARNING
    )


__all__ = ["REDACTED", "RedactingFilter", "redact_headers", "redact_mapping", "setup_logging"]
