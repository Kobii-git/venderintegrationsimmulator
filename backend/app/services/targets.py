"""Target configuration keeps credentials encrypted and legacy primary views synchronized."""

from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import object_session

from app.core.security import SecretEncryptor
from app.models import DeliveryJob, Simulation, SimulationTarget
from app.schemas.simulation import AuthConfigResponse, TargetInput, TargetResponse
from app.services.destination_config import destination_for_response, store_destination


def target_configs(simulation: Simulation) -> list[dict[str, Any]]:
    if simulation.targets:
        return [t.config for t in simulation.targets]
    return [
        {
            "id": "primary",
            "name": "Primary",
            "enabled": True,
            "payload_format": "default",
            "device_ids": [],
            "scenario_ids": [],
            "queue_limit": 10000,
            "destination": simulation.destination,
            "auth_config": simulation.auth_config,
            "destination_secret_values": simulation.destination_secret_values,
        }
    ]


def set_targets(
    simulation: Simulation, inputs: list[TargetInput], encryptor: SecretEncryptor
) -> None:
    existing = {t.target_id: t for t in simulation.targets}
    records = []
    for position, item in enumerate(inputs):
        row = existing.get(item.id) or SimulationTarget(target_id=item.id, stats={})
        old = row.config or {}
        dest, secrets = store_destination(
            item.destination, encryptor, existing_secrets=old.get("destination_secret_values")
        )
        auth = encryptor.merge_auth_config_update(
            old.get("auth_config", {}), item.auth_config.model_dump(exclude_unset=True)
        )
        config = item.model_dump(mode="json", exclude={"destination", "auth_config"})
        config.update(destination=dest, destination_secret_values=secrets, auth_config=auth)
        row.position, row.config = position, config
        records.append(row)
    simulation.targets = records
    sync_primary(simulation)


def sync_primary(simulation: Simulation) -> None:
    if simulation.targets:
        config = simulation.targets[0].config
        simulation.destination = config["destination"]
        simulation.destination_secret_values = config["destination_secret_values"]
        simulation.auth_config = config["auth_config"]


def update_primary(simulation: Simulation) -> None:
    if simulation.targets:
        row = simulation.targets[0]
        row.config = {
            **row.config,
            "destination": simulation.destination,
            "destination_secret_values": simulation.destination_secret_values,
            "auth_config": simulation.auth_config,
        }


def public_targets(simulation: Simulation, encryptor: SecretEncryptor) -> list[TargetResponse]:
    if simulation.simulation_mode == "pull_api":
        return []
    stats = {row.target_id: dict(row.stats or {}) for row in simulation.targets}
    db = object_session(simulation)
    if db is not None:
        queued = (
            db.query(DeliveryJob.target_id, func.count())
            .filter(
                DeliveryJob.simulation_id == simulation.id,
                DeliveryJob.status.in_(["pending", "active"]),
            )
            .group_by(DeliveryJob.target_id)
            .all()
        )
        for target_id, count in queued:
            stats.setdefault(target_id, {})["queued"] = count
    return [
        TargetResponse(
            **{
                k: c[k]
                for k in (
                    "id",
                    "name",
                    "enabled",
                    "payload_format",
                    "device_ids",
                    "scenario_ids",
                    "queue_limit",
                )
            },
            destination=destination_for_response(
                c["destination"], c.get("destination_secret_values", {})
            ),
            auth_config=AuthConfigResponse.model_validate(
                encryptor.sanitize_auth_config_for_api(c["auth_config"])
            ),
            stats=stats.get(c["id"], {}),
        )
        for c in target_configs(simulation)
    ]
