"""API 2.0 security-log workflow, using the official Sentinel connector contracts."""

import base64
import gzip
import hashlib
import hmac
import json
import time
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode, urlsplit, urlunsplit

from app.domain.enums import FidelityMode
from app.products.native import NativeRequest
from app.products.plugin import NoOpProductPlugin
from app.products.workflow import (
    BaseProductWorkflowPlugin,
    VendorWorkflowError,
    WorkflowResponse,
)

MAX_BYTES = 950_000
TYPE_ALIASES = {
    "ttp_url": "url protect",
    "ttp_attachment": "attachment protect",
    "ttp_impersonation": "impersonation protect",
}


class MimecastPlugin(NoOpProductPlugin, BaseProductWorkflowPlugin):
    def __init__(self) -> None:
        super().__init__("mimecast")

    def post_render(
        self,
        payload: dict[str, Any],
        fidelity_mode: FidelityMode,
        *,
        scenario_id: str,
        correlation_id: str,
    ) -> dict[str, Any]:
        record = payload.get("record", {})
        if "timestamp" in record:
            record["timestamp"] = int(record["timestamp"])
        if record.get("type") in TYPE_ALIASES:
            record["type"] = TYPE_ALIASES[record["type"]]
        return payload

    def handle_native_request(self, context: NativeRequest) -> WorkflowResponse:
        if context.route_id == "download":
            return self._download(context)
        if context.route_id == "siem-batch":
            try:
                limit = int(context.query.get("pageSize", "20"))
            except ValueError as exc:
                raise VendorWorkflowError(400, {"message": "Invalid pageSize"}) from exc
            if not 1 <= limit <= 100:
                raise VendorWorkflowError(400, {"message": "pageSize must be 1–100"})
            types = set(context.query.get("type", "").split(",")) - {""}
            items, next_cursor, terminal, _ = context.page(
                "siem-batch",
                limit,
                context.query.get("nextPage"),
                None,
                None,
                types or None,
            )
            values = []
            if items:
                ttl = int(context.options.get("download_ttl_seconds", 900))
                claims = {
                    "sid": context.simulation_id,
                    "activation": context.activation_id,
                    "cursor": context.query.get("nextPage"),
                    "limit": limit,
                    "types": sorted(types),
                    "exp": int(time.time()) + ttl,
                }
                token = self._sign(claims, context.signing_key)
                parsed = urlsplit(context.url)
                base_path = parsed.path.rsplit("/siem/v1/batch/events/cg", 1)[0]
                url = urlunsplit(
                    (
                        parsed.scheme,
                        parsed.netloc,
                        base_path + "/downloads",
                        urlencode(
                            {"simulation_id": context.simulation_id, "token": token}
                        ),
                        "",
                    )
                )
                values = [{"url": url}]
            return WorkflowResponse(
                body={"value": values, "@nextPage": next_cursor or terminal}
            )

        meta = context.body.get("meta", {})
        if not isinstance(meta, dict) or not isinstance(
            meta.get("pagination", {}), dict
        ):
            raise VendorWorkflowError(
                400, {"message": "Expected meta.pagination object"}
            )
        pagination = meta.get("pagination", {})
        try:
            limit = int(pagination.get("pageSize", 50))
        except (ValueError, TypeError) as exc:
            raise VendorWorkflowError(400, {"message": "Invalid pageSize"}) from exc
        if not 1 <= limit <= 100:
            raise VendorWorkflowError(400, {"message": "pageSize must be 1–100"})
        data = context.body.get("data", [])
        if not isinstance(data, list) or not data or not isinstance(data[0], dict):
            raise VendorWorkflowError(
                400, {"message": "Expected data array with one query object"}
            )
        query = data[0]
        from_key, to_key = (
            ("startDateTime", "endDateTime")
            if context.route_id == "audit"
            else ("from", "to")
        )
        since, until = self._date(query.get(from_key)), self._date(query.get(to_key))
        cursor = pagination.get("pageToken") or None
        if cursor is not None and not isinstance(cursor, str):
            raise VendorWorkflowError(400, {"message": "Expected pageToken string"})
        if since and until and since > until:
            raise VendorWorkflowError(400, {"message": "from must be before to"})
        oldest_first = query.get("oldestFirst", False)
        if context.route_id != "audit" and type(oldest_first) is not bool:
            raise VendorWorkflowError(400, {"message": "oldestFirst must be a boolean"})
        reverse = context.route_id != "audit" and not oldest_first
        query_context = {
            "from": since.astimezone(UTC).isoformat() if since else None,
            "to": until.astimezone(UTC).isoformat() if until else None,
            "reverse": reverse,
        }
        items, next_cursor, _, total = context.page(
            context.route_id, limit, cursor, since, until, None,
            reverse=reverse, query_context=query_context,
        )
        field = {
            "url": "clickLogs",
            "attachment": "attachmentLogs",
            "impersonation": "impersonationLogs",
            "dlp": "dlpLogs",
        }.get(context.route_id)
        return WorkflowResponse(
            body={
                "meta": {
                    "status": 200,
                    "pagination": {"next": next_cursor or "", "totalCount": total},
                },
                "data": items if context.route_id == "audit" else [{field: items}],
                "fail": [],
            }
        )

    @staticmethod
    def _date(value: Any) -> datetime | None:
        if value is None:
            return None
        try:
            result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return result.replace(tzinfo=UTC) if result.tzinfo is None else result
        except ValueError as exc:
            raise VendorWorkflowError(
                400, {"message": "Invalid ISO8601 time filter"}
            ) from exc

    @staticmethod
    def _sign(claims: dict[str, Any], key: str) -> str:
        data = (
            base64.urlsafe_b64encode(
                json.dumps(claims, separators=(",", ":"), sort_keys=True).encode()
            )
            .decode()
            .rstrip("=")
        )
        signature = hmac.new(
            key.encode(), ("mimecast-download:" + data).encode(), hashlib.sha256
        ).hexdigest()
        return data + "." + signature

    def _download(self, context: NativeRequest) -> WorkflowResponse:
        token = context.query.get("token", "")
        try:
            if len(token) > 4096:
                raise ValueError
            data, signature = token.rsplit(".", 1)
            expected = hmac.new(
                context.signing_key.encode(),
                ("mimecast-download:" + data).encode(),
                hashlib.sha256,
            ).hexdigest()
            if not hmac.compare_digest(signature, expected):
                raise ValueError
            claims = json.loads(base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)))
            if (
                claims["sid"] != context.simulation_id
                or claims["activation"] != context.activation_id
                or not 1 <= claims["limit"] <= 100
            ):
                raise ValueError
            if claims["exp"] <= int(time.time()):
                raise VendorWorkflowError(403, {"message": "Download link expired"})
        except (ValueError, KeyError, TypeError) as exc:
            raise VendorWorkflowError(
                403, {"message": "Invalid download link"}
            ) from exc
        items, _, _, _ = context.page(
            "siem-batch",
            claims["limit"],
            claims["cursor"],
            None,
            None,
            set(claims["types"]) or None,
        )
        raw = b"".join(
            json.dumps(item, separators=(",", ":"), ensure_ascii=False).encode() + b"\n"
            for item in items
        )
        if len(raw) > MAX_BYTES:
            raise VendorWorkflowError(
                413,
                {
                    "message": "Synthetic download exceeds 950000 bytes; use a smaller pageSize"
                },
            )
        return WorkflowResponse(
            raw_content=gzip.compress(raw, mtime=0),
            media_type="application/gzip",
            headers={
                "Content-Disposition": 'attachment; filename="mimecast-events.ndjson.gz"',
                "Cache-Control": "private, no-store",
            },
        )


def get_plugin() -> MimecastPlugin:
    return MimecastPlugin()
