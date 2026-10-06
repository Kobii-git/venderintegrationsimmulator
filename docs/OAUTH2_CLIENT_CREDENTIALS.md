# OAuth2 Client Credentials Simulator

The **simulated OAuth2 client-credentials flow** lets external collectors obtain a test access token and call mock vendor API routes.

> **This is a testing simulator, not a production authorization server.** Do not use it as a real identity provider.

## Flow

```text
1. POST /api/v1/oauth2/token?simulation_id=<ID>
   grant_type=client_credentials&client_id=...&client_secret=...

2. Response: { access_token, token_type, expires_in, scope? }

3. GET /api/v1/mock/{product}/{route}
   Authorization: Bearer <access_token>
```

## Configuration

Set `inbound_config.auth_method_id` to `oauth2_client_credentials` on a pull simulation.

| Field | Description |
|-------|-------------|
| `auth_config.oauth_client_id` | Expected client ID (stored in plaintext) |
| `auth_config.oauth_client_secret` | Client secret (encrypted at rest) |
| `inbound_config.oauth_token_ttl_seconds` | Token lifetime (60–86400, default 3600) |
| `inbound_config.oauth_allowed_scopes` | Optional allow-list; empty = any scope accepted |

### Token request

```bash
curl -X POST "http://localhost:8080/api/v1/oauth2/token?simulation_id=<SIMULATION_ID>" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=client_credentials" \
  -d "client_id=sim-client-001" \
  -d "client_secret=your-secret" \
  -d "scope=read"
```

Alternative: HTTP Basic auth with `client_id:client_secret` in the `Authorization` header.

### API access

```bash
TOKEN=$(curl -s -X POST "http://localhost:8080/api/v1/oauth2/token?simulation_id=<ID>" \
  -d "grant_type=client_credentials&client_id=...&client_secret=..." | jq -r .access_token)

curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8080/api/v1/mock/demo-pull/events?simulation_id=<ID>&limit=5"
```

## Error responses (RFC 6749 style)

| Error | When |
|-------|------|
| `invalid_client` | Wrong client ID or secret |
| `invalid_scope` | Requested scope not in allow-list |
| `unsupported_grant_type` | Not `client_credentials` |
| `temporarily_unavailable` | Simulated token endpoint failure |

## OAuth fault injection

`inbound_config.oauth_fault_config` supports:

| Fault | Effect |
|-------|--------|
| `invalid_client` | Always reject token requests |
| `token_endpoint_failure` | Return 503 (or custom 5xx) from token endpoint |
| `wrong_scope` | Reject all scope requests |
| `reject_tokens_as_expired` | Issue tokens but reject them on API calls |

## Inspection

- Token requests logged to `inbound_request_logs` with `request_kind=token`
- Access tokens stored as **SHA-256 hashes** only — plaintext tokens are never persisted
- Request/response bodies redact `client_secret` and mask `access_token` in logs
- UI shows issued token metadata (client ID, scope, expiry) without secrets
- UI/API history uses an independent token-record ID and never a stored token prefix
- `GET /api/v1/simulations/{id}/oauth-tokens` — issued token metadata
- `GET /api/v1/simulations/{id}/inbound-requests?request_kind=token` — token request history

## Security notes

- Client secrets use the same Fernet encryption as other auth credentials
- Secrets are never returned via API, shown in UI, or written unredacted to logs
- Tokens expire per configured TTL; expired tokens are rejected and cleaned up by retention
- Success and error responses include `Cache-Control: no-store` and `Pragma: no-cache`
- Only the **client credentials** grant is implemented — no authorization code, refresh tokens, or PKCE

## Related

- [INBOUND_MOCK_API.md](INBOUND_MOCK_API.md) — pull-based mock API
- [SECURITY.md](SECURITY.md) — trust boundaries and secret handling
- [DECISIONS.md](DECISIONS.md) — ADR-020 OAuth2 client credentials
