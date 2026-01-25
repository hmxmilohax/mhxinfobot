#!/bin/sh
set -eu

: "${REPO_URL:=https://github.com/hmxmilohax/mhxinfobot}"
: "${APP_DIR:=/opt/mhxinfobot}"

if [ ! -d "$APP_DIR/.git" ]; then
  echo "[mhxinfobot] Cloning repo..."
  rm -rf "$APP_DIR"
  git clone --depth 1 "$REPO_URL" "$APP_DIR"
else
  echo "[mhxinfobot] Updating repo..."
  git -C "$APP_DIR" fetch --depth 1 origin
  git -C "$APP_DIR" reset --hard origin/main
fi

if [ ! -f "$APP_DIR/config.json" ]; then
  echo "[mhxinfobot] ERROR: config.json not found at $APP_DIR/config.json (bind-mount it)."
  exit 1
fi

exec python "$APP_DIR/mhxinfobot.py"
