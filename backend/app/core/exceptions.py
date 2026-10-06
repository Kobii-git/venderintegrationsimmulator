from typing import Any

from app.domain.enums import DeliveryErrorCategory


class AppError(Exception):
    """Base application error with HTTP mapping."""

    code: str = "app_error"
    status_code: int = 400

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class NotFoundError(AppError):
    code = "not_found"
    status_code = 404


class ValidationAppError(AppError):
    code = "validation_error"
    status_code = 422


class ConflictError(AppError):
    code = "conflict"
    status_code = 409


class TransportError(AppError):
    """Base transport/delivery error (for future delivery layer)."""

    code = "transport_error"
    status_code = 502
    category: DeliveryErrorCategory = DeliveryErrorCategory.UNKNOWN

    def __init__(
        self,
        message: str,
        *,
        category: DeliveryErrorCategory | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details=details)
        if category is not None:
            self.category = category


class DnsError(TransportError):
    code = "dns_error"
    category = DeliveryErrorCategory.DNS


class ConnectionTransportError(TransportError):
    code = "connection_error"
    category = DeliveryErrorCategory.UNKNOWN


class TlsError(TransportError):
    code = "tls_error"
    category = DeliveryErrorCategory.TLS


class TransportTimeoutError(TransportError):
    code = "timeout_error"
    category = DeliveryErrorCategory.TIMEOUT


class AuthenticationError(TransportError):
    code = "authentication_error"
    category = DeliveryErrorCategory.AUTH
    status_code = 401


class RateLimitError(TransportError):
    code = "rate_limit_error"
    category = DeliveryErrorCategory.HTTP_4XX
    status_code = 429
