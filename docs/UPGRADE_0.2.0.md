# Upgrade Notes: 0.2.0

`0.2.0` is a repair and completion release for the existing Integration Simulator. It intentionally corrects the `/api/v1` configuration contract in place; there is no `/api/v2` compatibility layer.

## Before upgrading

1. Retain the previous application image and an external copy of the data volume.
2. Preserve the current `SECRET_KEY`, or `/data/.secret_key` when using the generated-key option.
3. Stop all collectors and the previous container cleanly.
4. Read the breaking API/export changes below.

## Automatic upgrade

Starting `0.2.0` with an existing SQLite volume first validates secret decryptability and creates `/data/backups/pre-config-v2-<timestamp>.db` through the SQLite backup API. It then applies Alembic revisions:

- `007_secure_configuration_and_integrity`
- `008_materialized_pull_datasets`

The key-aware configuration converter upgrades saved configurations to version 3. It first preserves the existing version 1 to 2 conversion: encrypting legacy header/query values, splitting query strings out of destination URLs, migrating inbound credentials, and converting flat overrides. Invalid/unknown override values are held in an encrypted inactive quarantine and surfaced as warnings.

It then removes complete username/password user-info from HTTP URLs. Explicit Basic authentication is retained; otherwise the URL values become encrypted Basic authentication only when the selected product supports it. Incomplete credentials, unsupported products, or conflicts with another authentication method stop startup before any database write and identify only affected simulation IDs. Use the retained previous image to correct those configurations, then retry the upgrade.

Startup validates every candidate and encryption key before creating the backup or committing conversions. Startup exits without changing the source database if candidate validation, key validation, or backup creation fails. Non-secret migration warnings are stored in runtime metadata.

## Breaking contract changes

- Create/update requests cannot set `status`; use `/start` and `/stop`.
- `scenario_overrides` is keyed by selected scenario ID.
- Destination headers/query parameters are ordered structured entries and sensitive by default.
- New destination URLs reject embedded queries and fragments.
- HTTP URLs reject embedded credentials with HTTP 422; configure authentication separately. Direct engine requests fail as `malformed_destination`.
- Inbound credentials live only in encrypted `auth_config`.
- Pull `/send` returns a validation error; start materializes finite route datasets.
- Export format is `2.0`. Sanitized imports return `missing_secrets` and cannot start/send until credentials are supplied.
- Format `1.0` remains importable through an in-memory converter; its legacy header/query values are treated as sensitive.
- OAuth history exposes an independent token-record ID, never a token prefix.
- Generic HTTP connection tests accept optional `sensitive_header_names` and `sensitive_query_names`; response bodies, response headers (including cookies), destination evidence, and error text are redacted against exact outbound secret values.

## Runtime changes

- Restart still stops running simulations by default. `SCHEDULER_RESUME_ON_RESTART=true` enables validated, paused-start resume without catch-up bursts.
- Finite schedules count `event_count` against the current start activation while retaining lifetime counters and history from earlier manual, burst, replay, or scheduled activity.
- Pull datasets and cursor identity survive safe process resume; stop/start creates a new activation.
- UDP success is explicitly best effort. TCP/TLS confirms transport connection/write, not collector processing.
- Random seeds reproduce pseudo-random scenario/plugin values by event sequence; correlation IDs and actual delivery times remain unique/current.

## Deployment changes

Default Compose binds `127.0.0.1:8080:8080` and passes `SECRET_KEY` and the opt-in `SCHEDULER_RESUME_ON_RESTART` setting from `.env`. Remote collectors must use `docker-compose.protected.yml` or an authenticated tunnel as documented in [PUBLIC_EXPOSURE.md](PUBLIC_EXPOSURE.md).

## Rollback

Stop `0.2.0`, restore the newest matching `pre-config-v2-*.db` and encryption key, remove SQLite `-wal`/`-shm` sidecars, and run the retained previous image. Alembic revisions 007/008 are forward-only; do not run the old image against the upgraded database.

## Verification record

Working-folder validation on 2026-08-26 passed backend lint/format/strict typing, 197 tests, both dependency audits, 9 migration cases, frontend lint/type/10 tests/audit/build on Node 20, 4 real-backend Playwright workflows, the complete 17-step UpGuard operator workflow, and the clean production-image HTTP/UDP/TCP/TLS, retained-database migration, restart, persistence, response-echo secret-canary, exact-byte, pull-pagination, and backup-restore probes. The final `scripts/verify-all.sh` rerun passed after the operator-discovered preview identity, stale-preview coordination, edit payload, successful-attempt category, finite activation, and Compose safe-resume fixes. A clean-checkout rerun, GitHub Actions, and the retained `0.1.0` image rollback remain release prerequisites.

One development-only pytest advisory is governed by the expiring waiver in [SECURITY_WAIVERS.md](SECURITY_WAIVERS.md); pytest is not installed in the production image.
