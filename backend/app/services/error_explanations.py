"""Human-readable explanations for delivery error categories."""

from app.domain.enums import DeliveryErrorCategory

EXPLANATIONS: dict[str, str] = {
    DeliveryErrorCategory.DNS: "The destination hostname could not be resolved.",
    DeliveryErrorCategory.CONNECTION: (
        "A network connection to the destination could not be established."
    ),
    DeliveryErrorCategory.CONNECTION_TIMEOUT: (
        "The connection attempt timed out before reaching the server."
    ),
    DeliveryErrorCategory.READ_TIMEOUT: (
        "The server accepted the connection but did not respond in time."
    ),
    DeliveryErrorCategory.TIMEOUT: "The request timed out.",
    DeliveryErrorCategory.TLS: "TLS/SSL handshake or certificate verification failed.",
    DeliveryErrorCategory.MALFORMED_DESTINATION: "The destination URL is malformed or unusable.",
    DeliveryErrorCategory.AUTH: (
        "Authentication failed — check credentials configured on the simulation."
    ),
    DeliveryErrorCategory.RATE_LIMIT: "The destination returned a rate-limit response.",
    DeliveryErrorCategory.HTTP_4XX: (
        "The destination rejected the request with a client error (4xx)."
    ),
    DeliveryErrorCategory.HTTP_5XX: "The destination server returned an error (5xx).",
    DeliveryErrorCategory.INTERNAL: "An internal simulator error occurred during delivery.",
    DeliveryErrorCategory.UNKNOWN: "An unknown delivery error occurred.",
}


def explain_error_category(category: str | None) -> str | None:
    if not category:
        return None
    try:
        return EXPLANATIONS[DeliveryErrorCategory(category)]
    except ValueError:
        return EXPLANATIONS[DeliveryErrorCategory.UNKNOWN]
