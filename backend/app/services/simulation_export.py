"""Export and import simulation configurations."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qsl, urlsplit, urlunsplit

from app.core.exceptions import ValidationAppError
from app.core.http_url import reject_embedded_url_credentials
from app.core.security import SecretEncryptor
from app.domain.fault_config import parse_fault_config
from app.domain.inbound import InboundConfig
from app.repositories.simulation import SimulationRepository
from app.schemas.simulation import (
    AuthConfigInput,
    ConfiguredValueInput,
    DestinationConfig,
    ScheduleConfig,
    SimulationCreate,
    SimulationResponse,
    TargetInput,
)
from app.schemas.simulation_export import (
    SUPPORTED_EXPORT_FORMAT_VERSIONS,
    ExportedAuthConfig,
    ExportedSimulation,
    SimulationExportDocument,
    SimulationImportResponse,
)
from app.services.destination_config import destination_for_export
from app.services.simulation import SimulationService
from app.services.targets import target_configs

logger = logging.getLogger(__name__)


class SimulationExportService:
    """Serialize and deserialize simulation configurations."""

    def __init__(
        self,
        repo: SimulationRepository,
        catalog: SimulationService,
        encryptor: SecretEncryptor,
    ) -> None:
        self._repo = repo
        self._catalog = catalog
        self._encryptor = encryptor

    def export_simulation(
        self,
        simulation_id: str,
        *,
        include_secrets: bool = False,
    ) -> SimulationExportDocument:
        simulation = self._repo.get_by_id_or_raise(simulation_id)
        auth_public = self._encryptor.sanitize_auth_config_for_api(simulation.auth_config)
        exported_auth = ExportedAuthConfig(
            auth_method_id=auth_public.get("auth_method_id", "none"),
            username=auth_public.get("username"),
            header_name=auth_public.get("header_name"),
            header_prefix=auth_public.get("header_prefix"),
            has_password=bool(auth_public.get("has_password")),
            has_token=bool(auth_public.get("has_token")),
            oauth_client_id=auth_public.get("oauth_client_id"),
            has_oauth_client_secret=bool(auth_public.get("has_oauth_client_secret")),
        )

        if include_secrets:
            decrypted = self._encryptor.decrypt_auth_config(simulation.auth_config)
            exported_auth.password = decrypted.get("password")
            exported_auth.token = decrypted.get("token")
            exported_auth.oauth_client_secret = decrypted.get("oauth_client_secret")
            logger.warning(
                "Simulation exported with secrets",
                extra={"simulation_id": simulation_id, "audit": "secret_export"},
            )

        return SimulationExportDocument(
            exported_at=datetime.now(UTC),
            includes_secrets=include_secrets,
            simulation=ExportedSimulation(
                name=simulation.name,
                product_id=simulation.product_id,
                scenario_id=simulation.scenario_id,
                scenario_ids=simulation.scenario_ids or [simulation.scenario_id],
                simulation_mode=simulation.simulation_mode,
                fidelity_mode=simulation.fidelity_mode,
                destination=destination_for_export(
                    simulation.destination or {},
                    simulation.destination_secret_values or {},
                    self._encryptor,
                    include_secrets=include_secrets,
                ),
                auth_config=exported_auth,
                scenario_overrides=dict(simulation.scenario_overrides or {}),
                schedule=dict(simulation.schedule or {}),
                fault_config=dict(simulation.fault_config or {}),
                inbound_config=dict(simulation.inbound_config or {}),
                random_seed=simulation.random_seed,
                targets=self._export_targets(simulation, include_secrets),
                devices=simulation.devices or [],
                replay_config=simulation.replay_config or {},
            ),
        )

    def _export_targets(self, simulation: Any, include_secrets: bool) -> list[dict[str, Any]]:
        if simulation.simulation_mode == "pull_api":
            return []
        result = []
        for target in target_configs(simulation):
            item = {
                k: v
                for k, v in target.items()
                if k not in ("destination_secret_values", "auth_config", "destination")
            }
            item["destination"] = destination_for_export(
                target["destination"],
                target.get("destination_secret_values", {}),
                self._encryptor,
                include_secrets=include_secrets,
            )
            auth = self._encryptor.sanitize_auth_config_for_api(target.get("auth_config", {}))
            if include_secrets:
                auth.update(
                    {
                        k: v
                        for k, v in self._encryptor.decrypt_auth_config(
                            target.get("auth_config", {})
                        ).items()
                        if k in ("password", "token", "oauth_client_secret")
                    }
                )
            item["auth_config"] = auth
            result.append(item)
        return result

    def import_simulation(
        self, document: SimulationExportDocument | dict[str, Any]
    ) -> SimulationImportResponse:
        raw_document = (
            document.model_dump(mode="json")
            if isinstance(document, SimulationExportDocument)
            else dict(document)
        )
        if str(raw_document.get("format_version", "")) == "1.0":
            raw_document = self._convert_v1_document(raw_document)
        document = SimulationExportDocument.model_validate(raw_document)
        if document.format_version not in SUPPORTED_EXPORT_FORMAT_VERSIONS:
            raise ValidationAppError(
                f"Unsupported export format version: {document.format_version}",
                details={"supported_versions": sorted(SUPPORTED_EXPORT_FORMAT_VERSIONS)},
            )

        exported = document.simulation
        auth_input = self._build_auth_input(exported.auth_config, document.includes_secrets)
        fault_config = parse_fault_config(exported.fault_config)
        inbound_raw = dict(exported.inbound_config)
        if document.format_version == "1.0":
            legacy_username = inbound_raw.pop("username", None)
            legacy_password = inbound_raw.pop("password", None)
            legacy_token = inbound_raw.pop("token", None)
            if auth_input.username is None and legacy_username is not None:
                auth_input.username = str(legacy_username)
            if document.includes_secrets:
                auth_input.password = auth_input.password or legacy_password
                auth_input.token = auth_input.token or legacy_token
        inbound_config = InboundConfig.model_validate(inbound_raw)
        destination, destination_missing = self._import_destination(
            exported.destination,
            includes_secrets=document.includes_secrets,
        )
        overrides = self._catalog.normalize_imported_overrides(
            exported.product_id,
            exported.scenario_ids,
            exported.scenario_overrides,
        )
        missing = destination_missing + self._missing_auth_secrets(exported.auth_config, auth_input)

        create_fields: dict[str, Any] = dict(
            name=exported.name,
            product_id=exported.product_id,
            scenario_id=exported.scenario_id,
            scenario_ids=exported.scenario_ids,
            simulation_mode=exported.simulation_mode,
            fidelity_mode=exported.fidelity_mode,
            destination=destination,
            auth_config=auth_input,
            scenario_overrides=overrides,
            schedule=ScheduleConfig.model_validate(exported.schedule),
            fault_config=fault_config,
            inbound_config=inbound_config,
            random_seed=exported.random_seed,
            devices=exported.devices,
            replay_config=exported.replay_config,
        )
        if exported.targets:
            targets = []
            for target in exported.targets:
                data = dict(target)
                target_destination, target_missing = self._import_destination(
                    data["destination"], includes_secrets=document.includes_secrets
                )
                target_auth_export = ExportedAuthConfig.model_validate(data["auth_config"])
                target_auth = self._build_auth_input(target_auth_export, document.includes_secrets)
                missing.extend(
                    f"targets.{data['id']}.{m}"
                    for m in target_missing
                    + self._missing_auth_secrets(target_auth_export, target_auth)
                )
                data["destination"] = target_destination
                data["auth_config"] = target_auth
                data.pop("stats", None)
                targets.append(TargetInput.model_validate(data))
            create_fields.pop("destination")
            create_fields.pop("auth_config")
            create_fields["targets"] = targets
        create_data = SimulationCreate.model_validate(create_fields)
        created: SimulationResponse = self._catalog.create_simulation(create_data)
        return SimulationImportResponse(
            simulation_id=created.id,
            name=created.name,
            secrets_imported=document.includes_secrets
            and bool(
                auth_input.password
                or auth_input.token
                or auth_input.oauth_client_secret
                or any(item.value for item in destination.headers + destination.query_params)
            ),
            missing_secrets=missing,
        )

    @staticmethod
    def _convert_v1_document(raw: dict[str, Any]) -> dict[str, Any]:
        """Normalize the permissive 1.0 shape before validating it as a 2.0 document."""
        converted = dict(raw)
        simulation = dict(converted.get("simulation") or {})
        simulation.pop("status", None)
        scenario_id = str(simulation.get("scenario_id") or "")
        simulation["scenario_ids"] = list(
            simulation.get("scenario_ids") or ([scenario_id] if scenario_id else [])
        )

        inbound = dict(simulation.get("inbound_config") or {})
        legacy_auth = dict(simulation.get("auth_config") or simulation.pop("authentication", {}))
        legacy_auth["auth_method_id"] = str(
            legacy_auth.get("auth_method_id")
            or legacy_auth.pop("method", None)
            or legacy_auth.pop("type", None)
            or "none"
        )
        aliases = {
            "client_id": "oauth_client_id",
            "client_secret": "oauth_client_secret",
            "api_key": "token",
        }
        for old_name, new_name in aliases.items():
            value = legacy_auth.pop(old_name, None)
            if value is not None and legacy_auth.get(new_name) is None:
                legacy_auth[new_name] = value
        for field in (
            "username",
            "password",
            "token",
            "oauth_client_id",
            "oauth_client_secret",
        ):
            value = inbound.pop(field, None)
            if value is not None and legacy_auth.get(field) is None:
                legacy_auth[field] = value
        legacy_auth.setdefault("has_password", legacy_auth.get("password") is not None)
        legacy_auth.setdefault("has_token", legacy_auth.get("token") is not None)
        legacy_auth.setdefault(
            "has_oauth_client_secret", legacy_auth.get("oauth_client_secret") is not None
        )
        allowed_auth_fields = set(ExportedAuthConfig.model_fields)
        simulation["auth_config"] = {
            key: value for key, value in legacy_auth.items() if key in allowed_auth_fields
        }
        simulation["inbound_config"] = inbound
        simulation.setdefault("scenario_overrides", {})
        simulation.setdefault("schedule", {"type": "manual"})
        simulation.setdefault("fault_config", {})
        simulation.setdefault("destination", {})
        converted["simulation"] = simulation
        return converted

    def _build_auth_input(
        self,
        auth: ExportedAuthConfig,
        includes_secrets: bool,
    ) -> AuthConfigInput:
        return AuthConfigInput(
            auth_method_id=auth.auth_method_id,
            username=auth.username,
            password=auth.password if includes_secrets else None,
            token=auth.token if includes_secrets else None,
            oauth_client_id=auth.oauth_client_id,
            oauth_client_secret=auth.oauth_client_secret if includes_secrets else None,
            header_name=auth.header_name,
            header_prefix=auth.header_prefix,
        )

    def _import_destination(
        self, raw: dict[str, Any], *, includes_secrets: bool
    ) -> tuple[DestinationConfig, list[str]]:
        data = dict(raw)
        missing: list[str] = []
        for field in ("headers", "query_params"):
            source = data.get(field, [])
            entries: list[ConfiguredValueInput] = []
            if isinstance(source, dict):
                source = [
                    {"name": name, "value": value, "sensitive": True, "has_value": True}
                    for name, value in source.items()
                ]
            for raw_item in source if isinstance(source, list) else []:
                if not isinstance(raw_item, dict) or not raw_item.get("name"):
                    continue
                item = dict(raw_item)
                has_value = bool(item.pop("has_value", item.get("value") is not None))
                sensitive = bool(item.get("sensitive", True))
                if sensitive and not includes_secrets:
                    item.pop("value", None)
                    if has_value:
                        missing.append(f"destination.{field}.{item['name']}")
                entries.append(ConfiguredValueInput.model_validate(item))
            data[field] = entries

        if data.get("url"):
            try:
                reject_embedded_url_credentials(str(data["url"]))
            except ValueError as exc:
                raise ValidationAppError(str(exc)) from None
            parsed = urlsplit(str(data["url"]))
            if parsed.query:
                for name, value in parse_qsl(parsed.query, keep_blank_values=True):
                    data["query_params"].append(
                        ConfiguredValueInput(
                            name=name,
                            value=value if includes_secrets else None,
                            sensitive=True,
                        )
                    )
                    if not includes_secrets:
                        missing.append(f"destination.query_params.{name}")
                data["url"] = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
        return DestinationConfig.model_validate(data), missing

    @staticmethod
    def _missing_auth_secrets(exported: ExportedAuthConfig, imported: AuthConfigInput) -> list[str]:
        missing: list[str] = []
        if exported.has_password and not imported.password:
            missing.append("auth_config.password")
        if exported.has_token and not imported.token:
            missing.append("auth_config.token")
        if exported.has_oauth_client_secret and not imported.oauth_client_secret:
            missing.append("auth_config.oauth_client_secret")
        return missing
