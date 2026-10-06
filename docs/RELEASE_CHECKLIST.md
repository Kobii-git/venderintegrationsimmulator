# 0.4.0 release gates

See [implementation evidence](IMPLEMENTATION_STATUS.md). Source checks, 271 backend tests, 12 frontend tests and seven local Chromium workflows passed. Production/development lock audits report no known vulnerabilities.

- [ ] Build and run the production image and Linux amd64/arm64 variants.
- [ ] Run the 15-minute Linux 100-EPS/four-collector benchmark and retain its report.
- [ ] Run the configured Sentinel smoke test and inspect parsed fields.
- [ ] Validate advertised fixtures against installed vendor/Sentinel parser versions.
- [x] Initialize the owner-designated authoritative checkout for `Kobii-git/venderintegrationsimmulator` on `main`.
- [x] Build the local Linux ARM64 image and verify standalone startup, UI/API and persistence.
- [ ] Confirm the `main` publication workflow and pulled AMD64/ARM64 image checks.
- [ ] Publish only after applicable deployment gates pass.

The older checklist below records prior release work; its checked entries are historical and do not prove 0.4.0 image acceptance.

# 0.3.0 Release Checklist

Run from a clean authoritative checkout with Docker 24+, Compose v2, Python 3.12, and Node 20. Do not
publish while any required gate remains open.

## Release prerequisites

- [ ] The validated 0.2.0 code is in authoritative Git history and its release is published.
- [ ] A retained 0.2.0 image and matching rollback database/key are available.
- [ ] The 0.3.0 changes are transferred to an authoritative checkout without initializing history in
  the unversioned implementation folder.

## Automated gates

- [x] `scripts/verify-backend.sh`: Ruff, formatting, strict mypy, 213 pytest cases, and both audits.
- [x] `scripts/verify-migrations.sh`: 10 clean, legacy, failure-atomicity, backup, and revision 009
  upgrade/downgrade coverage.
- [x] `scripts/verify-frontend.sh`: ESLint, TypeScript, 12 Vitest cases, audit, and production build.
- [x] Six real-backend Chromium workflows, including Sophos and Okta operator flows.
- [x] Clean production image plus HTTP/Syslog/protocol/restart/persistence/migration/canary workflows.
- [x] `scripts/verify-all.sh` passes in the unversioned implementation folder.
- [ ] Repeat `scripts/verify-all.sh` from a clean authoritative checkout.
- [ ] GitHub Actions is green on Python 3.12 and Node 20.

## Compatibility and security

- [x] Unchanged pre-0.3 product manifests load.
- [x] Existing configuration-version-3 simulations start without conversion.
- [x] Export/import round trips cover formats 1.0, 2.0, and 2.1.
- [x] Revision 009 upgrades and downgrades without corrupting existing event history.
- [x] Vendor-option schemas reject invalid and secret-like configuration.
- [x] Authorization, client secrets, issued tokens, cookies, and sensitive structured values are absent
  from logs, database evidence, APIs, exports, errors, and cURL.

## Sophos Central workflow

- [x] Token -> Who-am-I -> first SIEM page -> cursor continuation passes against the real backend.
- [x] Invalid client, scope, bearer, tenant header, cursor, limit, and `from_date` are vendor-shaped.
- [x] Excluded types and the 24-hour filter behave deterministically.
- [x] All five scenarios validate against the shipped event shapes.

## Okta workflow

- [x] SSWS and OAuth System Log authentication pass.
- [x] Raw arrays, filters, ordering, bounded and continuous pagination, empty pages, and Link headers
  match the documented simulator contract.
- [x] Event-hook verification success/malformed/timeout/4xx/5xx cases pass.
- [x] Hook envelope, duplicate/out-of-order behavior, timeout, redirects, and retry policy pass.
- [x] All six scenarios work in their declared pull and push modes.

## UI and documentation

- [x] Split form components preserve preview staleness and existing payload behavior.
- [x] Schema-driven vendor options, endpoint copy controls, and action execution pass component tests.
- [x] Installation, upgrade, security, architecture, vendor, export, and release documents match the
  verified artifact.
- [x] Application, API, frontend, Compose image, and health response report `0.3.0`.

## Rollback and publication

- [ ] Restore the pre-upgrade database and key, start the retained 0.2.0 image, and verify old data.
- [ ] Tag and publish 0.3.0 only after every applicable item above is checked.
