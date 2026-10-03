#!/usr/bin/env bash
# run.sh — Launcher for Disk Cleaner
#
# Usage:
#   ./run.sh                        # interactive TUI
#   ./run.sh --scan                 # scan + report only (no deletion)
#   ./run.sh --dry-run              # show what would be deleted
#   ./run.sh --clean                # scan + clean all categories silently
#   ./run.sh --category pip_cache   # target a specific category
#   ./run.sh --list                 # list all rule IDs

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Require Python 3.10+
PYTHON=""
for candidate in python3 python3.12 python3.11 python3.10; do
    if command -v "$candidate" &>/dev/null; then
        VER=$("$candidate" -c "import sys; print(sys.version_info >= (3,10))" 2>/dev/null)
        if [[ "$VER" == "True" ]]; then
            PYTHON="$candidate"
            break
        fi
    fi
done

if [[ -z "$PYTHON" ]]; then
    echo "ERROR: Python 3.10 or newer is required but not found." >&2
    exit 1
fi

# Must be run as root for full access
if [[ "$EUID" -ne 0 ]]; then
    echo ""
    echo "  ⚠  Some paths (apt cache, /var/log, /tmp) need root access."
    echo "     Re-run with: sudo ./run.sh $*"
    echo ""
    read -rp "  Continue anyway? [y/N] " ans
    [[ "${ans,,}" =~ ^y ]] || exit 0
fi

exec "$PYTHON" main.py "$@"
