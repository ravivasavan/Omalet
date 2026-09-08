#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
VENV_PYTHON="${HOME}/.local/share/omarchy/owlet/venv/bin/python"
STATE_DIR="${HOME}/.local/state/omarchy"
STATE_FILE="${STATE_DIR}/owlet.json"

if [[ ! -x $VENV_PYTHON ]]; then
  if ! "$ROOT/setup.sh"; then
    mkdir -p "$STATE_DIR"
    printf '%s\n' '{"ok":false,"status":"error","error":"Could not install the Owlet helper","needs_login":false,"label":"Omalet"}' > "$STATE_FILE"
    echo "owlet: setup failed" >&2
    exit 1
  fi
fi

exec "$VENV_PYTHON" "$ROOT/fetch.py" "$@"
