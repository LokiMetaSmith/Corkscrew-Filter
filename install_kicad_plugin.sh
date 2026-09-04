#!/usr/bin/env bash
# Installs the OpenAuto EM Live KiCad Action Plugin into KiCad 10 / 9 / 8 / 7.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="python3"

if [ -f "$SCRIPT_DIR/.venv/bin/python" ]; then
    PYTHON_BIN="$SCRIPT_DIR/.venv/bin/python"
elif [ -f "$SCRIPT_DIR/.venv/Scripts/python.exe" ]; then
    PYTHON_BIN="$SCRIPT_DIR/.venv/Scripts/python.exe"
fi

echo "Running OpenAuto EM Live Plugin Installer..."
exec "$PYTHON_BIN" "$SCRIPT_DIR/kicad_plugin/install_plugin.py" "$@"
