"""Apply controlled payload and delivery faults to generated event instances."""

from __future__ import annotations

import copy
import json
from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.config import Settings
from app.core.exceptions import ValidationAppError
from app.domain.fault_config import FaultConfig


def validate_fault_config(fault: FaultConfig, settings: Settings) -> None:
    if not fault.enabled:
        return

    if fault.delivery.pre_delay_ms > settings.fault_max_delivery_delay_ms:
        raise ValidationAppError(
            f"pre_delay_ms exceeds maximum of {settings.fault_max_delivery_delay_ms}ms",
            details={"max_delay_ms": settings.fault_max_delivery_delay_ms},
        )
    if fault.delivery.duplicate_send_count > settings.fault_max_duplicate_sends:
        raise ValidationAppError(
            f"duplicate_send_count exceeds maximum of {settings.fault_max_duplicate_sends}",
            details={"max_duplicate_sends": settings.fault_max_duplicate_sends},
        )
    if fault.payload.large_field_size_kb > settings.fault_max_large_field_kb:
        raise ValidationAppError(
            f"large_field_size_kb exceeds maximum of {settings.fault_max_large_field_kb}",
            details={"max_large_field_kb": settings.fault_max_large_field_kb},
        )


def resolve_timestamp_value(fault: FaultConfig) -> str | None:
    ts = fault.payload.timestamp
    if fault.payload.remove_timestamp or fault.payload.invalid_timestamp:
        return None
    if ts.mode == "current":
        return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    if ts.mode == "fixed":
        return ts.fixed_value
    if ts.mode == "offset" and ts.offset_amount and ts.offset_unit:
        delta = _offset_delta(ts.offset_amount, ts.offset_unit)
        base = datetime.now(UTC)
        value = base - delta if ts.offset_direction == "past" else base + delta
        return value.strftime("%Y-%m-%dT%H:%M:%SZ")
    return None


def apply_payload_faults(
    payload: dict[str, Any],
    fault: FaultConfig,
) -> tuple[dict[str, Any] | str, list[str], dict[str, Any]]:
    """Return mutated payload (or malformed string), applied fault names, and delivery hints."""
    if not fault.enabled:
        return payload, [], {}

    mutated = copy.deepcopy(payload)
    applied: list[str] = []
    delivery_hints: dict[str, Any] = {}

    if fault.payload.malformed_json:
        applied.append("malformed_json")
        delivery_hints["malformed_body"] = json.dumps(mutated)[:-1] + ",not-valid-json"
        return mutated, applied, delivery_hints

    if fault.payload.remove_timestamp:
        for path in fault.payload.timestamp.field_paths:
            if _remove_path(mutated, path):
                applied.append(f"remove_timestamp:{path}")

    elif fault.payload.invalid_timestamp:
        for path in fault.payload.timestamp.field_paths:
            if _set_path(mutated, path, "NOT-A-VALID-TIMESTAMP"):
                applied.append(f"invalid_timestamp:{path}")

    else:
        timestamp_value = resolve_timestamp_value(fault)
        if timestamp_value and fault.payload.timestamp.mode != "current":
            for path in fault.payload.timestamp.field_paths:
                if _set_path(mutated, path, timestamp_value):
                    applied.append(f"timestamp_{fault.payload.timestamp.mode}:{path}")

    for path in fault.payload.remove_fields:
        if _remove_path(mutated, path):
            applied.append(f"remove_field:{path}")

    for path in fault.payload.null_fields:
        if _set_path(mutated, path, None):
            applied.append(f"null_field:{path}")

    for key, value in fault.payload.extra_fields.items():
        _set_path(mutated, key, value)
        applied.append(f"extra_field:{key}")

    if fault.payload.large_field_path:
        size = fault.payload.large_field_size_kb * 1024
        _set_path(mutated, fault.payload.large_field_path, "X" * size)
        applied.append(
            f"large_field:{fault.payload.large_field_path}:{fault.payload.large_field_size_kb}kb"
        )

    return mutated, applied, delivery_hints


def build_fault_metadata(
    fault: FaultConfig,
    applied_faults: list[str],
    *,
    duplicate_mode: str | None = None,
    source_event_id: str | None = None,
) -> dict[str, Any]:
    if not fault.enabled and not applied_faults:
        return {}
    metadata: dict[str, Any] = {
        "enabled": fault.enabled,
        "applied_faults": applied_faults,
        "intentionally_modified": bool(applied_faults),
    }
    if duplicate_mode:
        metadata["duplicate_mode"] = duplicate_mode
    if source_event_id:
        metadata["source_event_id"] = source_event_id
    if fault.payload.malformed_json:
        metadata["malformed_json"] = True
    if fault.delivery.pre_delay_ms:
        metadata["delivery_pre_delay_ms"] = fault.delivery.pre_delay_ms
    if fault.delivery.duplicate_send_count > 1:
        metadata["duplicate_send_count"] = fault.delivery.duplicate_send_count
    return metadata


def _offset_delta(amount: int, unit: str) -> timedelta:
    if unit == "minutes":
        return timedelta(minutes=amount)
    if unit == "hours":
        return timedelta(hours=amount)
    return timedelta(days=amount)


def _path_parts(path: str) -> list[str]:
    return [part for part in path.split(".") if part]


def _get_parent(data: Any, parts: list[str]) -> tuple[Any, str] | tuple[None, None]:
    if not parts:
        return None, None
    current = data
    for part in parts[:-1]:
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            return None, None
    if not isinstance(current, dict | list):
        return None, None
    return current, parts[-1]


def _set_path(data: dict[str, Any], path: str, value: Any) -> bool:
    parent, key = _get_parent(data, _path_parts(path))
    if parent is None or key is None:
        return False
    if isinstance(parent, dict):
        parent[key] = value
        return True
    if key.isdigit() and int(key) < len(parent):
        parent[int(key)] = value
        return True
    return False


def _remove_path(data: dict[str, Any], path: str) -> bool:
    parent, key = _get_parent(data, _path_parts(path))
    if parent is None or key is None:
        return False
    if isinstance(parent, dict) and key in parent:
        del parent[key]
        return True
    if isinstance(parent, list) and key.isdigit() and int(key) < len(parent):
        parent.pop(int(key))
        return True
    return False
