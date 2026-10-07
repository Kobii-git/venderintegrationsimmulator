import math
import re
import uuid
from datetime import datetime
from ipaddress import ip_address
from typing import Any, Literal, Self
from urllib.parse import urlsplit

from app.core.http_url import reject_embedded_url_credentials, split_url_query
from app.domain.enums import FidelityMode, ScheduleType, SimulationMode
from app.domain.fault_config import FaultConfig
from app.domain.inbound import InboundConfig
from pydantic import BaseModel, ConfigDict, Field, model_serializer, model_validator

SyslogProtocol = Literal["udp", "tcp", "tls"]
SyslogFormat = Literal["rfc3164", "rfc5424", "raw"]
TcpFraming = Literal["newline", "octet_counting"]

FORCED_SENSITIVE_NAMES = frozenset(
    {"authorization", "proxy-authorization", "cookie", "set-cookie", "sig"}
)
SECRET_NAME_PATTERN = re.compile(
    r"(?:password|passwd|secret|token|api[-_]?key|code|signature)", re.I
)


class ConfiguredValueInput(BaseModel):
    """A named destination value. Sensitive values are write-only."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    value: str | None = None
    sensitive: bool = True

    @model_validator(mode="after")
    def enforce_sensitive_names(self) -> Self:
        self.name = self.name.strip()
        if not self.name:
            raise ValueError("name cannot be blank")
        normalized = self.name.casefold()
        if normalized in FORCED_SENSITIVE_NAMES or SECRET_NAME_PATTERN.search(normalized):
            self.sensitive = True
        return self


class ConfiguredValueResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    sensitive: bool
    has_value: bool
    value: str | None = None

    @model_serializer
    def serialize(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "name": self.name,
            "sensitive": self.sensitive,
            "has_value": self.has_value,
        }
        if not self.sensitive:
            result["value"] = self.value or ""
        return result


class DestinationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transport_id: str = "http_webhook"
    # HTTP webhook fields
    url: str | None = None
    method: str = "POST"
    headers: list[ConfiguredValueInput] = Field(default_factory=list)
    query_params: list[ConfiguredValueInput] = Field(default_factory=list)
    timeout_seconds: int = Field(default=30, ge=1, le=300)
    verify_tls: bool = True
    follow_redirects: bool = True
    ca_file: str | None = None
    endpoint: str | None = None
    dcr_immutable_id: str | None = None
    stream: str | None = None
    tenant_id: str | None = None
    batch_max_bytes: int = Field(default=950_000, ge=1024, le=1_000_000)
    max_retries: int = Field(default=3, ge=0, le=8)

    # Syslog fields
    host: str | None = None
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

    @model_validator(mode="after")
    def validate_destination_values(self) -> Self:
        # Accept 0.4.0 configurations while applying the new wire-size cap.
        self.batch_max_bytes = min(self.batch_max_bytes, 950_000)
        if self.transport_id == "azure_logs_ingestion":
            if (
                not self.endpoint
                or not self.endpoint.startswith("https://")
                or not self.dcr_immutable_id
                or not self.stream
                or not self.tenant_id
            ):
                raise ValueError(
                    "Azure ingestion requires an HTTPS endpoint, DCR immutable ID, "
                    "stream and tenant ID"
                )
            parsed_endpoint = urlsplit(self.endpoint)
            if (
                parsed_endpoint.username
                or parsed_endpoint.password
                or parsed_endpoint.query
                or parsed_endpoint.fragment
            ):
                raise ValueError("Azure endpoint cannot contain credentials, query or fragment")
        if self.transport_id == "cloudflare_logpush":
            self.method = "POST"
        if self.transport_id == "azure_function_app":
            parsed = urlsplit(self.url or "")
            if (
                parsed.scheme != "https"
                or not parsed.hostname
                or parsed.username
                or parsed.password
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError(
                    "Function App requires an HTTPS URL without credentials, query or fragment"
                )
            if self.headers or self.query_params:
                raise ValueError("Function App authentication uses the encrypted function key only")
            self.method = "POST"
            self.verify_tls = True
            self.follow_redirects = False
        if self.transport_id == "syslog" and self.host:
            from app.transports.syslog.models import SyslogDestination

            SyslogDestination.model_validate(
                {
                    key: value
                    for key, value in self.model_dump().items()
                    if key in SyslogDestination.model_fields
                }
            )
        if self.url:
            reject_embedded_url_credentials(self.url)
            parsed = urlsplit(self.url)
            if parsed.fragment:
                raise ValueError("URL fragments are not supported")
            self.url, inline_query = split_url_query(self.url)
            self.query_params.extend(
                ConfiguredValueInput(name=name, value=value, sensitive=True)
                for name, value in inline_query
            )
        self._validate_unique(self.headers, case_sensitive=False, label="header")
        self._validate_unique(self.query_params, case_sensitive=True, label="query parameter")
        return self

    @staticmethod
    def _validate_unique(
        values: list[ConfiguredValueInput], *, case_sensitive: bool, label: str
    ) -> None:
        names = [item.name if case_sensitive else item.name.casefold() for item in values]
        if len(names) != len(set(names)):
            raise ValueError(f"Duplicate {label} names are not allowed")


class DestinationConfigResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transport_id: str = "http_webhook"
    url: str | None = None
    method: str = "POST"
    headers: list[ConfiguredValueResponse] = Field(default_factory=list)
    query_params: list[ConfiguredValueResponse] = Field(default_factory=list)
    timeout_seconds: int = 30
    verify_tls: bool = True
    follow_redirects: bool = True
    ca_file: str | None = None
    endpoint: str | None = None
    dcr_immutable_id: str | None = None
    stream: str | None = None
    tenant_id: str | None = None
    batch_max_bytes: int = Field(default=950_000, ge=1024, le=1_000_000)
    max_retries: int = Field(default=3, ge=0, le=8)

    host: str | None = None
    port: int = 514
    protocol: SyslogProtocol = "udp"
    format: SyslogFormat = "rfc5424"
    facility: int = 16
    severity: int = 6
    syslog_hostname: str | None = None
    app_name: str = "integration-simulator"
    proc_id: str = "-"
    msg_id: str = "-"
    tcp_framing: TcpFraming = "newline"
    rate_limit_per_second: float | None = None


class AuthConfigInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    auth_method_id: str = "none"
    username: str | None = None
    password: str | None = None
    token: str | None = None
    oauth_client_id: str | None = None
    oauth_client_secret: str | None = None
    header_name: str | None = None
    header_prefix: str | None = None


class AuthConfigResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    auth_method_id: str = "none"
    username: str | None = None
    header_name: str | None = None
    header_prefix: str | None = None
    has_password: bool = False
    has_token: bool = False
    oauth_client_id: str | None = None
    has_oauth_client_secret: bool = False


class ScheduleConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: ScheduleType = ScheduleType.MANUAL
    interval_seconds: int | None = Field(default=None, ge=1)
    events_per_second: float | None = Field(default=None, ge=0.1, le=100)
    scenario_weights: dict[str, float] = Field(default_factory=dict)
    user_pool: list[str] = Field(default_factory=list, max_length=1000)
    incident_preset: (
        Literal["password_spray", "privileged_logon", "firewall_scan", "malware_detection"] | None
    ) = None
    event_count: int | None = Field(default=None, ge=1)
    next_run_at: datetime | None = None

    @model_validator(mode="after")
    def validate_schedule(self) -> Self:
        if self.events_per_second is not None and self.interval_seconds is not None:
            raise ValueError("events_per_second and interval_seconds are mutually exclusive")
        if any(not math.isfinite(v) or v <= 0 for v in self.scenario_weights.values()):
            raise ValueError("Scenario weights must be finite and positive")
        if any(
            not name or len(name) > 255 or any(ord(c) < 32 for c in name) for name in self.user_pool
        ):
            raise ValueError("User pool names must contain 1–255 printable characters")
        if (
            self.type in {ScheduleType.CONTINUOUS, ScheduleType.FINITE}
            and self.interval_seconds is None
            and self.events_per_second is None
        ):
            raise ValueError("interval_seconds is required for continuous and finite schedules")
        if self.type == ScheduleType.FINITE and self.event_count is None:
            raise ValueError("event_count is required when schedule type is finite")
        return self


class SimulationRuntimeStats(BaseModel):
    model_config = ConfigDict(extra="ignore")

    events_generated: int = 0
    events_attempted: int = 0
    events_successful: int = 0
    events_failed: int = 0
    events_partial: int = 0
    last_delivery_at: str | None = None
    last_http_status: int | None = None
    last_latency_ms: int | None = None
    last_error_message: str | None = None
    last_event_id: str | None = None
    started_at: str | None = None
    stopped_at: str | None = None
    last_error_at: str | None = None
    interrupted_on_restart: bool = False
    inbound_requests_total: int = 0
    inbound_requests_successful: int = 0
    inbound_requests_failed: int = 0
    inbound_items_returned_total: int = 0
    last_inbound_at: str | None = None
    last_inbound_items: int | None = None
    pull_dataset_activation_id: str | None = None
    pull_dataset_item_count: int = 0


class SimulatedDevice(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), min_length=1, max_length=64)
    hostname: str = Field(min_length=1, max_length=255, pattern=r"^[!-~]+$")
    ip_address: str
    vendor: str | None = None

    @model_validator(mode="after")
    def valid_address(self) -> Self:
        ip_address(self.ip_address)
        return self


class TargetInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), min_length=1, max_length=64)
    name: str = Field(default="Primary", min_length=1, max_length=255)
    enabled: bool = True
    destination: DestinationConfig
    auth_config: AuthConfigInput = Field(default_factory=AuthConfigInput)
    payload_format: Literal[
        "default",
        "native",
        "cef",
        "json",
        "xml",
        "csv",
        "SecurityEvent",
        "WindowsEvent",
        "CommonSecurityLog",
    ] = "default"
    device_ids: list[str] = Field(default_factory=list)
    scenario_ids: list[str] = Field(default_factory=list)
    queue_limit: int = Field(default=10000, ge=1, le=100000)


class TargetResponse(BaseModel):
    id: str
    name: str
    enabled: bool
    destination: DestinationConfigResponse
    auth_config: AuthConfigResponse
    payload_format: str
    device_ids: list[str]
    scenario_ids: list[str]
    queue_limit: int
    stats: dict[str, Any] = Field(default_factory=dict)


class SimulationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    product_id: str = Field(min_length=1, max_length=64)
    scenario_id: str | None = Field(default=None, min_length=1, max_length=64)
    scenario_ids: list[str] = Field(default_factory=list)
    simulation_mode: SimulationMode = SimulationMode.PUSH_WEBHOOK
    fidelity_mode: FidelityMode = FidelityMode.VENDOR_ACCURATE
    destination: DestinationConfig = Field(default_factory=DestinationConfig)
    auth_config: AuthConfigInput = Field(default_factory=AuthConfigInput)
    targets: list[TargetInput] | None = Field(default=None, min_length=1, max_length=16)
    devices: list[SimulatedDevice] = Field(default_factory=list)
    replay_config: dict[str, Any] = Field(default_factory=dict)
    scenario_overrides: dict[str, dict[str, Any]] = Field(default_factory=dict)
    schedule: ScheduleConfig = Field(default_factory=ScheduleConfig)
    random_seed: int | None = None
    fault_config: FaultConfig = Field(default_factory=FaultConfig)
    inbound_config: InboundConfig = Field(default_factory=InboundConfig)

    @model_validator(mode="after")
    def validate_scenarios(self) -> Self:
        if self.targets is not None:
            if {"destination", "auth_config"} & self.model_fields_set:
                raise ValueError("Use targets or legacy destination/auth_config, not both")
            if len({t.id for t in self.targets}) != len(self.targets):
                raise ValueError("Target IDs must be unique")
        if len({d.id for d in self.devices}) != len(self.devices):
            raise ValueError("Device IDs must be unique")
        if not self.scenario_ids and not self.scenario_id:
            raise ValueError("scenario_id or scenario_ids is required")
        if not self.scenario_ids and self.scenario_id:
            self.scenario_ids = [self.scenario_id]
        if not self.scenario_id and self.scenario_ids:
            self.scenario_id = self.scenario_ids[0]
        return self


class SimulationUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=255)
    scenario_id: str | None = Field(default=None, min_length=1, max_length=64)
    scenario_ids: list[str] | None = None
    simulation_mode: SimulationMode | None = None
    fidelity_mode: FidelityMode | None = None
    destination: DestinationConfig | None = None
    auth_config: AuthConfigInput | None = None
    targets: list[TargetInput] | None = Field(default=None, min_length=1, max_length=16)
    devices: list[SimulatedDevice] | None = None
    replay_config: dict[str, Any] | None = None
    scenario_overrides: dict[str, dict[str, Any]] | None = None
    schedule: ScheduleConfig | None = None
    random_seed: int | None = None
    fault_config: FaultConfig | None = None
    inbound_config: InboundConfig | None = None

    @model_validator(mode="after")
    def exclusive_targets(self) -> Self:
        if self.devices is not None and len({d.id for d in self.devices}) != len(self.devices):
            raise ValueError("Device IDs must be unique")
        if self.targets is not None and ({"destination", "auth_config"} & self.model_fields_set):
            raise ValueError("Use targets or legacy destination/auth_config, not both")
        if self.targets is not None and len({t.id for t in self.targets}) != len(self.targets):
            raise ValueError("Target IDs must be unique")
        return self


class SimulationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    product_id: str
    scenario_id: str
    scenario_ids: list[str]
    simulation_mode: str
    fidelity_mode: str
    status: str
    destination: DestinationConfigResponse
    auth_config: AuthConfigResponse
    targets: list[TargetResponse] = Field(default_factory=list)
    devices: list[SimulatedDevice] = Field(default_factory=list)
    replay_config: dict[str, Any] = Field(default_factory=dict)
    scenario_overrides: dict[str, dict[str, Any]]
    schedule: dict[str, Any]
    fault_config: dict[str, Any]
    inbound_config: dict[str, Any]
    random_seed: int | None = None
    missing_secrets: list[str] = Field(default_factory=list)
    runtime_stats: SimulationRuntimeStats
    created_at: datetime
    updated_at: datetime


class SimulationSendResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    simulation_id: str
    event_id: str
    correlation_id: str
    scenario_id: str
    payload: dict[str, Any]
    payload_source: str = "generated"
    delivery_success: bool
    response_status_code: int | None = None
    latency_ms: int | None = None
    error_message: str | None = None


class SimulationBurstRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    count: int = Field(ge=1)
    interval_ms: int = Field(default=0, ge=0)
    events_per_second: float | None = Field(default=None, ge=0.1)
    scenario_id: str | None = None
    confirm_large_run: bool = False


class SimulationBurstResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    simulation_id: str
    requested: int
    generated: int
    successful: int
    failed: int
    event_ids: list[str]
    faults_enabled: bool


class VersionResponse(BaseModel):
    app_name: str
    version: str
    environment: str
