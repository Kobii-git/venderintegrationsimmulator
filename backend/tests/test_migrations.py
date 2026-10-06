"""Fresh, upgrade, integrity-repair, and key-aware configuration migration tests."""

import json
import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from app.api.deps import get_product_registry
from app.core.security import SecretEncryptor
from app.services.configuration_migration import (
    migrate_legacy_configurations,
    preflight_configuration_upgrade,
)
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


def _alembic_upgrade(database_url: str, revision: str) -> None:
    ini = Path(__file__).resolve().parents[1] / "alembic.ini"
    config = Config(str(ini))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, revision)


def _alembic_downgrade(database_url: str, revision: str) -> None:
    ini = Path(__file__).resolve().parents[1] / "alembic.ini"
    config = Config(str(ini))
    config.set_main_option("sqlalchemy.url", database_url)
    command.downgrade(config, revision)


def test_vendor_workflow_event_columns_upgrade_and_downgrade(test_settings) -> None:
    database = Path(test_settings.resolved_database_url.removeprefix("sqlite:///"))
    _alembic_upgrade(test_settings.resolved_database_url, "008_materialized_pull_datasets")
    with sqlite3.connect(database) as connection:
        before = {row[1] for row in connection.execute("PRAGMA table_info(event_instances)")}
        assert {"event_kind", "action_id"}.isdisjoint(before)

    _alembic_upgrade(test_settings.resolved_database_url, "009_vendor_workflow_actions")
    with sqlite3.connect(database) as connection:
        upgraded = {row[1] for row in connection.execute("PRAGMA table_info(event_instances)")}
        assert {"event_kind", "action_id"} <= upgraded
        indexes = {row[1] for row in connection.execute("PRAGMA index_list(event_instances)")}
        assert "ix_event_instances_action_id" in indexes

    _alembic_downgrade(test_settings.resolved_database_url, "008_materialized_pull_datasets")
    with sqlite3.connect(database) as connection:
        downgraded = {row[1] for row in connection.execute("PRAGMA table_info(event_instances)")}
        assert {"event_kind", "action_id"}.isdisjoint(downgraded)


def _insert_legacy_simulation(
    database: Path, *, auth_config: dict[str, object] | None = None
) -> None:
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            INSERT INTO simulations (
                id, name, product_id, scenario_id, scenario_ids, simulation_mode,
                fidelity_mode, status, destination, auth_config, scenario_overrides,
                schedule, runtime_state, fault_config, inbound_config
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "legacy-simulation",
                "Retained 0.1 simulation",
                "upguard",
                "data-leak",
                json.dumps(["data-leak"]),
                "push_webhook",
                "troubleshooting",
                "stopped",
                json.dumps(
                    {
                        "transport_id": "http_webhook",
                        "url": "https://example.com/hook?access_token=url-canary-42",
                        "headers": {"X-Api-Key": "header-canary-42"},
                        "query_params": {"password": "query-canary-42"},
                    }
                ),
                json.dumps(auth_config or {"auth_method_id": "none"}),
                json.dumps(
                    {
                        "affected_domain": "retained.example",
                        "unknown_legacy_field": "quarantine-me",
                    }
                ),
                json.dumps({"type": "manual"}),
                json.dumps({}),
                json.dumps({}),
                json.dumps({}),
            ),
        )


def _insert_orphans(database: Path) -> None:
    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA foreign_keys=OFF")
        connection.execute(
            """
            INSERT INTO delivery_attempts (
                id, event_instance_id, attempt_number, started_at, transport_id,
                destination_summary, request_headers_redacted,
                request_query_params_redacted, response_headers_redacted, success
            ) VALUES (
                'orphan-attempt', 'missing-event', 1, CURRENT_TIMESTAMP, 'http_webhook',
                'redacted', '{}', '{}', '{}', 0
            )
            """
        )


