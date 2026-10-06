"""Key-aware migration of legacy configuration JSON after Alembic completes."""

from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlsplit, urlunsplit

from jsonschema import Draft202012Validator
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.http_url import (
    EmbeddedUrlCredentials,
    get_embedded_url_credentials,
    strip_embedded_url_credentials,
)
from app.core.security import SecretEncryptor
from app.models import Simulation
from app.products.registry import ProductRegistry
from app.schemas.simulation import ConfiguredValueInput, DestinationConfig
from app.services.destination_config import store_destination

logger = logging.getLogger(__name__)

CURRENT_CONFIGURATION_VERSION = 3


@dataclass(frozen=True)
class ConfigurationMigrationResult:
    migrated: int
    backup_path: Path | None
    warning_count: int


def migrate_legacy_configurations(
    db: Session,
    registry: ProductRegistry,
    encryptor: SecretEncryptor,
    settings: Settings,
    *,
    backup_path: Path | None = None,
) -> ConfigurationMigrationResult:
    simulations = (
        db.query(Simulation)
        .filter(Simulation.configuration_version < CURRENT_CONFIGURATION_VERSION)
        .order_by(Simulation.created_at)
        .all()
    )
    if not simulations:
        return ConfigurationMigrationResult(0, None, 0)

    # Validate every conversion before touching data so a conflict cannot leave a partial upgrade.
    for simulation in simulations:
        auth = encryptor.decrypt_auth_config(simulation.auth_config or {})
        for value in (simulation.destination_secret_values or {}).values():
            encryptor.decrypt(str(value))
        _validate_url_credential_migration(
            simulation.id,
            simulation.product_id,
            simulation.destination or {},
            auth,
            registry,
        )

    backup_path = backup_path or _backup_sqlite_database(settings)
    warnings = 0
    for simulation in simulations:
        try:
            warning_messages: list[str] = []
            if simulation.configuration_version < CURRENT_CONFIGURATION_VERSION:
                # URL user-info must be removed before v1 destinations are validated.
                warning_messages.extend(_migrate_v2_to_v3(simulation, registry, encryptor))
            if simulation.configuration_version < 2:
                warning_messages.extend(_migrate_v1_to_v2(simulation, registry, encryptor))
            warnings += len(warning_messages)
            runtime = dict(simulation.runtime_state or {})
            if warning_messages:
                runtime["configuration_migration_warnings"] = warning_messages
            simulation.runtime_state = runtime
            simulation.configuration_version = CURRENT_CONFIGURATION_VERSION
            from app.services.targets import update_primary

            update_primary(simulation)
            db.commit()
        except Exception:
            db.rollback()
            raise

    _compact_sqlite_database(settings)
    logger.warning(
        "Migrated %d legacy simulation configuration(s); backup=%s warnings=%d",
        len(simulations),
        backup_path,
        warnings,
    )
    return ConfigurationMigrationResult(len(simulations), backup_path, warnings)


def preflight_configuration_upgrade(
    settings: Settings,
    encryptor: SecretEncryptor,
    registry: ProductRegistry,
) -> Path | None:
    """Validate encryption and back up a legacy SQLite database before Alembic writes."""
    source = _sqlite_path(settings)
    if not source.is_file():
        return None
    with sqlite3.connect(f"file:{source}?mode=ro", uri=True) as connection:
        table = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='simulations'"
        ).fetchone()
        if table is None:
            return None
        columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(simulations)")}
        has_version = "configuration_version" in columns
        where = (
            f" WHERE configuration_version < {CURRENT_CONFIGURATION_VERSION}" if has_version else ""
        )
        secret_column = (
            ", destination_secret_values" if "destination_secret_values" in columns else ""
        )
        rows = connection.execute(
            f"SELECT id, product_id, destination, auth_config{secret_column} "
            f"FROM simulations{where}"  # noqa: S608 - column/table names are fixed constants
        ).fetchall()
        if not rows:
            from alembic.config import Config
            from alembic.script import ScriptDirectory

            backend_root = Path(__file__).resolve().parents[2]
            cfg = Config(str(backend_root / "alembic.ini"))
            cfg.set_main_option("script_location", str(backend_root / "alembic"))
            head = ScriptDirectory.from_config(cfg).get_current_head()
            version_table = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE name='alembic_version'"
            ).fetchone()
            revision = (
                connection.execute("SELECT version_num FROM alembic_version").fetchone()
                if version_table
                else None
            )
            if revision and revision[0] == head:
                return None
        for row in rows:
            auth = encryptor.decrypt_auth_config(json.loads(row[3] or "{}"))
            destination = json.loads(row[2] or "{}")
            _validate_url_credential_migration(
                str(row[0]), str(row[1]), destination, auth, registry
            )
            if len(row) > 4:
                destination_secrets = json.loads(row[4] or "{}")
                for value in destination_secrets.values():
                    encryptor.decrypt(str(value))
    return _backup_sqlite_database(settings)


