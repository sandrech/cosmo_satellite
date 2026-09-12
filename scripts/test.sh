#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
(cd "$ROOT/backend" && PYTHONPATH=src pytest -q)
(cd "$ROOT/frontend" && npm test && npm run build)
