"""Validation for product-defined, explicitly non-secret inbound options."""

from typing import Any

from jsonschema import Draft202012Validator

from app.core.exceptions import ValidationAppError
from app.products.manifest import ProductManifest


def validate_inbound_options(
    manifest: ProductManifest,
    options: dict[str, Any],
    *,
    workflow_plugin: Any | None = None,
) -> None:
    schema = manifest.inbound_options_schema or {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    }
    validator = Draft202012Validator(schema)
    errors = [
        {
            "path": ".".join(str(part) for part in error.absolute_path),
            "message": error.message,
        }
        for error in validator.iter_errors(options)
    ]
    if errors:
        raise ValidationAppError(
            "Vendor options failed schema validation",
            details={"product_id": manifest.id, "errors": errors},
        )
    if workflow_plugin is not None:
        workflow_plugin.validate_inbound_options(options)