def _backup_sqlite_database(settings: Settings) -> Path:
    source = _sqlite_path(settings)
    if not source.is_file():
        raise RuntimeError(f"Cannot back up missing SQLite database: {source}")
    backup_dir = settings.resolved_data_dir / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    target = backup_dir / f"pre-config-v2-{timestamp}.db"
    with sqlite3.connect(source) as source_db, sqlite3.connect(target) as target_db:
        source_db.backup(target_db)
    target.chmod(0o600)
    return target


def _sqlite_path(settings: Settings) -> Path:
    url = settings.resolved_database_url
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        raise RuntimeError("Automatic configuration backup currently supports SQLite only")
    return Path(url.removeprefix(prefix)).resolve()


def _compact_sqlite_database(settings: Settings) -> None:
    source = _sqlite_path(settings)
    with sqlite3.connect(source, isolation_level=None) as connection:
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        connection.execute("VACUUM")


def _migrate_v1_to_v2(
    simulation: Simulation,
    registry: ProductRegistry,
    encryptor: SecretEncryptor,
) -> list[str]:
    destination = dict(simulation.destination or {})
    headers = _legacy_values(destination.get("headers"))
    query_params = _legacy_values(destination.get("query_params"))

    if destination.get("url"):
        parsed = urlsplit(str(destination["url"]))
        for name, value in parse_qsl(parsed.query, keep_blank_values=True):
            query_params.append(ConfiguredValueInput(name=name, value=value, sensitive=True))
        destination["url"] = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
    destination["headers"] = [item.model_dump() for item in headers]
    destination["query_params"] = [item.model_dump() for item in query_params]
    parsed_destination = DestinationConfig.model_validate(destination)
    stored, encrypted = store_destination(parsed_destination, encryptor)
    simulation.destination = stored
    simulation.destination_secret_values = encrypted

    inbound = dict(simulation.inbound_config or {})
    auth_update: dict[str, Any] = {}
    for field in ("username", "password", "token"):
        value = inbound.pop(field, None)
        if value is not None:
            auth_update[field] = value
    if auth_update:
        existing_public = encryptor.decrypt_auth_config(simulation.auth_config or {})
        for field, value in auth_update.items():
            existing_public.setdefault(field, value)
        simulation.auth_config = encryptor.encrypt_auth_config(existing_public)
    simulation.inbound_config = inbound

    nested, warning_messages, quarantined = _legacy_overrides(simulation, registry)
    simulation.scenario_overrides = nested
    if quarantined:
        runtime = dict(simulation.runtime_state or {})
        runtime["configuration_migration_quarantine"] = {
            name: {
                "has_value": True,
                "encrypted_value": encryptor.encrypt(
                    json.dumps(value, separators=(",", ":"), sort_keys=True)
                ),
            }
            for name, value in quarantined.items()
        }
        simulation.runtime_state = runtime
    return warning_messages


