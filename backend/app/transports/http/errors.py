import socket

import httpx
from app.domain.enums import DeliveryErrorCategory


def categorize_http_status(status_code: int) -> DeliveryErrorCategory | None:
    if 200 <= status_code < 300:
        return None
    if status_code in {401, 403}:
        return DeliveryErrorCategory.AUTH
    if status_code == 429:
        return DeliveryErrorCategory.RATE_LIMIT
    if 400 <= status_code < 500:
        return DeliveryErrorCategory.HTTP_4XX
    if 500 <= status_code < 600:
        return DeliveryErrorCategory.HTTP_5XX
    return DeliveryErrorCategory.UNKNOWN


def categorize_exception(exc: Exception) -> tuple[DeliveryErrorCategory, str]:
    if isinstance(exc, httpx.InvalidURL):
        return DeliveryErrorCategory.MALFORMED_DESTINATION, f"Invalid URL: {exc}"

    if isinstance(exc, httpx.ConnectTimeout):
        return DeliveryErrorCategory.CONNECTION_TIMEOUT, "Connection timed out"

    if isinstance(exc, httpx.ReadTimeout):
        return DeliveryErrorCategory.READ_TIMEOUT, "Read timed out"

    if isinstance(exc, httpx.WriteTimeout):
        return DeliveryErrorCategory.TIMEOUT, "Write timed out"

    if isinstance(exc, httpx.PoolTimeout):
        return DeliveryErrorCategory.TIMEOUT, "Pool timed out"

    if isinstance(exc, httpx.TimeoutException):
        return DeliveryErrorCategory.TIMEOUT, "Request timed out"

    if isinstance(exc, httpx.ConnectError):
        message = str(exc)
        root = exc.__cause__ or exc
        if isinstance(root, socket.gaierror) or "getaddrinfo" in message.lower():
            return DeliveryErrorCategory.DNS, f"DNS resolution failed: {message}"
        if "certificate" in message.lower() or "ssl" in message.lower():
            return DeliveryErrorCategory.TLS, f"TLS error: {message}"
        return DeliveryErrorCategory.CONNECTION, f"Connection failed: {message}"

    if isinstance(exc, httpx.HTTPError):
        message = str(exc)
        if "certificate" in message.lower() or "ssl" in message.lower():
            return DeliveryErrorCategory.TLS, f"TLS error: {message}"
        return DeliveryErrorCategory.UNKNOWN, message

    return DeliveryErrorCategory.INTERNAL, f"Unexpected error: {exc}"
