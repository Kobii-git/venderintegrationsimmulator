# Release 0.4.7 — review fixes and deployment guides

Reviewed 7 October 2026. Source is maintained on `main` in
[the application repository](https://github.com/Kobii-git/venderintegrationsimmulator).

## Changes

[Finding-by-finding remediation and regression evidence](REVIEW_FIXES_0.4.7.md).

- OAuth request bodies are streamed with a 16 KiB ceiling and 64 submitted form
  fields/JSON properties. Invalid input receives an OAuth `400`; oversized input
  receives `413`. Both retain `Cache-Control: no-store` and `Pragma: no-cache`.
  Native mock POST requests retain their 1,000,000-byte ceiling. The gateway caps
  collector-facing requests at 1 MiB; the separate dataset upload limit stays
  100 MiB.
- HTTP receiver responses are streamed with independent 1 MiB encoded/decoded
  ceilings. Identity, gzip and deflate are supported. Unsupported, stacked or
  malformed encodings produce a controlled error. Redaction precedes history
  truncation. Azure token, ingestion and Function-health calls share these limits;
  the separately deployed Function relay closes excessive responses with a bounded
  `502` failure. Redeploy its updated source package to update an existing relay.
- Redirects retain the five-hop ceiling. Same-origin redirects work; HTTPS
  downgrades and credential-bearing cross-origin redirects are rejected before
  reaching the new destination. A receiver using an authenticated redirect to a
  different hostname must instead be configured with its final trusted URL.
  Uncredentialed cross-origin redirects still work. Redirect bodies are discarded.
- OAuth evidence masks sensitive query/body/header/metadata names and exact
  submitted/configured values, including duplicate query credentials and escaped
  echoes. Existing history is retained and is not rewritten. Rotate credentials
  that were exposed in older request evidence and apply normal history retention.
- Cloudflare and Azure delivery batches partition consecutive jobs by their full
  stored configuration. Old jobs keep their recorded URL, credentials, transport
  and format through stop/edit/restart. Newly queued jobs record subsecond creation
  times for FIFO ordering; existing jobs are not rewritten.
- Cloudflare and Mimecast show scenario-specific effective fields. Fixed outcomes
  are hidden/deprecated in metadata. Old configurations and imports continue
  accepting those properties, while emitted outcomes remain fixed.
- Mimecast protection/DLP requests now default to newest-first. Set
  `oldestFirst: true` for ascending order. Values must be booleans. Ordering happens
  before pagination, with stable sequence tie-breaking. New POST checkpoints bind
  normalized time filters and ordering. Changing that context requires restarting
  without `pageToken`. Pre-0.4.7 POST checkpoints also return `400` with restart
  instructions. SIEM CG checkpoints and still-valid signed downloads keep their
  existing behavior. Strict cursor validation rejects malformed/stale tokens and
  out-of-range offsets with vendor-appropriate errors.
- Delivery history explains `response_too_large`, `invalid_response` and
  `redirect_rejected`. Optional native paging options preserve existing plugin
  calls and defaults.
- All 90 offline articles cover 220 method-specific production/simulator
  walkthrough pairs, actual synthetic fixtures, operational verification and
  explicit current/legacy support. Each method records documentation status and
  separate simulator/production verification notes. The documentation gate checks
  inventories, samples/hashes, walkthrough anchors, internal links, references and
  actual simulator capabilities. It does not certify licensed vendor/parser or
  live Sentinel acceptance.
- Upload logs preserves a new dataset selection when the initial list response
  arrives late.

## Data compatibility and backup

There is **no database schema migration**, key rotation or new storage transport.
Keep the complete existing `/data` volume, including the database, uploaded and
materialized datasets, and `.secret_key`. If your installation supplies an explicit
`SECRET_KEY`, retain that same value. Normal container replacement preserves saved
simulations, encrypted target snapshots, queued jobs and unexpired Mimecast links.
Starting a new pull activation replaces its dataset as before; this differs from
ordinary container recreation.

Before replacing the deployed container, stop it and make an operator-owned backup
of the complete named volume. Keep that backup with its key in protected storage.
Do not remove the volume when removing the container. Rollback below uses the same
volume because this patch does not alter the schema.

## Server update

These commands match the existing `integration-simulator` name, port `8080` and
`integration-simulator-data` named volume. Run them on your server after publication
is verified. They are instructions; this update does not execute server deployment.

```bash
docker pull ghcr.io/kobii-git/venderintegrationsimmulator:0.4.7 &&
docker stop integration-simulator &&
docker rm integration-simulator &&
docker run -d \
  --name integration-simulator \
  --restart unless-stopped \
  -p 8080:8080 \
  -v integration-simulator-data:/data \
  ghcr.io/kobii-git/venderintegrationsimmulator:0.4.7
```

Confirm startup and inspect the installed version:

```bash
docker logs --tail 80 integration-simulator
curl --fail http://127.0.0.1:8080/api/v1/health
```

Open `/guides` and `/raw-logs`, check saved simulations and send one authorized lab
record to its intended destination. Receiver acknowledgment and live Sentinel
arrival are separate checks.

## Rollback to 0.4.6

```bash
docker pull ghcr.io/kobii-git/venderintegrationsimmulator:0.4.6 &&
docker stop integration-simulator &&
docker rm integration-simulator &&
docker run -d \
  --name integration-simulator \
  --restart unless-stopped \
  -p 8080:8080 \
  -v integration-simulator-data:/data \
  ghcr.io/kobii-git/venderintegrationsimmulator:0.4.6
```

Rollback restores the earlier HTTP boundaries and Mimecast default order. Stop
collectors first and restart POST pagination without a saved checkpoint when
switching versions. Preserve the CG dataset and download expiry; do not start a
new pull activation merely to test a retained link.

## Verification

Local verification and publication evidence are recorded in
[Implementation status](IMPLEMENTATION_STATUS.md). The release requires backend,
frontend, migration/rollback, relay, browser, dependency and production-image checks,
then native AMD64/ARM64 publication and a pulled-image recreation check. Live cloud
resources, licensed vendor parsers and Sentinel ingestion remain external
acceptance checks; this release provisions none automatically.
