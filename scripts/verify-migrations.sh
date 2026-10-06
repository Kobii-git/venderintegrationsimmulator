#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")/../backend"
python3 -m pytest -q tests/test_migrations.py
