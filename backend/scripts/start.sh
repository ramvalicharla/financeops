#!/usr/bin/env bash
set -e

if [ -d /opt/venv/bin ]; then
  export PATH="/opt/venv/bin:${PATH}"
fi

if [ -x /opt/venv/bin/python ]; then
  PYTHON_BIN="/opt/venv/bin/python"
else
  PYTHON_BIN="${PYTHON_BIN:-python}"
  if [ -x "${PYTHON_BIN}" ]; then
    :
  elif ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
    if command -v python3 >/dev/null 2>&1; then
      PYTHON_BIN="python3"
    else
      echo "Python interpreter not found. Set PYTHON_BIN or ensure python is on PATH."
      exit 1
    fi
  fi
fi

if ! "${PYTHON_BIN}" -c "import psycopg2; print('psycopg2 OK')"; then
  echo "psycopg2 import failed"
  exit 1
fi

echo "Starting application..."
if [ "$(basename "$PWD")" = "backend" ]; then
  cd ..
  export PYTHONPATH="${PYTHONPATH:+${PYTHONPATH}:}backend"
fi
APP_PORT="${PORT:-10000}"
echo "Starting FastAPI on port ${APP_PORT}"
exec uvicorn financeops.main:app \
  --host 0.0.0.0 \
  --port "${APP_PORT}" \
  --workers 1
