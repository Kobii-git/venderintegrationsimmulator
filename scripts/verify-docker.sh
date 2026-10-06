#!/usr/bin/env sh
set -eu

root_dir=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
project_name="integration-simulator-ci-$$"

cleanup() {
  docker compose -p "$project_name" \
    -f "$root_dir/docker-compose.yml" \
    -f "$root_dir/docker-compose.test.yml" \
    down --volumes --remove-orphans --rmi local >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

docker compose -p "$project_name" \
  -f "$root_dir/docker-compose.yml" \
  -f "$root_dir/docker-compose.test.yml" \
  build --no-cache
docker compose -p "$project_name" \
  -f "$root_dir/docker-compose.yml" \
  -f "$root_dir/docker-compose.test.yml" \
  run --rm --no-deps integration-simulator \
  alembic upgrade 006_oauth2_client_credentials
docker compose -p "$project_name" \
  -f "$root_dir/docker-compose.yml" \
  -f "$root_dir/docker-compose.test.yml" \
  run --rm --no-deps \
  -v "$root_dir/tests/blackbox:/blackbox:ro" \
  integration-simulator python /blackbox/prepare_legacy.py
docker compose -p "$project_name" \
  -f "$root_dir/docker-compose.yml" \
  -f "$root_dir/docker-compose.test.yml" \
  up -d
python3 "$root_dir/tests/blackbox/workflow.py"

docker compose -p "$project_name" \
  -f "$root_dir/docker-compose.yml" \
  -f "$root_dir/docker-compose.test.yml" \
  exec -T integration-simulator python -c \
  "from pathlib import Path; db=Path('/data/integration_simulator.db'); backups=list(Path('/data/backups').glob('pre-config-v2-*.db')); raise SystemExit(not backups or b'upgrade-secret-canary' in db.read_bytes())"

if docker compose -p "$project_name" \
  -f "$root_dir/docker-compose.yml" \
  -f "$root_dir/docker-compose.test.yml" \
  logs integration-simulator | grep -F "blackbox-secret-canary" >/dev/null
then
  echo "secret canary found in production logs" >&2
  exit 1
fi

if docker compose -p "$project_name" \
  -f "$root_dir/docker-compose.yml" \
  -f "$root_dir/docker-compose.test.yml" \
  exec -T integration-simulator python -c \
  "from pathlib import Path; raise SystemExit(b'blackbox-secret-canary' in Path('/data/integration_simulator.db').read_bytes())"
then
  :
else
  echo "secret canary found in production database" >&2
  exit 1
fi

docker compose -p "$project_name" \
  -f "$root_dir/docker-compose.yml" \
  -f "$root_dir/docker-compose.test.yml" \
  restart integration-simulator
python3 "$root_dir/tests/blackbox/workflow.py"

docker compose -p "$project_name" \
  -f "$root_dir/docker-compose.yml" \
  -f "$root_dir/docker-compose.test.yml" \
  stop integration-simulator
docker compose -p "$project_name" \
  -f "$root_dir/docker-compose.yml" \
  -f "$root_dir/docker-compose.test.yml" \
  run --rm --no-deps \
  -v "$root_dir/tests/blackbox:/blackbox:ro" \
  integration-simulator python /blackbox/verify_rollback.py
echo "Production image verification passed"