def _migrate_v2_to_v3(
    simulation: Simulation,
    registry: ProductRegistry,
    encryptor: SecretEncryptor,
) -> list[str]:
    destination = dict(simulation.destination or {})
    url = str(destination.get("url") or "")
    credentials = get_embedded_url_credentials(url) if url else None
    if credentials is None:
        return []

    auth = encryptor.decrypt_auth_config(simulation.auth_config or {})
    _validate_url_credential_migration(
        simulation.id,
        simulation.product_id,
        destination,
        auth,
        registry,
    )
    auth_method = str(auth.get("auth_method_id") or "none")
    if auth_method == "none":
        assert credentials.username is not None
        assert credentials.password is not None
        auth["auth_method_id"] = "basic"
        auth["username"] = credentials.username
        auth["password"] = credentials.password
        simulation.auth_config = encryptor.encrypt_auth_config(auth)
        warning = "Embedded URL credentials were moved to encrypted authentication configuration"
    else:
        warning = "Embedded URL credentials were removed in favour of explicit Basic authentication"

    destination["url"] = strip_embedded_url_credentials(url)
    simulation.destination = destination
    return [warning]


def _validate_url_credential_migration(
    simulation_id: str,
    product_id: str,
    destination: dict[str, Any],
    auth: dict[str, Any],
    registry: ProductRegistry,
) -> EmbeddedUrlCredentials | None:
    url = str(destination.get("url") or "")
    credentials = get_embedded_url_credentials(url) if url else None
    if credentials is None:
        return None

    reason: str | None = None
    if not credentials.complete:
        reason = "username and password are both required"
    else:
        auth_method = str(auth.get("auth_method_id") or "none")
        manifest = registry.get_manifest(product_id)
        if auth_method == "basic":
            return credentials
        if auth_method != "none":
            reason = f"authentication method '{auth_method}' is already configured"
        elif manifest is None or "basic" not in manifest.supported_auth_methods:
            reason = f"product '{product_id}' does not support Basic authentication"
        else:
            return credentials

    raise RuntimeError(
        "Embedded URL credentials for simulation "
        f"'{simulation_id}' cannot be migrated automatically: {reason}. "
        "Restore the pre-upgrade application and configure authentication separately."
    )


def _legacy_values(raw: Any) -> list[ConfiguredValueInput]:
    if isinstance(raw, dict):
        return [
            ConfiguredValueInput(name=str(name), value=str(value), sensitive=True)
            for name, value in raw.items()
        ]
    result: list[ConfiguredValueInput] = []
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict) or not item.get("name"):
            continue
        migrated = dict(item)
        migrated["sensitive"] = True
        result.append(ConfiguredValueInput.model_validate(migrated))
    return result


def _legacy_overrides(
    simulation: Simulation, registry: ProductRegistry
) -> tuple[dict[str, dict[str, Any]], list[str], dict[str, Any]]:
    raw = simulation.scenario_overrides or {}
    scenario_ids = simulation.scenario_ids or [simulation.scenario_id]
    nested: dict[str, dict[str, Any]] = {}
    recognized: set[str] = set()
    quarantined: dict[str, Any] = {}
    already_nested = bool(set(raw) & set(scenario_ids)) and all(
        isinstance(value, dict) for value in raw.values()
    )

    for scenario_id in scenario_ids:
        scenario = registry.get_scenario(simulation.product_id, scenario_id)
        if scenario is None:
            continue
        properties = scenario.config_schema.get("properties", {})
        source = raw.get(scenario_id, {}) if already_nested else raw
        if not isinstance(source, dict):
            continue
        values: dict[str, Any] = {}
        for key, value in source.items():
            property_schema = properties.get(key)
            quarantine_key = f"{scenario_id}.{key}" if already_nested else str(key)
            if property_schema is None or not Draft202012Validator(property_schema).is_valid(value):
                quarantined[quarantine_key] = value
                continue
            values[str(key)] = value
            recognized.add(str(key))
        if values:
            nested[scenario_id] = values

    if already_nested:
        for scenario_id, values in raw.items():
            if scenario_id not in scenario_ids:
                quarantined[str(scenario_id)] = values
    else:
        for key in set(raw) - recognized:
            quarantined.setdefault(str(key), raw[key])

    warnings = [f"Legacy scenario override '{key}' was quarantined" for key in sorted(quarantined)]
    return nested, warnings, quarantined
