# Adding a Product Module

Product modules live under `products/<product_id>/` and are loaded at startup.

## Directory structure

```
products/my-vendor/
├── manifest.yaml          # Product metadata
├── plugin.py              # Optional enrichment hooks
└── scenarios/
    ├── scenario-one.json
    └── scenario-two.json
```

## Scenario JSON format

```json
{
  "content_type": "application/json",
  "method": "POST",
  "body": { "event": "{{ correlation_id }}" },
  "diagnostic_fields": {
    "simulator_event_id": "{{ correlation_id }}"
  },
  "diagnostic_merge": "nested"
}
```

Templates use Jinja2 with a restricted sandbox. Available context includes `correlation_id`, `generated_at_iso`, `random_int`, and scenario variables.

## Plugin (optional)

```python
class MyVendorPlugin(ProductPlugin):
    def enrich_context(self, scenario_id, overrides):
        return {"custom_field": "value"}

    def post_render(self, payload, fidelity_mode, **kwargs):
        return payload
```

## Steps

1. Create `products/<id>/manifest.yaml` with supported modes, transports, auth methods.
2. Add scenario JSON files.
3. Implement `plugin.py` if vendor-specific logic is needed.
4. Add tests in `backend/tests/test_<product>.py`.
5. Add vendor docs under `docs/vendor/<id>/`.

## Testing

```bash
cd backend && pytest tests/test_products.py tests/test_upguard.py -v
```

Restart the application (or Docker container) to load new products.
