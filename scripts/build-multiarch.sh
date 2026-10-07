#!/usr/bin/env sh
set -eu
root_dir=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
output=${1:-"$root_dir/integration-simulator-0.4.7.oci.tar"}
docker buildx build --platform linux/amd64,linux/arm64 \
  --file "$root_dir/docker/Dockerfile" --tag integration-simulator:0.4.7 \
  --output "type=oci,dest=$output" "$root_dir"
echo "Saved multi-platform OCI image: $output"
