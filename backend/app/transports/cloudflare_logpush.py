"""Bounded Cloudflare HTTP Logpush uploads (gzip-compressed NDJSON)."""

import gzip
import json
from typing import Any

from app.transports.delivery_result import DeliveryResult
from app.transports.http_webhook import HttpWebhookTransport

MAX_RECORDS = 1000
MAX_BYTES = 950_000


def encode_logpush(payload: bytes) -> bytes:
    value = json.loads(payload)
    records = value if isinstance(value, list) else [value]
    if not records or len(records) > MAX_RECORDS or any(not isinstance(r, dict) for r in records):
        raise ValueError("Logpush requires 1–1000 JSON objects per upload")
    raw = b"".join(
        json.dumps(r, ensure_ascii=False, separators=(",", ":")).encode() + b"\n" for r in records
    )
    if len(raw) > MAX_BYTES:
        raise ValueError("Logpush upload exceeds the simulator's 950000-byte uncompressed limit")
    return gzip.compress(raw, mtime=0)


class CloudflareLogpushTransport(HttpWebhookTransport):
    transport_id = "cloudflare_logpush"

    async def deliver(
        self,
        destination: dict[str, Any],
        payload: bytes,
        content_type: str,
        auth_config: dict[str, Any],
    ) -> DeliveryResult:
        del content_type
        destination = {
            **destination,
            "method": "POST",
            "headers": {
                **destination.get("headers", {}),
                "Content-Disposition": 'attachment; filename="test.txt.gz"'
                if json.loads(payload) == {"content": "tests"}
                else 'attachment; filename="logs.ndjson.gz"',
            },
        }
        return await super().deliver(
            destination, encode_logpush(payload), "application/gzip", auth_config
        )

    async def test_destination(
        self,
        destination: dict[str, Any],
        auth_config: dict[str, Any],
    ) -> DeliveryResult:
        return await self.deliver(
            destination, b'{"content":"tests"}', "application/json", auth_config
        )
