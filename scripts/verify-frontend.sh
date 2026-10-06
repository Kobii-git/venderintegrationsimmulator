#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")/../frontend"
npm ci
npm run lint
npm run typecheck
npm test
npm audit --audit-level=high
npm run build
