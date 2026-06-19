#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

UV_BIN="${UV_BIN:-uv}"
NPM_BIN="${NPM_BIN:-npm}"
BACKEND_HOST="${PRINTPILOT_BACKEND_HOST:-0.0.0.0}"
BACKEND_PORT="${PRINTPILOT_BACKEND_PORT:-8001}"
FRONTEND_HOST="${PRINTPILOT_FRONTEND_HOST:-0.0.0.0}"
FRONTEND_PORT="${PRINTPILOT_FRONTEND_PORT:-5173}"

backend_pid=""
frontend_pid=""

require_command() {
    if ! command -v "$1" >/dev/null 2>&1; then
        echo "Missing required command: $1" >&2
        exit 127
    fi
}

stop_children() {
    local status=$?
    trap - EXIT INT TERM

    if [[ -n "$frontend_pid" ]] && kill -0 "$frontend_pid" 2>/dev/null; then
        kill "$frontend_pid" 2>/dev/null || true
    fi
    if [[ -n "$backend_pid" ]] && kill -0 "$backend_pid" 2>/dev/null; then
        kill "$backend_pid" 2>/dev/null || true
    fi

    wait "$frontend_pid" 2>/dev/null || true
    wait "$backend_pid" 2>/dev/null || true
    exit "$status"
}

trap stop_children EXIT INT TERM

require_command "$UV_BIN"
require_command "$NPM_BIN"

cd "$PROJECT_ROOT"
"$UV_BIN" run uvicorn backend.app.main:app --host "$BACKEND_HOST" --port "$BACKEND_PORT" &
backend_pid=$!

cd "$PROJECT_ROOT/frontend"
"$NPM_BIN" run dev -- --host "$FRONTEND_HOST" --port "$FRONTEND_PORT" &
frontend_pid=$!

wait -n "$backend_pid" "$frontend_pid"
