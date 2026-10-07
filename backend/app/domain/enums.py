from enum import StrEnum


class FidelityMode(StrEnum):
    VENDOR_ACCURATE = "vendor_accurate"
    TROUBLESHOOTING = "troubleshooting"


class SimulationStatus(StrEnum):
    STOPPED = "stopped"
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"


class EventInstanceStatus(StrEnum):
    PARTIAL = "partial"
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PayloadSource(StrEnum):
    GENERATED = "generated"
    MANUAL_OVERRIDE = "manual_override"
    REPLAY_EXACT = "replay_exact"
    REPLAY_REGENERATE = "replay_regenerate"


class ScheduleType(StrEnum):
    MANUAL = "manual"
    CONTINUOUS = "continuous"
    FINITE = "finite"


class SimulationMode(StrEnum):
    PUSH_WEBHOOK = "push_webhook"
    PULL_API = "pull_api"


class DeliveryErrorCategory(StrEnum):
    RESPONSE_TOO_LARGE = "response_too_large"
    INVALID_RESPONSE = "invalid_response"
    REDIRECT_REJECTED = "redirect_rejected"
    DNS = "dns"
    CONNECTION = "connection"
    CONNECTION_TIMEOUT = "connection_timeout"
    READ_TIMEOUT = "read_timeout"
    TIMEOUT = "timeout"
    TLS = "tls"
    MALFORMED_DESTINATION = "malformed_destination"
    AUTH = "auth"
    RATE_LIMIT = "rate_limit"
    HTTP_4XX = "http_4xx"
    HTTP_5XX = "http_5xx"
    INTERNAL = "internal"
    UNKNOWN = "unknown"
