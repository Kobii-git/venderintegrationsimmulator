# Product Module Specification

How vendor/product modules are structured, discovered, validated, and extended. Products are **not** hardcoded in the application core.

This document is the authoritative guide for adding a new vendor. You should not need to read core application source code to add a standard product.

---

## Quick start: add a new vendor

1. Create a folder: `products/<product_id>/` where `<product_id>` matches `^[a-z][a-z0-9-]*$`.
2. Add `manifest.yaml` (see schema below).
3. Add one or more scenario templates under `scenarios/*.json`.
4. Restart the application (products are loaded at startup).
5. Verify:
   - `GET /api/v1/products` lists your product
   - `GET /api/v1/products/<product_id>/scenarios/<scenario_id>` returns metadata

Only add `plugin.py` if configuration and templates are insufficient.

---

## Directory layout

```text
products/
    <product_id>/
        manifest.yaml          # Required
        scenarios/
            <scenario_id>.json # One or more scenario templates
        plugin.py              # Optional — complex behaviour only
```

### Example: demo product (shipped with the simulator)

```text
products/
    demo-http/
        manifest.yaml
        scenarios/
            ping.json
        plugin.py              # Optional demonstration plugin
```

### Example: demo syslog product

```text
products/
    demo-syslog/
        manifest.yaml
        scenarios/
            ping.json
            json-event.json
```

Use `supported_transports: [syslog]` and `default_transport: syslog` for syslog-only products. See [docs/TRANSPORTS.md](TRANSPORTS.md) for destination field reference.

### Example: Fortinet FortiGate product

```text
products/
    fortinet/
        manifest.yaml
        plugin.py
        scenarios/
            forward-traffic-allow.json
            forward-traffic-deny.json
            local-traffic.json
            vpn-event.json
            user-auth-event.json
            system-event.json
            threat-virus.json
```

Vendor-specific documentation: [docs/vendor/fortinet/README.md](vendor/fortinet/README.md).

```text
products/
    upguard/
        manifest.yaml
        scenarios/
            score-change.json
            data-leak.json
            identity-breach.json
            vulnerability.json
        plugin.py              # Only if templates are insufficient
```

---

## manifest.yaml schema

Validated by Pydantic at load time. Invalid manifests prevent the product from loading and produce clear error messages.

### Required fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Stable slug; **must match directory name** |
| `display_name` | string | Human-readable label (alias: `name`) |
| `version` | string | Product module version |
| `supported_modes` | list[string] | Alias: `simulation_modes` |
| `supported_transports` | list[string] | Alias: `transports` |
| `supported_auth_methods` | list[string] | Alias: `authentication` |

### Optional fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `description` | string | null | Product description |
| `scenarios` | list | `[]` | Scenario catalog entries |
| `plugin` | bool | `false` | Set `true` if `plugin.py` is required |
| `diagnostic_merge` | string | `nested` | `nested` or `top_level` for troubleshooting payloads |
| `inbound_options_schema` | object | `{}` | JSON Schema for non-secret vendor settings |
| `actions` | list | `[]` | Operator-triggered outbound workflow actions |

### Supported capability IDs (validated at load time)

| Category | Allowed values |
|----------|----------------|
| Simulation modes | `push_webhook`, `pull_api` |
| Transports | `http_webhook`, `syslog` |
| Authentication (outbound) | `none`, `basic`, `bearer`, `api_key_header` |
| Authentication (inbound) | `none`, `api_key`, `basic`, `bearer`, `oauth2_client_credentials` |

### Scenario entry (within `scenarios` list)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | yes | Unique within product |
| `display_name` | string | yes | Alias: `name` |
| `description` | string | no | Scenario description |
| `default_transport` | string | no | Default: `http_webhook` |
| `template` | string | yes | Path relative to product dir, e.g. `scenarios/ping.json` |
| `config_schema` | object | no | JSON Schema for simulation variable overrides |
| `supported_modes` | list | no | Modes in which this scenario can be selected |
| `delivery_policy` | object | no | Timeout, redirect, retry count, and retry categories |

