#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="${PRINTPILOT_WEB_PROXY_NAME:-3dprintpilot-web-proxy}"
LISTEN_PORT="${PRINTPILOT_WEB_PROXY_PORT:-80}"
TARGET_HOST="${PRINTPILOT_WEB_PROXY_TARGET_HOST:-127.0.0.1}"
TARGET_PORT="${PRINTPILOT_WEB_PROXY_TARGET_PORT:-8001}"
SYSTEMD_DIR="${PRINTPILOT_SYSTEMD_SYSTEM_DIR:-/etc/systemd/system}"
PROXY_BIN="${PRINTPILOT_SYSTEMD_SOCKET_PROXYD:-}"

if [[ -z "$PROXY_BIN" ]]; then
    if [[ -x /lib/systemd/systemd-socket-proxyd ]]; then
        PROXY_BIN="/lib/systemd/systemd-socket-proxyd"
    elif [[ -x /usr/lib/systemd/systemd-socket-proxyd ]]; then
        PROXY_BIN="/usr/lib/systemd/systemd-socket-proxyd"
    else
        echo "systemd-socket-proxyd was not found" >&2
        exit 127
    fi
fi

run_privileged() {
    if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
        "$@"
    elif command -v sudo >/dev/null 2>&1 && sudo -n true 2>/dev/null; then
        sudo "$@"
    elif command -v pkexec >/dev/null 2>&1; then
        pkexec "$@"
    else
        echo "Root privileges are required to install a system port ${LISTEN_PORT} proxy." >&2
        echo "Run this script with sudo or from a desktop session that can prompt for pkexec." >&2
        exit 1
    fi
}

socket_tmp="$(mktemp)"
service_tmp="$(mktemp)"
trap 'rm -f "$socket_tmp" "$service_tmp"' EXIT

cat >"$socket_tmp" <<EOF
[Unit]
Description=3dPrintPilot web endpoint proxy socket

[Socket]
ListenStream=0.0.0.0:${LISTEN_PORT}
NoDelay=true
Service=${SERVICE_NAME}.service

[Install]
WantedBy=sockets.target
EOF

cat >"$service_tmp" <<EOF
[Unit]
Description=3dPrintPilot web endpoint proxy
Requires=${SERVICE_NAME}.socket
After=network-online.target

[Service]
ExecStart=${PROXY_BIN} ${TARGET_HOST}:${TARGET_PORT}
PrivateTmp=true
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
EOF

run_privileged install -m 0644 "$socket_tmp" "${SYSTEMD_DIR}/${SERVICE_NAME}.socket"
run_privileged install -m 0644 "$service_tmp" "${SYSTEMD_DIR}/${SERVICE_NAME}.service"
run_privileged systemctl daemon-reload
run_privileged systemctl enable --now "${SERVICE_NAME}.socket"

echo "Installed ${SERVICE_NAME}.socket on port ${LISTEN_PORT} -> ${TARGET_HOST}:${TARGET_PORT}"
