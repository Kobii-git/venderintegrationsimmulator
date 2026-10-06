"""OAuth2 client-credentials token issuance and validation."""

from __future__ import annotations

import base64
import json
import secrets
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import parse_qs

from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.redaction import REDACTED, truncate_body
from app.core.security import SecretEncryptor
from app.domain.enums import SimulationMode, SimulationStatus
from app.domain.inbound import InboundConfig
from app.inbound.auth import InboundAuthResult
from app.models import InboundRequestLog, OAuthAccessToken, Simulation
from app.products.workflow import ProductWorkflowPlugin
from app.repositories.inbound import InboundRequestRepository
from app.repositories.oauth import OAuthTokenRepository
from app.repositories.simulation import SimulationRepository

OAUTH_TOKEN_ROUTE_ID = "oauth_token"
OAUTH_TOKEN_PATH = "/api/v1/oauth2/token"


@dataclass
class IssuedToken:
    access_token: str
    token_type: str
    expires_in: int
    scope: str | None
    record_id: str


class OAuthTokenService:
    """Issue and validate OAuth2 client-credentials tokens for pull simulations."""

    def __init__(
        self,
        db: Session,
        encryptor: SecretEncryptor,
    ) -> None:
        self._db = db
        self._encryptor = encryptor
        self._simulations = SimulationRepository(db)
        self._tokens = OAuthTokenRepository(db)
        self._inbound_logs = InboundRequestRepository(db)

    async def handle_token_request(
        self,
        request: Request,
        *,
        simulation: Simulation | None = None,
        route_id: str = OAUTH_TOKEN_ROUTE_ID,
        workflow_plugin: ProductWorkflowPlugin | None = None,
        required_scopes: list[str] | None = None,
    ) -> JSONResponse:
        started = time.perf_counter()
        simulation = simulation or self._resolve_simulation(request)

        def oauth_error(
            error: str,
            description: str,
            *,
            status_code: int = 400,
        ) -> JSONResponse:
            body: dict[str, Any] = {"error": error, "error_description": description}
            if workflow_plugin is not None:
                body = workflow_plugin.format_oauth_error(route_id, body)
            return JSONResponse(
                status_code=status_code,
                content=body,
                headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
            )

        if simulation is None:
            return oauth_error(
                "invalid_request",
                "No active pull_api simulation found; pass simulation_id",
                status_code=400,
            )

        inbound_settings = InboundConfig.model_validate(simulation.inbound_config or {})
        if inbound_settings.auth_method_id != "oauth2_client_credentials":
            return oauth_error(
                "invalid_request",
                "Simulation is not configured for OAuth2 client credentials",
                status_code=400,
            )

        fault = inbound_settings.oauth_fault_config
        if fault.enabled and fault.token_endpoint_failure:
            status = fault.token_endpoint_status or 503
            response = oauth_error(
                "temporarily_unavailable",
                "Simulated token endpoint failure",
                status_code=status,
            )
            self._persist_token_log(
                simulation,
                request,
                response,
                auth_result=InboundAuthResult(success=False, method_id="oauth2_client_credentials"),
                started=started,
                token_metadata=None,
            )
            return response

        form = await self._parse_token_request(request)
        grant_type = form.get("grant_type", [""])[0]
        if grant_type != "client_credentials":
            response = oauth_error(
                "unsupported_grant_type",
                "Only client_credentials grant is supported",
            )
            self._persist_token_log(
                simulation,
                request,
                response,
                auth_result=InboundAuthResult(success=False, method_id="oauth2_client_credentials"),
                started=started,
                token_metadata=None,
                request_body=self._redact_token_request_body(form),
            )
            return response

        client_id, client_secret = self._extract_client_credentials(request, form)
        if fault.enabled and fault.invalid_client:
            response = oauth_error("invalid_client", "Simulated invalid client", status_code=401)
            self._persist_token_log(
                simulation,
                request,
                response,
                auth_result=InboundAuthResult(success=False, method_id="oauth2_client_credentials"),
                started=started,
                token_metadata=None,
                request_body=self._redact_token_request_body(form),
            )
            return response

        auth_config = self._encryptor.decrypt_auth_config(simulation.auth_config)
        expected_client_id = auth_config.get("oauth_client_id")
        expected_client_secret = auth_config.get("oauth_client_secret")
        if not expected_client_id or not expected_client_secret:
            response = oauth_error(
                "invalid_client",
                "OAuth client credentials are not configured on this simulation",
                status_code=401,
            )
            self._persist_token_log(
                simulation,
                request,
                response,
                auth_result=InboundAuthResult(success=False, method_id="oauth2_client_credentials"),
                started=started,
                token_metadata=None,
                request_body=self._redact_token_request_body(form),
            )
            return response

        if client_id != expected_client_id or client_secret != expected_client_secret:
            response = oauth_error("invalid_client", "Invalid client credentials", status_code=401)
            self._persist_token_log(
                simulation,
                request,
                response,
                auth_result=InboundAuthResult(success=False, method_id="oauth2_client_credentials"),
                started=started,
                token_metadata=None,
                request_body=self._redact_token_request_body(form),
            )
            return response

        assert client_id is not None

        requested_scope = form.get("scope", [""])[0] or None
        if fault.enabled and fault.wrong_scope:
            response = oauth_error("invalid_scope", "Simulated invalid scope", status_code=400)
            self._persist_token_log(
                simulation,
                request,
                response,
                auth_result=InboundAuthResult(success=False, method_id="oauth2_client_credentials"),
                started=started,
                token_metadata=None,
                request_body=self._redact_token_request_body(form),
            )
            return response

        requested_parts = set(requested_scope.split()) if requested_scope else set()
        required = set(required_scopes or [])
        if required and requested_parts != required:
            response = oauth_error(
                "invalid_scope",
                "Requested scope does not match this product workflow",
                status_code=400,
            )
            self._persist_token_log(
                simulation,
                request,
                response,
                auth_result=InboundAuthResult(success=False, method_id="oauth2_client_credentials"),
                started=started,
                token_metadata=None,
                request_body=self._redact_token_request_body(form),
            )
            return response

        if requested_scope and inbound_settings.oauth_allowed_scopes:
            allowed = set(inbound_settings.oauth_allowed_scopes)
            if not requested_parts.issubset(allowed):
                response = oauth_error(
                    "invalid_scope",
                    "Requested scope is not allowed for this simulation",
                    status_code=400,
                )
                self._persist_token_log(
                    simulation,
                    request,
                    response,
                    auth_result=InboundAuthResult(
                        success=False, method_id="oauth2_client_credentials"
                    ),
                    started=started,
                    token_metadata=None,
                    request_body=self._redact_token_request_body(form),
                )
                return response

        issued = self._issue_token(
            simulation,
            client_id=client_id,
            scope=requested_scope,
            ttl_seconds=inbound_settings.oauth_token_ttl_seconds,
            force_expired=fault.enabled and fault.reject_tokens_as_expired,
        )
        body = {
            "access_token": issued.access_token,
            "token_type": issued.token_type,
            "expires_in": issued.expires_in,
        }
        if issued.scope:
            body["scope"] = issued.scope
        if workflow_plugin is not None:
            body = workflow_plugin.format_oauth_success(route_id, body)

        response = JSONResponse(
            status_code=200,
            content=body,
            headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
        )
        token_metadata = {
            "client_id": client_id,
            "scope": issued.scope,
            "expires_in": issued.expires_in,
            "token_record_id": issued.record_id,
        }
        self._persist_token_log(
            simulation,
            request,
            response,
            auth_result=InboundAuthResult(success=True, method_id="oauth2_client_credentials"),
            started=started,
            token_metadata=token_metadata,
            request_body=self._redact_token_request_body(form),
        )
        self._update_runtime_stats(simulation, token_issued=True)
        return response

    def validate_bearer_token(
        self,
        simulation: Simulation,
        bearer_token: str,
        *,
        required_scopes: list[str] | None = None,
    ) -> InboundAuthResult:
        inbound_settings = InboundConfig.model_validate(simulation.inbound_config or {})
        fault = inbound_settings.oauth_fault_config
        if fault.enabled and fault.reject_tokens_as_expired:
            return InboundAuthResult(
                success=False,
                method_id="oauth2_client_credentials",
                message="Access token expired",
            )

        token_hash = OAuthTokenRepository.hash_token(bearer_token)
        record = self._tokens.get_by_hash(token_hash)
        if record is None or record.simulation_id != simulation.id:
            return InboundAuthResult(
                success=False,
                method_id="oauth2_client_credentials",
                message="Invalid bearer token",
            )

        now = datetime.now(UTC)
        expires_at = record.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if now >= expires_at:
            return InboundAuthResult(
                success=False,
                method_id="oauth2_client_credentials",
                message="Access token expired",
            )

        if inbound_settings.oauth_allowed_scopes and record.scope:
            requested_parts = set(record.scope.split())
            allowed = set(inbound_settings.oauth_allowed_scopes)
            if not requested_parts.issubset(allowed):
                return InboundAuthResult(
                    success=False,
                    method_id="oauth2_client_credentials",
                    message="Insufficient scope",
                )

        if required_scopes:
            token_scopes = set(record.scope.split()) if record.scope else set()
            if not set(required_scopes).issubset(token_scopes):
                return InboundAuthResult(
                    success=False,
                    method_id="oauth2_client_credentials",
                    message="Insufficient scope",
                )

        return InboundAuthResult(success=True, method_id="oauth2_client_credentials")

    def list_issued_tokens(self, simulation_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
        records = self._tokens.list_for_simulation(simulation_id, limit=limit)
        now = datetime.now(UTC)
        return [
            {
                "id": record.id,
                "client_id": record.client_id,
                "scope": record.scope,
                "issued_at": record.issued_at,
                "expires_at": record.expires_at,
                "revoked": record.revoked,
                "is_expired": (
                    (
                        record.expires_at.replace(tzinfo=UTC)
                        if record.expires_at.tzinfo is None
                        else record.expires_at
                    )
                    <= now
                ),
            }
            for record in records
        ]

    def _issue_token(
        self,
        simulation: Simulation,
        *,
        client_id: str,
        scope: str | None,
        ttl_seconds: int,
        force_expired: bool,
    ) -> IssuedToken:
        access_token = secrets.token_urlsafe(32)
        token_hash = OAuthTokenRepository.hash_token(access_token)
        now = datetime.now(UTC)
        if force_expired:
            expires_at = now - timedelta(seconds=1)
            expires_in = 0
        else:
            expires_at = now + timedelta(seconds=ttl_seconds)
            expires_in = ttl_seconds

        record = OAuthAccessToken(
            simulation_id=simulation.id,
            token_hash=token_hash,
            client_id=client_id,
            scope=scope,
            issued_at=now,
            expires_at=expires_at,
        )
        self._tokens.create(record)
        self._db.commit()
        return IssuedToken(
            access_token=access_token,
            token_type="Bearer",
            expires_in=expires_in,
            scope=scope,
            record_id=record.id,
        )

    def _resolve_simulation(self, request: Request) -> Simulation | None:
        simulation_id = request.query_params.get("simulation_id") or request.headers.get(
            "X-Simulator-Simulation-Id"
        )
        if not simulation_id:
            form_simulation_id = request.query_params.get("simulation_id")
            if form_simulation_id:
                simulation_id = form_simulation_id

        if simulation_id:
            simulation = self._simulations.get_by_id(simulation_id)
            if (
                simulation
                and simulation.simulation_mode == SimulationMode.PULL_API.value
                and simulation.status == SimulationStatus.RUNNING.value
            ):
                return simulation
            return None

        running = self._simulations.list_by_status(SimulationStatus.RUNNING)
        pull_running = [
            sim
            for sim in running
            if sim.simulation_mode == SimulationMode.PULL_API.value
            and InboundConfig.model_validate(sim.inbound_config or {}).auth_method_id
            == "oauth2_client_credentials"
        ]
        return pull_running[0] if len(pull_running) == 1 else None

    async def _parse_token_request(self, request: Request) -> dict[str, list[str]]:
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            payload = await request.json()
            if isinstance(payload, dict):
                return {str(k): [str(v)] for k, v in payload.items()}
            return {}
        body = await request.body()
        if not body:
            return {}
        decoded = body.decode("utf-8", errors="replace")
        return parse_qs(decoded, keep_blank_values=True)

    def _extract_client_credentials(
        self, request: Request, form: dict[str, list[str]]
    ) -> tuple[str | None, str | None]:
        client_id = form.get("client_id", [None])[0]
        client_secret = form.get("client_secret", [None])[0]
        if client_id and client_secret:
            return client_id, client_secret

        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Basic "):
            try:
                decoded = base64.b64decode(auth_header[6:]).decode("utf-8")
                user, _, password = decoded.partition(":")
                return user or None, password or None
            except (ValueError, UnicodeDecodeError):
                return None, None
        return client_id, client_secret

    def _oauth_error(
        self,
        error: str,
        description: str,
        *,
        status_code: int = 400,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status_code,
            content={"error": error, "error_description": description},
            headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
        )

    def _redact_token_request_body(self, form: dict[str, list[str]]) -> str:
        redacted = {
            key: (REDACTED if key == "client_secret" else values[0] if values else "")
            for key, values in form.items()
        }
        return truncate_body(json.dumps(redacted, separators=(",", ":"))) or ""

    def _redact_token_response_body(self, response: JSONResponse) -> str:
        raw = ""
        body = getattr(response, "body", None)
        if body:
            raw = (
                body.decode("utf-8", errors="replace")
                if isinstance(body, bytes | bytearray)
                else str(body)
            )
        if not raw:
            return ""
        try:
            content = json.loads(raw)
        except json.JSONDecodeError:
            return truncate_body(raw) or ""
        if not isinstance(content, dict):
            return truncate_body(raw) or ""
        redacted = dict(content)
        for field in ("access_token", "refresh_token"):
            if field in redacted:
                redacted[field] = REDACTED
        return truncate_body(json.dumps(redacted, separators=(",", ":"))) or ""

    def _persist_token_log(
        self,
        simulation: Simulation,
        request: Request,
        response: JSONResponse,
        *,
        auth_result: InboundAuthResult,
        started: float,
        token_metadata: dict[str, Any] | None,
        request_body: str | None = None,
    ) -> None:
        from app.core.redaction import redact_headers

        headers = redact_headers(
            {k: v for k, v in request.headers.items()},
            extra_sensitive={"authorization"},
        )
        log = InboundRequestLog(
            simulation_id=simulation.id,
            product_id=simulation.product_id,
            route_id=str(request.scope.get("workflow_route_id") or OAUTH_TOKEN_ROUTE_ID),
            received_at=datetime.now(UTC),
            request_method=request.method.upper(),
            request_path=request.url.path,
            request_query_params=dict(request.query_params),
            request_headers_redacted=headers,
            request_body=request_body,
            response_status_code=response.status_code,
            response_headers=dict(response.headers),
            response_body=self._redact_token_response_body(response),
            auth_method_id=auth_result.method_id,
            auth_result="success" if auth_result.success else "failed",
            latency_ms=max(int((time.perf_counter() - started) * 1000), 0),
            items_returned=0,
            error_message=None if auth_result.success else auth_result.message,
            request_kind="token",
            token_metadata=token_metadata,
        )
        self._inbound_logs.create(log)
        self._db.commit()

    def _update_runtime_stats(self, simulation: Simulation, *, token_issued: bool) -> None:
        runtime = dict(simulation.runtime_state or {})
        runtime["inbound_requests_total"] = runtime.get("inbound_requests_total", 0) + 1
        if token_issued:
            runtime["oauth_tokens_issued_total"] = runtime.get("oauth_tokens_issued_total", 0) + 1
        runtime["last_inbound_at"] = datetime.now(UTC).isoformat()
        simulation.runtime_state = runtime
        self._simulations.update(simulation)
