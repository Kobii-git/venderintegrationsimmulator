import json
from datetime import UTC, datetime
from typing import Any

from app.domain.inbound import InboundFaultConfig


def parse_time_filter(query_params: dict[str, str]) -> datetime | None:
    for key in ("since", "from", "start_time", "startTime", "from_time"):
        raw = query_params.get(key)
        if not raw:
            continue
        try:
            if raw.isdigit():
                return datetime.fromtimestamp(int(raw), tz=UTC)
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            continue
    return None


def parse_limit(query_params: dict[str, str], default: int, maximum: int) -> int:
    for key in ("limit", "pageSize", "page_size", "top"):
        raw = query_params.get(key)
        if raw and raw.isdigit():
            return min(int(raw), maximum)
    return min(default, maximum)


def apply_inbound_fault_body(
    body: dict[str, Any] | list[Any] | str,
    fault: InboundFaultConfig,
    *,
    pagination_inconsistent: bool = False,
) -> str | bytes:
    if fault.malformed_json:
        return "{ this is not valid json"
    if isinstance(body, str):
        return body
    payload = body
    if pagination_inconsistent and isinstance(payload, dict):
        payload = dict(payload)
        for key in ("nextPageToken", "nextToken", "cursor"):
            if key in payload:
                payload[key] = "invalid-cursor-token"
                break
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False)


def encode_basic_challenge() -> dict[str, str]:
    return {"WWW-Authenticate": 'Basic realm="integration-simulator"'}
