# Capability Ledger and Roadmap

This ledger records the implemented `0.3.0` platform and deliberately separates future product work
from release blockers.

## Completed platform capabilities

| Capability | Implemented evidence |
|---|---|
| Product system | Validated manifests and scenarios, JSON Schema controls, generic delivery policies, optional payload and workflow plugin contracts |
| HTTP and Syslog push | Structured secret values, Basic/bearer/API-key auth, HTTP policy controls, UDP/TCP/TLS and standard/raw framing |
| Runtime | Manual, continuous, finite, multi-scenario, transactional lifecycle, safe opt-in resume, duplicate/out-of-order/burst faults |
| Evidence | Redacted ordered attempts, response/error details, replay, cURL, global event search, action event metadata |
| Pull workflow engine | Materialized stable datasets, arrays/envelopes/static bodies, body or Link cursors, required headers, vendor errors and response headers |
| Inbound configuration | Schema-validated non-secret vendor options, API-key prefixes, Basic/bearer/API-key and scoped OAuth client credentials |
| Vendor actions | Manifest-defined methods/templates/policies/assertions through a generic simulation action API |
| Sophos Central | Token issuance, Who-am-I discovery, tenant enforcement, SIEM cursor/time/exclusion behavior, five event scenarios |
| Okta | SSWS/OAuth System Log, filters/order/polling Links, event-hook verification/envelope/retry policy, six scenarios |
| Secure portability | Encrypted credentials, centralized secret redaction, configuration version 3, export/import 1.0/2.0/2.1 |
| Persistence | Alembic through revision 009; workflow actions share event history using nullable action metadata |
| Operator UI | Split focused form sections/hooks, schema-rendered vendor options, endpoint copying, live action execution |
| Maintenance | HTTPX ASGI test transport, pytest 9/pytest-asyncio 1.4, no active security-audit waiver |
| Verification | Backend, migrations, frontend, browser, Docker, persistence, restart, canary and aggregate scripts |

## Post-0.3 roadmap

1. UpGuard HMAC signing, expanded Fortinet IPS/web-filter/application-control/SSL scenarios, and a
   generic CEF formatter.
2. Tenable asynchronous export jobs, status polling, binary chunk downloads, and expiry behavior.
3. Outbound OAuth2, mTLS client certificates, and destination allowlists.
4. Application login, RBAC, audit ownership, and multi-user deployment hardening.
5. PostgreSQL, distributed scheduling, scenario playlists, pause/resume, cron/jitter profiles, and
   stateful incident lifecycles.
6. Broader component and browser coverage for failure recovery, accessibility, and responsive UI.

These are new capabilities, not incomplete 0.3.0 implementation. Each needs its own threat model,
compatibility contract, and acceptance tests.
