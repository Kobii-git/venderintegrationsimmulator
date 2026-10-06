#!/usr/bin/env sh
set -eu

root_dir=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
project_name="integration-simulator-browser-$$"

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
  build
docker compose -p "$project_name" \
  -f "$root_dir/docker-compose.yml" \
  -f "$root_dir/docker-compose.test.yml" \
  up -d

cd "$root_dir/frontend"
npm ci
npx playwright install chromium
npm run test:e2e
echo "Browser workflow verification passed"
