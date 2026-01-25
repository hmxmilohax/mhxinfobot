#!/bin/sh
set -eu

: "${REPO_URL:=https://github.com/hmxmilohax/mhxinfobot}"
: "${APP_DIR:=/opt/mhxinfobot}"
: "${BRANCH:=main}"

git config --global --add safe.directory "$APP_DIR" || true

# Clone/update repo in the named volume
if [ ! -d "$APP_DIR/.git" ]; then
  echo "[mhxinfobot] Cloning repo..."
  rm -rf "$APP_DIR"
  git clone --depth 1 --branch "$BRANCH" "$REPO_URL" "$APP_DIR"
else
  echo "[mhxinfobot] Updating repo..."
  git -C "$APP_DIR" fetch --depth 1 origin "$BRANCH"
  git -C "$APP_DIR" reset --hard "origin/$BRANCH"
fi

# Inject config from the separate bind mount
if [ ! -f /config/config.json ]; then
  echo "[mhxinfobot] ERROR: /config/config.json not found (bind-mount it)."
  exit 1
fi

cp /config/config.json "$APP_DIR/config.json"

exec python "$APP_DIR/mhxinfobot.py"
