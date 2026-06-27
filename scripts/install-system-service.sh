#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_NAME="${1:-3dprintpilot.service}"
TEMPLATE="$PROJECT_ROOT/systemd/system/3dprintpilot.service.in"
SYSTEMD_DIR="${PRINTPILOT_SYSTEMD_DIR:-/etc/systemd/system}"
SERVICE_PATH="$SYSTEMD_DIR/$SERVICE_NAME"
SERVICE_USER="${PRINTPILOT_SERVICE_USER:-${SUDO_USER:-$(id -un)}}"
SERVICE_GROUP="${PRINTPILOT_SERVICE_GROUP:-$(id -gn "$SERVICE_USER")}"
SERVICE_HOME="${PRINTPILOT_SERVICE_HOME:-}"
ROOT_CMD=()
LEGACY_USER_UNIT="${PRINTPILOT_LEGACY_USER_UNIT:-$HOME/.config/systemd/user/$SERVICE_NAME}"

escape_sed_replacement() {
    local value="$1"
    value="${value//\\/\\\\}"
    value="${value//&/\\&}"
    value="${value//|/\\|}"
    printf '%s' "$value"
}

case "$SERVICE_NAME" in
    */*)
        echo "Service name must not contain path separators: $SERVICE_NAME" >&2
        exit 2
        ;;
esac

if ! command -v systemctl >/dev/null 2>&1; then
    echo "systemctl is required to install a systemd system service." >&2
    exit 127
fi

if (( EUID != 0 )); then
    if ! command -v sudo >/dev/null 2>&1; then
        echo "sudo is required to install the system service as a non-root user." >&2
        exit 127
    fi
    ROOT_CMD=(sudo)
fi

if [[ "$SERVICE_USER" == "root" && -z "${PRINTPILOT_ALLOW_ROOT_SERVICE:-}" ]]; then
    echo "Refusing to install a root-run service by default." >&2
    echo "Run this script as the account that should run 3dPrintPilot, or set PRINTPILOT_SERVICE_USER." >&2
    exit 1
fi

if [[ -z "$SERVICE_HOME" ]]; then
    SERVICE_HOME="$(getent passwd "$SERVICE_USER" | cut -d: -f6 || true)"
fi

if [[ -z "$SERVICE_HOME" ]]; then
    echo "Could not resolve home directory for service user: $SERVICE_USER" >&2
    exit 1
fi

USER_ENV_FILE="${PRINTPILOT_USER_ENV_FILE:-$SERVICE_HOME/.config/3dprintpilot/3dprintpilot.env}"

cleanup_legacy_user_service() {
    if [[ "${PRINTPILOT_SKIP_LEGACY_USER_CLEANUP:-0}" == "1" ]]; then
        return
    fi

    if [[ ! -e "$LEGACY_USER_UNIT" ]]; then
        return
    fi

    echo "Disabling legacy systemd user service: $LEGACY_USER_UNIT"
    systemctl --user disable --now "$SERVICE_NAME" >/dev/null 2>&1 || true
    rm -f "$LEGACY_USER_UNIT"
    systemctl --user daemon-reload >/dev/null 2>&1 || true
}

UV_BIN_PATH="$(command -v "${UV_BIN:-uv}" || true)"
NPM_BIN_PATH="$(command -v "${NPM_BIN:-npm}" || true)"

if [[ -z "$UV_BIN_PATH" ]]; then
    echo "uv is required to start the backend service." >&2
    exit 127
fi

if [[ -z "$NPM_BIN_PATH" ]]; then
    echo "npm is required to start the frontend service." >&2
    exit 127
fi

if [[ ! -d "$PROJECT_ROOT/frontend/node_modules" ]]; then
    echo "frontend/node_modules is missing. Run this first:" >&2
    echo "  cd $PROJECT_ROOT/frontend && npm install" >&2
    exit 1
fi

cleanup_legacy_user_service

service_path_value="$(dirname "$UV_BIN_PATH"):$(dirname "$NPM_BIN_PATH"):$SERVICE_HOME/.local/bin:$SERVICE_HOME/.cargo/bin:/usr/local/bin:/usr/bin:/bin"
tmp_unit="$(mktemp "${TMPDIR:-/tmp}/3dprintpilot.XXXXXX.service")"
cleanup() {
    rm -f "$tmp_unit"
}
trap cleanup EXIT

sed \
    -e "s|@PROJECT_DIR@|$(escape_sed_replacement "$PROJECT_ROOT")|g" \
    -e "s|@SERVICE_PATH@|$(escape_sed_replacement "$service_path_value")|g" \
    -e "s|@UV_BIN@|$(escape_sed_replacement "$UV_BIN_PATH")|g" \
    -e "s|@NPM_BIN@|$(escape_sed_replacement "$NPM_BIN_PATH")|g" \
    -e "s|@SERVICE_USER@|$(escape_sed_replacement "$SERVICE_USER")|g" \
    -e "s|@SERVICE_GROUP@|$(escape_sed_replacement "$SERVICE_GROUP")|g" \
    -e "s|@USER_ENV_FILE@|$(escape_sed_replacement "$USER_ENV_FILE")|g" \
    "$TEMPLATE" > "$tmp_unit"

if command -v systemd-analyze >/dev/null 2>&1; then
    systemd-analyze verify "$tmp_unit"
fi

"${ROOT_CMD[@]}" install -D -m 0644 "$tmp_unit" "$SERVICE_PATH"
"${ROOT_CMD[@]}" systemctl daemon-reload
"${ROOT_CMD[@]}" systemctl enable "$SERVICE_NAME"
"${ROOT_CMD[@]}" systemctl restart "$SERVICE_NAME"

cat <<EOF
Installed and started or restarted $SERVICE_NAME.

Useful commands:
  systemctl status $SERVICE_NAME
  journalctl -u $SERVICE_NAME -f
  sudo systemctl restart $SERVICE_NAME
  sudo systemctl disable --now $SERVICE_NAME

Configuration files:
  /etc/3dprintpilot/3dprintpilot.env
  $USER_ENV_FILE

Legacy cleanup:
  Removed $LEGACY_USER_UNIT when it existed.
EOF
