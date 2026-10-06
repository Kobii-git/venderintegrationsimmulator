"""One record contract for previews, preflight, queued and immediate Azure sends."""

import json
from typing import Any

from app.formats.source import custom_ingestion_record, render_source

AZURE_TRANSPORTS = frozenset({"azure_logs_ingestion", "azure_function_app"})
MAX_BATCH_BYTES = 950_000
MAX_FIELD_BYTES = 64 * 1024


def validate_record(record: Any, limit: int = MAX_BATCH_BYTES) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise ValueError("Ingestion records must be JSON objects")
    for key, value in record.items():
        if (
            len(
                json.dumps(
                    value, ensure_ascii=False, separators=(",", ":"), allow_nan=False
                ).encode("utf-8")
            )
            > MAX_FIELD_BYTES
        ):
            raise ValueError(f"Field {key!r} exceeds 64 KiB")
    if len(
        json.dumps(record, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode(
            "utf-8"
        )
    ) + 2 > min(limit, MAX_BATCH_BYTES):
        raise ValueError("A single JSON record exceeds the batch byte limit")
    return record


def ingestion_record(
    payload: dict[str, Any], payload_format: str, product_id: str
) -> dict[str, Any]:
    body, content_type = render_source(payload, payload_format)
    if payload_format != "default" and content_type == "application/json" and isinstance(body, str):
        body = json.loads(body)
    if payload_format == "default" or content_type != "application/json":
        body = custom_ingestion_record(payload, body, product_id)
    return validate_record(body)
