# Installation and Upgrade

## Requirements

- Docker 24 or later with Docker Compose v2.
- For local development: Python 3.12 and Node.js 22.

## Pull and run the published image

If the registry package is private, authenticate Docker once using an account with access.
For the repository owner, the GitHub CLI flow is:

```bash
gh auth refresh --hostname github.com --scopes read:packages
gh auth token --hostname github.com | docker login ghcr.io --username Kobii-git --password-stdin
```

This uses the token through standard input. For another authorized account, replace the
username. Public packages need no registry login.

```bash
docker pull ghcr.io/kobii-git/venderintegrationsimmulator:0.4.0
docker run -d --name integration-simulator --restart unless-stopped \
  -p 127.0.0.1:8080:8080 -v integration-simulator-data:/data \
  ghcr.io/kobii-git/venderintegrationsimmulator:0.4.0
```

The image contains the frontend, backend, vendor catalog and database migrations.
It works with its defaults and automatically initializes its database and encryption key.
Open <http://localhost:8080>. No clone, source mounts, environment file or database service
is required. Linux AMD64 and ARM64 are supported. A Docker-compatible container runtime
is required to run the image.

Use `docker compose -f docker-compose.image.yml up -d` for the image-only Compose file.
It defaults to `latest`; prefix the command with `SIMULATOR_VERSION=0.4.0` to pin a version.
After choosing a new version, update with `docker compose -f docker-compose.image.yml pull`
then `docker compose -f docker-compose.image.yml up -d` (use the same version for both).

To update a container started directly, back up its data and key, pull the chosen tag,
then recreate it with the same volume and settings:

```bash
docker pull ghcr.io/kobii-git/venderintegrationsimmulator:latest
docker stop integration-simulator
docker rm integration-simulator
docker run -d --name integration-simulator --restart unless-stopped \
  -p 127.0.0.1:8080:8080 -v integration-simulator-data:/data \
  ghcr.io/kobii-git/venderintegrationsimmulator:latest
```

Releases use `vX.Y.Z` source tags and `X.Y.Z` image tags. Each successful push to `main`
also publishes an immutable `sha-<full commit>` image reference for reproducible runs.

## One-command Docker start

```bash
cp .env.example .env
docker compose up -d --build
```

Open <http://localhost:8080>. The default mapping is `127.0.0.1:8080:8080`; it is not reachable from other hosts.

`SECRET_KEY` may be set in `.env` using a stable random value:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

If it is omitted, the application generates `/data/.secret_key` once. This is also stable across container recreation because `/data` is a named volume. Back up and restore that file with the database. Supplying `SECRET_KEY` is preferable when deployment tooling already manages secrets; changing either key source makes existing encrypted values unreadable.

## Persistent data and ownership

The `integration-simulator-data` volume is mounted at `/data`. The image runs as UID/GID `1000` and needs write access to that directory.

| Path | Purpose |
|---|---|
| `/data/integration_simulator.db` | SQLite configuration, history, pull data, and token records |
| `/data/.secret_key` | Generated encryption key when no environment key is supplied |
| `/data/backups/pre-config-v2-*.db` | Automatic pre-conversion database backups (name retained for compatibility) |

For a host bind mount, create the exact directory and set ownership before changing Compose:

```bash
mkdir -p ./data
sudo chown 1000:1000 ./data
```

Do not run `docker compose down -v` unless deleting all persisted data is intended.

## Automatic database upgrade

On startup the application:

1. Locates simulations with `configuration_version` below 3.
2. Verifies every candidate, existing encrypted value, and encryption key before writing anything.
3. Creates a timestamped backup with the SQLite backup API under `/data/backups`.
4. Applies Alembic migrations through revision 009. Revision 009 adds nullable workflow-action
   metadata to event history and has a tested downgrade.
5. Preserves the version 1 to 2 conversion: encrypts legacy custom headers/query values, removes URL query strings, migrates inbound credentials, and converts scenario overrides.
6. Applies the version 2 to 3 URL remediation. Complete URL credentials are stripped when explicit Basic authentication exists, or migrated into encrypted Basic authentication when the selected product supports it.
7. Rejects incomplete URL credentials, products without Basic support, and conflicts with another authentication method before any database writes. The error identifies simulation IDs but never credential values.
8. Commits the validated conversions with `configuration_version=3`; unknown/invalid legacy overrides remain in encrypted inactive quarantine and non-secret migration warnings are stored in runtime metadata.
9. Starts recovery, retention, and scheduler work only after migration completes.

If validation, backup creation, or secret decryption fails, startup exits before changing the source database. Keep the container stopped and correct the identified configuration using the retained previous image, fix volume permissions, or restore the original key. Never edit encrypted fields directly.

## Rollback rehearsal

Release rollback should restore the pre-upgrade database and run the retained previous image:

```bash
docker compose stop integration-simulator
docker compose cp integration-simulator:/data/backups/pre-config-v2-YYYYMMDDTHHMMSSZ.db ./pre-config-v2.db
# Keep a second offline copy before replacing the live file.
docker compose run --rm --no-deps --user root \
  -v "$PWD/pre-config-v2.db:/restore.db:ro" \
  integration-simulator sh -c \
  'rm -f /data/integration_simulator.db-wal /data/integration_simulator.db-shm && cp /restore.db /data/integration_simulator.db && chown 1000:1000 /data/integration_simulator.db'
# Change the image/build reference to the retained 0.2.0 image, then start it.
docker compose up -d integration-simulator
```

When `SECRET_KEY` was not set, restore the matching `/data/.secret_key` as well. Never point a
0.2.0 image at a database still upgraded to revision 009. See [UPGRADE_0.3.0.md](UPGRADE_0.3.0.md).

## Retention and restart policy

Retention runs at startup and as one hourly maintenance job by default. Configure `EVENT_RETENTION_DAYS`, `EVENT_RETENTION_MAX_PER_SIMULATION`, and `EVENT_RETENTION_CLEANUP_INTERVAL_SECONDS`; the interval minimum is 60 seconds.

Running simulations stop as interrupted after a normal process restart. Set `SCHEDULER_RESUME_ON_RESTART=true` only when safe resume is wanted. Resume validates the persisted schedule, secrets, limits, progress, and pull activation before restarting work and never emits a catch-up burst.

## Protected remote exposure

The default service must stay localhost-bound. For a remote collector, follow [PUBLIC_EXPOSURE.md](PUBLIC_EXPOSURE.md), which provides a Compose TLS/basic-auth gateway profile and an SSH tunnel alternative.

## Local development

Backend production dependencies are separated from development tools and both lock files require hashes:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --require-hashes -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
```

Frontend installation must use the committed lockfile:

```bash
cd frontend
npm ci
npm run dev
```

Run all provider-neutral release checks from the repository root with `scripts/verify-all.sh`; it includes the dedicated migration suite between backend and frontend verification.

## Health and shutdown

```bash
curl -fsS http://localhost:8080/api/v1/health
docker compose down
```

`docker compose down` retains the data volume.
