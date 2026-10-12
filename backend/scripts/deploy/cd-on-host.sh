#!/usr/bin/env bash
# cd-on-host.sh — single-host production CD (full Day-1 stack, no Multilogin).
# Invoked by .github/workflows/deploy.yml over SSH. Never git commit / git push.
#
# Required env:
#   DEPLOY_SHA
#   API_IMAGE WORKER_IMAGE WORKER_DOCUMENT_IMAGE
#   WORKER_EMBEDDING_IMAGE WORKER_JOB_MATCHING_IMAGE
#   GHCR_USER GHCR_TOKEN
set -euo pipefail
# When Actions extracts this file to /tmp, REPO_ROOT must point at the checkout.
if [[ -n "${REPO_ROOT:-}" ]]; then
  SCRIPT_DIR="${REPO_ROOT}/backend/scripts/deploy"
else
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fi
# shellcheck source=_common.sh
source "$SCRIPT_DIR/_common.sh"

DEPLOY_STATE="${REPO_ROOT}/.deploy"
HOLD_FILE="${DEPLOY_STATE}/hold"
OVERLAY="${COMPOSE_DIR}/docker-compose.cd-images.yml"
IMAGE_TAG="${IMAGE_TAG:-${DEPLOY_SHA:-}}"

log() { echo "==> $*"; }

if [[ -f "$HOLD_FILE" ]]; then
  echo "HOLD: ${HOLD_FILE} exists — skipping CD (hotfix in progress)."
  echo "Remove the hold file when you want automatic deploys again."
  exit 0
fi

require_env() {
  local name="$1"
  if [[ -z "${!name:-}" ]]; then
    echo "ERROR: ${name} is required" >&2
    exit 1
  fi
}

require_env DEPLOY_SHA
require_env API_IMAGE
require_env WORKER_IMAGE
require_env WORKER_DOCUMENT_IMAGE
require_env WORKER_EMBEDDING_IMAGE
require_env WORKER_JOB_MATCHING_IMAGE
require_env GHCR_USER
require_env GHCR_TOKEN
require_env IMAGE_TAG

cd "$REPO_ROOT"

log "Fetching origin"
git fetch origin

if [[ -n "$(git status --porcelain)" ]]; then
  echo "ERROR: working tree is dirty; refusing to reset. Commit, stash, or revert local edits." >&2
  git status --porcelain >&2
  exit 1
fi

if git rev-parse --abbrev-ref --symbolic-full-name '@{u}' >/dev/null 2>&1; then
  unpushed="$(git rev-list --count origin/main..HEAD 2>/dev/null || echo 0)"
else
  unpushed="$(git rev-list --count origin/main..HEAD 2>/dev/null || echo 0)"
fi
if [[ "${unpushed}" != "0" ]]; then
  echo "ERROR: ${unpushed} unpushed commit(s) on this branch vs origin/main; refusing to reset." >&2
  git log --oneline origin/main..HEAD >&2 || true
  exit 1
fi

if ! git cat-file -t "${DEPLOY_SHA}" >/dev/null 2>&1; then
  echo "ERROR: DEPLOY_SHA ${DEPLOY_SHA} is not available after git fetch" >&2
  exit 1
fi

log "Checking out main at ${DEPLOY_SHA} (not detached)"
git checkout main
git reset --hard "${DEPLOY_SHA}"
# Re-load helpers from the deployed SHA (profiles / service list).
# shellcheck source=_common.sh
source "$SCRIPT_DIR/_common.sh"

mkdir -p "$DEPLOY_STATE"
if [[ -f "${DEPLOY_STATE}/current_sha" ]]; then
  cp "${DEPLOY_STATE}/current_sha" "${DEPLOY_STATE}/previous_sha"
fi
echo "${DEPLOY_SHA}" > "${DEPLOY_STATE}/candidate_sha"

