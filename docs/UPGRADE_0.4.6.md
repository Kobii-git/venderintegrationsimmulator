# Upgrade to 0.4.6

Cloudflare and Mimecast are available in Generate raw log, saved simulations and Log Lab. The container also bundles the searchable Deployment Guides library at `/guides`: 90 guides cover 33 security vendors, three demo products and uploaded logs. Each includes production and simulator procedures, method support labels, licensing/network/credential context, samples, KQL, troubleshooting, maintenance, rollback and reviewed official references. Markdown reading is offline; reference links need internet access. Commands are copied explicitly and are never executed by the application.

## Cloudflare

Nine scenarios cover HTTP requests, WAF block/challenge, DNS, Access, Gateway DNS/HTTP/network and audit. Raw generation/downloads remain readable JSON. Choose **cloudflare_logpush** for native HTTP Logpush: POST gzip-compressed NDJSON with configurable encrypted headers and query values. Queued records are grouped into bounded uploads; encoding permits 1–1000 records with a 950000-byte uncompressed cap. Normal queue claims group at most 20 records. Wire preview returns gzip bytes as base64, compression metadata and record count. **Validate Logpush destination** sends the compressed `test.txt.gz` validation object.

Generic HTTP/Azure delivery remains available separately. For new real Sentinel collection use the documented Cloudflare Azure Blob/CCF route; the older Function connector is a migration path. The guides cover the other documented Logpush destinations and legacy Logpull. Storage transports and Logpull emulation are excluded.

## Mimecast

Nine scenarios cover receipt, delivery, rejection, bounce, URL/attachment/impersonation protection, DLP and audit. Choose **Pull API**, the API 2.0 profile and lab OAuth client credentials. Start the simulation to materialize its persistent datasets, obtain a token at the displayed OAuth URL, then use SIEM batch discovery, signed gzip downloads and `@nextPage`. Audit/protection POST routes accept their vendor-specific request bodies and return the current envelopes. Audit returns records directly in `data`; DLP uses `data[0].dlpLogs`.

Pages are capped at 100. Downloads are capped at 950000 uncompressed bytes; links expire after 900 seconds by default, configurable 60–3600 seconds. Links are signed and scoped to simulation and dataset activation. Repeat downloads are stable and remain valid after ordinary container recreation with the same `/data` and encryption key. Starting a new materialization invalidates links to the old activation; deleting the simulation removes its dataset. Download and OAuth tokens are redacted in history. API 1.0 four-key signing is documented for migration only.

## Deployment guide API

- `GET /api/v1/guides` returns metadata; optional filters: `product_id`, `method`, `destination`, `q`.
- `GET /api/v1/guides/{product_id}/{method_id}` returns metadata and Markdown content.

The UI offers vendor/method/destination filters, search, contents links, command copying, printing and Markdown download. Links from simulation and raw-log forms select the appropriate vendor. Executable HTML and unsafe URL schemes are disabled in Markdown.

## Data and server update

No database schema migration is added. Preserve the existing named volume and encryption key; encrypted callback URLs, credentials and datasets remain compatible. Keep any externally supplied `SECRET_KEY` unchanged if your deployment uses one.

For the existing server's standalone Docker configuration:

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

Check the version/readiness endpoints and open Deployment Guides. To roll back, stop/remove this container and run the previous tested image with the same volume/key. Do not delete the volume during an update.

## Verification scope

Local backend/frontend, fixture, OAuth, checkpoint, link expiry/repeat/scope, malformed requests, empty/rate-limit responses, gzip/NDJSON batches, redaction, guide coverage/internal links, browser navigation and Docker persistence checks are included. Migration/rollback and existing vendor workflows remain covered. CI builds and tests AMD64/ARM64 separately before publishing version, commit and latest tags. Live vendor endpoints, licensed connector deployment, parser fidelity and final Sentinel table acceptance require their own environment checks; local Docker acceptance is a separate result.
