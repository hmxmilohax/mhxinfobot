#!/bin/sh
set -eu

: "${REPO_URL:=https://github.com/hmxmilohax/mhxinfobot}"
: "${APP_DIR:=/opt/mhxinfobot}"
: "${BRANCH:=main}"

mkdir -p "$APP_DIR"
git config --global --add safe.directory "$APP_DIR" || true

if [ ! -d "$APP_DIR/.git" ]; then
  echo "[mhxinfobot] Cloning repo..."
  find "$APP_DIR" -mindepth 1 -maxdepth 1 -exec rm -rf {} +
  git clone --depth 1 --branch "$BRANCH" "$REPO_URL" "$APP_DIR"
else
  echo "[mhxinfobot] Updating repo..."
  git -C "$APP_DIR" fetch --depth 1 origin "$BRANCH"
  git -C "$APP_DIR" reset --hard "origin/$BRANCH"
fi

if [ ! -f /config/config.json ]; then
  echo "[mhxinfobot] ERROR: /config/config.json not found (bind-mount it)."
  exit 1
fi

cp /config/config.json "$APP_DIR/config.json"

cd "$APP_DIR"
exec python mhxinfobot.py
