# Protected Remote Exposure

Default Compose publishes Integration Simulator only at `127.0.0.1:8080`. Keep that mapping unchanged. The application has no login/RBAC, so a raw public port is never an acceptable exposure method.

## TLS/basic-auth gateway profile

The optional `docker-compose.protected.yml` profile runs Caddy on `0.0.0.0:8443`, terminates TLS with an internal CA, requires HTTP Basic authentication, and proxies over the private Compose network.

Generate a password hash without placing plaintext in the Compose file:

```bash
docker run --rm -it caddy:2.10.2-alpine caddy hash-password
```

Add the username and resulting hash to `.env`. Keep the hash single-quoted so its `$` characters are literal:

```dotenv
REMOTE_USERNAME=collector
REMOTE_PASSWORD_HASH='$2a$14$replace-with-the-generated-hash'
```

Start the protected profile:

```bash
docker compose \
  -f docker-compose.yml \
  -f docker-compose.protected.yml \
  --profile protected-exposure \
  up -d --build
```

Remote URL example:

```text
https://simulator.example.internal:8443/api/v1/mock/demo-pull/events?simulation_id=...
```

Caddy's local CA persists in `integration-simulator-caddy-data`. Export and trust that CA only on intended collectors, configure host/cloud firewall source allowlists, and use internal DNS. Basic auth protects management routes and the UI. `/api/v1/mock/*` and `/api/v1/oauth2/token` bypass gateway Basic auth so vendor Bearer/SSWS/OAuth authentication works without competing Authorization headers. Configure simulation-specific inbound authentication on those routes; the gateway does not add authentication to a mock configured as `none`.

## SSH tunnel profile

When the collector environment can maintain SSH, leave only the localhost mapping and forward a remote port through an authenticated host:

```bash
ssh -N -L 18080:127.0.0.1:8080 simulator-host
```

The client on the SSH-originating machine then uses `http://127.0.0.1:18080`. Use key-based SSH authentication and host/firewall restrictions. For cloud collectors that cannot maintain SSH, use the TLS gateway behind a private load balancer or equivalent authenticated tunnel rather than binding port 8080 broadly.

## Required controls

- TLS for every non-local HTTP path.
- Gateway/tunnel authentication plus simulation-specific inbound auth.
- Firewall or security-group source restriction.
- No anonymous exposure of the UI, export endpoints, or OpenAPI docs.
- Stable key and `/data` backups before changing deployment topology.
- Rotation of gateway, Basic, bearer, API-key, and OAuth test credentials after a shared test window.

The built-in OAuth server is a simulator and does not replace the outer deployment boundary.
