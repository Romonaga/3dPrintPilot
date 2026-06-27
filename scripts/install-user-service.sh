#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "scripts/install-user-service.sh now installs the system service; use scripts/install-system-service.sh." >&2
exec "$SCRIPT_DIR/install-system-service.sh" "$@"
