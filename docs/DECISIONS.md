# Architecture Decision Log

Accepted decisions for Integration Simulator. ADR numbers are unique; records 018–020 replace the duplicate numbers previously used for Fortinet, inbound pull, and OAuth.

## ADR-001: Vendor-neutral core with product modules

**Decision:** The application core owns generic simulation concepts. Manifests, scenarios, and optional plugins under `products/` own vendor behaviour. Core code never branches on vendor name.

## ADR-002: SQLite with SQLAlchemy and Alembic

**Decision:** Keep one SQLite database in `/data`, use SQLAlchemy 2.x, and apply forward-only Alembic migrations. Every connection enables foreign keys, WAL, and a bounded busy timeout.

## ADR-003: Single application container

**Decision:** One image runs FastAPI, APScheduler, and the compiled React SPA. A persistent volume owns database, generated key, and backups. No broker or database service is required.

## ADR-004: Registry-owned transport capabilities

**Decision:** HTTP/HTTPS and Syslog UDP/TCP/TLS implement a common registry contract, including delivery and connection-test capabilities. Adding a transport must not add central protocol branching.

## ADR-005: Two fidelity modes

**Decision:** `vendor_accurate` contains only vendor fields. `troubleshooting` may add clearly identified simulator correlation data. This applies to JSON and Fortinet text output.

## ADR-006: Encrypt secrets and redact all evidence

**Decision:** Auth and structured destination secrets are Fernet-encrypted. Decryption occurs only at the delivery/auth boundary. Reads expose markers, evidence is redacted before persistence, default exports omit values, and confirmed secret export is explicit. A user-supplied `SECRET_KEY` or the volume-persisted `/data/.secret_key` keeps encryption stable.

## ADR-007: YAML manifests and JSON scenarios

**Decision:** Products use validated YAML manifests and JSON scenario documents. Scenario JSON Schemas are validated while loading and values are validated at create, update, preview, send, scheduled, and pull-generation boundaries.

## ADR-008: Serve the frontend from FastAPI

**Decision:** The production image builds the React application with `npm ci` and serves its static files and SPA fallback from FastAPI. API paths never fall through to the SPA.

## ADR-009: Repair the contract in `/api/v1`

**Decision:** The `0.2.0` repair corrects the existing `/api/v1` schemas in place and documents export format `2.0` as intentionally breaking. There is no compatibility `/api/v2`; format `1.0` imports are converted in memory.

## ADR-010: No AI runtime dependency

**Decision:** Payload generation is templates, schema validation, and deterministic plugins. The product has no LLM or cloud-AI dependency.

## ADR-011: Persist delivery attempts as primary evidence

**Decision:** Each retry is an individually addressable ordered attempt. Attempts store exact redacted request metadata, response/error data, latency, and protocol confirmation semantics. cURL selects a particular attempt.

## ADR-012: Python 3.12 and strict typed boundaries

**Decision:** Python 3.12, Pydantic v2, SQLAlchemy 2.x typing, Ruff, and strict mypy define backend quality. Node 20, strict TypeScript, ESLint, and lockfile builds define frontend quality.

## ADR-013: Repository/service persistence boundary

**Decision:** API routes remain thin. Services own validation and transactions; repositories own deterministic persistence ordering and cascade-aware deletion.

## ADR-014: Sandboxed Jinja templates

**Decision:** Scenario templates use Jinja `SandboxedEnvironment` with strict undefined values and a limited helper/context set. Plugins receive an injected random generator rather than module-global randomness.

## ADR-015: HTTP delivery semantics

**Decision:** `httpx` performs GET/POST/PUT/HEAD with configurable redirects, timeout, and TLS verification. HTTP 2xx after a response is success; network and HTTP failures remain distinguishable.

## ADR-016: Preview and send are separate operator actions

**Decision:** Preview generates without delivery. Sending a preview carries the selected scenario ID and exact previewed payload unless the operator explicitly regenerates. Canonical templates are never mutated.

## ADR-017: In-process scheduler with bounded execution

**Decision:** APScheduler owns continuous and finite push jobs with one active instance and coalescing. Manual sends and pull activations do not create interval jobs. Configurable interval, count, burst, and concurrency limits bound work.

## ADR-018: Fortinet remains a product module

**Decision:** FortiGate KVP scenarios, field assumptions, and enrichment remain under `products/fortinet/`. Raw Syslog transport is generic. Simulator correlation fields are troubleshooting-only.

## ADR-019: Pull APIs use generic manifest routes

**Decision:** Product manifests declare mock routes served under `/api/v1/mock/{product_id}/{path}`. Inbound auth, response generation, faults, and auditing are generic services; unmatched calls are audited globally.

## ADR-020: OAuth is a constrained simulator

**Decision:** Support only the client-credentials grant required for collector testing. Client secrets are encrypted, access tokens are stored only as hashes, token responses prohibit caching, and history uses an independent token-record ID instead of a token prefix.

## ADR-021: Structured secure destination values

**Decision:** Custom headers and query parameters are ordered `{name, value, sensitive}` entries, sensitive by default. Authorization, cookie, password, token, key, signature and secret-like names are always sensitive. Hidden values survive an edit only while their entry remains; omission from a full destination update deletes the value. Starting in 0.4.5, full HTTP webhook URLs are accepted as input: inline query strings are extracted into sensitive entries before testing or encrypted persistence. Stored destination URLs contain no query strings. URL fragments remain unsupported for saved destinations.

## ADR-022: Per-scenario override maps

**Decision:** Overrides are keyed by selected scenario ID. Unknown scenarios, unselected scenarios, unknown properties, and invalid values are rejected. Legacy flat values are mapped when recognized; invalid or unknown data is encrypted and quarantined as inactive migration information.

## ADR-023: Materialized finite pull datasets

**Decision:** Starting pull mode materializes a finite dataset for every route from a single activation anchor. Items persist route, scenario, sequence, generated time, and payload. Cursor tokens bind activation, route, and next sequence. Stop/start makes a new activation; safe process resume keeps the current one.

## ADR-024: Default stop and safe opt-in resume

**Decision:** Restart defaults to marking running records stopped/interrupted. Opt-in resume starts the scheduler paused, validates state and limits, restores eligible jobs without catch-up, retains pull activations, resumes finite progress, and marks unsafe records `error` with a recovery message.

## ADR-025: Localhost-default deployment

**Decision:** Default Compose publishes only `127.0.0.1:8080`. Remote collectors must use the provided TLS/basic-auth gateway profile or an authenticated tunnel with network controls. The application retains its trusted-user model and does not add login/RBAC in this release.

## ADR-026: Declarative vendor workflows with an optional shaping contract

**Decision:** Manifests declare non-secret option schemas, route handlers, response profiles, actions,
and delivery policies. A separate optional workflow protocol handles the small amount of vendor
validation and response shaping that cannot be expressed declaratively. Core services dispatch by
manifest capabilities and never compare a vendor ID.

## ADR-027: Additive 2.1 export without a configuration conversion

**Decision:** Sophos and Okta introduce additive `vendor_options` and `api_key_prefix` fields. New
exports therefore use format `2.1`, while imports retain `1.0` and `2.0`. Existing persisted records
need no semantic conversion, so internal configuration version remains 3; Alembic revision 009 only
adds nullable workflow-action metadata to event history.
