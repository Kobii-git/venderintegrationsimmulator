from typing import Any, Literal

from app.products.manifest import DeliveryPolicy
from pydantic import BaseModel, ConfigDict, Field


class ScenarioTemplate(BaseModel):
    """Parsed scenario template JSON file."""

    model_config = ConfigDict(extra="forbid")

    content_type: str = "application/json"
    method: str = "POST"
    body: dict[str, Any] | str = Field(default_factory=dict)
    diagnostic_fields: dict[str, Any] = Field(default_factory=dict)
    diagnostic_merge: Literal["nested", "top_level"] | None = None


class ScenarioDefinition(BaseModel):
    """Fully loaded scenario: manifest metadata plus parsed template."""

    id: str
    product_id: str
    display_name: str
    description: str | None
    default_transport: str
    config_schema: dict[str, Any]
    supported_modes: list[str] = Field(default_factory=list)
    delivery_policy: DeliveryPolicy = Field(default_factory=DeliveryPolicy)
    template_path: str
    template: ScenarioTemplate

    def default_variable_values(self) -> dict[str, Any]:
        """Extract default values from config_schema properties."""
        properties = self.config_schema.get("properties", {})
        defaults: dict[str, Any] = {}
        for name, schema in properties.items():
            if isinstance(schema, dict) and "default" in schema:
                defaults[name] = schema["default"]
        return defaults
