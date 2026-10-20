# Release 0.6.0 — Modern console tools and monitoring

The second Modern console phase improves Log Lab, uploads, raw log generation
and delivery monitoring. API and storage contracts remain compatible; no database
migration or encryption-key change is required.

## What changes

- **Log Lab:** numbered Source, Devices, Collectors, Traffic and Replay sections,
  section links, a live configuration summary and a persistent save action.
  Advanced event identities, incident weights, routing, queues and TLS controls
  remain available in expandable sections. Saving configuration sends nothing.
  Dataset deletion requires confirmation; changing replay options clears stale
  previews.
- **Upload logs:** four steps — Upload & validate, Destination, Review & send,
  Progress. Select the parser before uploading, inspect the validated records,
  review pacing and destination, then explicitly send. Back retains entries in
  memory. Reloading or leaving discards unsaved entries. Reviews hide credentials
  and URL query values. Records are validated again immediately before creation.
  A failed Start retains the saved upload and retries that run; queued records
  must drain before starting another upload. Counts distinguish generated,
  queued, Azure-accepted and failed records.
- **Raw logs:** searchable products, grouped controls, customization on demand
  and a dedicated output panel with line/byte counts, copy and exact downloads.
  Generated output receives focus; changing inputs clears stale output. This
  tool only generates a sample and never delivers it.
- **Monitoring:** Overview, Deliveries/Requests and Connection views; pause/resume
  updates, refresh explicitly, clear filters, and open a delivery with the keyboard.
  Status remains visible for Syslog without an HTTP status; stored UTC timestamps
  display consistently in local time. Advanced burst actions
  remain available with input limits. Late responses cannot overwrite newer filters.
- **Delivery evidence:** clear selected-attempt outcome, attempt selection and
  Summary, Request & response, Event payload tabs. Replay controls explain that
  they send events. Replay leaves the original evidence open and links to the
  new delivery. Clipboard failures give actionable feedback.
- Consistent console colors, readable fields, responsive tables and layouts.
  Pages load on demand, reducing the initial JavaScript bundle.

## Installation and update

Follow [installation and updates](INSTALLATION.md). Keep the existing persistent
volume and encryption key. To pin this release, use:

```text
ghcr.io/kobii-git/venderintegrationsimmulator:0.6.0
```

`latest` follows the tested main publication. Check the matching
[verification workflow](https://github.com/Kobii-git/venderintegrationsimmulator/actions/workflows/verify.yml)
for publication and native AMD64/ARM64 pulled-image checks.

## Compatibility and rollback

Saved simulations, datasets, collector configurations, authentication, replay,
wire evidence and export/import keep their existing contracts. No new migration
is introduced. Stop running simulations before editing their configuration.

Back up the complete data volume before updating, including its encryption key.
To roll back, use the previously published `0.5.0` image with the same volume.
Verify that image is available before replacing a working container.

## Verification scope

Checks include frontend lint/types/component tests and production build,
real-backend browser workflows, backend and relay regressions, migration/rollback,
dependency audits, production protocol/persistence tests, and published native
AMD64/ARM64 pulled-image startup/UI/API/persistence tests. Browser checks cover
320px, 390px, 768px and 1280px layouts, keyboard tabs, paused updates, stale
responses, upload validation/recovery and exact raw downloads.

Transport or API acceptance does not establish downstream table arrival,
Microsoft Sentinel acceptance, or compatibility with installed vendor parsers.
Those remain separate operator acceptance checks.
