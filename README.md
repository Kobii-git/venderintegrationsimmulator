# Integration Simulator

Self-hosted `0.4.8` tool for security engineers to **simulate**, **test**, and **troubleshoot** push, Syslog, and pull-based vendor integrations.

Generate realistic vendor payloads, deliver them to your webhook endpoint, inspect request/response details, replay events, inject faults, and validate ingestion pipelines — without needing the real UpGuard product.

## Install

With Docker installed and running, run this command:

```bash
docker run -d --name integration-simulator \
  --pull always --restart unless-stopped \
  -p 127.0.0.1:8080:8080 \
  -v integration-simulator-data:/data \
  ghcr.io/kobii-git/venderintegrationsimmulator:latest
```

Open **http://localhost:8080** on the Docker host. No registry login, source clone,
environment variables, environment file or separate database is required. Docker
pulls the complete application and creates the data volume automatically. The
application initializes its database and encryption key. AMD64 and ARM64 are supported.

## Update

For an installation started with the command above, pull the latest image and
replace the container using the same data volume:

```bash
docker pull ghcr.io/kobii-git/venderintegrationsimmulator:latest &&
docker stop integration-simulator &&
docker rm integration-simulator &&
docker run -d --name integration-simulator --restart unless-stopped \
  -p 127.0.0.1:8080:8080 \
  -v integration-simulator-data:/data \
  ghcr.io/kobii-git/venderintegrationsimmulator:latest
```

The volume preserves saved configuration, history, uploaded datasets and the
original encryption key. Keep a backup of the complete volume before upgrading.
Pulling alone does not update an existing container.

Prefer the same command for installation and updates? Save the standalone
[docker-compose.image.yml](docker-compose.image.yml) file in a folder, then run
this command from that folder each time:

```bash
docker compose -f docker-compose.image.yml up -d --pull always
```

No source checkout or file edits are required. Use the same installation method
for future updates; see [installation and updates](docs/INSTALLATION.md) for details.
`latest` follows tested `main` builds; version and commit tags are also published.

Release 0.4.8 simplifies installation and update instructions.
[Release notes](docs/UPGRADE_0.4.8.md).

## What it does

- Simulates UpGuard webhook scenarios (data leak, vulnerability, score changes, etc.)
- Simulates FortiGate syslog events (traffic, VPN, auth, system, UTM) via the generic syslog transport
- Exposes **pull-based mock REST APIs** so collectors can poll the simulator as a fake vendor API (`pull_api` mode)
- Simulates **OAuth2 client-credentials** token issuance for pull-based integrations (testing only)
- Simulates the Sophos Central token → Who-am-I → SIEM events collector workflow
- Simulates Okta System Log polling plus event-hook verification and delivery
- Sends outbound HTTP webhooks with configurable auth, headers, and query parameters
- Records delivery history with redacted credentials
- Supports continuous, finite, and manual send modes
- Provides troubleshooting: correlation ID search, cURL copy, replay, raw JSON override
- Supports controlled fault injection for edge-case testing

Release 0.4.7 bounds HTTP request/response handling, protects credentials across redirects, preserves queued configuration snapshots, corrects Mimecast ordering/checkpoints and expands all 90 deployment articles into 220 method walkthrough pairs. Generate readable raw logs, inspect native wire data and follow separate production/Sentinel and simulator walkthroughs. [Upgrade and server update notes](docs/UPGRADE_0.4.7.md).

## Generate raw logs

Open **Generate raw log** to choose a product and scenario, customize sample values,
and generate a raw body without a destination or saved simulation. Copy or download
the displayed JSON, native text or XML. The default **Vendor payload** mode omits
simulator diagnostics; **Include simulator diagnostics** enables them where supported.
Nothing is sent. UpGuard data leak, identity breach and vulnerability schemas are
inferred; validate them against real tenant samples.

Release 0.4.4 adds this generator. [Upgrade notes](docs/UPGRADE_0.4.4.md).

## Log Lab

