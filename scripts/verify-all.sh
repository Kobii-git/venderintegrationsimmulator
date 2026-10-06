#!/usr/bin/env sh
set -eu

"$(dirname "$0")/verify-backend.sh"
"$(dirname "$0")/verify-migrations.sh"
"$(dirname "$0")/verify-frontend.sh"
"$(dirname "$0")/verify-browser.sh"
"$(dirname "$0")/verify-docker.sh"
docker build -f "$(dirname "$0")/../docker/Dockerfile" -t integration-simulator:0.4.0 "$(dirname "$0")/.."
"$(dirname "$0")/verify-standalone-image.sh"
