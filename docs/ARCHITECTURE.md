# Architecture

Integration Simulator `0.4.0` is a vendor-neutral, single-operator engineering tool. One container runs the FastAPI application, the APScheduler runtime, and the compiled React UI. SQLite and the generated encryption key live in the persistent `/data` volume.

## Implemented system

```text
Browser / collector
        |
        v
FastAPI /api/v1 + React SPA
        |
        +-- product registry ---- manifests, scenario JSON, payload/workflow plugins
        +-- simulation services - lifecycle, preview, faults, replay, export/import
        +-- scheduler ----------- continuous/finite push jobs, maintenance
        +-- inbound services ---- materialized pull data, auth, OAuth, audit
        +-- transport registry -- HTTP/HTTPS and Syslog UDP/TCP/TLS
        |
        v
SQLite /data/integration_simulator.db
```

The core references products, transports, and authentication methods by registry ID. Vendor-specific payload generation stays under `products/`; shared serializers implement source-format and table mappings.

## Responsibilities

| Area | Responsibility |
|---|---|
| `backend/app/api` | Versioned HTTP routes and exception rendering |
| `backend/app/services` | Simulation, delivery, migration, pull, retention, and export orchestration |
| `backend/app/domain` | Validated lifecycle, schedule, inbound, OAuth, and fault types |
| `backend/app/products` and `products/` | Manifest validation, scenario schemas/templates, seeded plugin hooks |
| `backend/app/transports` | Registry-owned delivery and connection-test capabilities |
| `backend/app/auth_strategies` | Outbound Basic, bearer, and API-key application |
| `backend/app/inbound` | Inbound auth, OAuth token issuance, and response construction |
| `backend/app/repositories` | Ordered, transactional SQLite access |
| `frontend/src` | Mode-aware operator UI and delivery/inbound evidence views |

## API and configuration boundaries

- The route prefix remains `/api/v1`. New exports use format `3.0`; imports retain `1.0`, `2.0`, and `2.1` compatibility.
- Create/update requests cannot set lifecycle status. New simulations are `stopped`; only lifecycle endpoints change state.
- Scenario overrides are maps keyed by selected scenario ID and are checked against each scenario's JSON Schema at every generation boundary.
- Custom destination headers and query values are ordered structured entries. Sensitive values are encrypted separately and are materialized only immediately before authentication or transport delivery.
- HTTP destination URLs cannot contain user-info. Authentication is represented separately so credentials cannot be persisted, exported, or surfaced as part of a URL.
- Inbound credentials are stored only in encrypted `auth_config`; product manifests declare supported inbound methods.
- Non-secret vendor settings live in schema-validated `vendor_options`; secret-like manifest option names are rejected at startup.
- Generic response profiles support JSON envelopes, raw arrays, static discovery, body or `Link` cursors, required headers, and vendor error shaping without core vendor-name branches.

## Persistence and integrity

SQLite uses foreign-key enforcement, WAL mode, and a bounded busy timeout on every connection. Alembic is the only schema upgrade mechanism. Revision 010 adds target, delivery-job and dataset persistence to the workflow-aware event history. Cascades and repository transactions keep attempts, inbound logs, OAuth token records, pull activations, and pull items tied to simulation ownership.

Before a legacy configuration conversion, startup validates every candidate and all encrypted values before any write, then creates a timestamped SQLite backup through the SQLite backup API. The key-aware converter preserves version 1 to 2 structured-secret conversion and advances configurations to version 3 after safely stripping or migrating URL credentials. Ambiguous cases block startup atomically and identify affected simulation IDs. Unknown or invalid legacy overrides are encrypted in an inactive quarantine record with an operator-visible warning.

## Runtime ownership

- Manual push simulations use `/send`; continuous and finite push simulations use APScheduler interval jobs.
- Finite completion uses a persisted activation-start counter, so each start emits its configured count without resetting lifetime statistics or history.
- Default restart behaviour marks persisted `running` simulations `stopped` and interrupted.
- With `SCHEDULER_RESUME_ON_RESTART=true`, the scheduler starts paused, validates persisted work, restores eligible jobs or pull activations, marks unsafe resumptions `error`, and then resumes. Interval jobs wait one full interval, so no catch-up burst occurs.
- Pull simulations register no outbound job. Starting creates a finite, materialized activation per product route. Safe process resume retains that activation; stop/start creates a new one.
- Manifest-defined actions execute through the normal transport and redacted evidence pipeline and persist as `workflow_action` events with an `action_id`.
- A single maintenance job runs retention at startup and on the configured interval.

## Delivery and evidence

HTTP/HTTPS supports GET, POST, PUT, and HEAD; redirects, TLS verification, timeout, structured headers/query entries, and all registered outbound auth methods are configurable. The engine collects exact outbound secret values and removes them from request evidence, response headers/bodies, and error messages; `Cookie` and `Set-Cookie` are sensitive by default. Attempts retain the exact redacted URL and ordered request/response evidence. cURL is generated from a selected attempt; legacy evidence can be returned with `exact=false` and warnings.

Syslog supports raw, RFC 3164, and RFC 5424 messages over UDP, TCP, and TLS, including TCP framing and rate limits. UDP success means only that the local datagram transport accepted the message. TCP/TLS confirms connection and write, not receiver processing.

Inbound request auditing includes matched successes, auth failures, injected faults, route failures, token requests, and unmatched `/mock` calls. Unmatched rows have a nullable simulation ID and are visible in the global inbound view.

## Security and deployment boundary

This programme deliberately retains the trusted-user model: no application login, RBAC, multi-tenancy, or destination allowlist. Compose binds the application to `127.0.0.1:8080` by default. Remote collection requires the documented TLS/authenticated gateway or an authenticated tunnel plus network restrictions.

## Deliberately deferred

PostgreSQL, multiple application replicas, distributed scheduling, built-in login/RBAC, UpGuard HMAC, mTLS client authentication, destination allowlists, Tenable asynchronous exports are outside `0.4.0`.

## Log lab delivery

A simulation contains independently encrypted target configurations and optional device identities. Logical events are generated once, rendered per target, and classified by the final outcome for every selected target. Legacy destination/auth updates synchronize only the primary target. Rate-based generation persists bounded per-target delivery jobs; independent workers claim batches, perform network IO outside write transactions, then persist attempts and cumulative outcomes together. Restart reclaims pending/active jobs with at-least-once semantics.

Source metadata, event-family scenarios, field references and fixtures live in product modules. Shared serializers handle CEF, event XML, mapped JSON and CSV; transports add Syslog framing or HTTP/API envelopes. Azure ingestion has OAuth refresh and byte-limited batches. Uploaded datasets use generated filenames under `/data/datasets`; SQLite stores metadata and replay cursor/timing state. See [Log Lab operations](LOG_LAB.md) and [verification status](IMPLEMENTATION_STATUS.md).