def _insert_v2_simulation(
    database: Path,
    *,
    simulation_id: str = "v2-simulation",
    product_id: str = "upguard",
    url: str = "https://example.com/hook",
    auth_config: dict[str, object] | None = None,
) -> None:
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            INSERT INTO simulations (
                id, name, product_id, scenario_id, scenario_ids, simulation_mode,
                fidelity_mode, status, destination, auth_config, scenario_overrides,
                schedule, runtime_state, fault_config, inbound_config,
                configuration_version, destination_secret_values
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                simulation_id,
                "Retained v2 simulation",
                product_id,
                "data-leak" if product_id == "upguard" else "ping",
                json.dumps(["data-leak" if product_id == "upguard" else "ping"]),
                "push_webhook",
                "troubleshooting",
                "stopped",
                json.dumps(
                    {
                        "transport_id": "http_webhook",
                        "url": url,
                        "method": "POST",
                        "headers": [
                            {"name": "X-Tenant", "value": "engineering", "sensitive": False}
                        ],
                        "query_params": [],
                    }
                ),
                json.dumps(auth_config or {"auth_method_id": "none"}),
                json.dumps({}),
                json.dumps({"type": "manual"}),
                json.dumps({}),
                json.dumps({}),
                json.dumps({}),
                2,
                json.dumps({}),
            ),
        )
        connection.execute(
            """
            INSERT INTO inbound_request_logs (
                id, simulation_id, product_id, route_id, request_method, request_path,
                response_status_code, auth_method_id, auth_result, latency_ms,
                items_returned, request_kind
            ) VALUES (
                'orphan-inbound', 'missing-simulation', 'demo-pull', 'events', 'GET',
                '/mock/events', 404, 'none', 'unmatched', 0, 0, 'api'
            )
            """
        )
        connection.execute(
            """
            INSERT INTO oauth_access_tokens (
                id, simulation_id, token_hash, client_id, issued_at, expires_at, revoked
            ) VALUES (
                'orphan-token', 'missing-simulation', 'orphan-hash', 'client',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 0
            )
            """
        )


