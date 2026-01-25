#!/bin/sh
set -eu

if [ ! -f /config/config.json ]; then
  echo "[mhxinfobot] ERROR: /config/config.json not found (bind-mount it)."
  exit 1
fi

cp /config/config.json /app/config.json
cd /app
exec python mhxinfobot.py
