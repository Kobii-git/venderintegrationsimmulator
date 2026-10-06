# Implementation and verification, 4 October 2026

## Raw log generator, 6 October 2026 (0.4.4)

- Added **Generate raw log** without requiring a destination or saved simulation.
  Product/scenario selection, optional sample values and diagnostic mode produce
  a raw body that can be copied or downloaded. Setting changes invalidate old
  output and pending responses. Default formats share the existing source renderer;
  source logs omit transport and event-hook envelopes.
- Local verification: 303 backend tests, 16 frontend tests, lint/format/type
  checks, production frontend build, 10 migration checks and all 11 Chromium
  workflows passed together against the production image. Generation exercised
  149 scenarios across 35 products. Locked
  Python and npm dependency audits found no known vulnerabilities.
- The local ARM64 production image passed default startup, SPA/API generation,
  and database/encryption-key persistence after container recreation. A full Docker
  disk initially interrupted the persistence test; removing simulator intermediate
  frontend build caches restored space, and the complete check then passed.
- Existing preview/send contracts are preserved. No migration or dependency change.
  Real UpGuard type/schema fidelity and Logic App/Sentinel acceptance remain separate
  environment checks. See [upgrade and operator notes](UPGRADE_0.4.4.md).
- The 0.4.3 publication gate caught a browser assertion that compared mutable
  statistics from other active simulations. Version 0.4.4 checks the raw page's
  own write requests instead; backend tests independently verify that raw
  generation creates no simulation or delivery. No 0.4.3 image was published.

Release 0.4.0 implements the four planned stages in source. The deployment and external compatibility gates below remain open; this is not a claim of certified vendor-parser or live Sentinel compatibility.

## Delivered

| Stage | Source implementation |
|---|---|
| Baseline repairs | Final retry outcomes, persisted acceptance semantics, header/framing validation, bounded TCP operations and cancellation cleanup, collector-specific pacing, readiness, compatible vendor auth gateway paths, patched development locks. |
| Collectors and formats | Stable independent targets, encrypted credentials, primary-target legacy compatibility, simulated devices, filters, logical event generation once with per-target rendering, partial outcomes, shared CEF/XML/JSON/CSV and Syslog framing, wire previews. |
| API, rates and replay | Azure OAuth/refresh/byte batches/204/throttling, default custom-table envelope and explicit built-in mappings, rate schedules/weights/user pools/incident presets, durable bounded workers with batched writes, upload/preview/delete and fixed/original/looping replay. |
| Catalog and deployment | 30 source profiles, 120 synthetic family scenarios plus retained legacy scenarios, 168 fixtures, cited versions/references/compatibility labels, Log Lab editor, per-collector live statistics, Alembic 010, export 3.0 with old imports, non-root persistent container configuration and multiarch build/acceptance workflow. |

The application retains UpGuard and demonstration products, existing vendor plugins, fault injection and the Okta/Sophos polling workflows. Genuine Windows AMA/WEF and native cloud/S3 connectors require the external environments described in the operator guide.

## Verified locally

- Fresh hashed backend installation passes `pip check` and contains one pytest-asyncio distribution (the original installation had duplicate metadata). The original virtual environment is retained as `backend/.venv.before-log-lab`.
- Full backend suite: **271 tests passed**, including migrations, legacy credential canaries, retry outcomes, per-target partial delivery, upload parsing/replay, original timing, queue overflow/outage isolation and restart, OAuth refresh/throttling/batching, real UDP/TCP/TLS/HTTP captures, certificate rejection, slow writes and cancellation.
- Backend Ruff lint/format and mypy checks passed. The full suite was rerun after final-response filters, migration path handling and connection-test cleanup changes.
- Clean frontend installation: type checking, lint, **12 unit tests**, production build and **7 Chromium browser workflows** passed. Browser workflows cover the new multi-collector lab/replay editor and retained UpGuard, Fortinet, OAuth, Sophos and Okta behavior.
- Production and development Python dependency audits and the complete npm audit found **zero known vulnerabilities** in the locked dependencies at verification time.
- Catalog/fixture regeneration is idempotent. Fixtures are tested for stable representative output and structural checks; external vendor-specific parser acceptance is not implied.
- Docker Compose configuration and build script syntax validated without a daemon.

[One-minute local diagnostic](verification/macos-fanout-60s.json): 6,040 logical events; all four independent UDP, TCP, TLS and HTTP receivers captured 6,040 unique records each. No missing events, duplicates or parse errors. Measured rate 99.72 EPS over 60.568 seconds; management P95 198.57 ms; peak process RSS 131.17 MiB. The host was macOS ARM64, so this does **not** satisfy the planned 15-minute Linux acceptance gate.

