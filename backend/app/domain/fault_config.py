"""Fault injection configuration models."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DuplicateMode(StrEnum):
    NONE = "none"
    EXACT_PAYLOAD = "exact_payload"
    DUPLICATE_CORRELATION_ID = "duplicate_correlation_id"
    REPEAT_SCENARIO_NEW_IDS = "repeat_scenario_new_ids"


class TimestampFault(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["current", "fixed", "offset"] = "current"
    fixed_value: str | None = None
    offset_amount: int | None = Field(default=None, ge=1)
    offset_unit: Literal["minutes", "hours", "days"] | None = None
    offset_direction: Literal["past", "future"] = "past"
    field_paths: list[str] = Field(
        default_factory=lambda: ["notification.occurredAt", "_simulator.simulator_timestamp"]
    )


class PayloadFaults(BaseModel):
    model_config = ConfigDict(extra="forbid")

    remove_timestamp: bool = False
    invalid_timestamp: bool = False
    timestamp: TimestampFault = Field(default_factory=TimestampFault)
    remove_fields: list[str] = Field(default_factory=list)
    null_fields: list[str] = Field(default_factory=list)
    extra_fields: dict[str, Any] = Field(default_factory=dict)
    large_field_path: str | None = None
    large_field_size_kb: int = Field(default=64, ge=1, le=512)
    malformed_json: bool = False


class DuplicateTesting(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: DuplicateMode = DuplicateMode.NONE
    source_event_id: str | None = None
    correlation_id: str | None = None


class DeliveryBehaviour(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pre_delay_ms: int = Field(default=0, ge=0)
    timeout_seconds: int | None = Field(default=None, ge=1, le=300)
    duplicate_send_count: int = Field(default=1, ge=1, le=3)
    retry_count: int = Field(default=0, ge=0, le=3)
    retry_delay_ms: int = Field(default=500, ge=0)


class FaultConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    payload: PayloadFaults = Field(default_factory=PayloadFaults)
    duplicate: DuplicateTesting = Field(default_factory=DuplicateTesting)
    delivery: DeliveryBehaviour = Field(default_factory=DeliveryBehaviour)

    @model_validator(mode="after")
    def validate_enabled_sections(self) -> Self:
        if not self.enabled:
            return self
        if (
            self.duplicate.mode == DuplicateMode.EXACT_PAYLOAD
            and not self.duplicate.source_event_id
        ):
            raise ValueError(
                "duplicate.source_event_id is required when duplicate.mode is 'exact_payload'"
            )
        if self.duplicate.mode == DuplicateMode.DUPLICATE_CORRELATION_ID and not (
            self.duplicate.source_event_id or self.duplicate.correlation_id
        ):
            raise ValueError(
                "duplicate.source_event_id or duplicate.correlation_id is required "
                "when duplicate.mode is 'duplicate_correlation_id'"
            )
        if self.payload.timestamp.mode == "fixed" and not self.payload.timestamp.fixed_value:
            raise ValueError("timestamp.fixed_value is required when timestamp.mode is 'fixed'")
        if self.payload.timestamp.mode == "offset" and (
            self.payload.timestamp.offset_amount is None
            or self.payload.timestamp.offset_unit is None
        ):
            raise ValueError(
                "timestamp.offset_amount and timestamp.offset_unit are required "
                "when timestamp.mode is 'offset'"
            )
        return self


def parse_fault_config(raw: dict[str, Any] | None) -> FaultConfig:
    if not raw:
        return FaultConfig()
    return FaultConfig.model_validate(raw)