Release 0.4.0 added 30 source profiles, device identities, independent collectors, Azure Logs Ingestion, rate scheduling and uploaded-log replay. Open **Log Lab** in the navigation to configure a simulation. See [the deployment/operator guide](docs/LOG_LAB.md), [Sentinel smoke test](docs/SENTINEL_SMOKE_TEST.md) and [implementation status](docs/IMPLEMENTATION_STATUS.md). Live Sentinel/parser compatibility requires verification in your environment.

Release 0.4.2 fixes Log Lab and Upload logs on HTTP LAN addresses by supporting UUID generation outside secure browser contexts. [Upgrade notes](docs/UPGRADE_0.4.2.md).

Release 0.4.1 adds **Upload logs** for one-off Azure ingestion and a **Function App → DCE** relay destination for one-off uploads and Log Lab replay. Validate every record, preview unchanged JSON or a custom-table envelope, and track acceptance/failures until delivery drains. [Relay code and deployment guide](azure/function-relay/README.md) · [Upgrade notes](docs/UPGRADE_0.4.1.md).

## Build from GitHub source

```bash
git clone https://github.com/Kobii-git/venderintegrationsimmulator.git
cd venderintegrationsimmulator
docker compose up -d --build
```

Open **http://localhost:8080**

Data persists in the `integration-simulator-data` Docker volume (`/data` inside the container).

## Development

### Backend (Python 3.12+)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
python3 -m pip install --require-hashes -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm ci
npm run dev
```

UI: http://localhost:5173 (proxies `/api` to backend)

### Tests

```bash
# From the repository root
scripts/verify-all.sh
# Standalone image startup and persistent data (after building the image)
scripts/verify-standalone-image.sh
```

## Documentation

| Document | Description |
|----------|-------------|
| [docs/INSTALLATION.md](docs/INSTALLATION.md) | Installation and deployment |
| [docs/UPGUARD.md](docs/UPGUARD.md) | UpGuard product module |
| [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) | Operator troubleshooting guide |
| [docs/FAULT_TESTING.md](docs/FAULT_TESTING.md) | Fault injection guide |
| [docs/EXPORT_IMPORT.md](docs/EXPORT_IMPORT.md) | Export/import format 3.0 and legacy conversion |
| [docs/SECURITY.md](docs/SECURITY.md) | Security model and trust boundaries |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System architecture |
| [docs/TRANSPORTS.md](docs/TRANSPORTS.md) | Transport layer (HTTP, Syslog, Azure ingestion) |
| [docs/INBOUND_MOCK_API.md](docs/INBOUND_MOCK_API.md) | Materialized pull-based mock REST API |
| [docs/OAUTH2_CLIENT_CREDENTIALS.md](docs/OAUTH2_CLIENT_CREDENTIALS.md) | OAuth2 client-credentials simulator |
| [docs/PUBLIC_EXPOSURE.md](docs/PUBLIC_EXPOSURE.md) | Exposing the simulator to cloud collectors |
| [docs/vendor/fortinet/README.md](docs/vendor/fortinet/README.md) | Fortinet FortiGate product module |
| [docs/vendor/sophos-central/README.md](docs/vendor/sophos-central/README.md) | Sophos Central workflow module |
| [docs/vendor/okta/README.md](docs/vendor/okta/README.md) | Okta System Log and event-hook module |
| [docs/ADDING_A_PRODUCT.md](docs/ADDING_A_PRODUCT.md) | Adding new vendor modules |
| [docs/RELEASE_CHECKLIST.md](docs/RELEASE_CHECKLIST.md) | Release verification checklist |
| [docs/UPGRADE_0.2.0.md](docs/UPGRADE_0.2.0.md) | Breaking changes, automatic upgrade, and rollback |
| [docs/UPGRADE_0.3.0.md](docs/UPGRADE_0.3.0.md) | Additive 0.3.0 configuration and database upgrade |

## Trust model

This is an **internal engineering tool**. It stores integration credentials, can send outbound traffic to arbitrary destinations, and has no application login/RBAC. Default Compose binds to localhost; use the documented protected gateway or tunnel for remote collectors and never expose it anonymously.

See [docs/SECURITY.md](docs/SECURITY.md) for full details.

## License

Proprietary — all rights reserved unless otherwise specified.
