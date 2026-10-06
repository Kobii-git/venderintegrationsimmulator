from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

SyslogProtocol = Literal["udp", "tcp", "tls"]
SyslogFormat = Literal["rfc3164", "rfc5424", "raw"]
TcpFraming = Literal["newline", "octet_counting"]


class SyslogDestination(BaseModel):
    """Validated syslog destination configuration."""

    model_config = ConfigDict(extra="forbid")

    host: str = Field(min_length=1, max_length=255)
    port: int = Field(default=514, ge=1, le=65535)
    protocol: SyslogProtocol = "udp"
    format: SyslogFormat = "rfc5424"
    facility: int = Field(default=16, ge=0, le=23)
    severity: int = Field(default=6, ge=0, le=7)
    syslog_hostname: str | None = Field(default=None, max_length=255)
    app_name: str = Field(default="integration-simulator", max_length=48)
    proc_id: str = Field(default="-", max_length=128)
    msg_id: str = Field(default="-", max_length=32)
    tcp_framing: TcpFraming = "newline"
    rate_limit_per_second: float | None = Field(default=None, ge=0.1, le=1000.0)
    timeout_seconds: float = Field(default=10.0, ge=0.5, le=300.0)
    verify_tls: bool = True

    ca_file: str | None = None

    @field_validator("syslog_hostname", "app_name", "proc_id", "msg_id", "host")
    @classmethod
    def header_token(cls, value: str | None) -> str | None:
        if value is not None and (not value or any(ord(c) < 33 or ord(c) > 126 for c in value)):
            raise ValueError("Syslog header fields must contain printable ASCII without spaces")
        return value

    @property
    def summary(self) -> str:
        return f"{self.protocol.upper()}://{self.host}:{self.port}"
