#!/usr/bin/env bash
set -euo pipefail

BACKEND_URL="${PRINTPILOT_BACKEND_URL:-http://127.0.0.1:${PRINTPILOT_BACKEND_PORT:-8001}}"
FRONTEND_URL="${PRINTPILOT_FRONTEND_URL:-http://127.0.0.1:${PRINTPILOT_FRONTEND_PORT:-5173}}"
SERVICE_NAME="${PRINTPILOT_SERVICE_NAME:-3dprintpilot.service}"
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

section "Systemd user service"
if command -v systemctl >/dev/null 2>&1; then
    systemctl --user is-enabled "$SERVICE_NAME"
    systemctl --user is-active "$SERVICE_NAME"
else
    echo "systemctl not found; skipping service status"
fi

section "Installed unit syntax"
if command -v systemd-analyze >/dev/null 2>&1; then
    systemd-analyze verify "${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user/$SERVICE_NAME"
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
