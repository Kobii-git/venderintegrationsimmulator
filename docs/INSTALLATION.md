# Installation and Update

## Install with Docker

Install and start Docker (Docker 24 or later). Then run:

```bash
docker run -d --name integration-simulator \
  --pull always --restart unless-stopped \
  -p 127.0.0.1:8080:8080 \
  -v integration-simulator-data:/data \
  ghcr.io/kobii-git/venderintegrationsimmulator:latest
```

Open **http://localhost:8080** on the Docker host.

That is the complete setup. The public image needs no registry login, source
clone, environment variables, environment file or separate database. It includes
the frontend, backend, vendor catalog and database migrations. Docker selects
Linux AMD64 or ARM64 automatically and creates the named data volume; the
application initializes its database and generates a persistent encryption key.
The container restarts automatically with Docker unless you stop it explicitly.

The default port is available on the Docker host only. For access from another
machine or remote collectors, see [protected remote exposure](#protected-remote-exposure).

## Update a Docker installation

For an installation started with the command above, keep a backup of the complete
`integration-simulator-data` volume, then run:

```bash
docker pull ghcr.io/kobii-git/venderintegrationsimmulator:latest &&
docker stop integration-simulator &&
docker rm integration-simulator &&
docker run -d --name integration-simulator --restart unless-stopped \
  -p 127.0.0.1:8080:8080 \
  -v integration-simulator-data:/data \
  ghcr.io/kobii-git/venderintegrationsimmulator:latest
```

This downloads the image before stopping the application, then replaces the
container. The same volume retains saved configuration, history, uploaded datasets
and the original encryption key. Database migrations run automatically at startup.
Pulling alone does not update a running container. If you previously customized
the port, volume or other settings, retain those settings when replacing it.

Confirm the application is ready and inspect the installed version:

```bash
curl --fail http://localhost:8080/api/v1/ready
```

## Compose: one command for installation and updates

Docker Compose v2 is required for this alternative. Save
[docker-compose.image.yml](../docker-compose.image.yml) in a dedicated folder.
You can download just that file without cloning the repository:

```bash
curl -fLO https://raw.githubusercontent.com/Kobii-git/venderintegrationsimmulator/main/docker-compose.image.yml
```

Run this from that folder for both the first installation and every update:

```bash
docker compose -f docker-compose.image.yml up -d --pull always
```

It pulls `latest` and creates or replaces the container as needed, retaining the
data volume. Open **http://localhost:8080**. No file edits or environment variables
are required. Keep a backup of the complete volume before upgrading.

Continue using the same folder and installation method. Compose prefixes its
volume name with the project name; it does not automatically reuse a volume from
`docker run`. Switching methods or folders requires explicitly reusing the original
volume to keep existing data.

## Image versions

`latest` is the default and follows successful, tested `main` builds. Each release
also publishes a version tag such as `0.5.0` and a `sha-<full commit>` tag. Source
release tags use `vX.Y.Z`; image version tags use `X.Y.Z`.

Version pinning is optional: replace `:latest` in the Docker commands with a
published version tag. For Compose, replace the image tag in your saved file with
that version. Retain that choice for both installation and updates.

## Optional: build from source

Published-image installation above does not require a build. To build your own:

```bash
git clone https://github.com/Kobii-git/venderintegrationsimmulator.git
cd venderintegrationsimmulator
docker compose up -d --build
```

No `.env` file or manually supplied secret is needed. The generated
`/data/.secret_key` stays in the data volume. If an existing deployment supplies
its own `SECRET_KEY`, retain that same value when updating.

## Persistent data and ownership

The named data volume is mounted at `/data` (`integration-simulator-data` for
`docker run`, or a project-prefixed name for Compose). The image runs as UID/GID `1000` and needs write access to that directory.

| Path | Purpose |
|---|---|
| `/data/integration_simulator.db` | SQLite configuration, history, pull data, and token records |
| `/data/.secret_key` | Generated encryption key when no environment key is supplied |
| `/data/backups/pre-config-v2-*.db` | Automatic pre-conversion database backups (name retained for compatibility) |

The default named volume needs no ownership setup. Only if you choose a host bind
mount instead, create the exact directory and set ownership before changing Compose:

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

Local development requires Python 3.12+ and Node.js 22.

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
curl -fsS http://localhost:8080/api/v1/ready
# Stop a Docker installation:
docker stop integration-simulator
# Or stop a Compose installation from its original folder:
docker compose -f docker-compose.image.yml down
```

Stopping the container or running Compose `down` retains the data volume.
