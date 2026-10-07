# Docker log lab, release 0.4.0

The Log Lab screen includes 32 synthetic catalog source profiles to the existing simulator. FastAPI, React, SQLite, product plugins, polling mocks and the single application container remain in place. The source list is practical Sentinel coverage, not a market-share ranking. See [the catalog](../products/catalog.json) and each product's `SOURCE.md`, scenario templates and checked-in wire fixtures for versions, field references and event families.

## Deploy and create a lab

```sh
cp .env.example .env
docker compose up -d --build
curl -fsS http://127.0.0.1:8080/api/v1/ready
```

Open `http://localhost:8080/lab`. Search for a source, select event families, add devices, and add collectors. A device's hostname and IP appear in generated payloads; collector host/IP identifies the network destination. The container does not spoof source IP addresses or create network interfaces. Each simulation has one source profile; create several simulations for a mixed vendor environment.

Each collector has a stable ID, enabled flag, payload format, protocol, authentication, device/scenario filters, and queue capacity. You can send the same logical event to four different IPs using UDP, TCP, TLS and HTTP, or to the Azure ingestion API. Formats are selected independently per collector. Saved wire previews show UTF-8 bytes, framing and base64; generated timestamps change on subsequent events. Credentials are redacted from previews and history.

Set continuous or finite scheduling and `events_per_second` for rate generation. The running aggregate of rate-based schedules is limited to 100 logical events/second. Fan-out multiplies deliveries, not logical event count. Legacy interval schedules remain supported and cannot be combined with a rate. Manual send and the existing burst controls remain available. Weights adjust scenario selection; a seed makes selection repeatable. Incident presets provide password spray, privileged logon, firewall scanning and malware sequences. Choose event families appropriate to the preset. Devices rotate in a stable order; the configurable user pool uses seeded selection. Scenarios expose user/address overrides, and password spray supplies a default user sequence when the pool is empty.

Live views show cumulative event outcomes and collector statistics. An event is delivered only if all selected collectors succeed; mixed success is `partial`. UDP confirmation means local socket acceptance; TCP/TLS means transport acceptance; HTTP and Azure mean API acceptance. None independently proves a Sentinel table record exists.

## Persistent queues and recovery

Rate-based delivery uses persistent, bounded per-target queues and independent workers. Network waits occur outside SQLite write transactions. Connection reuse and batches reduce overhead. A collector outage does not stop workers for healthy collectors. A full queue creates a visible failed delivery job and attempt; it does not silently drop the logical event. Queue capacity defaults to 10,000 per collector and can be adjusted in the editor.

Stopping generation leaves queued deliveries to drain. Shutdown allows workers ten seconds to finish and resets interrupted active jobs to pending. Container stop grace is 30 seconds. Restart reclaims active jobs; delivery is **at least once**, so a process interruption after remote acceptance can produce duplicates. Automatic resumption of event generation remains opt-in with `SCHEDULER_RESUME_ON_RESTART=true`; durable pending delivery jobs are reclaimed independently. Retention excludes pending events and preserves cumulative counters after detailed history expires.

Use one replica and one Uvicorn worker. Preserve the complete `/data` volume: database, encryption key, uploaded datasets and upgrade backups. Exported replay configurations contain local dataset IDs; export does not bundle dataset files. Re-upload and remap a dataset before importing its replay configuration on another installation.

## Uploaded replay

Upload UTF-8 plain text, NDJSON, a JSON array of objects, or header-based CSV. The upload API accepts the raw request body:

```sh
curl -fsS -X POST 'http://localhost:8080/api/v1/datasets?name=sample.ndjson&format=ndjson' \
  -H 'Content-Type:application/x-ndjson' --data-binary @sample.ndjson
```

Files receive generated names under `/data/datasets`; supplied names are display metadata. The default upload cap is 100 MiB; individual records are capped at 1 MiB. Normalized storage also has a 100 MiB cap. Failed or interrupted uploads are cleaned up. Referenced datasets cannot be deleted until simulations stop using them.

Select fixed-rate or original-timing replay, one pass or looping, and optional timestamp rewriting. Original timing uses the first recognized ISO timestamp in each record, preserves nonnegative gaps and caps a gap at 3,600 seconds by default (`max_original_gap_seconds` is configurable through the API). Cursor and pending timing state are persisted. An explicit new start begins a new pass; restart recovery retains its cursor.

Preview reports recognized and unknown ISO timestamp fields. Rewriting changes only recognized named fields and leaves unknown fields intact. Plain text timestamps and timestamps inside arrays are not automatically rewritten. CSV quoting is regenerated only when rewriting; otherwise raw CSV rows and NDJSON records are preserved. Line delimiters are removed before transport framing. JSON array uploads preserve object values and use normalized JSON serialization. Synthetic source formats do not convert arbitrary uploaded logs into vendor formats; replay uses their stored content type. Azure's default format wraps replay data in the custom-table envelope.

