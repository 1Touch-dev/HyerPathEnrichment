#!/usr/bin/env bash
# 08-redeploy-frontend.sh — full Next.js production build + pm2 restart.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
source "$SCRIPT_DIR/_common.sh"

cd "$FRONTEND_DIR"
if [[ ! -f .env.local ]]; then
  echo "ERROR: frontend/.env.local missing" >&2
  exit 1
fi

if [[ ! -d node_modules ]] || [[ package-lock.json -nt node_modules ]]; then
  echo "==> npm ci"
  npm ci
fi

echo "==> npm run build (full app)"
npm run build

echo "==> pm2 start/reload hyrepath-frontend"
export HOSTNAME=127.0.0.1
export PORT=3000
if pm2 describe hyrepath-frontend >/dev/null 2>&1; then
  pm2 restart hyrepath-frontend --update-env
else
  HOSTNAME=127.0.0.1 PORT=3000 pm2 start ./node_modules/next/dist/bin/next \
    --name hyrepath-frontend \
    --cwd "$FRONTEND_DIR" \
    -- start
fi
pm2 save
echo "Frontend listening on 127.0.0.1:3000 (publish via SG / Caddy)."
