"""Materialize and page stable datasets for pull simulations."""

from __future__ import annotations

import base64
import json
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.core.exceptions import ValidationAppError
from app.domain.enums import FidelityMode
from app.domain.inbound import InboundConfig
from app.models import PullDatasetActivation, PullDatasetItem, Simulation
from app.products.manifest import MockRouteRef
from app.products.registry import ProductRegistry
from app.repositories.pull_dataset import PullDatasetRepository


class PullDatasetService:
    def __init__(self, db: Session, registry: ProductRegistry) -> None:
        self._db = db
        self._registry = registry
        self._repo = PullDatasetRepository(db)

    def materialize(self, simulation: Simulation) -> PullDatasetActivation:
        settings = InboundConfig.model_validate(simulation.inbound_config or {})
        manifest = self._registry.get_manifest(simulation.product_id)
        if manifest is None:
            raise ValidationAppError(f"Product not found: {simulation.product_id}")

        anchor = datetime.now(UTC)
        dataset_routes = [
            route
            for route in manifest.mock_routes
            if route.handler in {"dataset_list", "dataset_single"}
        ]
        activation = PullDatasetActivation(
            id=str(uuid.uuid4()),
            simulation_id=simulation.id,
            activated_at=anchor,
            item_count=settings.dataset_size * len(dataset_routes),
        )
        items: list[PullDatasetItem] = []
        plugin = self._registry.get_plugin(simulation.product_id)
        for route in dataset_routes:
            configured_scenarios = route.scenario_ids or [route.scenario_id]
            selected_scenarios = [
                scenario_id
                for scenario_id in configured_scenarios
                if scenario_id in (simulation.scenario_ids or [simulation.scenario_id])
            ] or configured_scenarios
            for sequence in range(settings.dataset_size):
                scenario_id = selected_scenarios[sequence % len(selected_scenarios)]
                scenario = self._registry.get_scenario(simulation.product_id, scenario_id)
                if scenario is None:
                    raise ValidationAppError(
                        f"Scenario not found: {simulation.product_id}/{scenario_id}"
                    )
                generated_at = anchor - timedelta(
                    seconds=(settings.dataset_size - 1 - sequence) * settings.item_interval_seconds
                )
                payload = self._registry.renderer.render_scenario(
                    scenario,
                    fidelity_mode=FidelityMode(simulation.fidelity_mode),
                    correlation_id=str(uuid.uuid4()),
                    overrides=(simulation.scenario_overrides or {}).get(scenario_id, {}),
                    plugin=plugin,
                    diagnostic_merge=manifest.diagnostic_merge,
                    random_seed=simulation.random_seed,
                    event_sequence=sequence,
                    render_time=generated_at,
                )
                if isinstance(payload, str):
                    payload = {"message": payload}
                elif "_syslog_message" in payload:
                    payload = {"message": payload["_syslog_message"]}
                items.append(
                    PullDatasetItem(
                        activation_id=activation.id,
                        simulation_id=simulation.id,
                        route_id=route.id,
                        scenario_id=scenario_id,
                        sequence=sequence,
                        generated_at=generated_at,
                        payload=payload,
                    )
                )
        self._repo.replace(activation, items)
        self._db.commit()
        self._db.refresh(activation)
        return activation

    def has_active_dataset(self, simulation: Simulation) -> bool:
        activation_id = str(
            (simulation.runtime_state or {}).get("pull_dataset_activation_id") or ""
        )
        activation = self._repo.get_activation(activation_id) if activation_id else None
        return bool(activation and activation.simulation_id == simulation.id)

    def list_response(
        self,
        *,
        simulation: Simulation,
        route: MockRouteRef,
        limit: int,
        cursor: str | None,
        page: int | None,
        since: datetime | None,
        force_empty: bool,
    ) -> tuple[dict[str, Any], int]:
        activation_id = str(
            (simulation.runtime_state or {}).get("pull_dataset_activation_id") or ""
        )
        activation = self._repo.get_activation(activation_id) if activation_id else None
        if activation is None or activation.simulation_id != simulation.id:
            raise ValidationAppError("Pull dataset is not active; stop and start the simulation")
        offset = (
            self._decode_cursor(
                cursor, activation.id, route.id, self._repo.route_size(activation.id, route.id)
            )
            if cursor
            else 0
        )
        if page is not None:
            if page < 1:
                raise ValidationAppError("page must be at least 1")
            offset = (page - 1) * limit
        if force_empty:
            items: list[PullDatasetItem] = []
            total = 0
        else:
            items, total = self._repo.page(
                activation_id=activation.id,
                route_id=route.id,
                offset=offset,
                limit=limit,
                since=since,
            )
        payloads = [item.payload for item in items]
        response: dict[str, Any] = {route.items_field: payloads}
        if route.supports_pagination:
            next_offset = offset + len(items)
            if route.pagination_style == "page":
                response[route.page_field] = page or (offset // limit) + 1
                response[route.total_field] = total
            elif next_offset < total:
                response[route.next_token_field] = self._encode_cursor(
                    activation.id, route.id, next_offset
                )
        return response, len(items)

    def custom_page(
        self,
        *,
        simulation: Simulation,
        route: MockRouteRef,
        limit: int,
        cursor: str | None,
        since: datetime | None,
        force_empty: bool,
        transform: Callable[[list[dict[str, Any]]], list[dict[str, Any]]] | None = None,
        reverse: bool = False,
        query_context: dict[str, Any] | None = None,
    ) -> tuple[list[dict[str, Any]], str | None, str, int]:
        """Page a fully transformed route dataset for vendor-specific query semantics."""
        activation_id = str(
            (simulation.runtime_state or {}).get("pull_dataset_activation_id") or ""
        )
        activation = self._repo.get_activation(activation_id) if activation_id else None
        if activation is None or activation.simulation_id != simulation.id:
            raise ValidationAppError("Pull dataset is not active; stop and start the simulation")
        offset = (
            self._decode_cursor(
                cursor,
                activation.id,
                route.id,
                self._repo.route_size(activation.id, route.id),
                query_context,
            )
            if cursor
            else 0
        )
        if force_empty:
            payloads: list[dict[str, Any]] = []
        else:
            raw_items = self._repo.list_route_items(
                activation_id=activation.id,
                route_id=route.id,
                since=since,
            )
            payloads = [dict(item.payload) for item in raw_items]
            if transform is not None:
                payloads = transform(payloads)
        if reverse:
            payloads.reverse()
        total = len(payloads)
        page_items = payloads[offset : offset + limit]
        next_offset = offset + len(page_items)
        next_cursor = (
            self._encode_cursor(activation.id, route.id, next_offset, query_context)
            if next_offset < total
            else None
        )
        terminal_cursor = self._encode_cursor(
            activation.id,
            route.id,
            min(next_offset, total),
            query_context,
        )
        return page_items, next_cursor, terminal_cursor, total

    def single_response(self, simulation: Simulation, route: MockRouteRef) -> dict[str, Any]:
        activation_id = str(
            (simulation.runtime_state or {}).get("pull_dataset_activation_id") or ""
        )
        item = self._repo.first(activation_id=activation_id, route_id=route.id)
        if item is None:
            raise ValidationAppError("Pull dataset contains no item for this route")
        return dict(item.payload)

    @staticmethod
    def _encode_cursor(
        activation_id: str, route_id: str, offset: int, query_context: dict[str, Any] | None = None
    ) -> str:
        payload: dict[str, Any] = {"activation": activation_id, "route": route_id, "offset": offset}
        if query_context is not None:
            payload["query"] = query_context
        raw = json.dumps(payload, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")

    @staticmethod
    def _decode_cursor(
        cursor: str,
        activation_id: str,
        route_id: str,
        maximum: int = 10000,
        query_context: dict[str, Any] | None = None,
    ) -> int:
        import binascii
        import re

        try:
            if (
                not isinstance(cursor, str)
                or len(cursor) > 4096
                or not re.fullmatch(r"[A-Za-z0-9_-]+={0,2}", cursor)
            ):
                raise ValueError("invalid token")
            padded = cursor + "=" * (-len(cursor) % 4)

            def reject_constant(value: str) -> Any:
                raise ValueError("non-finite JSON value")

            def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
                result: dict[str, Any] = {}
                for key, value in pairs:
                    if key in result:
                        raise ValueError("duplicate JSON property")
                    result[key] = value
                return result

            payload = json.loads(
                base64.b64decode(padded.encode(), altchars=b"-_", validate=True),
                parse_constant=reject_constant,
                object_pairs_hook=unique_object,
            )
            if not isinstance(payload, dict):
                raise ValueError("cursor must be an object")
            if payload.get("activation") != activation_id or payload.get("route") != route_id:
                raise ValueError("cursor does not match the active dataset")
            offset = payload.get("offset")
            if type(offset) is not int or not 0 <= offset <= maximum:
                raise ValueError("invalid offset")
            if query_context is not None:
                if "query" not in payload:
                    raise ValidationAppError(
                        "Legacy POST checkpoint: restart the query without pageToken"
                    )
                if payload["query"] != query_context:
                    raise ValidationAppError(
                        "Checkpoint query changed: restart the query without pageToken"
                    )
            return offset
        except (
            ValueError,
            KeyError,
            TypeError,
            UnicodeError,
            RecursionError,
            binascii.Error,
        ) as exc:
            raise ValidationAppError("Invalid or stale pagination cursor") from exc
