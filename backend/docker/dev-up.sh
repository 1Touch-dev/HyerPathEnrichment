#!/usr/bin/env bash
# Single entrypoint for the "docker nodemon" local dev workflow: brings up
# the full backend stack (base + foundation + week2-ai overlays, with the
# llm/paid/observability profiles) using backend/.env.production, then runs
# two reload loops together:
#   - inner loop:  `docker compose watch` (develop.watch, docker-compose.watch.yml)
#                  — fast in-container code sync/restart, no image rebuild
#   - outer loop:  watch-infra.sh (backgrounded) — rebuilds when compose
#                  files, Dockerfiles, or env files change (things
#                  `docker compose watch` structurally can't react to)
#
# Multilogin / Tier 1 are never started by this script: no
# docker-compose.tier1.yml / docker-compose.multilogin.yml overlay is
# included, and backend/.env.production is expected to have
# ENABLE_TIER1=false (see backend/scripts/validate_env.sh).
#
# Usage:
#   bash dev-up.sh
#
# Env:
#   DEV_ENV_FILE  path to the env file passed to `--env-file` (default: ../.env.production)
#   DEV_PROFILES  space-separated `--profile` flags (default: "--profile llm --profile paid --profile observability")
#
# Stop with Ctrl-C: the trap below also stops the background infra watcher.
# Tear the stack down with: docker compose <same -f flags> down
#
# Portable to Linux/macOS/WSL2/Git Bash — POSIX/bash only, no OS branching.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

ENV_FILE="${DEV_ENV_FILE:-../.env.production}"
if [ ! -f "$ENV_FILE" ]; then
  echo "dev-up.sh: $ENV_FILE not found." >&2
  echo "  Create it before running the dev workflow — see backend/scripts/start_production.sh" >&2
  echo "  and backend/scripts/validate_env.sh for the expected shape." >&2
  exit 1
fi

IFS=' ' read -ra PROFILES <<< "${DEV_PROFILES:---profile llm --profile paid --profile observability}"
COMPOSE_FILES=(-f docker-compose.yml -f docker-compose.foundation.yml -f docker-compose.week2-ai.yml -f docker-compose.watch.yml)

echo "== dev-up: initial 'up -d --build' (env: $ENV_FILE) =="
docker compose "${COMPOSE_FILES[@]}" --env-file "$ENV_FILE" "${PROFILES[@]}" up -d --build

WATCH_INFRA_PID=""
cleanup() {
  if [ -n "$WATCH_INFRA_PID" ] && kill -0 "$WATCH_INFRA_PID" 2>/dev/null; then
    echo ""
    echo "== dev-up: stopping background infra watcher (pid $WATCH_INFRA_PID) =="
    kill "$WATCH_INFRA_PID" 2>/dev/null || true
    wait "$WATCH_INFRA_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

echo "== dev-up: starting background infra watcher (watch-infra.sh) =="
DEV_ENV_FILE="$ENV_FILE" DEV_PROFILES="${PROFILES[*]}" "$SCRIPT_DIR/watch-infra.sh" &
WATCH_INFRA_PID=$!

echo "== dev-up: starting foreground 'docker compose watch' (code reload) =="
docker compose "${COMPOSE_FILES[@]}" --env-file "$ENV_FILE" "${PROFILES[@]}" watch
