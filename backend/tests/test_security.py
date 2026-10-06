import logging

from app.core.logging import RedactingFilter
from app.core.redaction import redact_headers


def test_redact_headers_masks_sensitive_values() -> None:
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer secret",
        "X-Api-Key": "abc123",
    }
    redacted = redact_headers(headers)
    assert redacted["Content-Type"] == "application/json"
    assert redacted["Authorization"] == "***REDACTED***"
    assert redacted["X-Api-Key"] == "***REDACTED***"


def test_redacting_filter_masks_log_message_dict() -> None:
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg={"password": "secret", "event": "ok"},
        args=(),
        exc_info=None,
    )
    RedactingFilter().filter(record)
    assert record.msg["password"] == "***REDACTED***"
    assert record.msg["event"] == "ok"


def test_transport_exceptions_have_categories() -> None:
    from app.core.exceptions import DnsError, TransportTimeoutError
    from app.domain.enums import DeliveryErrorCategory

    assert DnsError("failed").category == DeliveryErrorCategory.DNS
    assert TransportTimeoutError("slow").category == DeliveryErrorCategory.TIMEOUT
