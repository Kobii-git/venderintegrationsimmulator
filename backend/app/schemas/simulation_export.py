"""Schemas for simulation export and import."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

EXPORT_FORMAT_VERSION = "3.0"
SUPPORTED_EXPORT_FORMAT_VERSIONS = frozenset({"1.0", "2.0", "2.1", EXPORT_FORMAT_VERSION})


class ExportedAuthConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    auth_method_id: str = "none"
    username: str | None = None
    header_name: str | None = None
    header_prefix: str | None = None
    has_password: bool = False
    has_token: bool = False
    oauth_client_id: str | None = None
    has_oauth_client_secret: bool = False
    password: str | None = None
    token: str | None = None
    oauth_client_secret: str | None = None


class ExportedSimulation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    product_id: str
    scenario_id: str
    scenario_ids: list[str]
    simulation_mode: str
    fidelity_mode: str
    destination: dict[str, Any]
    auth_config: ExportedAuthConfig
    scenario_overrides: dict[str, Any] = Field(default_factory=dict)
    schedule: dict[str, Any]
    fault_config: dict[str, Any] = Field(default_factory=dict)
    inbound_config: dict[str, Any] = Field(default_factory=dict)
    targets: list[dict[str, Any]] = Field(default_factory=list)
    devices: list[dict[str, Any]] = Field(default_factory=list)
    replay_config: dict[str, Any] = Field(default_factory=dict)
    random_seed: int | None = None


class SimulationExportDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    format_version: str = EXPORT_FORMAT_VERSION
    exported_at: datetime
    includes_secrets: bool = False
    simulation: ExportedSimulation


class SimulationImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document: dict[str, Any]


class SimulationImportResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    simulation_id: str
    name: str
    secrets_imported: bool
    missing_secrets: list[str] = Field(default_factory=list)
