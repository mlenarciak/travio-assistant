#!/usr/bin/env bash
set -euo pipefail

# Travio Assistant one-shot runner
# - Creates a venv (if missing)
# - Installs dependencies
# - Ensures .env.local exists (copies from .env.example if missing)
# - Starts FastAPI backend (port 8000 by default)
# - Starts Streamlit UI (port 8501 by default)

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${ROOT_DIR}/.venv"
BACKEND_HOST="127.0.0.1"
BACKEND_PORT=8000
FRONTEND_PORT=8501
RELOAD=1
RESET_VENV=0
DO_INSTALL=1
MAX_HEALTH_RETRIES=20
USE_MOCK_FLAG=""
TRAVIO_ID_FLAG=""
TRAVIO_KEY_FLAG=""
LANG_FLAG=""

usage() {
  cat <<USAGE
Usage: $(basename "$0") [options]

Options:
  --backend-port <port>     Backend port (default: 8000)
  --frontend-port <port>    Frontend port (default: 8501)
  --reset-venv              Recreate the virtual environment
  --no-install              Skip pip install
  --no-reload               Start uvicorn without autoreload (more robust in some envs)
  --live                    Write USE_MOCK_DATA=false into .env.local (if creating)
  --mock                    Write USE_MOCK_DATA=true into .env.local (if creating)
  --id <TRAVIO_ID>          When creating .env.local, set TRAVIO_ID
  --key <TRAVIO_KEY>        When creating .env.local, set TRAVIO_KEY
  --lang <X-Lang>           When creating .env.local, set TRAVIO_LANGUAGE (default en)
  -h, --help                Show this help

Examples:
  $(basename "$0")
  $(basename "$0") --live --id 13 --key your_api_key
  $(basename "$0") --backend-port 9000 --frontend-port 8700
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --backend-port) BACKEND_PORT="$2"; shift 2;;
    --frontend-port) FRONTEND_PORT="$2"; shift 2;;
    --reset-venv) RESET_VENV=1; shift;;
    --no-install) DO_INSTALL=0; shift;;
    --no-reload) RELOAD=0; shift;;
    --live) USE_MOCK_FLAG="false"; shift;;
    --mock) USE_MOCK_FLAG="true"; shift;;
    --id) TRAVIO_ID_FLAG="$2"; shift 2;;
    --key) TRAVIO_KEY_FLAG="$2"; shift 2;;
    --lang) LANG_FLAG="$2"; shift 2;;
    -h|--help) usage; exit 0;;
    *) echo "Unknown option: $1"; usage; exit 1;;
  esac
done

echo "=> Working directory: ${ROOT_DIR}"

# Recreate venv if requested
if [[ ${RESET_VENV} -eq 1 && -d "${VENV_DIR}" ]]; then
  echo "=> Resetting virtual environment"
  rm -rf "${VENV_DIR}"
fi

# Create venv if missing
if [[ ! -d "${VENV_DIR}" ]]; then
  echo "=> Creating virtual environment at ${VENV_DIR}"
  python3 -m venv "${VENV_DIR}"
fi

# Activate venv
source "${VENV_DIR}/bin/activate"
python -V

# Install dependencies
if [[ ${DO_INSTALL} -eq 1 ]]; then
  echo "=> Installing dependencies"
  pip install --upgrade pip >/dev/null
  pip install -r "${ROOT_DIR}/requirements.txt"
else
  echo "=> Skipping dependency installation"
fi

# Ensure .env.local exists
ENV_LOCAL="${ROOT_DIR}/.env.local"
if [[ ! -f "${ENV_LOCAL}" ]]; then
  if [[ -f "${ROOT_DIR}/.env.example" ]]; then
    echo "=> Creating ${ENV_LOCAL} from .env.example"
    cp -n "${ROOT_DIR}/.env.example" "${ENV_LOCAL}"
  else
    echo "=> Creating minimal ${ENV_LOCAL}"
    cat <<'EOF' >"${ENV_LOCAL}"
TRAVIO_ID=0
TRAVIO_KEY=replace_me
TRAVIO_BASE_URL=https://api.travio.it
TRAVIO_LANGUAGE=en
USE_MOCK_DATA=true
APP_NAME=Travio Assistant Backend
EOF
  fi
  echo "=> Wrote ${ENV_LOCAL}. Review values if running live."
