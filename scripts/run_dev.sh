#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_HOST="${COSMO_BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${COSMO_BACKEND_PORT:-8000}"
BACKEND_URL="http://${BACKEND_HOST}:${BACKEND_PORT}"
BACKEND_LOG="${TMPDIR:-/tmp}/cosmo-satellite-backend-${BACKEND_PORT}.log"
PYTHON_BIN="${PYTHON:-}"
BACKEND_PID=""
STARTED_BACKEND=0

if [[ -z "$PYTHON_BIN" ]]; then
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
  elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python)"
  else
    echo "[cosmo] Python 3.12+ не найден." >&2
    exit 1
  fi
fi

cleanup() {
  if [[ "$STARTED_BACKEND" == "1" && -n "$BACKEND_PID" ]]; then
    kill "$BACKEND_PID" 2>/dev/null || true
    wait "$BACKEND_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

health_ok() {
  curl --silent --fail --max-time 1 "$BACKEND_URL/api/health" >/dev/null 2>&1
}

if health_ok; then
  echo "[cosmo] Backend уже работает: $BACKEND_URL"
else
  if ! "$PYTHON_BIN" - <<'PY' >/dev/null 2>&1
import sys
if sys.version_info < (3, 12):
    raise SystemExit(1)
import networkx
import pydantic
PY
  then
    cat >&2 <<EOF2
[cosmo] Backend не запущен: для него нужны Python 3.12+, pydantic и networkx.
[cosmo] Установи backend один раз, например:

    $PYTHON_BIN -m pip install -e "$ROOT/backend"

после чего снова запусти ./scripts/run_dev.sh или npm run dev из frontend/.
EOF2
    exit 1
  fi

  : > "$BACKEND_LOG"
  (
    cd "$ROOT/backend"
    exec env PYTHONUNBUFFERED=1 PYTHONPATH=src "$PYTHON_BIN" -m backend_api.server \
      --host "$BACKEND_HOST" --port "$BACKEND_PORT"
  ) >"$BACKEND_LOG" 2>&1 &
  BACKEND_PID=$!
  STARTED_BACKEND=1

  echo "[cosmo] Запускаю backend: $BACKEND_URL"
  for _ in $(seq 1 100); do
    if health_ok; then
      break
    fi
    if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
      echo "[cosmo] Backend завершился при запуске. Лог:" >&2
      cat "$BACKEND_LOG" >&2
      exit 1
    fi
    sleep 0.1
  done

  if ! health_ok; then
    echo "[cosmo] Backend не прошёл health-check за 10 секунд. Лог:" >&2
    cat "$BACKEND_LOG" >&2
    exit 1
  fi

  echo "[cosmo] Backend готов. Лог: $BACKEND_LOG"
fi

if [[ ! -d "$ROOT/frontend/node_modules" ]]; then
  cat >&2 <<EOF2
[cosmo] Не найдены frontend/node_modules.
[cosmo] Сначала выполни:

    cd "$ROOT/frontend" && npm install
EOF2
  exit 1
fi

cd "$ROOT/frontend"
npm run dev:frontend
