#!/usr/bin/env bash
set -e

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

DEBUG_VALUE="${DEBUG:-false}"
case "${DEBUG_VALUE,,}" in
  true|false|1|0|yes|no|on|off) ;;
  *) DEBUG_VALUE="false" ;;
esac

ALEMBIC_CMD="/opt/venv/bin/alembic"
if [ ! -x "${ALEMBIC_CMD}" ]; then
  ALEMBIC_CMD="alembic"
  if ! command -v "${ALEMBIC_CMD}" >/dev/null 2>&1; then
    ALEMBIC_CMD=""
  fi
fi

"${PYTHON_BIN}" -c "import psycopg2; print('psycopg2 OK')"

echo "Running migrations..."
if [ -d backend ] && [ -f backend/alembic.ini ]; then
  cd backend
fi
if [ -n "${ALEMBIC_CMD}" ]; then
  DEBUG="${DEBUG_VALUE}" "${ALEMBIC_CMD}" upgrade head
else
  DEBUG="${DEBUG_VALUE}" "${PYTHON_BIN}" -m alembic upgrade head
fi

echo "Starting application..."
if [ "$(basename "$PWD")" = "backend" ]; then
  cd ..
  export PYTHONPATH="${PYTHONPATH:+${PYTHONPATH}:}backend"
fi
DEBUG="${DEBUG_VALUE}" exec "${PYTHON_BIN}" -m uvicorn financeops.main:app --host 0.0.0.0 --port ${PORT:-8080}
