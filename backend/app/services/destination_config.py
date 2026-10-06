"""Secure persistence and runtime reconstruction for destination configuration."""

from __future__ import annotations

from typing import Any

from app.core.exceptions import ValidationAppError
from app.core.security import SecretEncryptor
from app.schemas.simulation import (
    ConfiguredValueInput,
    ConfiguredValueResponse,
    DestinationConfig,
    DestinationConfigResponse,
)


def secret_storage_key(kind: str, name: str) -> str:
    normalized = name.casefold() if kind == "header" else name
    return f"{kind}:{normalized}"


def store_destination(
    destination: DestinationConfig,
    encryptor: SecretEncryptor,
    *,
    existing_secrets: dict[str, str] | None = None,
) -> tuple[dict[str, Any], dict[str, str]]:
    """Return a persistence-safe destination and encrypted secret-value map."""
    existing = existing_secrets or {}
    stored = destination.model_dump(mode="json")
    encrypted: dict[str, str] = {}
    stored["headers"] = _store_values(
        destination.headers,
        "header",
        encryptor,
        existing,
        encrypted,
    )
    stored["query_params"] = _store_values(
        destination.query_params,
        "query",
        encryptor,
        existing,
        encrypted,
    )
    return stored, encrypted


def _store_values(
    values: list[ConfiguredValueInput],
    kind: str,
    encryptor: SecretEncryptor,
    existing: dict[str, str],
    encrypted: dict[str, str],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in values:
        if item.sensitive:
            key = secret_storage_key(kind, item.name)
            if item.value is not None:
                encrypted[key] = encryptor.encrypt(item.value)
            elif key in existing:
                encrypted[key] = existing[key]
            result.append({"name": item.name, "sensitive": True})
        else:
            result.append(
                {
                    "name": item.name,
                    "sensitive": False,
                    "value": item.value or "",
                }
            )
    return result


def destination_for_delivery(
    stored: dict[str, Any],
    encrypted_values: dict[str, str],
    encryptor: SecretEncryptor,
) -> dict[str, Any]:
    """Reconstruct the legacy transport-facing header/query mappings in memory."""
    result = dict(stored)
    result["headers"] = _runtime_values(
        stored.get("headers", []), "header", encrypted_values, encryptor
    )
    result["query_params"] = _runtime_values(
        stored.get("query_params", []), "query", encrypted_values, encryptor
    )
    result["_sensitive_header_names"] = _sensitive_names(stored.get("headers", []))
    result["_sensitive_query_names"] = _sensitive_names(stored.get("query_params", []))
    return result


def destination_input_for_delivery(destination: DestinationConfig) -> dict[str, Any]:
    """Convert write-only structured input into a transport-facing in-memory mapping."""
    result = destination.model_dump(exclude={"headers", "query_params"})
    result["headers"] = _input_runtime_values(destination.headers, "headers")
    result["query_params"] = _input_runtime_values(destination.query_params, "query_params")
    result["_sensitive_header_names"] = [
        item.name for item in destination.headers if item.sensitive
    ]
    result["_sensitive_query_names"] = [
        item.name for item in destination.query_params if item.sensitive
    ]
    return result


def _input_runtime_values(values: list[ConfiguredValueInput], field_name: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in values:
        if item.sensitive and item.value is None:
            raise ValidationAppError(
                f"destination.{field_name}.{item.name} requires a value for one-shot delivery"
            )
        result[item.name] = item.value or ""
    return result


def _sensitive_names(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    return [
        str(item["name"])
        for item in values
        if isinstance(item, dict) and item.get("name") and item.get("sensitive", True)
    ]


def _runtime_values(
    values: Any,
    kind: str,
    encrypted_values: dict[str, str],
    encryptor: SecretEncryptor,
) -> dict[str, str]:
    if isinstance(values, dict):
        # Only reachable for a database that has not completed configuration migration.
        return {str(key): str(value) for key, value in values.items()}
    result: dict[str, str] = {}
    for raw in values if isinstance(values, list) else []:
        if not isinstance(raw, dict) or not raw.get("name"):
            continue
        name = str(raw["name"])
        if raw.get("sensitive", True):
            ciphertext = encrypted_values.get(secret_storage_key(kind, name))
            if ciphertext is not None:
                result[name] = encryptor.decrypt(ciphertext)
        else:
            result[name] = str(raw.get("value", ""))
    return result


def destination_for_response(
    stored: dict[str, Any], encrypted_values: dict[str, str]
) -> DestinationConfigResponse:
    public = dict(stored)
    public["headers"] = _public_values(stored.get("headers", []), "header", encrypted_values)
    public["query_params"] = _public_values(
        stored.get("query_params", []), "query", encrypted_values
    )
    return DestinationConfigResponse.model_validate(public)


def _public_values(
    values: Any, kind: str, encrypted_values: dict[str, str]
) -> list[ConfiguredValueResponse]:
    result: list[ConfiguredValueResponse] = []
    for raw in values if isinstance(values, list) else []:
        if not isinstance(raw, dict) or not raw.get("name"):
            continue
        name = str(raw["name"])
        sensitive = bool(raw.get("sensitive", True))
        if sensitive:
            result.append(
                ConfiguredValueResponse(
                    name=name,
                    sensitive=True,
                    has_value=secret_storage_key(kind, name) in encrypted_values,
                )
            )
        else:
            result.append(
                ConfiguredValueResponse(
                    name=name,
                    sensitive=False,
                    has_value=True,
                    value=str(raw.get("value", "")),
                )
            )
    return result


def missing_destination_secrets(
    stored: dict[str, Any], encrypted_values: dict[str, str]
) -> list[str]:
    missing: list[str] = []
    for field, kind in (("headers", "header"), ("query_params", "query")):
        values = stored.get(field, [])
        for raw in values if isinstance(values, list) else []:
            if not isinstance(raw, dict) or not raw.get("name") or not raw.get("sensitive", True):
                continue
            name = str(raw["name"])
            if secret_storage_key(kind, name) not in encrypted_values:
                missing.append(f"destination.{field}.{name}")
    return missing


def destination_for_export(
    stored: dict[str, Any],
    encrypted_values: dict[str, str],
    encryptor: SecretEncryptor,
    *,
    include_secrets: bool,
) -> dict[str, Any]:
    exported = dict(stored)
    for field, kind in (("headers", "header"), ("query_params", "query")):
        values: list[dict[str, Any]] = []
        raw_values = stored.get(field, [])
        for raw in raw_values if isinstance(raw_values, list) else []:
            if not isinstance(raw, dict) or not raw.get("name"):
                continue
            item = dict(raw)
            name = str(item["name"])
            if item.get("sensitive", True):
                item["has_value"] = secret_storage_key(kind, name) in encrypted_values
                if include_secrets and item["has_value"]:
                    item["value"] = encryptor.decrypt(
                        encrypted_values[secret_storage_key(kind, name)]
                    )
                else:
                    item.pop("value", None)
            values.append(item)
        exported[field] = values
    return exported
