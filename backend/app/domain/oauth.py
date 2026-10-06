"""OAuth2 client-credentials configuration for inbound mock API simulations."""

from pydantic import BaseModel, ConfigDict, Field


class OAuthFaultConfig(BaseModel):
    """Bounded fault injection for OAuth2 token endpoint and bearer validation."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    invalid_client: bool = False
    token_endpoint_failure: bool = False
    token_endpoint_status: int | None = Field(default=None, ge=500, le=599)
    wrong_scope: bool = False
    reject_tokens_as_expired: bool = False
