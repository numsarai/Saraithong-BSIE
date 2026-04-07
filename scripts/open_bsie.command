#!/bin/zsh

set -euo pipefail

SCRIPT_DIR="${0:A:h}"
PROJECT_ROOT="${SCRIPT_DIR:h}"
PORT="${PORT:-8757}"
BASE_URL="http://127.0.0.1:${PORT}"
HEALTH_URL="${BASE_URL}/health"
LOG_FILE="${TMPDIR:-/tmp}/bsie-desktop-launcher.log"
PYTHON_BIN="${PROJECT_ROOT}/.venv/bin/python"

health_ok() {
  curl -fsS --max-time 2 "${HEALTH_URL}" >/dev/null 2>&1
}

wait_for_health() {
  local attempt=0
  while (( attempt < 40 )); do
    if health_ok; then
      return 0
    fi
    sleep 0.5
    attempt=$((attempt + 1))
  done
  return 1
}

kill_stale_bsie() {
  local pid

  for pid in ${(f)"$(lsof -tiTCP:${PORT} -sTCP:LISTEN 2>/dev/null || true)"}; do
    [[ -n "${pid}" ]] && kill -9 "${pid}" 2>/dev/null || true
  done

  for pid in ${(f)"$(pgrep -f "${PROJECT_ROOT}/app.py" 2>/dev/null || true)"}; do
    [[ -n "${pid}" ]] && kill -9 "${pid}" 2>/dev/null || true
  done

  for pid in ${(f)"$(pgrep -f "${PROJECT_ROOT}/main_launcher.py" 2>/dev/null || true)"}; do
    [[ -n "${pid}" ]] && kill -9 "${pid}" 2>/dev/null || true
  done
}

show_error() {
  local message="$1"
  /usr/bin/osascript <<EOF >/dev/null 2>&1 || true
display alert "BSIE" message "${message}" as critical buttons {"OK"} default button "OK"
EOF
}

if health_ok; then
  open "${BASE_URL}"
  exit 0
fi

if [[ ! -x "${PYTHON_BIN}" ]]; then
  show_error "Cannot start BSIE because the virtual environment is missing at ${PYTHON_BIN}."
  exit 1
fi

kill_stale_bsie

cd "${PROJECT_ROOT}"
nohup "${PYTHON_BIN}" app.py >>"${LOG_FILE}" 2>&1 </dev/null &

if ! wait_for_health; then
  show_error "BSIE did not respond on port ${PORT}. Check ${LOG_FILE} for details."
  exit 1
fi

open "${BASE_URL}"
