import logging
from typing import Any

from jsonschema import Draft202012Validator
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.exceptions import NotFoundError, ValidationAppError
from app.core.security import SecretEncryptor
from app.core.ssrf import validate_destination_url
from app.domain.enums import SimulationMode, SimulationStatus
from app.domain.fault_injection import validate_fault_config
from app.domain.inbound import InboundConfig
from app.domain.runtime_state import default_runtime_state
from app.domain.schedule import validate_schedule_config
from app.formats.azure_ingestion import AZURE_TRANSPORTS
from app.models import Simulation
from app.products.registry import ProductRegistry
from app.repositories.simulation import SimulationRepository
from app.schemas.simulation import (
    AuthConfigResponse,
    DestinationConfig,
    ScheduleConfig,
    SimulatedDevice,
    SimulationCreate,
    SimulationResponse,
    SimulationRuntimeStats,
    SimulationUpdate,
    TargetInput,
)
from app.services.configuration_migration import CURRENT_CONFIGURATION_VERSION
from app.services.destination_config import (
    destination_for_response,
    missing_destination_secrets,
    store_destination,
)
from app.services.inbound_options import validate_inbound_options
from app.services.targets import public_targets, set_targets, target_configs, update_primary

logger = logging.getLogger(__name__)


class SimulationService:
    """Business logic for simulation management."""

    def __init__(
        self,
        db: Session,
        product_registry: ProductRegistry,
        encryptor: SecretEncryptor,
        settings: Settings | None = None,
    ) -> None:
        self._repo = SimulationRepository(db)
        self._products = product_registry
        self._encryptor = encryptor
        self._settings = settings or get_settings()

    def list_simulations(self) -> list[SimulationResponse]:
        return [self._to_response(item) for item in self._repo.list_all()]

    def get_simulation(self, simulation_id: str) -> SimulationResponse:
        simulation = self._repo.get_by_id_or_raise(simulation_id)
        return self._to_response(simulation)

    def create_simulation(self, data: SimulationCreate) -> SimulationResponse:
        scenario_ids = data.scenario_ids or ([data.scenario_id] if data.scenario_id else [])
        for scenario_id in scenario_ids:
            self._validate_product_and_scenario(data.product_id, scenario_id)
        self._validate_simulation_mode(data.product_id, data.simulation_mode.value)
        self._validate_scenario_modes(data.product_id, scenario_ids, data.simulation_mode.value)
        self._validate_schedule_limits(data.schedule, data.replay_config)
        self._validate_weights(data.schedule.model_dump(), scenario_ids)
        self._validate_scenario_overrides(data.product_id, scenario_ids, data.scenario_overrides)
        validate_fault_config(data.fault_config, self._settings)
        if data.simulation_mode != SimulationMode.PULL_API:
            for target in data.targets or [
                TargetInput(destination=data.destination, auth_config=data.auth_config)
            ]:
                self._validate_target(
                    data.product_id, target, scenario_ids, [d.id for d in data.devices]
                )
        else:
            self._validate_pull_product(data.product_id, data.inbound_config.auth_method_id)
            self._validate_inbound_options(data.product_id, data.inbound_config)

        encrypted_auth = self._encryptor.encrypt_auth_config(data.auth_config.model_dump())
        stored_destination, destination_secrets = store_destination(
            data.destination, self._encryptor
        )

        simulation = Simulation(
            name=data.name,
            product_id=data.product_id,
            scenario_id=scenario_ids[0],
            scenario_ids=scenario_ids,
            simulation_mode=data.simulation_mode.value,
            fidelity_mode=data.fidelity_mode.value,
            status=SimulationStatus.STOPPED.value,
            destination=stored_destination,
            destination_secret_values=destination_secrets,
            configuration_version=CURRENT_CONFIGURATION_VERSION,
            auth_config=encrypted_auth,
            scenario_overrides=data.scenario_overrides,
            schedule=data.schedule.model_dump(mode="json"),
            fault_config=data.fault_config.model_dump(mode="json"),
            inbound_config=data.inbound_config.model_dump(mode="json"),
            random_seed=data.random_seed,
            runtime_state=default_runtime_state(),
            devices=[d.model_dump(mode="json") for d in data.devices],
            replay_config=data.replay_config,
        )
        if data.simulation_mode != SimulationMode.PULL_API:
            set_targets(
                simulation,
                data.targets
                or [TargetInput(destination=data.destination, auth_config=data.auth_config)],
                self._encryptor,
            )
        self._validate_replay(simulation.replay_config)
        created = self._repo.create(simulation)
        logger.info(
            "Simulation created",
            extra={"simulation_id": created.id, "product_id": created.product_id},
        )
        return self._to_response(created)

    def update_simulation(self, simulation_id: str, data: SimulationUpdate) -> SimulationResponse:
        simulation = self._repo.get_by_id_or_raise(simulation_id)
        if simulation.status == SimulationStatus.RUNNING.value:
            raise ValidationAppError("Cannot update a running simulation; stop it first")

        updates = data.model_dump(exclude_unset=True, mode="json")

        if "scenario_ids" in updates and updates["scenario_ids"]:
            for scenario_id in updates["scenario_ids"]:
                self._validate_product_and_scenario(simulation.product_id, scenario_id)
            simulation.scenario_ids = updates["scenario_ids"]
            simulation.scenario_id = updates["scenario_ids"][0]
        elif "scenario_id" in updates:
            self._validate_product_and_scenario(simulation.product_id, updates["scenario_id"])
            simulation.scenario_id = updates["scenario_id"]
            simulation.scenario_ids = [updates["scenario_id"]]

        if "simulation_mode" in updates:
            self._validate_simulation_mode(simulation.product_id, updates["simulation_mode"])

        if "name" in updates:
            simulation.name = updates["name"]
        if "simulation_mode" in updates:
            simulation.simulation_mode = updates["simulation_mode"]
        if "fidelity_mode" in updates:
            simulation.fidelity_mode = updates["fidelity_mode"]
        if "destination" in updates:
            assert data.destination is not None
            destination = data.destination
            mode = updates.get("simulation_mode", simulation.simulation_mode)
            if mode != SimulationMode.PULL_API.value:
                self._validate_destination_for_product(simulation.product_id, destination)
                if (
                    destination.transport_id in {"http_webhook", "cloudflare_logpush"}
                    and destination.url
                ):
                    validate_destination_url(str(destination.url), self._settings)
            stored_destination, destination_secrets = store_destination(
                destination,
                self._encryptor,
                existing_secrets=simulation.destination_secret_values,
            )
            simulation.destination = stored_destination
            simulation.destination_secret_values = destination_secrets
        if "scenario_overrides" in updates:
            simulation.scenario_overrides = updates["scenario_overrides"]
        if "schedule" in updates and data.schedule is not None:
            self._validate_schedule_limits(
                data.schedule,
                data.replay_config if data.replay_config is not None else simulation.replay_config,
            )
            simulation.schedule = updates["schedule"]
        if "fault_config" in updates and data.fault_config is not None:
            validate_fault_config(data.fault_config, self._settings)
            simulation.fault_config = updates["fault_config"]
        if "inbound_config" in updates and data.inbound_config is not None:
            simulation.inbound_config = updates["inbound_config"]
        if "random_seed" in updates:
            simulation.random_seed = updates["random_seed"]
        if "auth_config" in updates and data.auth_config is not None:
            simulation.auth_config = self._encryptor.merge_auth_config_update(
                simulation.auth_config,
                data.auth_config.model_dump(exclude_unset=True),
            )

        if "devices" in updates:
            simulation.devices = updates["devices"] or []
        if "replay_config" in updates:
            simulation.replay_config = updates["replay_config"] or {}
            self._validate_replay(simulation.replay_config)
        if data.targets is not None:
            for target in data.targets:
                self._validate_target(
                    simulation.product_id,
                    target,
                    simulation.scenario_ids,
                    [d["id"] for d in simulation.devices],
                )
            set_targets(simulation, data.targets, self._encryptor)
        elif {"destination", "auth_config"} & updates.keys():
            update_primary(simulation)

        selected_scenarios = simulation.scenario_ids or [simulation.scenario_id]
        self._validate_weights(simulation.schedule or {}, selected_scenarios)
        if simulation.simulation_mode != SimulationMode.PULL_API.value:
            for config in target_configs(simulation):
                if set(config.get("scenario_ids", [])) - set(selected_scenarios) or set(
                    config.get("device_ids", [])
                ) - {d["id"] for d in simulation.devices or []}:
                    raise ValidationAppError(
                        "Target filters reference devices or scenarios outside this simulation"
                    )
        self._validate_scenario_modes(
            simulation.product_id,
            selected_scenarios,
            simulation.simulation_mode,
        )
        self._validate_scenario_overrides(
            simulation.product_id,
            selected_scenarios,
            simulation.scenario_overrides or {},
        )
        if simulation.simulation_mode == SimulationMode.PULL_API.value:
            inbound_auth = str((simulation.inbound_config or {}).get("auth_method_id", "none"))
            self._validate_pull_product(simulation.product_id, inbound_auth)
            self._validate_inbound_options(
                simulation.product_id,
                InboundConfig.model_validate(simulation.inbound_config or {}),
            )
        else:
            auth_public = self._encryptor.decrypt_auth_config(simulation.auth_config)
            self._validate_auth_method(
                simulation.product_id, str(auth_public.get("auth_method_id", "none"))
            )

        updated = self._repo.update(simulation)
        logger.info("Simulation updated", extra={"simulation_id": updated.id})
        return self._to_response(updated)

    def delete_simulation(self, simulation_id: str) -> None:
        simulation = self._repo.get_by_id_or_raise(simulation_id)
        if simulation.status == SimulationStatus.RUNNING.value:
            raise ValidationAppError("Cannot delete a running simulation; stop it first")
        self._repo.delete(simulation)
        logger.info("Simulation deleted", extra={"simulation_id": simulation_id})

    def normalize_imported_overrides(
        self,
        product_id: str,
        scenario_ids: list[str],
        raw: dict[str, Any],
    ) -> dict[str, dict[str, Any]]:
        if not raw:
            return {}
        if all(key in scenario_ids and isinstance(value, dict) for key, value in raw.items()):
            return {str(key): dict(value) for key, value in raw.items()}
        normalized: dict[str, dict[str, Any]] = {}
        recognized: set[str] = set()
        for scenario_id in scenario_ids:
            scenario = self._products.get_scenario(product_id, scenario_id)
            if scenario is None:
                continue
            properties = scenario.config_schema.get("properties", {})
            values = {key: value for key, value in raw.items() if key in properties}
            if values:
                normalized[scenario_id] = values
                recognized.update(values)
        unknown = set(raw) - recognized
        if unknown:
            raise ValidationAppError(
                "Legacy export contains unknown scenario overrides",
                details={"fields": sorted(unknown)},
            )
        return normalized

    @staticmethod
    def _validate_weights(schedule: dict[str, Any], scenarios: list[str]) -> None:
        if set(schedule.get("scenario_weights", {})) - set(scenarios):
            raise ValidationAppError("Scenario weights reference unselected scenarios")

    def _validate_target(
        self, product_id: str, target: TargetInput, scenarios: list[str], devices: list[str]
    ) -> None:
        self._validate_destination_for_product(product_id, target.destination)
        self._validate_auth_method(product_id, target.auth_config.auth_method_id)
        if target.destination.url:
            validate_destination_url(target.destination.url, self._settings)
        if set(target.scenario_ids) - set(scenarios) or set(target.device_ids) - set(devices):
            raise ValidationAppError(
                "Target filters reference devices or scenarios outside this simulation"
            )
        manifest = self._products.get_manifest(product_id)
        assert manifest is not None
        available = set(manifest.formats) | {"default", "json"}
        if "native" in available or "csv" in available:
            available.add("native")
        if product_id in ("windows-dc", "windows-sysmon"):
            available.add("WindowsEvent")
        if product_id == "windows-dc":
            available.add("SecurityEvent")
        if "cef" in available:
            available.add("CommonSecurityLog")
        if target.payload_format not in available:
            raise ValidationAppError(
                f"Unsupported payload format for {product_id}: {target.payload_format}"
            )
        if target.destination.transport_id in AZURE_TRANSPORTS and target.payload_format not in {
            "json",
            "default",
            "SecurityEvent",
            "WindowsEvent",
            "CommonSecurityLog",
        }:
            raise ValidationAppError("Azure ingestion requires JSON or an explicit table mapping")

    def _validate_replay(self, config: dict[str, Any]) -> None:
        if not config:
            return
        from app.models import UploadedDataset
        from app.schemas.dataset import ReplayConfig

        parsed = ReplayConfig.model_validate(config)
        if self._repo._db.get(UploadedDataset, parsed.dataset_id) is None:
            raise ValidationAppError("Replay dataset not found")

    def _validate_product_and_scenario(self, product_id: str, scenario_id: str) -> None:
        manifest = self._products.get_manifest(product_id)
        if manifest is None:
            raise NotFoundError(f"Product not found: {product_id}")

        if not manifest.scenarios:
            return

        scenario_ids = {scenario.id for scenario in manifest.scenarios}
        if scenario_id not in scenario_ids:
            raise ValidationAppError(
                f"Scenario '{scenario_id}' is not defined for product '{product_id}'",
                details={"valid_scenario_ids": sorted(scenario_ids)},
            )

    def _validate_simulation_mode(self, product_id: str, simulation_mode: str) -> None:
        manifest = self._products.get_manifest(product_id)
        if manifest is None:
            raise NotFoundError(f"Product not found: {product_id}")
        if simulation_mode not in manifest.supported_modes:
            raise ValidationAppError(
                f"Simulation mode '{simulation_mode}' is not supported by product '{product_id}'",
                details={"supported_modes": manifest.supported_modes},
            )

    def _validate_scenario_modes(
        self,
        product_id: str,
        scenario_ids: list[str],
        simulation_mode: str,
    ) -> None:
        for scenario_id in scenario_ids:
            scenario = self._products.get_scenario(product_id, scenario_id)
            if scenario is None or not scenario.supported_modes:
                continue
            if simulation_mode not in scenario.supported_modes:
                raise ValidationAppError(
                    f"Scenario '{scenario_id}' is not available in {simulation_mode} mode",
                    details={"supported_modes": scenario.supported_modes},
                )

    def _validate_schedule_limits(
        self, schedule: ScheduleConfig, replay_config: dict[str, Any] | None = None
    ) -> None:
        from app.services.datasets import schedule_settings_for_replay

        validate_schedule_config(
            schedule.model_dump(mode="json"),
            schedule_settings_for_replay(self._repo._db, replay_config or {}, self._settings),
        )

    def _validate_destination_for_product(
        self, product_id: str, destination: DestinationConfig
    ) -> None:
        manifest = self._products.get_manifest(product_id)
        if manifest is None:
            raise NotFoundError(f"Product not found: {product_id}")
        if (
            destination.transport_id not in manifest.supported_transports
            and destination.transport_id not in AZURE_TRANSPORTS
        ):
            raise ValidationAppError(
                f"Transport '{destination.transport_id}' is not supported by "
                f"product '{product_id}'",
                details={"supported_transports": manifest.supported_transports},
            )
        if destination.transport_id == "syslog" and (
            not destination.host or not destination.host.strip()
        ):
            raise ValidationAppError("destination.host is required for syslog transport")
        if destination.transport_id in {"http_webhook", "cloudflare_logpush"} and (
            not destination.url or not destination.url.strip()
        ):
            raise ValidationAppError("destination.url is required for http_webhook transport")

    def _validate_pull_product(self, product_id: str, inbound_auth_method: str) -> None:
        manifest = self._products.get_manifest(product_id)
        if manifest is None:
            raise NotFoundError(f"Product not found: {product_id}")
        if not manifest.mock_routes:
            raise ValidationAppError(
                f"Product '{product_id}' has no mock routes configured for pull API mode",
            )
        if inbound_auth_method not in manifest.supported_inbound_auth_methods:
            raise ValidationAppError(
                f"Inbound auth method '{inbound_auth_method}' is not supported by "
                f"product '{product_id}'",
                details={"supported_inbound_auth_methods": manifest.supported_inbound_auth_methods},
            )

    def _validate_inbound_options(self, product_id: str, inbound_config: InboundConfig) -> None:
        manifest = self._products.get_manifest(product_id)
        if manifest is None:
            raise NotFoundError(f"Product not found: {product_id}")
        validate_inbound_options(
            manifest,
            dict(inbound_config.vendor_options),
            workflow_plugin=self._products.get_workflow_plugin(product_id),
        )

    def _validate_auth_method(self, product_id: str, auth_method_id: str) -> None:
        manifest = self._products.get_manifest(product_id)
        if manifest is None:
            raise NotFoundError(f"Product not found: {product_id}")
        if auth_method_id not in manifest.supported_auth_methods:
            raise ValidationAppError(
                f"Auth method '{auth_method_id}' is not supported by product '{product_id}'",
                details={"supported_auth_methods": manifest.supported_auth_methods},
            )

    def _validate_scenario_overrides(
        self,
        product_id: str,
        scenario_ids: list[str],
        overrides: dict[str, dict[str, Any]],
    ) -> None:
        unknown_scenarios = set(overrides) - set(scenario_ids)
        if unknown_scenarios:
            raise ValidationAppError(
                "Scenario overrides reference unselected scenarios",
                details={"scenario_ids": sorted(unknown_scenarios)},
            )
        errors: list[dict[str, str]] = []
        for scenario_id, values in overrides.items():
            scenario = self._products.get_scenario(product_id, scenario_id)
            if scenario is None:
                raise ValidationAppError(f"Scenario not found: {product_id}/{scenario_id}")
            validator = Draft202012Validator(scenario.config_schema or {"type": "object"})
            for error in validator.iter_errors(values):
                path = ".".join(str(part) for part in error.absolute_path)
                errors.append(
                    {
                        "scenario_id": scenario_id,
                        "path": path,
                        "message": error.message,
                    }
                )
        if errors:
            raise ValidationAppError(
                "Scenario overrides failed schema validation", details={"errors": errors}
            )

    def _to_response(self, simulation: Simulation) -> SimulationResponse:
        auth_public = self._encryptor.sanitize_auth_config_for_api(simulation.auth_config)
        runtime = simulation.runtime_state or default_runtime_state()
        missing = missing_destination_secrets(
            simulation.destination or {}, simulation.destination_secret_values or {}
        )
        auth_method = str(auth_public.get("auth_method_id", "none"))
        if auth_method == "basic" and not auth_public.get("has_password"):
            missing.append("auth_config.password")
        if auth_method in {"bearer", "api_key_header"} and not auth_public.get("has_token"):
            missing.append("auth_config.token")
        inbound_method = str((simulation.inbound_config or {}).get("auth_method_id", "none"))
        if inbound_method == "oauth2_client_credentials" and not auth_public.get(
            "has_oauth_client_secret"
        ):
            missing.append("auth_config.oauth_client_secret")
        if simulation.simulation_mode != SimulationMode.PULL_API.value:
            missing = []
            for index, config in enumerate(target_configs(simulation)):
                if not config.get("enabled", True):
                    continue
                prefix = "" if index == 0 else f"targets.{config['id']}."
                target_missing = missing_destination_secrets(
                    config["destination"], config.get("destination_secret_values", {})
                )
                target_auth = self._encryptor.sanitize_auth_config_for_api(config["auth_config"])
                method = target_auth.get("auth_method_id", "none")
                if method == "basic" and not target_auth.get("has_password"):
                    target_missing.append("auth_config.password")
                if method in {"bearer", "api_key_header"} and not target_auth.get("has_token"):
                    target_missing.append("auth_config.token")
                if config["destination"].get(
                    "transport_id"
                ) == "azure_function_app" and not target_auth.get("has_token"):
                    target_missing.append("auth_config.token")
                if config["destination"].get("transport_id") == "azure_logs_ingestion" and not (
                    target_auth.get("has_oauth_client_secret")
                ):
                    target_missing.append("auth_config.oauth_client_secret")
                missing.extend(prefix + field for field in target_missing)
            missing = list(dict.fromkeys(missing))
        return SimulationResponse(
            id=simulation.id,
            name=simulation.name,
            product_id=simulation.product_id,
            scenario_id=simulation.scenario_id,
            scenario_ids=simulation.scenario_ids or [simulation.scenario_id],
            simulation_mode=simulation.simulation_mode,
            fidelity_mode=simulation.fidelity_mode,
            status=simulation.status,
            targets=public_targets(simulation, self._encryptor),
            devices=[SimulatedDevice.model_validate(d) for d in simulation.devices or []],
            replay_config=simulation.replay_config or {},
            destination=destination_for_response(
                simulation.destination or {}, simulation.destination_secret_values or {}
            ),
            auth_config=AuthConfigResponse(**auth_public),
            scenario_overrides=simulation.scenario_overrides,
            schedule=simulation.schedule,
            fault_config=simulation.fault_config or {},
            inbound_config=simulation.inbound_config or {},
            random_seed=simulation.random_seed,
            missing_secrets=missing,
            runtime_stats=SimulationRuntimeStats(**runtime),
            created_at=simulation.created_at,
            updated_at=simulation.updated_at,
        )
