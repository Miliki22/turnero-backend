#!/usr/bin/env bash
set -euo pipefail

PYTHONPATH="." .venv/bin/alembic "$@"