def test_fresh_current_and_partially_migrated_databases_reach_head(test_settings) -> None:
    database = Path(test_settings.resolved_database_url.removeprefix("sqlite:///"))

    _alembic_upgrade(test_settings.resolved_database_url, "007_secure_configuration_and_integrity")
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
            "007_secure_configuration_and_integrity",
        )
        assert "pull_dataset_items" not in {
            str(row[0])
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }

    _alembic_upgrade(test_settings.resolved_database_url, "head")
    _alembic_upgrade(test_settings.resolved_database_url, "head")
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
            "010_targets_queues_datasets",
        )
        tables = {
            str(row[0])
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert {"pull_dataset_activations", "pull_dataset_items"} <= tables
        foreign_keys = list(connection.execute("PRAGMA foreign_key_list(pull_dataset_items)"))
        assert foreign_keys and all(str(row[6]).upper() == "CASCADE" for row in foreign_keys)


def test_upgrade_repairs_orphans_backs_up_and_encrypts_legacy_configuration(
    test_settings,
) -> None:
    database = Path(test_settings.resolved_database_url.removeprefix("sqlite:///"))
    _alembic_upgrade(test_settings.resolved_database_url, "006_oauth2_client_credentials")
    _insert_legacy_simulation(database)
    _insert_orphans(database)

    encryptor = SecretEncryptor("test-secret-key-for-encryption-only")
    get_product_registry.cache_clear()
    registry = get_product_registry()
    backup = preflight_configuration_upgrade(test_settings, encryptor, registry)
    assert backup is not None and backup.is_file()
    assert b"header-canary-42" in backup.read_bytes()

    _alembic_upgrade(test_settings.resolved_database_url, "head")
    engine = create_engine(test_settings.resolved_database_url)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        get_product_registry.cache_clear()
        result = migrate_legacy_configurations(
            db,
            registry,
            encryptor,
            test_settings,
            backup_path=backup,
        )
        assert result.migrated == 1
        row = db.execute(
            text(
                "SELECT configuration_version, destination, destination_secret_values, "
                "scenario_overrides, runtime_state FROM simulations "
                "WHERE id='legacy-simulation'"
            )
        ).one()
        assert row[0] == 3
        assert "header-canary-42" not in row[1]
        assert "query-canary-42" not in row[1]
        assert "url-canary-42" not in row[1]
        assert "header:X-Api-Key".casefold() in row[2].casefold()
        assert json.loads(row[3]) == {"data-leak": {"affected_domain": "retained.example"}}
        assert "unknown_legacy_field" in row[4]
        assert "quarantine-me" not in row[4]
        for table in (
            "delivery_attempts",
            "inbound_request_logs",
            "oauth_access_tokens",
        ):
            assert db.execute(text(f"SELECT count(*) FROM {table}")).scalar_one() == 0
    finally:
        db.close()
        engine.dispose()

    source_bytes = database.read_bytes()
    for canary in (
        b"header-canary-42",
        b"query-canary-42",
        b"url-canary-42",
    ):
        assert canary not in source_bytes


def test_corrupt_encryption_key_fails_before_backup_or_schema_change(test_settings) -> None:
    database = Path(test_settings.resolved_database_url.removeprefix("sqlite:///"))
    _alembic_upgrade(test_settings.resolved_database_url, "006_oauth2_client_credentials")
    _insert_legacy_simulation(
        database,
        auth_config={
            "auth_method_id": "basic",
            "username": "operator",
            "password_encrypted": "not-a-fernet-token",
        },
    )
    before = database.read_bytes()

    with pytest.raises(ValueError, match="decrypt"):
        preflight_configuration_upgrade(
            test_settings,
            SecretEncryptor("test-secret-key-for-encryption-only"),
            get_product_registry(),
        )

    assert database.read_bytes() == before
    backups = test_settings.resolved_data_dir / "backups"
    assert not backups.exists() or not list(backups.iterdir())
    with sqlite3.connect(database) as connection:
        columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(simulations)")}
    assert "configuration_version" not in columns


def test_v2_url_credentials_migrate_to_encrypted_basic_auth_without_losing_public_values(
    test_settings,
) -> None:
    database = Path(test_settings.resolved_database_url.removeprefix("sqlite:///"))
    _alembic_upgrade(test_settings.resolved_database_url, "head")
    _insert_v2_simulation(
        database,
        url="https://url-user:url-password-canary@example.com/hook",
    )
    encryptor = SecretEncryptor("test-secret-key-for-encryption-only")
    get_product_registry.cache_clear()
    registry = get_product_registry()

    backup = preflight_configuration_upgrade(test_settings, encryptor, registry)
    assert backup is not None and b"url-password-canary" in backup.read_bytes()

    engine = create_engine(test_settings.resolved_database_url)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        result = migrate_legacy_configurations(
            db, registry, encryptor, test_settings, backup_path=backup
        )
        assert result.migrated == 1
        row = db.execute(
            text(
                "SELECT configuration_version, destination, auth_config "
                "FROM simulations WHERE id='v2-simulation'"
            )
        ).one()
        assert row[0] == 3
        destination = json.loads(row[1])
        assert destination["url"] == "https://example.com/hook"
        assert destination["headers"] == [
            {"name": "X-Tenant", "value": "engineering", "sensitive": False}
        ]
        auth = encryptor.decrypt_auth_config(json.loads(row[2]))
        assert auth["auth_method_id"] == "basic"
        assert auth["username"] == "url-user"
        assert auth["password"] == "url-password-canary"
    finally:
        db.close()
        engine.dispose()

    assert b"url-password-canary" not in database.read_bytes()


def test_clean_v2_configuration_advances_to_v3_without_changing_public_values(
    test_settings,
) -> None:
    database = Path(test_settings.resolved_database_url.removeprefix("sqlite:///"))
    _alembic_upgrade(test_settings.resolved_database_url, "head")
    _insert_v2_simulation(database)
    encryptor = SecretEncryptor("test-secret-key-for-encryption-only")
    get_product_registry.cache_clear()
    registry = get_product_registry()
    backup = preflight_configuration_upgrade(test_settings, encryptor, registry)
    assert backup is not None and backup.is_file()

    engine = create_engine(test_settings.resolved_database_url)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        result = migrate_legacy_configurations(
            db, registry, encryptor, test_settings, backup_path=backup
        )
        assert result.migrated == 1
        row = db.execute(
            text(
                "SELECT configuration_version, destination, auth_config "
                "FROM simulations WHERE id='v2-simulation'"
            )
        ).one()
        assert row[0] == 3
        assert json.loads(row[1]) == {
            "transport_id": "http_webhook",
            "url": "https://example.com/hook",
            "method": "POST",
            "headers": [{"name": "X-Tenant", "value": "engineering", "sensitive": False}],
            "query_params": [],
        }
        assert json.loads(row[2]) == {"auth_method_id": "none"}
    finally:
        db.close()
        engine.dispose()


def test_v2_explicit_basic_auth_wins_and_url_user_info_is_removed(test_settings) -> None:
    database = Path(test_settings.resolved_database_url.removeprefix("sqlite:///"))
    _alembic_upgrade(test_settings.resolved_database_url, "head")
    encryptor = SecretEncryptor("test-secret-key-for-encryption-only")
    auth = encryptor.encrypt_auth_config(
        {
            "auth_method_id": "basic",
            "username": "configured-user",
            "password": "configured-password-canary",
        }
    )
    _insert_v2_simulation(
        database,
        url="https://ignored-user:ignored-password-canary@example.com/hook",
        auth_config=auth,
    )
    get_product_registry.cache_clear()
    registry = get_product_registry()
    backup = preflight_configuration_upgrade(test_settings, encryptor, registry)
    assert backup is not None

    engine = create_engine(test_settings.resolved_database_url)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        migrate_legacy_configurations(db, registry, encryptor, test_settings, backup_path=backup)
        row = db.execute(
            text("SELECT destination, auth_config FROM simulations WHERE id='v2-simulation'")
        ).one()
        assert json.loads(row[0])["url"] == "https://example.com/hook"
        decrypted = encryptor.decrypt_auth_config(json.loads(row[1]))
        assert decrypted["username"] == "configured-user"
        assert decrypted["password"] == "configured-password-canary"
    finally:
        db.close()
        engine.dispose()

    source = database.read_bytes()
    assert b"ignored-password-canary" not in source
    assert b"configured-password-canary" not in source


@pytest.mark.parametrize(
    ("product_id", "url", "auth_config", "message"),
    [
        (
            "upguard",
            "https://username-only@example.com/hook",
            {"auth_method_id": "none"},
            "username and password",
        ),
        (
            "demo-http",
            "https://user:password@example.com/hook",
            {"auth_method_id": "none"},
            "does not support Basic",
        ),
        (
            "upguard",
            "https://user:password@example.com/hook",
            {"auth_method_id": "bearer", "token": "encrypted-elsewhere"},
            "already configured",
        ),
    ],
)
def test_v2_unsafe_url_conflicts_fail_before_backup_or_write(
    test_settings,
    product_id: str,
    url: str,
    auth_config: dict[str, object],
    message: str,
) -> None:
    database = Path(test_settings.resolved_database_url.removeprefix("sqlite:///"))
    _alembic_upgrade(test_settings.resolved_database_url, "head")
    _insert_v2_simulation(database, product_id=product_id, url=url, auth_config=auth_config)
    encryptor = SecretEncryptor("test-secret-key-for-encryption-only")
    get_product_registry.cache_clear()

    with pytest.raises(RuntimeError, match=message):
        preflight_configuration_upgrade(test_settings, encryptor, get_product_registry())

    with sqlite3.connect(database) as connection:
        row = connection.execute(
            "SELECT configuration_version, destination FROM simulations WHERE id='v2-simulation'"
        ).fetchone()
    assert row is not None and row[0] == 2 and url in str(row[1])
    backups = test_settings.resolved_data_dir / "backups"
    assert not backups.exists() or not list(backups.iterdir())
