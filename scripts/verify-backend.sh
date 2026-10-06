#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")/../backend"
python3 -m ruff check app tests
python3 -m ruff format --check app tests
python3 -m mypy app
python3 -m pytest -q
python3 -m pip_audit -r requirements.txt
python3 -m pip_audit -r requirements-dev.txt
