"""Inbound mock API configuration models."""

from typing import Literal

from app.domain.oauth import OAuthFaultConfig
from pydantic import BaseModel, ConfigDict, Field


class InboundFaultConfig(BaseModel):
    """Bounded fault injection for inbound mock API responses."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    response_status: int | None = Field(default=None, ge=400, le=599)
    delay_ms: int = Field(default=0, ge=0, le=30_000)
    malformed_json: bool = False
    force_empty: bool = False
    pagination_inconsistent: bool = False


class InboundConfig(BaseModel):
    """Configuration for pull-based (inbound) API simulations."""

    model_config = ConfigDict(extra="forbid")

    auth_method_id: Literal["none", "api_key", "basic", "bearer", "oauth2_client_credentials"] = (
        "none"
    )
    api_key_header: str = "X-Api-Key"
    api_key_query_param: str | None = None
    api_key_prefix: str = ""
    vendor_options: dict[str, object] = Field(default_factory=dict)
    oauth_token_ttl_seconds: int = Field(default=3600, ge=60, le=86_400)
    oauth_allowed_scopes: list[str] = Field(default_factory=list)
    oauth_fault_config: OAuthFaultConfig = Field(default_factory=OAuthFaultConfig)
    default_page_size: int = Field(default=50, ge=1, le=500)
    max_page_size: int = Field(default=100, ge=1, le=1000)
    pagination_style: Literal["cursor", "page"] = "cursor"
    dataset_size: int = Field(default=100, ge=1, le=10_000)
    item_interval_seconds: int = Field(default=60, ge=1, le=86_400)
    fault_config: InboundFaultConfig = Field(default_factory=InboundFaultConfig)
