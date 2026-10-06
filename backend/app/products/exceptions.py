class ProductModuleError(Exception):
    """Raised when a product module fails validation or loading."""

    def __init__(
        self,
        message: str,
        *,
        product_id: str | None = None,
        path: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.product_id = product_id
        self.path = path


class ManifestValidationError(ProductModuleError):
    """Invalid manifest.yaml content."""


class ScenarioTemplateError(ProductModuleError):
    """Invalid or missing scenario template."""
