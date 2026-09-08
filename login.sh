#!/usr/bin/env bash
set -euo pipefail

STATE_DIR="${HOME}/.local/state/omarchy"
AUTH_FILE="${STATE_DIR}/owlet-auth.json"
ROOT="$(cd "$(dirname "$0")" && pwd)"
REGION="${OWLET_REGION:-world}"

read_saved_email() {
  if [[ -f $AUTH_FILE ]]; then
    python3 - "$AUTH_FILE" <<'PY'
import json, sys
from pathlib import Path
try:
    data = json.loads(Path(sys.argv[1]).read_text())
except (OSError, json.JSONDecodeError):
    data = {}
print((data.get("email") or "").strip())
PY
  fi
}

email="${OWLET_EMAIL:-}"
password=""

if [[ -n ${OWLET_PASSWORD:-} ]]; then
  password="$OWLET_PASSWORD"
else
  IFS= read -r line1 || true
  IFS= read -r line2 || true
  if [[ -n ${line2:-} ]]; then
    email="${email:-$line1}"
    password="$line2"
  else
    password="${line1:-}"
  fi
fi

if [[ -z $email ]]; then
  email="$(read_saved_email)"
fi

if [[ -z $email ]]; then
  echo "owlet: email is required" >&2
  exit 1
fi

if [[ -z $password ]]; then
  echo "owlet: no password on stdin" >&2
  exit 1
fi

mkdir -p "$STATE_DIR"
umask 077
python3 - "$AUTH_FILE" "$email" "$REGION" <<'PY'
import json, sys
from pathlib import Path
path, email, region = sys.argv[1], sys.argv[2], sys.argv[3]
Path(path).write_text(json.dumps({"email": email, "region": region}) + "\n")
PY
chmod 600 "$AUTH_FILE"

printf '%s' "$password" | secret-tool store --label="Owlet ($email)" service owlet username "$email"
unset password

if ! secret-tool lookup service owlet username "$email" >/dev/null; then
  echo "owlet: could not store the password in the keyring" >&2
  exit 1
fi

exec "$ROOT/fetch.sh"
