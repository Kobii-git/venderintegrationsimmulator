"""Okta System Log and event-hook workflow behaviour."""

from __future__ import annotations

import json
import random
import re
import uuid
from datetime import datetime
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from app.domain.enums import FidelityMode
from app.products.plugin import ProductPlugin
from app.products.workflow import (
    BaseProductWorkflowPlugin,
    VendorWorkflowError,
    WorkflowResponse,
)

FILTER_PATTERN = re.compile(r'^(eventType|actor\.id|target\.id) eq "([^"]+)"$')


def _parse_instant(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class OktaPlugin(BaseProductWorkflowPlugin):
    product_id = "okta"

    def enrich_context(
        self,
        scenario_id: str,
        overrides: dict[str, Any],
        *,
        rng: random.Random,
    ) -> dict[str, Any]:
        del scenario_id
        return {
            "user_email": overrides.get("user_email", "analyst@example.com"),
            "user_name": overrides.get("user_name", "Example Analyst"),
            "source_ip": overrides.get("source_ip", "192.0.2.25"),
            "actor_id": f"00u{rng.getrandbits(64):016x}",
            "target_id": f"00u{rng.getrandbits(64):016x}",
            "application_id": f"0oa{rng.getrandbits(64):016x}",
            "transaction_id": uuid.UUID(int=rng.getrandbits(128)).hex,
        }

    def post_render(
        self,
        payload: dict[str, Any],
        fidelity_mode: FidelityMode,
        *,
        scenario_id: str,
        correlation_id: str,
    ) -> dict[str, Any]:
        del fidelity_mode, scenario_id, correlation_id
        return payload

    def validate_inbound_request(
        self,
        route_id: str,
        *,
        method: str,
        headers: dict[str, str],
        query_params: dict[str, str],
        vendor_options: dict[str, Any],
    ) -> None:
        del method, headers, vendor_options
        if route_id != "system-log":
            return
        if query_params.get("since") and query_params.get("after"):
            self._raise_bad_request(route_id, "since and after are mutually exclusive")
        sort_order = query_params.get("sortOrder", "DESCENDING")
        if sort_order not in {"ASCENDING", "DESCENDING"}:
            self._raise_bad_request(route_id, "sortOrder must be ASCENDING or DESCENDING")
        for field in ("since", "until"):
            raw = query_params.get(field)
            if raw:
                try:
                    _parse_instant(raw)
                except ValueError:
                    self._raise_bad_request(route_id, f"{field} must be an ISO-8601 timestamp")
        raw_filter = query_params.get("filter")
        if raw_filter and FILTER_PATTERN.fullmatch(raw_filter) is None:
            self._raise_bad_request(
                route_id,
                "filter supports eventType, actor.id, or target.id equality",
            )

    def filter_inbound_items(
        self,
        route_id: str,
        items: list[dict[str, Any]],
        query_params: dict[str, str],
    ) -> list[dict[str, Any]]:
        if route_id != "system-log":
            return items
        result = list(items)
        until = query_params.get("until")
        if until:
            until_time = _parse_instant(until)
            result = [
                item for item in result if _parse_instant(str(item.get("published"))) <= until_time
            ]
        raw_filter = query_params.get("filter")
        if raw_filter:
            match = FILTER_PATTERN.fullmatch(raw_filter)
            assert match is not None
            field, expected = match.groups()
            if field == "eventType":
                result = [item for item in result if item.get("eventType") == expected]
            elif field == "actor.id":
                result = [
                    item for item in result if (item.get("actor") or {}).get("id") == expected
                ]
            else:
                result = [
                    item
                    for item in result
                    if any(target.get("id") == expected for target in item.get("target") or [])
                ]
        query = query_params.get("q", "").casefold()
        if query:
            result = [
                item for item in result if query in json.dumps(item, sort_keys=True).casefold()
            ]
        if query_params.get("sortOrder", "DESCENDING") == "DESCENDING":
            result.reverse()
        return result

    def build_inbound_response(
        self,
        route_id: str,
        *,
        items: list[dict[str, Any]],
        next_cursor: str | None,
        terminal_cursor: str,
        total: int,
        request_url: str,
        query_params: dict[str, str],
        vendor_options: dict[str, Any],
        default_body: Any,
    ) -> WorkflowResponse | None:
        del total, vendor_options, default_body
        if route_id != "system-log":
            return None
        links = [f'<{request_url}>; rel="self"']
        polling = query_params.get("sortOrder") == "ASCENDING" and not query_params.get("until")
        cursor = next_cursor or (terminal_cursor if polling else None)
        if cursor:
            links.append(f'<{self._next_url(request_url, cursor)}>; rel="next"')
        return WorkflowResponse(body=items, headers={"Link": ", ".join(links)})

    def build_static_response(
        self,
        route_id: str,
        *,
        request_url: str,
        vendor_options: dict[str, Any],
    ) -> WorkflowResponse | None:
        del route_id, request_url, vendor_options
        return None

    def format_inbound_error(self, route_id: str, status_code: int, message: str) -> dict[str, Any]:
        del route_id, status_code
        return {
            "errorCode": "E0000001",
            "errorSummary": message,
            "errorLink": "E0000001",
            "errorId": f"oae{uuid.uuid4().hex}",
            "errorCauses": [],
        }

    def prepare_outbound_payload(
        self,
        scenario_id: str,
        payload: dict[str, Any],
        *,
        correlation_id: str,
    ) -> dict[str, Any]:
        del scenario_id
        published = str(payload.get("published") or datetime.now().astimezone().isoformat())
        return {
            "eventType": "com.okta.event_hook",
            "eventTypeVersion": "1.0",
            "cloudEventsVersion": "0.1",
            "source": "https://example.okta.com/api/v1/eventHooks/simulator",
            "eventId": correlation_id,
            "data": {"events": [payload]},
            "eventTime": published,
            "contentType": "application/json",
        }

    def _raise_bad_request(self, route_id: str, message: str) -> None:
        raise VendorWorkflowError(
            400,
            self.format_inbound_error(route_id, 400, message),
        )

    @staticmethod
    def _next_url(request_url: str, cursor: str) -> str:
        parsed = urlsplit(request_url)
        params = [
            (key, value)
            for key, value in parse_qsl(parsed.query, keep_blank_values=True)
            if key not in {"after", "since"}
        ]
        params.append(("after", cursor))
        return urlunsplit(
            (parsed.scheme, parsed.netloc, parsed.path, urlencode(params), parsed.fragment)
        )


def get_plugin() -> ProductPlugin:
    return OktaPlugin()