### Mock route entry (within `mock_routes` list, required for `pull_api` products)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | yes | Unique route identifier |
| `path` | string | yes | Path segment under `/api/v1/mock/{product_id}/` |
| `methods` | list | no | HTTP methods (default `GET`) |
| `scenario_id` | string | yes | Scenario used to generate response items |
| `scenario_ids` | list | no | Multiple scenarios rotated into one materialized route |
| `handler` | string | no | `dataset_list`, `dataset_single`, `static`, or `oauth_token` |
| `required_oauth_scopes` | list | no | Exact scopes accepted by token routes and required by API routes |
| `response_type` | string | no | `list` or `single` (default `list`) |
| `items_field` | string | no | JSON array field name (default `items`) |
| `next_token_field` | string | no | Pagination cursor field (default `nextPageToken`) |
| `supports_pagination` | bool | no | Default `true` |
| `supports_time_filter` | bool | no | Default `true` |
| `response_profile` | object | no | Body style, cursor names/location, limits, headers, and pagination policy |

Products with `pull_api` in `supported_modes` must declare at least one `mock_routes` entry.

Response profiles can return an envelope, a raw JSON array, or a static body. Pagination can be
placed in the body or in RFC 8288-style `Link` headers. Product workflow plugins may validate
requests, filter materialized items, shape success/error bodies, and wrap outbound payloads. Core
services never branch on a product ID.

Within `response_profile`, `required_headers` is a list of request header names that must be present,
and `response_headers` is a map of static headers to emit. `body_style` accepts `envelope`, `array`,
or `static`; `pagination_location` accepts `body`, `link_header`, or `none`. Cursor/limit/since/until
parameter names and minimum/default/maximum limits are independently configurable.

### Product actions

Actions declare an ID, supported modes, HTTP method, headers/body templates, accepted statuses,
delivery policy, and an optional response assertion. Execute one with:

```text
POST /api/v1/simulations/{simulation_id}/actions/{action_id}
```

The result and redacted attempts are persisted in normal event history with
`event_kind=workflow_action` and the declared `action_id`.

### Vendor option safety

`inbound_options_schema` must be a valid object JSON Schema. Top-level property names containing
password, secret, token, API key, or credential patterns are rejected; secrets belong in encrypted
`auth_config`. Options are validated on create, update, import, start, and every inbound request.

### Example manifest

```yaml
id: upguard
display_name: UpGuard
version: "1.0.0"
description: UpGuard webhook integration simulation

supported_modes:
  - push_webhook

supported_transports:
  - http_webhook

supported_auth_methods:
  - none
  - basic
  - bearer

diagnostic_merge: nested

scenarios:
  - id: data-leak
    display_name: Data Leak Detected
    description: Simulates an UpGuard data leak webhook event
    default_transport: http_webhook
    template: scenarios/data-leak.json
    config_schema:
      type: object
      properties:
        organisation_name:
          type: string
          description: Organisation name in the payload
          default: Example Corp
      additionalProperties: false
```

### Validation rules

- `id` must match `^[a-z][a-z0-9-]*$` and equal the directory name.
- Scenario `id` must be unique within the manifest.
- Scenario `template` file must exist on disk.
- Capability IDs must be from the allowed lists above.
- Duplicate scenario IDs fail validation.
- Bad YAML or JSON schema violations produce `ManifestValidationError` at startup.

---

## Scenario template format

Each scenario template is a JSON file referenced by the manifest.

```json
{
  "content_type": "application/json",
  "method": "POST",
  "body": {
    "event_type": "data_leak",
    "organisation": "{{ organisation_name }}",
    "sent_at": "{{ generated_at_iso }}",
    "event_id": "{{ correlation_id }}"
  },
  "diagnostic_fields": {
    "simulator_event_id": "{{ correlation_id }}",
    "simulator_timestamp": "{{ generated_at_iso }}",
    "simulator_product": "{{ product_id }}",
    "simulator_scenario": "{{ scenario_id }}"
  },
  "diagnostic_merge": "nested"
}
```

### Template fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `content_type` | string | `application/json` | Outbound content type |
| `method` | string | `POST` | HTTP method (for webhook transport) |
| `body` | object | `{}` | Payload template |
| `diagnostic_fields` | object | `{}` | Fields added in troubleshooting mode |
| `diagnostic_merge` | string | null | Override manifest `diagnostic_merge` for this scenario |

### Template variables

Templates use a **restricted Jinja2 sandbox** (no arbitrary Python execution).

#### Built-in context variables

