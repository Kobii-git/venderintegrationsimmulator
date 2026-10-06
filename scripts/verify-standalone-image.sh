#!/usr/bin/env sh
set -eu
image=${1:-integration-simulator:0.4.2}
root_dir=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
container="simulator-standalone-$$"
volume="$container-data"
cleanup() {
  docker rm -f "$container" >/dev/null 2>&1 || true
  docker volume rm "$volume" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM
# First run needs no Compose, environment file, volume or supporting service.
docker run -d --name "$container" -p 127.0.0.1::8080 "$image"
docker cp "$root_dir/tests/blackbox/standalone.py" "$container:/tmp/standalone.py"
docker exec "$container" python /tmp/standalone.py
docker rm -f "$container"
docker volume create "$volume" >/dev/null
docker run -d --name "$container" -p 127.0.0.1::8080 -v "$volume:/data" "$image"
docker cp "$root_dir/tests/blackbox/standalone.py" "$container:/tmp/standalone.py"
docker exec "$container" python /tmp/standalone.py create
docker rm -f "$container"
# Recreate to verify database, generated key and simulation persistence.
docker run -d --name "$container" -p 127.0.0.1::8080 -v "$volume:/data" "$image"
docker cp "$root_dir/tests/blackbox/standalone.py" "$container:/tmp/standalone.py"
docker exec "$container" python /tmp/standalone.py retained
echo "Standalone startup, UI, API and persistence verification passed"