## Formats and Sentinel

Windows/DC and Sysmon can emit event XML or mapped JSON entirely inside Docker. Genuine WEF/AMA Windows event collection still requires a Windows lab. Linux and appliances emit native syslog; CEF sources use shared header/extension escaping and vendor mappings. PAN-OS and Umbrella emit CSV rows without headers. Zscaler NSS output is configurable at the vendor: the supplied CSV/CEF fixtures define this simulator's feed layout, rather than all possible NSS configurations.

The original 30 profiles have 120 synthetic event-family scenarios and 168 format fixtures; Cloudflare and Mimecast add 18 scenarios and 18 JSON fixtures. existing Fortinet scenarios add traffic allow/deny coverage, and existing UpGuard, demonstrations, Okta and Sophos workflows remain available. Local checks validate fixture stability, XML structure, CSV column counts, JSON fields and CEF escaping. Complete acceptance against every external firmware-specific parser has **not** run. Use fixtures to verify the actual Sentinel parser you deploy.

Cloud JSON profiles test ingestion and analytics. They do not reproduce Microsoft's native Entra, Microsoft 365, Defender or Azure service connectors. Umbrella and AWS native S3 delivery is deferred. Okta and Sophos Central retain their existing polling APIs; other cloud profiles generate outbound records. See [Sentinel setup and smoke tests](SENTINEL_SMOKE_TEST.md).

## Packaging and verification

The image runs as UID 1000 on Python 3.12 and serves the compiled React UI. `/api/v1/health` is liveness; `/api/v1/ready` checks database, catalog and scheduler. `/api/v1/metrics` exposes process RSS and delivery-job counts behind the management gateway.

For collector certificates, mount a readable CA file into the container and enter its container path in the collector's CA field for Syslog/HTTP. Azure uses the system trust store or `SSL_CERT_FILE` for a mounted PEM bundle. Example Compose override:

```yaml
services:
  integration-simulator:
    volumes:
      - ./certificates:/certs:ro
    environment:
      SSL_CERT_FILE: /certs/ca-bundle.pem
```

Build a local native image with `docker compose build`. Build an OCI archive containing Linux amd64 and arm64 variants using `scripts/build-multiarch.sh`; Docker Buildx with suitable native builders or QEMU is required. The manual `Log lab deployment acceptance` GitHub workflow builds both architectures, saves the archive, and runs the sustained Linux test without publishing to a registry. The existing verification workflow also runs migrations, browser workflows, dependency audits and production-image checks.

For the 15-minute test on a Linux host with at least 2 vCPUs and 4 GiB RAM:

```sh
backend/.venv/bin/python scripts/benchmark-log-lab.py --prepare-ca --ca-dir /tmp/lab-certs
docker build -f docker/Dockerfile -t integration-simulator:0.4.0 .
docker run -d --name log-lab --network host --cpus=2 --memory=4g \
  -v /tmp/lab-certs:/certs:ro -v log-lab-data:/data integration-simulator:0.4.0
backend/.venv/bin/python scripts/benchmark-log-lab.py --duration 900 \
  --ca-dir /tmp/lab-certs --collector-ca-file /certs/ca.pem \
  --output /tmp/log-lab-benchmark.json
```

The receiver process and container must share the Linux host; host networking makes the four loopback receivers reachable. The script verifies captures, sequence IDs, missing/duplicate events, parsing errors, management latency and RSS. Record host details and retain the report. A shorter run is a diagnostic, not sustained acceptance. See [implementation and verification status](IMPLEMENTATION_STATUS.md).


## Azure uploads and relay (0.4.1)

Use **Upload logs** for a one-off file, or select **Uploaded logs** in Log Lab for
vendor-neutral timed/looping replay. Direct Azure ingestion uses the DCE endpoint,
DCR immutable ID, stream and client credentials. The **Azure Function App relay**
destination uses the function ingestion URL and encrypted key; routing is configured
in the relay app settings and the relay uses managed identity. Both transports use
the same payload rendering, validation, byte batching and acceptance semantics.

Choose `default` for the custom-table envelope or `json` for unchanged JSON/NDJSON
objects. Azure replay is preflighted before starting. Generated logs are validated
before each send. Authentication checks send no logs; **Send test record** explicitly
uploads a record. Replay completion waits for the delivery queue; an accepted API
request is not a table-arrival check. Stop prevents generation while queued delivery
may continue. See [relay deployment guide](../azure/function-relay/README.md) and
[0.4.1 upgrade notes](UPGRADE_0.4.1.md).

Deployment Guides at `/guides` cover every catalog profile plus UpGuard and utilities. Cloudflare native HTTP Logpush can be selected as a collector; Mimecast native API 2.0 pull is configured in the simulation form. See [0.4.6 notes](UPGRADE_0.4.6.md).