| Variable | Description |
|----------|-------------|
| `product_id` | Product slug |
| `scenario_id` | Scenario slug |
| `correlation_id` | Event correlation ID |
| `generated_at_iso` | Current UTC timestamp (ISO 8601) |
| User overrides | Values from `config_schema` / simulation `scenario_overrides` |

#### Built-in template functions

| Function | Example | Description |
|----------|---------|-------------|
| `uuid4()` | `{{ uuid4() }}` | Random UUID string |
| `now_iso()` | `{{ now_iso() }}` | Current UTC timestamp |
| `random_int(min, max)` | `{{ random_int(1, 100) }}` | Random integer (rendered as string in JSON) |

### Fidelity modes

| Mode | Behaviour |
|------|-----------|
| `vendor_accurate` | Only `body` is rendered and returned |
| `troubleshooting` | `diagnostic_fields` merged into payload (`nested` → `_simulator` key, `top_level` → top-level keys) |

---

## Optional plugin.py

Plugins are **optional**. Most products should not need one.

### When to use a plugin

| Use plugin for… | Do not use plugin for… |
|-----------------|------------------------|
| Dynamic context enrichment | Static payload structure |
| Rare post-render adjustments | Variable substitution (use templates) |
| Product-specific computed fields | Transport or auth logic (core responsibility) |

### Plugin interface

```python
class ProductPlugin:
    product_id: str

    def enrich_context(
        self,
        scenario_id: str,
        overrides: dict[str, Any],
    ) -> dict[str, Any]:
        """Return extra template variables. Default: empty dict."""
        return {}

    def post_render(
        self,
        payload: dict[str, Any],
        fidelity_mode: FidelityMode,
        *,
        scenario_id: str,
        correlation_id: str,
    ) -> dict[str, Any]:
        """Final payload adjustment. Default: return payload unchanged."""
        return payload
```

### Plugin module requirements

Expose **one** of:

- `get_plugin()` function returning a `ProductPlugin` instance, or
- `ProductPlugin` class (instantiated by the loader)

The instance's `product_id` must match the manifest `id`.

### Plugin lifecycle

1. Loaded at application startup if `plugin: true` in manifest or `plugin.py` exists.
2. `enrich_context()` called before template rendering.
3. `post_render()` called after rendering (troubleshooting diagnostics included).
4. Plugins cannot modify transport, auth, scheduling, or database behaviour.

### What remains core-controlled

- Transport selection and delivery
- Authentication strategy application
- Simulation persistence and scheduling
- Delivery attempt logging
- Secret encryption and redaction

---

## Registry lifecycle

1. On startup, `ProductRegistry.load_all()` scans `products/*/manifest.yaml`.
2. Each manifest is parsed and validated (capabilities, directory name, scenario uniqueness).
3. Scenario template JSON files are loaded and validated.
4. Optional `plugin.py` is imported from the product directory only.
5. Registry exposes read-only catalog via API.

---

## API endpoints

All endpoints use the `/api/v1` prefix.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/products` | List installed products |
| GET | `/api/v1/products/{product_id}` | Product detail + scenario summaries |
| GET | `/api/v1/products/{product_id}/scenarios` | List scenarios |
| GET | `/api/v1/products/{product_id}/scenarios/{scenario_id}` | Scenario detail for UI configuration |

Scenario detail includes `config_schema`, parsed `variables` (name, type, default, required), and `template_metadata` (content type, HTTP method).

---

## Extension without core changes

| Change | Requires core code? |
|--------|---------------------|
| New product folder + manifest | **No** |
| New scenario JSON | **No** |
| New transport type (e.g. syslog) | **Yes** — ADR required |
| New auth method (e.g. OAuth2) | **Yes** — ADR required |
| Product-specific payload logic | Optional `plugin.py` only |

---

## Checklist for a new vendor

- [ ] Create `products/<id>/` matching manifest `id`
- [ ] Define `supported_modes`, `supported_transports`, `supported_auth_methods`
- [ ] Add scenarios with templates and `config_schema` defaults
- [ ] Verify templates render with `vendor_accurate` and `troubleshooting` modes
- [ ] Confirm API returns product and scenario metadata
- [ ] Add plugin only if templates are insufficient
- [ ] Do **not** modify core application code for standard webhook products

---

## Internal demo product

`products/demo-http/` is shipped as an internal architecture verification product. It demonstrates manifest loading, template rendering, plugin hooks, and API responses. It is not a real vendor integration.
