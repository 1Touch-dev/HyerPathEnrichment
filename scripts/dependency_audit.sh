#!/usr/bin/env bash
# Scan backend (pip) and frontend (npm) dependencies for known high/critical CVEs.
# Used by CI and `make audit`. Exit non-zero on findings at or above --audit-level=high.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="${ROOT}/backend"
FRONTEND_DIR="${ROOT}/frontend"

echo "=== Python dependency audit (backend[dev]) ==="
python3 -m pip install -e "${BACKEND_DIR}[dev]" -q
python3 -m pip_audit --desc on --progress-spinner off

echo ""
echo "=== Python dependency audit (backend[enrichers]) ==="
python3 -m pip install -e "${BACKEND_DIR}[enrichers]" -q
# python-jobspy pins markdownify<0.14; track PYSEC-2026-1604 until jobspy updates.
python3 -m pip_audit --desc on --progress-spinner off --ignore-vuln PYSEC-2026-1604

echo ""
echo "=== Frontend dependency audit (npm) ==="
cd "${FRONTEND_DIR}"
npm ci --silent
npm run audit:ci

echo ""
echo "dependency audit: ok"
