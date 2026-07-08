#!/usr/bin/env bash
set -euo pipefail
JOB=3bd8961a-b04c-4967-adcf-773cab8e09ee
curl -sS "http://localhost:18080/api/v1/jobs/$JOB" | python3 -m json.tool | head -80
echo "--- download ---"
curl -sS -D - "http://localhost:18080/api/v1/jobs/$JOB/download" | head -40
