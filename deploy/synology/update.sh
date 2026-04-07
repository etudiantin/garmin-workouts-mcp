#!/usr/bin/env bash
# Usage: bash deploy/synology/update.sh [--no-rebuild]
# Loads NAS_HOST, NAS_USER, NAS_PATH from deploy/synology/.env

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/.env"

REBUILD=true
if [[ "${1:-}" == "--no-rebuild" ]]; then
  REBUILD=false
fi

echo "→ Pushing local commits..."
git -C "${SCRIPT_DIR}/../.." push origin main

echo "→ Pulling on NAS (${NAS_HOST})..."
ssh "${NAS_USER}@${NAS_HOST}" "cd ${NAS_PATH} && git pull"

if [[ "$REBUILD" == true ]]; then
  echo "→ Rebuilding and restarting container..."
  ssh "${NAS_USER}@${NAS_HOST}" \
    "cd ${NAS_PATH} && /usr/local/bin/docker compose -f deploy/synology/docker-compose.yml up -d --build"
else
  echo "→ Restarting container (no rebuild)..."
  ssh "${NAS_USER}@${NAS_HOST}" \
    "cd ${NAS_PATH} && /usr/local/bin/docker compose -f deploy/synology/docker-compose.yml up -d"
fi

echo "→ Checking container status..."
ssh "${NAS_USER}@${NAS_HOST}" "/usr/local/bin/docker logs garmin-workouts-mcp-fork --tail 5 2>&1"

echo "✓ Done."