fi

update_env_value() {
  local key="$1"
  local value="$2"
  if grep -q "^${key}=" "${ENV_LOCAL}"; then
    sed -i.bak "s/^${key}=.*/${key}=${value}/" "${ENV_LOCAL}"
  else
    printf '\n%s=%s\n' "${key}" "${value}" >>"${ENV_LOCAL}"
  fi
  rm -f "${ENV_LOCAL}.bak"
}

[[ -n "${USE_MOCK_FLAG}" ]] && update_env_value "USE_MOCK_DATA" "${USE_MOCK_FLAG}"
[[ -n "${TRAVIO_ID_FLAG}" ]] && update_env_value "TRAVIO_ID" "${TRAVIO_ID_FLAG}"
[[ -n "${TRAVIO_KEY_FLAG}" ]] && update_env_value "TRAVIO_KEY" "${TRAVIO_KEY_FLAG}"
[[ -n "${LANG_FLAG}" ]] && update_env_value "TRAVIO_LANGUAGE" "${LANG_FLAG}"

# Export env
set -a
[[ -f "${ROOT_DIR}/.env" ]] && source "${ROOT_DIR}/.env"
[[ -f "${ROOT_DIR}/.env.local" ]] && source "${ROOT_DIR}/.env.local"
set +a

# Trap to cleanup background processes
PIDS=()
cleanup() {
  echo "\n=> Shutting down..."
  for pid in "${PIDS[@]:-}"; do
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
      wait "$pid" 2>/dev/null || true
    fi
  done
}
trap cleanup EXIT INT TERM
LOGS_DIR="${ROOT_DIR}/logs"
mkdir -p "${LOGS_DIR}"

# Start backend (background)
echo "=> Starting backend on http://${BACKEND_HOST}:${BACKEND_PORT} (logs: ${LOGS_DIR}/backend.log)"
UVICORN_ARGS=(backend.app.main:app --host "${BACKEND_HOST}" --port "${BACKEND_PORT}")
if [[ ${RELOAD} -eq 1 ]]; then
  UVICORN_ARGS+=(--reload)
fi
nohup uvicorn "${UVICORN_ARGS[@]}" >"${LOGS_DIR}/backend.log" 2>&1 &
PIDS+=($!)
# Tail backend logs for visibility
tail -n +1 -F "${LOGS_DIR}/backend.log" &
PIDS+=($!)

# Wait for backend health (bash + curl)
echo -n "=> Waiting for backend to become ready"
HEALTH_URL="http://${BACKEND_HOST}:${BACKEND_PORT}/api/system/health"
READY=0
HTTP_CODE=""
for ((i = 1; i <= MAX_HEALTH_RETRIES; i++)); do
  HTTP_CODE=$(curl -s -o /dev/null -m 2 -w "%{http_code}" "$HEALTH_URL") || true
  if [[ "$HTTP_CODE" == "200" ]]; then
    STATUS=$(curl -s -m 2 "$HEALTH_URL" | sed -n 's/.*"status":"\([^"]*\)".*/\1/p') || true
  else
    STATUS=""
  fi
  if [[ "$HTTP_CODE" == "200" && "$STATUS" == "ok" ]]; then
    printf '\nBackend ready: ok\n'
    READY=1
    break
  fi
  sleep 0.5
  if (( i % 10 == 0 )); then
    printf "."
  fi
done

if [[ $READY -ne 1 ]]; then
  printf '\nBackend did not respond after %s attempts (last HTTP code: %s)\n' \
    "$MAX_HEALTH_RETRIES" "$HTTP_CODE" >&2
  echo "--- Last 100 lines of backend.log ---" >&2
  tail -n 100 "${LOGS_DIR}/backend.log" >&2 || true
  exit 1
fi

# Start Streamlit (foreground)
echo "=> Launching Streamlit UI on http://localhost:${FRONTEND_PORT}"
exec streamlit run frontend/app.py \
  --server.port "${FRONTEND_PORT}" \
  --browser.gatherUsageStats false
