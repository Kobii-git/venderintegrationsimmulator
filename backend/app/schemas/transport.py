from typing import Any, Literal, Self

from app.core.http_url import reject_embedded_url_credentials, split_url_query
from app.schemas.simulation import AuthConfigInput, DestinationConfig
from app.transports.delivery_result import DeliveryResult
from pydantic import BaseModel, ConfigDict, Field, model_validator

HttpMethod = Literal["GET", "POST", "PUT", "HEAD"]
SyslogProtocol = Literal["udp", "tcp", "tls"]
SyslogFormat = Literal["rfc3164", "rfc5424", "raw"]
TcpFraming = Literal["newline", "octet_counting"]


class HttpTransportRequest(BaseModel):
    """Request payload for HTTP transport operations."""

    model_config = ConfigDict(extra="forbid")

    url: str
    method: HttpMethod = "POST"
    headers: dict[str, str] = Field(default_factory=dict)
    query_params: dict[str, Any] = Field(default_factory=dict)
    body: Any | None = None
    content_type: str = "application/json"
    auth_config: AuthConfigInput = Field(default_factory=AuthConfigInput)
    timeout_seconds: int = Field(default=30, ge=1, le=300)
    verify_tls: bool = True
    follow_redirects: bool = True
    sensitive_header_names: list[str] = Field(default_factory=list)
    sensitive_query_names: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def reject_url_user_info(self) -> Self:
        reject_embedded_url_credentials(self.url)
        self.url, inline_query = split_url_query(self.url)
        for name, value in inline_query:
            if name in self.query_params:
                raise ValueError("Duplicate query parameter names are not allowed")
            self.query_params[name] = value
            if name not in self.sensitive_query_names:
                self.sensitive_query_names.append(name)
        return self


class HttpTestConnectionRequest(HttpTransportRequest):
    """Defaults to HEAD for low-impact destination probing."""

    method: HttpMethod = "HEAD"
    body: Any | None = None


class HttpSendRequest(HttpTransportRequest):
    """Send a one-off generic HTTP payload for diagnostics."""


class SyslogTransportRequest(BaseModel):
    """Request payload for syslog transport operations."""

    model_config = ConfigDict(extra="forbid")

    host: str
    port: int = Field(default=514, ge=1, le=65535)
    protocol: SyslogProtocol = "udp"
    format: SyslogFormat = "rfc5424"
    facility: int = Field(default=16, ge=0, le=23)
    severity: int = Field(default=6, ge=0, le=7)
    syslog_hostname: str | None = None
    app_name: str = Field(default="integration-simulator", max_length=48)
    proc_id: str = Field(default="-", max_length=128)
    msg_id: str = Field(default="-", max_length=32)
    tcp_framing: TcpFraming = "newline"
    rate_limit_per_second: float | None = Field(default=None, ge=0.1, le=1000.0)
    timeout_seconds: int = Field(default=10, ge=1, le=300)
    verify_tls: bool = True
    message: str = Field(default="integration-simulator connection test")
    content_type: str = "text/plain"


class DeliveryResultResponse(BaseModel):
    success: bool
    reached_server: bool
    started_at: str
    completed_at: str
    latency_ms: int
    destination: str
    method: str
    request_headers_redacted: dict[str, str] = Field(default_factory=dict)
    request_body: str | None = None
    response_status_code: int | None = None
    response_headers_redacted: dict[str, str] = Field(default_factory=dict)
    response_body: str | None = None
    error_message: str | None = None
    error_category: str | None = None
    delivery_confirmation: str = "confirmed"
    delivery_note: str | None = None

    @classmethod
    def from_delivery_result(cls, result: DeliveryResult) -> "DeliveryResultResponse":
        return cls(
            success=result.success,
            reached_server=result.reached_server,
            started_at=result.started_at.isoformat(),
            completed_at=result.completed_at.isoformat(),
            latency_ms=result.latency_ms,
            destination=result.destination,
            method=result.method,
            request_headers_redacted=result.request_headers_redacted,
            request_body=result.request_body,
            response_status_code=result.response_status_code,
            response_headers_redacted=result.response_headers_redacted,
            response_body=result.response_body,
            error_message=result.error_message,
            error_category=result.error_category,
            delivery_confirmation=result.delivery_confirmation,
            delivery_note=result.delivery_note,
        )


class HttpDeliveryResultResponse(DeliveryResultResponse):
    """Backward-compatible alias for HTTP transport responses."""


class AzureTransportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    destination: "DestinationConfig"
    auth_config: AuthConfigInput = Field(default_factory=AuthConfigInput)
    record: dict[str, Any] | None = None

    @model_validator(mode="after")
    def azure_only(self) -> Self:
        if self.destination.transport_id not in {"azure_logs_ingestion", "azure_function_app"}:
            raise ValueError("An Azure ingestion destination is required")
        return self
