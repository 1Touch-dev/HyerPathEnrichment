#!/usr/bin/env bash
# "Outer loop" watcher for the docker nodemon-style dev workflow.
#
# `docker compose watch` (docker-compose.watch.yml) only reloads code inside
# the containers it already manages — it can't (and structurally never will)
# react to changes in the compose files, Dockerfiles, or env files that shape
# the stack itself. This script covers that gap: it watches those infra-level
# inputs and re-runs the full `up -d --build` whenever one changes. Docker's
# build cache makes unaffected layers a no-op, so re-running this is cheap.
#
# Watched:
#   docker-compose.yml, docker-compose.foundation.yml,
#   docker-compose.week2-ai.yml, docker-compose.watch.yml,
#   Dockerfile.*, ../.env, ../.env.production
#
# Requires: watchfiles on PATH (`pip install watchfiles`).
#
# Usage:
#   bash watch-infra.sh
#
# Normally launched in the background by dev-up.sh; can also be run
# standalone (e.g. in its own terminal) for just the infra-reload loop.
#
# Env:
#   DEV_ENV_FILE  path to the env file passed to `--env-file` (default: ../.env.production)
#   DEV_PROFILES  space-separated `--profile` flags (default: "--profile llm --profile paid --profile observability")
#
# Portable to Linux/macOS/WSL2/Git Bash — POSIX/bash only, no OS branching.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if ! command -v watchfiles >/dev/null 2>&1; then
  echo "watch-infra.sh: 'watchfiles' not found on PATH." >&2
  echo "  Install it with: pip install watchfiles" >&2
  exit 1
fi

ENV_FILE="${DEV_ENV_FILE:-../.env.production}"

COMPOSE_FILES=(-f docker-compose.yml -f docker-compose.foundation.yml -f docker-compose.week2-ai.yml -f docker-compose.watch.yml)
IFS=' ' read -ra PROFILES <<< "${DEV_PROFILES:---profile llm --profile paid --profile observability}"

# Build the literal command string up front (rather than exporting a bash
# function) since watchfiles hands the target to the platform shell, which
# is not guaranteed to be bash.
TARGET_CMD="docker compose ${COMPOSE_FILES[*]} --env-file $ENV_FILE ${PROFILES[*]} up -d --build"

shopt -s nullglob
WATCH_TARGETS=()
for f in docker-compose.yml docker-compose.foundation.yml docker-compose.week2-ai.yml docker-compose.watch.yml Dockerfile.* "../.env" "$ENV_FILE"; do
  [ -e "$f" ] && WATCH_TARGETS+=("$f")
done
shopt -u nullglob

if [ "${#WATCH_TARGETS[@]}" -eq 0 ]; then
  echo "watch-infra.sh: no infra files found to watch (unexpected) — aborting" >&2
  exit 1
fi

echo "[watch-infra] watching for infra changes:"
printf '  %s\n' "${WATCH_TARGETS[@]}"
echo "[watch-infra] on change, will run: docker compose <files> --env-file <redacted> <profiles> up -d --build"
echo ""

exec watchfiles --filter all --target-type command "$TARGET_CMD" "${WATCH_TARGETS[@]}"
