#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_NAME="${1:-3dprintpilot.service}"
TEMPLATE="$PROJECT_ROOT/systemd/user/3dprintpilot.service.in"
USER_SYSTEMD_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
SERVICE_PATH="$USER_SYSTEMD_DIR/$SERVICE_NAME"

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
    echo "systemctl is required to install a systemd user service." >&2
    exit 127
fi

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

mkdir -p "$USER_SYSTEMD_DIR"

service_path_value="$(dirname "$UV_BIN_PATH"):$(dirname "$NPM_BIN_PATH"):%h/.local/bin:%h/.cargo/bin:/usr/local/bin:/usr/bin:/bin"

sed \
    -e "s|@PROJECT_DIR@|$(escape_sed_replacement "$PROJECT_ROOT")|g" \
    -e "s|@SERVICE_PATH@|$(escape_sed_replacement "$service_path_value")|g" \
    -e "s|@UV_BIN@|$(escape_sed_replacement "$UV_BIN_PATH")|g" \
    -e "s|@NPM_BIN@|$(escape_sed_replacement "$NPM_BIN_PATH")|g" \
    "$TEMPLATE" > "$SERVICE_PATH"

systemctl --user daemon-reload
systemctl --user enable "$SERVICE_NAME"
systemctl --user restart "$SERVICE_NAME"

cat <<EOF
Installed and started or restarted $SERVICE_NAME.

Useful commands:
  systemctl --user status $SERVICE_NAME
  journalctl --user -u $SERVICE_NAME -f
  systemctl --user restart $SERVICE_NAME
  systemctl --user disable --now $SERVICE_NAME
EOF
