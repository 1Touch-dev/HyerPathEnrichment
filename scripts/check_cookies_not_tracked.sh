#!/usr/bin/env bash
# Fail if session cookie jars are tracked by git (FIND-INFRA-001 regression).
# Paths may exist locally but must never be committed.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

FORBIDDEN=(
  backend/cookies.txt
  backend/docker/cookies.txt
)

tracked="$(git ls-files -- "${FORBIDDEN[@]}" 2>/dev/null || true)"
if [[ -n "${tracked}" ]]; then
  echo "ERROR: session cookie jars must not be tracked by git:" >&2
  echo "${tracked}" >&2
  echo "Remove with: git rm --cached -- <path>  (files are gitignored)." >&2
  exit 1
fi

echo "cookie regression check: ok (backend/cookies.txt and backend/docker/cookies.txt not tracked)"
