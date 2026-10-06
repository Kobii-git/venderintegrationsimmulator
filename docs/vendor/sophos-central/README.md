# Sophos Central Workflow Module

The `sophos-central` product simulates one tenant's configurable authentication, discovery, and SIEM
polling flow. It is intended for collectors that allow simulator-local URLs; Sophos DNS and TLS
hostname emulation are outside scope.

## Configure

Create a `pull_api` simulation and set:

- `auth_config.oauth_client_id` and encrypted `auth_config.oauth_client_secret`.
- `inbound_config.auth_method_id` to `oauth2_client_credentials`.
- `inbound_config.oauth_allowed_scopes` to `['token']`.
- `inbound_config.vendor_options.tenant_id` to the UUID the collector should discover.

Start the simulation, then read its inbound endpoint information for complete URLs.

## Workflow

1. `POST .../api/v2/oauth2/token` with client-credentials form authentication and exact scope
   `token`. Success and errors use Sophos-shaped bodies; access tokens are persisted only as hashes.
2. `GET .../whoami/v1` with the bearer token. The response contains the configured tenant ID,
   `idType: tenant`, and simulator-local global/data-region URLs.
3. `GET .../siem/v1/events` with bearer authentication and matching `X-Tenant-ID`.

The events endpoint supports `limit` from 200 to 1000, opaque `cursor`, Unix `from_date` within the
last 24 hours, and comma-separated `exclude_types`. A cursor takes precedence over `from_date`.
Responses contain `items`, `has_more`, and `next_cursor` when another stable page exists.

## Scenarios

- Core malware detection
- Behavioral detection
- Potentially unwanted application detection
- IPS inbound detection
- IPS outbound detection

## Security and evidence

Client secrets and access tokens are excluded from logs, database evidence, APIs, exports, and cURL
diagnostics. The token request, discovery request, and every SIEM page remain visible as redacted
inbound evidence.

The simulated contract follows the configurable portions of the official
[Sophos authentication and discovery workflow](https://developer.sophos.com/intro),
[SIEM events endpoint](https://developer.sophos.com/docs/siem-v1/1/routes/events/get), and
[SIEM event schemas](https://developer.sophos.com/siem-api-schemas).
