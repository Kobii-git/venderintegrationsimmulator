"""Tests for syslog message formatting."""

from app.transports.syslog.formats import (
    extract_message,
    format_rfc3164,
    format_rfc5424,
    format_syslog_message,
    frame_message,
    priority,
)
from app.transports.syslog.models import SyslogDestination


def test_priority_calculation() -> None:
    assert priority(16, 6) == 134


def test_format_rfc5424_includes_version_and_fields() -> None:
    config = SyslogDestination(host="127.0.0.1", syslog_hostname="collector", app_name="demo")
    message = format_rfc5424("hello world", config)
    assert message.startswith("<134>1 ")
    assert " collector demo - - - hello world" in message


def test_format_rfc3164_includes_tag() -> None:
    config = SyslogDestination(host="127.0.0.1", app_name="demo")
    message = format_rfc3164("hello world", config)
    assert message.startswith("<134>")
    assert " demo: hello world" in message


def test_format_raw_preserves_message() -> None:
    config = SyslogDestination(host="127.0.0.1", format="raw")
    assert format_syslog_message(b"CEF:0|Vendor|App|1.0|1|Test|3|", "text/plain", config) == (
        "CEF:0|Vendor|App|1.0|1|Test|3|"
    )


def test_extract_message_from_json_payload() -> None:
    payload = b'{"event":"test","_syslog_message":"raw only"}'
    assert extract_message(payload, "application/json") == "raw only"


def test_frame_message_newline() -> None:
    assert frame_message("hello", "newline") == b"hello\n"


def test_frame_message_octet_counting() -> None:
    assert frame_message("hi", "octet_counting") == b"2 hi"
