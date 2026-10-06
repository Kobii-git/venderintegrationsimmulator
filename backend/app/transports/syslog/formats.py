import json
from datetime import UTC, datetime

from app.transports.syslog.models import SyslogDestination


def priority(facility: int, severity: int) -> int:
    return facility * 8 + severity


def extract_message(payload: bytes, content_type: str) -> str:
    text = payload.decode("utf-8", errors="replace")
    if content_type == "application/json":
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return text
        if isinstance(parsed, dict) and "_syslog_message" in parsed:
            return str(parsed["_syslog_message"])
        if isinstance(parsed, str):
            return parsed
        return json.dumps(parsed, separators=(",", ":"), ensure_ascii=False)
    return text


def format_rfc3164(message: str, config: SyslogDestination) -> str:
    now = datetime.now(UTC)
    timestamp = now.strftime("%b ") + f"{now.day:2d}" + now.strftime(" %H:%M:%S")
    hostname = config.syslog_hostname or "-"
    tag = config.app_name[:32]
    pri = priority(config.facility, config.severity)
    return f"<{pri}>{timestamp} {hostname} {tag}: {message}"


def format_rfc5424(message: str, config: SyslogDestination) -> str:
    now = datetime.now(UTC)
    timestamp = now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"
    hostname = config.syslog_hostname or "-"
    app_name = config.app_name or "-"
    proc_id = config.proc_id or "-"
    msg_id = config.msg_id or "-"
    pri = priority(config.facility, config.severity)
    return f"<{pri}>1 {timestamp} {hostname} {app_name} {proc_id} {msg_id} - {message}"


def format_raw(message: str, _config: SyslogDestination) -> str:
    return message


def format_syslog_message(
    payload: bytes,
    content_type: str,
    config: SyslogDestination,
) -> str:
    message = extract_message(payload, content_type)
    if config.format == "raw":
        return format_raw(message, config)
    if config.format == "rfc3164":
        return format_rfc3164(message, config)
    return format_rfc5424(message, config)


def frame_message(message: str, framing: str) -> bytes:
    encoded = message.encode("utf-8")
    if framing == "octet_counting":
        return f"{len(encoded)} ".encode("ascii") + encoded
    if "\n" in message.rstrip("\n") or "\r" in message:
        raise ValueError("Newline framing cannot carry embedded CR/LF; use octet_counting")
    return encoded.rstrip(b"\n") + b"\n"
