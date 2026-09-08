#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$ROOT/.." && pwd)"
PORT="${PORT:-8769}"
VIEW_W=1600
VIEW_H=1200
OUT_W=2400
OUT_H=1800
TMP="$(mktemp -d)"
cd "$ROOT"

python3 -m http.server "$PORT" --bind 127.0.0.1 >/tmp/omalet-preview-http.log 2>&1 &
SERVER_PID=$!
trap 'kill "$SERVER_PID" 2>/dev/null || true; rm -rf "$TMP"' EXIT
sleep 0.3

export FONTCONFIG_PATH=/etc/fonts
export FONTCONFIG_FILE=/etc/fonts/fonts.conf

capture() {
  local state=$1 dest=$2 mode=${3:-full}
  local raw="$TMP/${state}.png"
  chromium --headless=new --disable-gpu --hide-scrollbars \
    --no-first-run --no-default-browser-check \
    --window-size="${VIEW_W},${VIEW_H}" \
    --force-device-scale-factor=2 \
    --screenshot="$raw" \
    --virtual-time-budget=4000 \
    "http://127.0.0.1:${PORT}/index.html?state=${state}&capture=1"
  mkdir -p "$(dirname "$REPO/$dest")"
  if [[ $mode == panel ]]; then
    magick "$raw" -gravity NorthEast -crop 1920x1440+36+0 +repage \
      -resize "${OUT_W}x${OUT_H}!" -strip "$REPO/$dest"
  else
    magick "$raw" -resize "${OUT_W}x${OUT_H}!" -strip "$REPO/$dest"
  fi
  echo "$dest"
}

capture vitals preview.png full
capture tray screenshots/tray.png full
capture vitals screenshots/vitals.png panel
capture charging screenshots/charging.png panel
capture alert-oxygen screenshots/alert.png panel
capture alert-heart screenshots/alert-heart.png panel
capture alert-battery screenshots/alert-battery.png panel
capture sock-off screenshots/sock-off.png panel
capture login screenshots/login.png panel
