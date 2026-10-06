# Security Model

## Trust boundary

Integration Simulator `0.3.0` is an internal administrative engineering tool for trusted users. It has no application login, RBAC, tenancy boundary, or destination allowlist. Anyone who can reach its UI/API can configure outbound traffic and operate simulations.

Default Docker Compose binds only to `127.0.0.1:8080`. Do not publish that service directly to an untrusted network. Use the protected gateway/tunnel procedure in [PUBLIC_EXPOSURE.md](PUBLIC_EXPOSURE.md) when a remote collector must connect.

## Secret storage and rendering

- Passwords, bearer/API-key values, OAuth client secrets, and sensitive destination headers/query entries are encrypted with Fernet in SQLite.
- The key comes from `SECRET_KEY`, or is generated once at `/data/.secret_key` with mode `0600`. The generated-key option is stable only while that file is retained with the data volume and backup.
- Sensitive destination names are enforced case-insensitively for headers and include authorization, cookie, password, token, key, and secret patterns. Query names retain case-sensitive identity while sensitivity rules still protect recognized secret names.
- HTTP destination URLs may not contain username/password user-info. Configure credentials through the separate authentication fields; this prevents credentials from entering URL validation messages, logs, or exported destination data.
- Decryption occurs only immediately before applying authentication or invoking a transport.
- Read APIs and the UI return `has_value`/credential markers. Sensitive values are never returned.
- Default export keeps configuration shape, non-secret identifiers, secret field names, and markers but no values. A secret export requires both `include_secrets=true` and `confirm_secret_export=true`; its response must be handled as a secret document.
- Importing a sanitized export produces a stopped simulation with `missing_secrets`; start/send is blocked until required values are replaced.
- Vendor options are explicitly non-secret, validated against the selected product schema, and rejected when a manifest defines secret-like option names.
- Issued Sophos/Okta OAuth access tokens are stored only as hashes. Token and client-secret values are redacted from token audit bodies and all inbound evidence.

## Evidence guarantees

Before delivery, the HTTP engine collects exact secret values from outbound authentication and sensitive request headers/query parameters. It removes those values from destination evidence, request bodies, response headers (including `Cookie` and `Set-Cookie`), response bodies, and transport error messages on success and failure. One-shot scenario responses receive the same treatment while the unmodified payload is delivered to the receiver. The persistence layer repeats redaction as defense in depth.

Request URLs retain scheme, host, non-default port, path, and redacted query values. Logs, destination summaries, history, API reads, default exports, generated cURL, and validation errors use redacted representations; validation responses do not echo rejected input values.

The automated secret-canary suites place canaries in auth passwords/tokens, OAuth secrets, Authorization/custom headers, URL/query data, inbound auth, and bodies. Backend tests and the production-image workflow fail if those canaries appear in database configuration/history, container logs, read APIs, default exports, or cURL. These checks are the release guarantee; they do not make a confirmed-secret export safe to disclose.

Production and development dependency sets are audited independently. Any development-only exception must be documented with scope, owner, and expiry in [SECURITY_WAIVERS.md](SECURITY_WAIVERS.md); production audits have no ignored advisories.

## OAuth

The token endpoint is a test-only client-credentials simulator, not an identity provider. Client secrets are encrypted. Issued access tokens are returned once, stored only as SHA-256 hashes, and represented in history by independent random token-record IDs. Token responses, including errors, return `Cache-Control: no-store` and `Pragma: no-cache`.

## Network and protocol limits

- Arbitrary outbound destinations are intentional, including private and loopback addresses. Private-target warnings are advisory; SSRF prevention would conflict with the internal collector use case.
- UDP is best effort. A successful local send does not verify receiver delivery or acknowledgement.
- TCP/TLS success confirms connection and write only, not downstream application processing.
- Disable TLS verification only against deliberate test receivers. The production black-box suite exercises both trusted/untrusted test certificate paths.
- The Caddy protected profile uses an internally issued TLS certificate and HTTP Basic authentication. Restrict its source addresses at the host/cloud firewall and distribute the local CA only to intended clients.

## Upgrade safety

Configuration version 3 adds URL credential remediation on top of the existing version 1 to 2 structured-secret conversion. Before any conversion, startup proves that every candidate and encryption key is valid. Complete URL credentials are either stripped in favour of explicit Basic authentication or migrated into encrypted Basic authentication when the selected product supports it. Incomplete, unsupported, or conflicting credentials stop startup and report only the affected simulation IDs.

After successful preflight, startup creates the existing timestamped SQLite backup with the SQLite backup API and commits conversions. If preflight or backup creation fails, the source database is not modified. Backups and `/data/.secret_key` are security-sensitive and require the same access controls as the live database.

## Deliberate limitations

Built-in login/RBAC, multi-tenancy, destination allowlists, outbound mTLS client authentication, external secret managers, and distributed audit infrastructure are deferred. Localhost binding and external network/authentication controls are required compensating boundaries for this release.
