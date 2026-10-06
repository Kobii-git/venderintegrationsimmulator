"""Default runtime counters and state for simulations."""

from datetime import UTC, datetime
from typing import Any


def default_runtime_state() -> dict[str, Any]:
    return {
        "events_generated": 0,
        "events_attempted": 0,
        "events_successful": 0,
        "events_failed": 0,
        "scenario_index": 0,
        "schedule_activation_start_count": 0,
        "last_delivery_at": None,
        "last_http_status": None,
        "last_latency_ms": None,
        "last_error_message": None,
        "last_event_id": None,
        "started_at": None,
        "stopped_at": None,
        "last_error_at": None,
        "interrupted_on_restart": False,
        "inbound_requests_total": 0,
        "inbound_requests_successful": 0,
        "inbound_requests_failed": 0,
        "inbound_items_returned_total": 0,
        "last_inbound_at": None,
        "last_inbound_items": None,
        "pull_dataset_activation_id": None,
        "pull_dataset_item_count": 0,
    }


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()
