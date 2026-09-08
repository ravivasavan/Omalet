#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="${HOME}/.local/share/omarchy/owlet/venv"
STATE_DIR="${HOME}/.local/state/omarchy"
STATE_FILE="${STATE_DIR}/owlet.json"
REQ="$ROOT/requirements.txt"

write_state() {
  local error=$1
  mkdir -p "$STATE_DIR"
  python3 - "$STATE_FILE" "$error" <<'PY'
import json, sys, time
from pathlib import Path
path, error = Path(sys.argv[1]), sys.argv[2]
path.write_text(json.dumps({
    "ok": False,
    "status": "setup",
    "error": error,
    "needs_login": False,
    "label": "Omalet",
    "fetched_at": int(time.time()),
}) + "\n")
PY
}

if [[ ! -f $REQ ]]; then
  echo "owlet: missing requirements.txt" >&2
  exit 1
fi

write_state "Installing Owlet helper…"
mkdir -p "$(dirname "$VENV_DIR")"
python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --disable-pip-version-check --upgrade pip wheel
"$VENV_DIR/bin/pip" install --disable-pip-version-check -r "$REQ"
