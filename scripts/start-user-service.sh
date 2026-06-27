#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "scripts/start-user-service.sh is kept for compatibility; use scripts/start-service.sh." >&2
exec "$SCRIPT_DIR/start-service.sh" "$@"