## Open verification gates

1. Run the 900-second benchmark on a documented Linux host with at least 2 vCPUs and 4 GiB RAM. The manual CI workflow runs a container constrained to those resources and saves receiver/memory/latency evidence.
2. Run the [Sentinel smoke test](SENTINEL_SMOKE_TEST.md) against a configured workspace, DCR and credentials. Validate table arrival and parsed fields. API acceptance is distinct from this gate.
3. Validate all advertised fixtures against the actual installed vendor/Sentinel parsers. Firmware-specific optional/trailing fields, cloud native connector schemas and configurable NSS layouts require environment-specific acceptance.

## Docker publication verified, 6 October 2026

[The publication workflow](https://github.com/Kobii-git/venderintegrationsimmulator/actions/runs/37515547469)
passed backend/frontend, migrations, seven Chromium workflows and production-image integration checks.
Native Linux AMD64 and ARM64 runners built, pushed, pulled and tested their images before
publishing the combined `0.4.0`, `latest` and commit-tagged manifest. Both variants passed
default startup, UI/API readiness and database/key persistence after container recreation.
An anonymous pull of the public `0.4.0` image and the same standalone checks also passed
on the local ARM64 Docker host. Published multi-platform digest:
`sha256:613e5471e856ac1ebbca09fcf794daba949bd6b6d7654a26ca04dbc1ccb2a358`.

## Recovery baseline

The authoritative application repository is now https://github.com/Kobii-git/venderintegrationsimmulator.
Version 0.4.4 source, deployment configuration and verification scripts are maintained on `main`.
Future updates increment the application version and publish versioned and commit-tagged images.

## HTTP LAN browser fix, 6 October 2026 (0.4.2)

- Fixed the blank Log Lab page on HTTP LAN addresses where browsers omit
  `crypto.randomUUID()`. Collector, device and Upload logs target identifiers now
  use native UUID generation when available, with a cryptographically random UUID
  v4 fallback through `crypto.getRandomValues()`.
- Reproduced the original render exception before applying the fix. All 13
  frontend tests, lint, type checking and the production build passed afterward.
  Three Chromium workflows passed against the production image, including Log Lab
  creation without `randomUUID` and Upload logs target creation without Azure calls.
  All 13 version/health and migration tests passed.
- No database migrations, authentication changes or log-payload changes. Azure
  and Sentinel acceptance remain separate environment checks. See the
  [0.4.2 upgrade notes](UPGRADE_0.4.2.md).

A private source archive was captured before implementation at `/private/tmp/vendor-simulator-before-implementation-20261004.tgz`. No application database was present in the initial workspace. Keep an operator-owned copy before upgrading a deployed instance: `/private/tmp` is temporary. Startup captures a preflight SQLite backup before schema/configuration upgrades; restore the database together with its encryption key for rollback. See [upgrade notes](UPGRADE_0.4.0.md).


## Azure uploads and Function App relay, 6 October 2026 (0.4.1)

- Added one-off **Upload logs**, a generic uploaded-log source and the Function App
  relay transport in Log Lab. Full-file preflight, wire preview and delivery share
  timestamp/payload rendering; finite/EOF replay waits for its queue to drain.
- Added synchronous, function-key protected Python 3.12 relay code, hashed runtime
  dependencies, Flex Consumption Bicep, scoped managed identity access, packaging
  and manual deployment instructions. Local parameter/dependency outputs are ignored.
- Local verification passed the full 293-test backend suite, plus the final legacy
  batch-size compatibility regression and targeted upload/migration checks; 21 relay
  tests, 12 frontend tests, eight Chromium workflows, lint/type/build checks, Bicep
  compilation and source packaging. Locked dependency audits found no known vulnerabilities.
- Docker black-box upgrade/protocol/persistence checks and fresh standalone startup,
  UI/API readiness and database/key persistence passed on the local ARM64 host.
- CI now gates image publication on relay tests, dependency audit, packaging and Bicep
  compilation as well as existing application checks. Native AMD64/ARM64 images are
  pulled and tested before version/latest/commit manifests are published.
- Azure deployment, actual managed identity role propagation and destination-table
  arrival remain unverified live; no Azure resources were created in this update.
  See [relay deployment guide](../azure/function-relay/README.md) and
  [upgrade notes](UPGRADE_0.4.1.md). GitHub Release/source tags remain pending separate approval.
