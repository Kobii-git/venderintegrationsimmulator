# Troubleshooting Guide

## Delivery failed

1. Open the simulation **Live view** and click the failed delivery row.
2. Check **HTTP status**, **error category**, and **explanation**.
3. Verify destination URL, auth, and network connectivity.
4. Use **Copy as cURL** to reproduce outside the simulator (secrets redacted).

## Cannot find an event

- Copy the **correlation ID** from the delivery detail page.
- Filter delivery history by correlation ID.
- Or use global search: `GET /api/v1/events?correlation_id=...`

## Credentials not working

- Edit the simulation and re-enter the password (passwords are never shown after save).
- Ensure `SECRET_KEY` is stable across container restarts if using Docker.
- Check that basic auth username/password are configured on the simulation, not just in a one-off product send.

## Simulation interrupted after restart

Running simulations are marked **stopped** on container restart (safe default). Start again manually.

## Export / import

- **Export config** on the live view downloads a JSON file without secrets.
- Import via `POST /api/v1/simulations/import`.
- Re-enter credentials after importing a sanitized export.

## Fault injection

See [FAULT_TESTING.md](FAULT_TESTING.md).

## Logs

```bash
docker compose logs -f integration-simulator
```

Logs are secret-redacted. Set `LOG_LEVEL=DEBUG` only temporarily in trusted environments.

## Common HTTP errors

| Status | Likely cause |
|--------|--------------|
| Connection timeout | Destination unreachable or firewall |
| 401/403 | Auth misconfiguration at collector |
| 400 | Payload rejected by collector parser |
| 500 | Collector internal error |

The simulator reports what the destination returned; it cannot simulate destination-side errors without a mock server.
