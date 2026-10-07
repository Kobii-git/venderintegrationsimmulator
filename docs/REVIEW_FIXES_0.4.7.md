# Review remediation record — 0.4.7

Review date: 7 October 2026. These changes address the nine findings against the
0.4.6 baseline. They require no database schema migration or key replacement.

| Finding | Correction | Regression evidence |
|---|---|---|
| Unbounded OAuth requests | Incremental 16 KiB reader, 64-field/property cap, controlled OAuth errors before credential authentication; native POST and collector gateway limits retained separately from uploads. | `test_oauth_inbound.py`, request-stream cases in `test_http_boundaries.py`; gateway configuration validation. |
| Unbounded receiver responses | Raw streaming with independent encoded/decoded budgets, bounded gzip/deflate decoding and early closure, shared by webhook/Logpush/Azure and standalone relay. | Plain/compressed boundary, concatenated gzip, malformed/stacked encoding and unread-tail tests; all four Azure HTTP paths; relay closure tests. |
| Batching used the wrong stored configuration | Consecutive full-snapshot groups preserve their recorded destination, credentials, format and transport. New queue creation times have subsecond precision for FIFO; old rows remain unchanged. | A/A/B/C/A partition test; persisted stop/edit/backlog/recovery with Cloudflare→HTTP and Azure→Function changes, six successful jobs and distinct credential/destination captures. |
| Ineffective Cloudflare/Mimecast controls | Per-scenario visible fields; literal outcomes; ineffective legacy fields marked hidden/deprecated while stored/imported values remain accepted. | Every visible property changes its native record or documented Azure envelope; literal-outcome and legacy-override tests; raw/simulation browser checks. |
| Mimecast ignored ordering | Boolean `oldestFirst` determines order before slicing. New POST tokens bind normalized time/order; changed or context-less legacy POST tokens require a fresh query. CG paging/downloads remain compatible. | Both orders and full traversal for all four protection/DLP routes, default-order equivalence, strict booleans, changed filters and legacy POST restart tests. |
| Invalid cursors could cause server errors | Bounded strict base64/JSON object decoding, unique properties, finite values, matching activation/route and integer offset within actual stored route size. | Arrays/scalars/null, boolean/float/string offsets, stale route/activation, malformed base64/JSON, duplicate properties and oversized tokens; retained Okta/Sophos workflows. |
| OAuth evidence could expose credentials | Sensitive-name plus exact-value masking across query, submitted fields, headers and metadata before serialization/truncation. Duplicate query/JSON credentials and escaped echoes are collected. Headers of malformed/oversized bodies are masked when credentials cannot be safely extracted. | Successful/failed authentication, redundant query and JSON credentials, Basic escaped/Unicode values, database/detail canaries and retained token metadata. |
| Deployment guides were incomplete | All 90 articles and 220 inventory entries have distinct production/simulator procedures or explicit alternatives, real fixtures, current/legacy labels and method-level documentation/acceptance metadata. UpGuard REST/webhooks, Mimecast roles/apps and TLS listener procedures are expanded. | Offline gate verifies walkthrough anchors, inventories, JSON examples, fixture hashes, references, internal links and supported simulator routes. Browser filters/contents/copy/print/download and an isolated Ubuntu rsyslog certificate/listener/marker test pass. |
| Cross-origin redirects could leak custom credentials | Explicit five-hop redirects allow same origin, reject HTTPS downgrade and credential-bearing origin changes before sending, and discard redirect bodies. | Basic/Bearer/custom header/API-key/query credential rejection with no second-origin request; legitimate uncredentialed redirects, same-origin authentication/method handling and five/six-hop tests. |

## Compatibility and operational scope

Saved simulations, encrypted target snapshots, uploaded/materialized datasets and
unexpired signed Mimecast downloads retain the existing `/data` and key format.
Ordinary container recreation is covered by the standalone-image check. A new pull
activation still replaces its prior dataset as in earlier releases. Existing POST
checkpoints must restart, and protection/DLP defaults now sort newest-first.

Delivery history exposes controlled `response_too_large`, `invalid_response` and
`redirect_rejected` explanations. Optional native paging additions retain the
original positional plugin interface and defaults. Guide rendering remains
read-only, offline and excludes executable HTML or automatic command execution.
The Upload logs late-list race found by browser testing is also fixed.

Documentation completeness and local wire checks do not certify a licensed vendor,
installed parser, live Azure permissions or Sentinel table arrival. Production
verification metadata remains `not_run`. No cloud resources or deployed server are
changed automatically. Existing historical evidence is retained; rotate any
credentials exposed before this release and follow the history retention policy.

See [upgrade/update/rollback instructions](UPGRADE_0.4.7.md) and
[verification status](IMPLEMENTATION_STATUS.md) for release checks.
