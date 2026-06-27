#!/usr/bin/env bash
set -euo pipefail

BACKEND_URL="${PRINTPILOT_BACKEND_URL:-http://127.0.0.1:${PRINTPILOT_BACKEND_PORT:-8002}}"
FRONTEND_URL="${PRINTPILOT_FRONTEND_URL:-http://127.0.0.1:${PRINTPILOT_FRONTEND_PORT:-8001}}"
SERVICE_NAME="${PRINTPILOT_SERVICE_NAME:-3dprintpilot.service}"
SYSTEMD_UNIT_PATH="${PRINTPILOT_SYSTEMD_UNIT_PATH:-/etc/systemd/system/$SERVICE_NAME}"
PUBLIC_URL="${PRINTPILOT_PUBLIC_URL:-}"
SKIP_DB="${PRINTPILOT_SKIP_DB_CHECK:-0}"
CHECK_RETRIES="${PRINTPILOT_CHECK_RETRIES:-5}"
CHECK_RETRY_DELAY="${PRINTPILOT_CHECK_RETRY_DELAY:-1}"

section() {
    printf '\n== %s ==\n' "$1"
}

retry() {
    local attempt=1
    local status=0

    while (( attempt <= CHECK_RETRIES )); do
        if "$@"; then
            return 0
        fi
        status=$?
        if (( attempt == CHECK_RETRIES )); then
            return "$status"
        fi
        sleep "$CHECK_RETRY_DELAY"
        attempt=$((attempt + 1))
    done
}

section "Backend health"
retry curl -fsS "$BACKEND_URL/api/health"
printf '\n'

section "Frontend"
retry curl -fsSI "$FRONTEND_URL/" | sed -n '1,8p'

if [[ -n "$PUBLIC_URL" ]]; then
    section "Public web endpoint"
    retry curl -fsSI "$PUBLIC_URL/" | sed -n '1,8p'
fi

section "Systemd system service"
if command -v systemctl >/dev/null 2>&1; then
    systemctl is-enabled "$SERVICE_NAME"
    systemctl is-active "$SERVICE_NAME"
else
    echo "systemctl not found; skipping service status"
fi

section "Installed unit syntax"
if command -v systemd-analyze >/dev/null 2>&1; then
    systemd-analyze verify "$SYSTEMD_UNIT_PATH"
else
    echo "systemd-analyze not found; skipping unit verification"
fi

if [[ "$SKIP_DB" != "1" ]]; then
    section "Alembic database state"
    uv run alembic current
else
    section "Alembic database state"
    echo "Skipped because PRINTPILOT_SKIP_DB_CHECK=1"
fi
