import asyncio
import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.exceptions import ValidationAppError
from app.core.redaction import (
    REDACTED,
    redact_headers,
    redact_mapping,
    redact_secret_values,
    truncate_body,
)
from app.core.security import SecretEncryptor, resolve_secret_key
from app.domain.enums import SimulationMode, SimulationStatus
from app.domain.inbound import InboundConfig
from app.inbound.auth import InboundAuthResult, inbound_sensitive_header_names, verify_inbound_auth
from app.inbound.oauth import OAuthTokenService
from app.inbound.response_builder import (
    apply_inbound_fault_body,
    encode_basic_challenge,
    parse_limit,
    parse_time_filter,
)
from app.models import InboundRequestLog, Simulation
from app.products.native import NativeRequest
from app.products.registry import ProductRegistry
from app.products.workflow import VendorWorkflowError
from app.repositories.inbound import InboundRequestRepository
from app.repositories.simulation import SimulationRepository
from app.services.inbound_options import validate_inbound_options
from app.services.pull_dataset import PullDatasetService

logger = logging.getLogger(__name__)


class InboundMockService:
    """Handle inbound mock API requests for pull-based simulations."""

    def __init__(
        self,
        db: Session,
        registry: ProductRegistry,
        encryptor: SecretEncryptor,
    ) -> None:
        self._db = db
        self._registry = registry
        self._encryptor = encryptor
        self._simulations = SimulationRepository(db)
        self._inbound_logs = InboundRequestRepository(db)
        self._oauth = OAuthTokenService(db, encryptor)
        self._datasets = PullDatasetService(db, registry)

    async def handle_request(self, product_id: str, path: str, request: Request) -> Response:
        started = time.perf_counter()
        route_path = path.strip("/")
        method = request.method.upper()
        response: Response

        manifest = self._registry.get_manifest(product_id)
        if manifest is None:
            response = JSONResponse(status_code=404, content={"error": "Product not found"})
            self._persist_unmatched_log(product_id, "unmatched", request, response, started)
            return response

        route = self._registry.get_mock_route(product_id, route_path)
        if route is None or method not in {m.upper() for m in route.methods}:
            response = JSONResponse(status_code=404, content={"error": "Route not found"})
            self._persist_unmatched_log(product_id, "unmatched", request, response, started)
            return response

        simulation = self._resolve_simulation(
            product_id, request, allow_inactive=route.signed_download
        )
        if simulation is None:
            response = JSONResponse(
                status_code=404,
                content={"error": "No active pull_api simulation for this product"},
            )
            self._persist_unmatched_log(product_id, route.id, request, response, started)
            return response

        inbound_settings = InboundConfig.model_validate(simulation.inbound_config or {})
        workflow = self._registry.get_workflow_plugin(product_id)
        try:
            validate_inbound_options(
                manifest,
                dict(inbound_settings.vendor_options),
                workflow_plugin=workflow,
            )
        except ValidationAppError as exc:
            response = self._error_response(workflow, route.id, 422, str(exc))
            self._persist_log(
                simulation,
                route.id,
                request,
                response,
                InboundAuthResult(success=False, method_id="none", message=str(exc)),
                started,
                0,
                route_path,
            )
            return response

        if route.handler == "oauth_token":
            request.scope["workflow_route_id"] = route.id
            return await self._oauth.handle_token_request(
                request,
                simulation=simulation,
                route_id=route.id,
                workflow_plugin=workflow,
                required_scopes=route.required_oauth_scopes,
            )

        auth_config = self._build_inbound_auth_config(simulation, inbound_settings)
        oauth_validator: Callable[[str], InboundAuthResult] | None = None
        if inbound_settings.auth_method_id == "oauth2_client_credentials":

            def oauth_validator(token: str) -> InboundAuthResult:
                return self._oauth.validate_bearer_token(
                    simulation,
                    token,
                    required_scopes=route.required_oauth_scopes,
                )

        auth_result = verify_inbound_auth(
            request,
            auth_config,
            oauth_token_validator=oauth_validator,
        )

        if route.signed_download and callable(getattr(workflow, "handle_native_request", None)):
            auth_result = InboundAuthResult(success=True, method_id="signed_download")

        if not auth_result.success:
            status = 401
            headers = encode_basic_challenge() if inbound_settings.auth_method_id == "basic" else {}
            response = self._error_response(
                workflow,
                route.id,
                status,
                auth_result.message or "Unauthorized",
                headers=headers,
            )
            self._persist_log(
                simulation, route.id, request, response, auth_result, started, 0, route_path
            )
            return response

        profile = route.response_profile
        missing_headers = [
            header_name
            for header_name in profile.required_headers
            if not request.headers.get(header_name)
        ]
        if missing_headers:
            response = self._error_response(
                workflow,
                route.id,
                400,
                f"Missing required request headers: {', '.join(missing_headers)}",
            )
            self._persist_log(
                simulation, route.id, request, response, auth_result, started, 0, route_path
            )
            return response

        try:
            if workflow is not None:
                workflow.validate_inbound_request(
                    route.id,
                    method=method,
                    headers=dict(request.headers),
                    query_params=dict(request.query_params),
                    vendor_options=dict(inbound_settings.vendor_options),
                )
        except VendorWorkflowError as exc:
            response = JSONResponse(
                status_code=exc.status_code,
                content=exc.body,
                headers=exc.headers,
            )
            self._persist_log(
                simulation, route.id, request, response, auth_result, started, 0, route_path
            )
            return response

        fault = inbound_settings.fault_config
        if fault.enabled and fault.delay_ms:
            await asyncio.sleep(fault.delay_ms / 1000)

        if fault.enabled and fault.response_status:
            response = JSONResponse(
                status_code=fault.response_status,
                content={"error": f"Simulated HTTP {fault.response_status}"},
            )
            self._persist_log(
                simulation, route.id, request, response, auth_result, started, 0, route_path
            )
            return response

        native_handler = getattr(workflow, "handle_native_request", None)
        if callable(native_handler):
            native_items_returned = 0
            try:
                request_body: dict[str, Any] = {}
                if request.method == "POST":
                    raw = await request.body()
                    if len(raw) > 1_000_000:
                        raise VendorWorkflowError(413, {"message": "Request body too large"})
                    import json

                    try:
                        request_body = json.loads(raw)
                    except (ValueError, UnicodeDecodeError) as exc:
                        raise VendorWorkflowError(400, {"message": "Invalid JSON body"}) from exc
                    if not isinstance(request_body, dict):
                        raise VendorWorkflowError(400, {"message": "Expected JSON object"})

                def page_reader(
                    route_id: str,
                    limit: int,
                    cursor: str | None,
                    since: datetime | None,
                    until: datetime | None,
                    types: set[str] | None,
                ) -> tuple[list[dict[str, Any]], str | None, str, int]:
                    nonlocal native_items_returned
                    data_route = next(
                        r
                        for r in manifest.mock_routes
                        if r.id == route_id and r.handler == "dataset_list"
                    )

                    def transform(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
                        records = [item.get("record", item) for item in items]
                        if types:
                            records = [r for r in records if r.get("type") in types]
                        if until:

                            def in_range(record: dict[str, Any]) -> bool:
                                value = record.get("timestamp", record.get("eventTime"))
                                if isinstance(value, int):
                                    return datetime.fromtimestamp(value / 1000, tz=UTC) <= until
                                return (
                                    datetime.fromisoformat(str(value).replace("Z", "+00:00"))
                                    <= until
                                )

                            records = [r for r in records if in_range(r)]
                        return records

                    page = self._datasets.custom_page(
                        route=data_route,
                        simulation=simulation,
                        limit=limit,
                        cursor=cursor,
                        since=since,
                        force_empty=fault.enabled and fault.force_empty,
                        transform=transform,
                    )
                    native_items_returned = len(page[0])
                    return page

                shaped = native_handler(
                    NativeRequest(
                        route_id=route.id,
                        method=method,
                        url=str(request.url),
                        query=dict(request.query_params),
                        body=request_body,
                        simulation_id=simulation.id,
                        activation_id=str(
                            (simulation.runtime_state or {}).get("pull_dataset_activation_id") or ""
                        ),
                        signing_key=resolve_secret_key(),
                        options=dict(inbound_settings.vendor_options),
                        page=page_reader,
                    )
                )
                if shaped.raw_content is not None:
                    response = Response(
                        content=shaped.raw_content,
                        status_code=shaped.status_code,
                        headers=shaped.headers,
                        media_type=shaped.media_type,
                    )
                elif fault.enabled and fault.malformed_json:
                    response = Response(content="{ malformed", media_type="application/json")
                else:
                    if (
                        fault.enabled
                        and fault.pagination_inconsistent
                        and isinstance(shaped.body, dict)
                    ):
                        if "@nextPage" in shaped.body:
                            shaped.body["@nextPage"] = "invalid-cursor-token"
                        elif isinstance(shaped.body.get("meta"), dict):
                            shaped.body["meta"].get("pagination", {})["next"] = (
                                "invalid-cursor-token"
                            )
                    response = JSONResponse(
                        content=shaped.body, status_code=shaped.status_code, headers=shaped.headers
                    )
            except (VendorWorkflowError, ValidationAppError) as exc:
                if isinstance(exc, VendorWorkflowError):
                    if route.signed_download and exc.status_code == 403:
                        auth_result = InboundAuthResult(
                            success=False,
                            method_id="signed_download",
                            message="Invalid or expired download link",
                        )
                    response = JSONResponse(
                        status_code=exc.status_code, content=exc.body, headers=exc.headers
                    )
                else:
                    response = self._error_response(workflow, route.id, 400, str(exc))
            self._persist_log(
                simulation,
                route.id,
                request,
                response,
                auth_result,
                started,
                native_items_returned,
                route_path,
            )
            return response

        scenario = self._registry.get_scenario(product_id, route.scenario_id)
        if scenario is None:
            response = JSONResponse(status_code=500, content={"error": "Scenario not found"})
            self._persist_log(
                simulation, route.id, request, response, auth_result, started, 0, route_path
            )
            return response

        query_params = dict(request.query_params)
        default_limit = profile.default_limit or inbound_settings.default_page_size
        maximum_limit = profile.maximum_limit or inbound_settings.max_page_size
        limit = parse_limit(
            {"limit": query_params.get(profile.limit_request_param, "")},
            default_limit,
            maximum_limit,
        )
        raw_limit = query_params.get(profile.limit_request_param)
        if raw_limit and (
            not raw_limit.isdigit()
            or int(raw_limit) < profile.minimum_limit
            or int(raw_limit) > maximum_limit
        ):
            response = self._error_response(
                workflow,
                route.id,
                400,
                f"{profile.limit_request_param} must be between "
                f"{profile.minimum_limit} and {maximum_limit}",
            )
            self._persist_log(
                simulation, route.id, request, response, auth_result, started, 0, route_path
            )
            return response
        since = None
        if route.supports_time_filter:
            since_key = profile.since_request_param
            since = (
                parse_time_filter({"since": query_params.get(since_key, "")})
                if since_key
                else parse_time_filter(query_params)
            )
        cursor = query_params.get(profile.cursor_request_param) or next(
            (
                query_params[key]
                for key in ("pageToken", "nextPageToken", "cursor")
                if query_params.get(key)
            ),
            None,
        )
        force_empty = fault.enabled and fault.force_empty

        response_status = 200
        response_headers = dict(profile.response_headers)
        if route.handler == "static":
            shaped = (
                workflow.build_static_response(
                    route.id,
                    request_url=str(request.url),
                    vendor_options=dict(inbound_settings.vendor_options),
                )
                if workflow is not None
                else None
            )
            if shaped is None:
                body: Any = self._datasets.single_response(simulation, route)
                items_returned = 1
            else:
                body = shaped.body
                response_status = shaped.status_code
                response_headers.update(shaped.headers)
                items_returned = 0
        elif route.handler == "dataset_single":
            body = self._datasets.single_response(simulation, route)
            items_returned = 1
        else:
            transform = None
            if workflow is not None:

                def transform(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
                    return workflow.filter_inbound_items(route.id, items, query_params)

            try:
                items, next_cursor, terminal_cursor, total = self._datasets.custom_page(
                    route=route,
                    simulation=simulation,
                    limit=limit,
                    cursor=cursor,
                    since=since,
                    force_empty=force_empty,
                    transform=transform,
                )
            except ValidationAppError as exc:
                response = self._error_response(
                    workflow,
                    route.id,
                    400 if workflow is not None else 422,
                    str(exc),
                )
                self._persist_log(
                    simulation,
                    route.id,
                    request,
                    response,
                    auth_result,
                    started,
                    0,
                    route_path,
                )
                return response
            if profile.body_style == "array":
                body = items
            else:
                body = {route.items_field: items}
                if next_cursor and profile.pagination_location == "body":
                    body[profile.cursor_response_field] = next_cursor
            items_returned = len(items)
            shaped = (
                workflow.build_inbound_response(
                    route.id,
                    items=items,
                    next_cursor=next_cursor,
                    terminal_cursor=terminal_cursor,
                    total=total,
                    request_url=str(request.url),
                    query_params=query_params,
                    vendor_options=dict(inbound_settings.vendor_options),
                    default_body=body,
                )
                if workflow is not None
                else None
            )
            if shaped is not None:
                body = shaped.body
                response_status = shaped.status_code
                response_headers.update(shaped.headers)

        if fault.enabled and fault.malformed_json:
            serialized = apply_inbound_fault_body(
                body,
                fault,
                pagination_inconsistent=fault.pagination_inconsistent,
            )
            response = Response(
                content=serialized,
                media_type="application/json",
                status_code=response_status,
                headers=response_headers,
            )
        else:
            if fault.enabled and fault.pagination_inconsistent and isinstance(body, dict):
                body = dict(body)
                for key in ("nextPageToken", "nextToken", "cursor"):
                    if key in body:
                        body[key] = "invalid-cursor-token"
                        break
            response = JSONResponse(
                status_code=response_status,
                content=body,
                headers=response_headers,
            )

        self._persist_log(
            simulation,
            route.id,
            request,
            response,
            auth_result,
            started,
            items_returned,
            route_path,
        )
        return response

    @staticmethod
    def _error_response(
        workflow: Any | None,
        route_id: str,
        status_code: int,
        message: str,
        *,
        headers: dict[str, str] | None = None,
    ) -> JSONResponse:
        body = (
            workflow.format_inbound_error(route_id, status_code, message)
            if workflow is not None
            else {"error": message}
        )
        return JSONResponse(status_code=status_code, content=body, headers=headers or {})

    def _resolve_simulation(
        self, product_id: str, request: Request, *, allow_inactive: bool = False
    ) -> Simulation | None:
        simulation_id = request.query_params.get("simulation_id") or request.headers.get(
            "X-Simulator-Simulation-Id"
        )
        if simulation_id:
            simulation = self._simulations.get_by_id(simulation_id)
            if (
                simulation
                and simulation.product_id == product_id
                and simulation.simulation_mode == SimulationMode.PULL_API.value
                and (allow_inactive or simulation.status == SimulationStatus.RUNNING.value)
            ):
                return simulation
            return None

        running = self._simulations.list_by_product_and_mode(
            product_id, SimulationMode.PULL_API.value, SimulationStatus.RUNNING.value
        )
        return running[0] if running else None

    def _build_inbound_auth_config(
        self, simulation: Simulation, inbound_settings: InboundConfig
    ) -> dict[str, Any]:
        decrypted = self._encryptor.decrypt_auth_config(simulation.auth_config)
        method = inbound_settings.auth_method_id
        config: dict[str, Any] = {
            "auth_method_id": method,
            "api_key_header": inbound_settings.api_key_header,
            "api_key_query_param": inbound_settings.api_key_query_param,
            "api_key_prefix": inbound_settings.api_key_prefix,
        }
        if method == "api_key":
            config["token"] = decrypted.get("token") or decrypted.get("api_key")
        elif method == "basic":
            config["username"] = decrypted.get("username")
            config["password"] = decrypted.get("password")
        elif method == "bearer":
            config["token"] = decrypted.get("token")
        elif method == "oauth2_client_credentials":
            config["oauth_client_id"] = decrypted.get("oauth_client_id")
        return config

    def _update_runtime_stats(
        self, simulation: Simulation, items_returned: int, *, success: bool
    ) -> None:
        runtime = dict(simulation.runtime_state or {})
        runtime["inbound_requests_total"] = runtime.get("inbound_requests_total", 0) + 1
        counter = "inbound_requests_successful" if success else "inbound_requests_failed"
        runtime[counter] = runtime.get(counter, 0) + 1
        runtime["inbound_items_returned_total"] = (
            runtime.get("inbound_items_returned_total", 0) + items_returned
        )
        runtime["last_inbound_at"] = datetime.now(UTC).isoformat()
        runtime["last_inbound_items"] = items_returned
        simulation.runtime_state = runtime

    def _persist_log(
        self,
        simulation: Simulation,
        route_id: str,
        request: Request,
        response: Response,
        auth_result: InboundAuthResult,
        started: float,
        items_returned: int,
        route_path: str,
    ) -> None:
        inbound_settings = InboundConfig.model_validate(simulation.inbound_config or {})
        auth_config = self._build_inbound_auth_config(simulation, inbound_settings)
        sensitive = inbound_sensitive_header_names(auth_config)
        headers = redact_headers(
            {k: v for k, v in request.headers.items()},
            extra_sensitive=sensitive,
        )
        query_params = dict(request.query_params)
        if "token" in query_params:
            query_params["token"] = REDACTED
        if (
            inbound_settings.api_key_query_param
            and inbound_settings.api_key_query_param in query_params
        ):
            query_params[inbound_settings.api_key_query_param] = REDACTED
        generic_query = redact_mapping(query_params)
        query_params = generic_query if isinstance(generic_query, dict) else {}

        decrypted = self._encryptor.decrypt_auth_config(simulation.auth_config or {})
        secret_values = {
            str(decrypted[field])
            for field in ("password", "token", "oauth_client_secret", "api_key")
            if decrypted.get(field)
        }

        response_body: str | None = ""
        if isinstance(response, JSONResponse):
            content = response.body
            if content:
                response_body = truncate_body(
                    content.decode("utf-8", errors="replace")
                    if isinstance(content, bytes | bytearray)
                    else str(content)
                )
        elif response.body is not None:
            response_body = truncate_body(
                response.body.decode("utf-8", errors="replace")
                if isinstance(response.body, bytes | bytearray)
                else str(response.body)
            )

        if response.headers.get("content-type", "").startswith("application/gzip"):
            response_body = f"[binary gzip response: {len(response.body)} bytes]"
        if response_body:
            import re

            response_body = re.sub(r'(token=)[^&"\s]+', r"\1***REDACTED***", response_body)
        response_body = redact_secret_values(response_body, secret_values)
        success = auth_result.success and response.status_code < 400
        log = InboundRequestLog(
            simulation_id=simulation.id,
            product_id=simulation.product_id,
            route_id=route_id,
            received_at=datetime.now(UTC),
            request_method=request.method.upper(),
            request_path=f"/api/v1/mock/{simulation.product_id}/{route_path}",
            request_query_params=query_params,
            request_headers_redacted=headers,
            request_body=None,
            response_status_code=response.status_code,
            response_headers=dict(response.headers),
            response_body=response_body,
            auth_method_id=auth_result.method_id,
            auth_result="success" if auth_result.success else "failed",
            latency_ms=max(int((time.perf_counter() - started) * 1000), 0),
            items_returned=items_returned,
            error_message=None if auth_result.success else auth_result.message,
            request_kind="api",
            token_metadata=None,
        )
        self._inbound_logs.create(log)
        self._update_runtime_stats(simulation, items_returned, success=success)
        self._db.commit()

    def _persist_unmatched_log(
        self,
        product_id: str,
        route_id: str,
        request: Request,
        response: Response,
        started: float,
    ) -> None:
        query = redact_mapping(dict(request.query_params))
        response_body = (
            response.body.decode("utf-8", errors="replace")
            if isinstance(response.body, bytes | bytearray)
            else str(response.body or "")
        )
        self._inbound_logs.create(
            InboundRequestLog(
                simulation_id=None,
                product_id=product_id,
                route_id=route_id,
                received_at=datetime.now(UTC),
                request_method=request.method.upper(),
                request_path=request.url.path,
                request_query_params=query if isinstance(query, dict) else {},
                request_headers_redacted=redact_headers(dict(request.headers)),
                request_body=None,
                response_status_code=response.status_code,
                response_headers=dict(response.headers),
                response_body=truncate_body(response_body),
                auth_method_id="none",
                auth_result="unmatched",
                latency_ms=max(int((time.perf_counter() - started) * 1000), 0),
                items_returned=0,
                error_message="Request did not resolve to an active simulation",
                request_kind="api",
                token_metadata=None,
            )
        )
        self._db.commit()

    def list_requests(
        self, simulation_id: str, *, limit: int = 50, request_kind: str | None = None
    ) -> list[InboundRequestLog]:
        return self._inbound_logs.list_requests(
            simulation_id, limit=limit, request_kind=request_kind
        )

    def list_all_requests(
        self,
        *,
        limit: int = 100,
        simulation_id: str | None = None,
        request_kind: str | None = None,
        response_status: int | None = None,
    ) -> list[InboundRequestLog]:
        return self._inbound_logs.list_all(
            limit=limit,
            simulation_id=simulation_id,
            request_kind=request_kind,
            response_status=response_status,
        )

    def get_request(self, simulation_id: str, request_id: str) -> InboundRequestLog | None:
        return self._inbound_logs.get_by_id(simulation_id, request_id)

    def get_request_any(self, request_id: str) -> InboundRequestLog | None:
        return self._inbound_logs.get_by_id_any(request_id)

    def get_endpoint_info(
        self, simulation_id: str, *, public_base_url: str
    ) -> dict[str, Any] | None:
        simulation = self._simulations.get_by_id(simulation_id)
        if simulation is None:
            return None
        manifest = self._registry.get_manifest(simulation.product_id)
        if manifest is None:
            return None
        inbound_settings = InboundConfig.model_validate(simulation.inbound_config or {})
        base_url = public_base_url.rstrip("/")
        routes = []
        for route in manifest.mock_routes:
            path = f"/api/v1/mock/{simulation.product_id}/{route.path}"
            routes.append(
                {
                    "id": route.id,
                    "path": path,
                    "url": f"{base_url}{path}?simulation_id={simulation.id}",
                    "methods": route.methods,
                    "handler": route.handler or "dataset_list",
                }
            )
        oauth_token_url = None
        if inbound_settings.auth_method_id == "oauth2_client_credentials":
            oauth_token_url = next(
                (route["url"] for route in routes if route["handler"] == "oauth_token"),
                f"{base_url}/api/v1/oauth2/token?simulation_id={simulation.id}",
            )
        discovery_urls = [route["url"] for route in routes if route["handler"] == "static"]
        api_urls = [
            route["url"]
            for route in routes
            if route["handler"] in {"dataset_list", "dataset_single"}
        ]
        return {
            "simulation_id": simulation.id,
            "product_id": simulation.product_id,
            "simulation_mode": simulation.simulation_mode,
            "status": simulation.status,
            "auth_method_id": inbound_settings.auth_method_id,
            "routes": routes,
            "oauth_token_url": oauth_token_url,
            "discovery_urls": discovery_urls,
            "api_urls": api_urls,
            "oauth_token_ttl_seconds": inbound_settings.oauth_token_ttl_seconds,
            "oauth_allowed_scopes": inbound_settings.oauth_allowed_scopes,
            "vendor_options": inbound_settings.vendor_options,
            "query_hint": (
                "Pass simulation_id query param when multiple pull simulations " "share a product"
            ),
        }

    def list_issued_tokens(self, simulation_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
        return self._oauth.list_issued_tokens(simulation_id, limit=limit)
