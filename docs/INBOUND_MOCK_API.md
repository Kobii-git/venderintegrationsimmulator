# Inbound Mock REST API

Pull mode lets an external collector call Integration Simulator as if it were a vendor API. Routes,
response shapes, authentication requirements, and non-secret vendor settings are declared by product
modules; the core request service does not branch on vendor names.

```text
Collector -> /api/v1/mock/{product_id}/{route} -> running pull_api simulation
```

## Quick start

1. Create a `pull_api` simulation for a product that declares `mock_routes`.
2. Configure inbound authentication and any schema-driven vendor options.
3. Start the simulation. Its materialized dataset remains stable for that activation.
4. Read `GET /api/v1/simulations/{id}/inbound-endpoint` and use the complete URLs it returns.
5. Inspect requests through `GET /api/v1/simulations/{id}/inbound-requests`.

The endpoint-info response includes complete route URLs with `simulation_id`, the configured token
URL, discovery URLs, API URLs, route handlers, and non-secret vendor options. This avoids manually
assembling paths for collectors that accept configurable base URLs.

## Manifest route contract

| Field | Purpose |
|---|---|
| `path`, `methods` | Path under `/api/v1/mock/{product_id}/` and allowed methods |
| `scenario_id`, `scenario_ids` | One scenario or a rotating set used to materialize route data |
| `handler` | `dataset_list`, `dataset_single`, `static`, or `oauth_token` |
| `required_oauth_scopes` | Exact scopes accepted by a token route and required by protected API routes |
| `response_profile.body_style` | JSON `envelope`, raw `array`, or `static` response |
| `response_profile.pagination_location` | Continuation in the response body, `Link` header, or nowhere |
| `response_profile.required_headers` | Request headers that must be present after authentication |
| `response_profile.response_headers` | Static response headers added by the route |

Response profiles also name the cursor, limit, since, and until parameters; set page-size bounds;
control self/next links; and choose the body cursor field. A product workflow plugin may add vendor
validation, filtering, static discovery, vendor-shaped errors, and final response shaping.

## Simulation configuration

`inbound_config` contains:

- Authentication method and header/query placement.
- `api_key_prefix`, for schemes such as Okta's `SSWS ` prefix.
- OAuth token lifetime, allowed scopes, and controlled OAuth faults.
- Materialized dataset size, item interval, page-size limits, and pull faults.
- `vendor_options`, validated against the selected product's `inbound_options_schema`.

Vendor options are deliberately non-secret. Product schemas cannot declare secret-like option
names, and unknown fields are rejected when the schema forbids them. Credentials belong only in the
encrypted `auth_config`.

## Authentication

| Method | Client requirement |
|---|---|
| `none` | No authentication |
| `api_key` | Configured header or query parameter, optionally with `api_key_prefix` |
| `basic` | `Authorization: Basic ...` |
| `bearer` | `Authorization: Bearer <token>` |
| `oauth2_client_credentials` | Obtain a scoped token, then use bearer authentication |

Manifest-defined `oauth_token` handlers can expose vendor-shaped token paths and bodies. The
provider-neutral `/api/v1/oauth2/token` endpoint remains available for generic products. Issued
access tokens are stored only as hashes, and request/audit evidence is redacted.

See [OAUTH2_CLIENT_CREDENTIALS.md](OAUTH2_CLIENT_CREDENTIALS.md).

## Materialized dataset lifecycle

Start creates an activation anchor and persists every rendered item. Repeated pages, time filters,
and process restarts read the same rows. Stop/start creates a new activation; safe process resume
keeps the prior activation and cursor identity.

Cursor tokens bind the activation, route, and next sequence. Malformed tokens, tokens from another
route, and tokens from an earlier activation are rejected. Vendor plugins may impose additional
cursor rules, bounded polling semantics, filters, ordering, or time windows.

## Faults and request evidence

Inbound faults support a forced HTTP status, bounded delay, empty results, malformed JSON, and an
inconsistent pagination token. Every matched or unmatched call records redacted request headers and
query parameters, response status/body/headers, authentication outcome, latency, and item count.

API surfaces:

- `GET /api/v1/simulations/{id}/inbound-requests`
- `GET /api/v1/simulations/{id}/inbound-requests/{request_id}`
- `GET /api/v1/simulations/{id}/inbound-endpoint`
- `GET /api/v1/inbound-requests`
- `GET /api/v1/inbound-requests/{request_id}`

## Shipped workflows

- [Sophos Central](vendor/sophos-central/README.md): client credentials, Who-am-I, and SIEM events.
- [Okta](vendor/okta/README.md): System Log polling plus event-hook verification and delivery.
- `demo-pull`: provider-neutral examples, including declarative required-header enforcement.

Default Compose is localhost-only. Follow [PUBLIC_EXPOSURE.md](PUBLIC_EXPOSURE.md) before allowing a
remote collector to reach these endpoints.

See [PRODUCT_MODULE_SPEC.md](PRODUCT_MODULE_SPEC.md) for the complete manifest contract.
