"""SSRF awareness helpers for outbound webhook destinations.

This tool is intentionally outbound-HTTP-capable for integration testing.
Private-network destinations are allowed by default so engineers can test
against internal collectors, but deployments should restrict network access.
"""

from __future__ import annotations

import ipaddress
import logging
from urllib.parse import urlparse

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

PRIVATE_NETWORK_WARNING = (
    "Destination resolves to a private, loopback, or link-local address. "
    "This is permitted for internal integration testing but must not be exposed "
    "on an untrusted network without additional controls."
)


def is_private_or_reserved_host(host: str) -> bool:
    if not host:
        return False
    host_lower = host.lower()
    if host_lower in {"localhost", "127.0.0.1", "::1"}:
        return True
    try:
        addr = ipaddress.ip_address(host_lower.strip("[]"))
        return bool(
            addr.is_private
            or addr.is_loopback
            or addr.is_link_local
            or addr.is_reserved
            or addr.is_multicast
        )
    except ValueError:
        return False


def validate_destination_url(url: str, settings: Settings | None = None) -> list[str]:
    """Return non-blocking warnings for a destination URL."""
    settings = settings or get_settings()
    warnings: list[str] = []
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        warnings.append("Destination scheme should be http or https")
    if is_private_or_reserved_host(parsed.hostname or ""):
        warnings.append(PRIVATE_NETWORK_WARNING)
        if settings.ssrf_warn_on_private_destinations:
            logger.warning(
                "Private-network webhook destination configured",
                extra={"destination_host": parsed.hostname},
            )
    return warnings