log "Writing ${OVERLAY}"
{
  echo "services:"
  echo "  migrate:"
  echo "    image: ${API_IMAGE}:${IMAGE_TAG}"
  echo "  api:"
  echo "    image: ${API_IMAGE}:${IMAGE_TAG}"
  echo "  worker:"
  echo "    image: ${WORKER_IMAGE}:${IMAGE_TAG}"
  echo "  worker-email:"
  echo "    image: ${WORKER_IMAGE}:${IMAGE_TAG}"
  echo "  worker-cleanup:"
  echo "    image: ${WORKER_IMAGE}:${IMAGE_TAG}"
  echo "  worker-tier234:"
  echo "    image: ${WORKER_IMAGE}:${IMAGE_TAG}"
  echo "  worker-interview-ai:"
  echo "    image: ${WORKER_IMAGE}:${IMAGE_TAG}"
  echo "  worker-document:"
  echo "    image: ${WORKER_DOCUMENT_IMAGE}:${IMAGE_TAG}"
  echo "  worker-embedding:"
  echo "    image: ${WORKER_EMBEDDING_IMAGE}:${IMAGE_TAG}"
  echo "  worker-job-matching:"
  echo "    image: ${WORKER_JOB_MATCHING_IMAGE}:${IMAGE_TAG}"
} > "$OVERLAY"

compose_cd() {
  compose -f docker-compose.cd-images.yml "$@"
}

log "Validating compose config"
if ! compose_cd config >/dev/null; then
  echo "ERROR: docker compose config failed; stack not touched" >&2
  compose_cd config >&2 || true
  exit 1
fi

log "GHCR login"
echo "${GHCR_TOKEN}" | docker login ghcr.io -u "${GHCR_USER}" --password-stdin

log "Pulling CD-pinned app images"
compose_cd pull "${CD_APP_SERVICES[@]}"

log "Starting postgres + redis (no-build)"
compose_cd up -d --no-build postgres redis

log "Waiting for postgres healthy"
cid=""
for _ in $(seq 1 90); do
  cid="$(postgres_container)"
  if [[ -n "$cid" ]] && docker inspect -f '{{.State.Health.Status}}' "$cid" 2>/dev/null | grep -q healthy; then
    break
  fi
  sleep 2
done
cid="$(postgres_container)"
if [[ -z "$cid" ]]; then
  echo "ERROR: postgres did not become healthy" >&2
  exit 1
fi

log "Ensuring langfuse + glitchtip databases exist"
PGUSER="$(env_get POSTGRES_USER)"
PGUSER="${PGUSER:-hyrepath}"
for db in langfuse glitchtip; do
  docker exec -i "$cid" psql -U "$PGUSER" -d postgres -tc "SELECT 1 FROM pg_database WHERE datname='${db}'" | grep -q 1 \
    || docker exec -i "$cid" psql -U "$PGUSER" -d postgres -c "CREATE DATABASE ${db} OWNER ${PGUSER};"
done

log "Starting full Day-1 stack (no-build, no Multilogin)"
compose_cd up -d --no-build "${DAY1_SERVICES[@]}"

log "Frontend (full Next.js)"
bash "${SCRIPT_DIR}/08-redeploy-frontend.sh"

log "Health"
if ! bash "${SCRIPT_DIR}/99-health.sh"; then
  echo "ERROR: health failed; current_sha not advanced" >&2
  {
    echo "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
    echo "SHA=${DEPLOY_SHA}"
    echo "PREVIOUS=$(cat "${DEPLOY_STATE}/previous_sha" 2>/dev/null || echo none)"
    echo "RESULT=HEALTH_FAIL"
  } >> "${DEPLOY_STATE}/history.log"
  exit 1
fi

echo "${DEPLOY_SHA}" > "${DEPLOY_STATE}/current_sha"
{
  echo "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
  echo "SHA=${DEPLOY_SHA}"
  echo "PREVIOUS=$(cat "${DEPLOY_STATE}/previous_sha" 2>/dev/null || echo none)"
  echo "RESULT=SUCCESS"
} >> "${DEPLOY_STATE}/history.log"

log "Deployed ${DEPLOY_SHA} (branch=$(git branch --show-current))"
