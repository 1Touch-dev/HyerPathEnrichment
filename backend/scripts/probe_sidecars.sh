#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

service docker start >/dev/null 2>&1 || true
docker rm -f gmaps-probe sa-probe ev-probe 2>/dev/null || true

echo "== starting google-maps-scraper =="
docker run -d --name gmaps-probe -p 18080:8080 gosom/google-maps-scraper:latest -web -addr 0.0.0.0:8080
sleep 5

echo "== gmaps POST /api/v1/jobs =="
curl -sS -X POST http://localhost:18080/api/v1/jobs \
  -H 'Content-Type: application/json' \
  -d '{"name":"e2e-probe","keywords":["coffee shop San Francisco"],"depth":1,"lang":"en","max_time":180000000000}' | tee /tmp/gmaps-create.json
echo

JOB_ID=$(python3 -c 'import json;print(json.load(open("/tmp/gmaps-create.json"))["id"])')
echo "job_id=$JOB_ID"

echo "== gmaps GET /api/v1/jobs/$JOB_ID =="
curl -sS "http://localhost:18080/api/v1/jobs/$JOB_ID" | tee /tmp/gmaps-status.json
echo

echo "== gmaps GET /search (current enricher path) =="
curl -sS -o /dev/null -w "status=%{http_code}\n" "http://localhost:18080/search?q=coffee&depth=1" || true

echo "== building social-analyzer =="
rm -rf /tmp/social-analyzer-src
git clone --depth 1 https://github.com/qeeqbox/social-analyzer.git /tmp/social-analyzer-src
docker build -t social-analyzer:local /tmp/social-analyzer-src
docker run -d --name sa-probe -p 19005:9005 social-analyzer:local
sleep 15

echo "== social-analyzer GET /get_settings =="
curl -sS http://localhost:19005/get_settings | head -c 300
echo

echo "== social-analyzer POST /analyze_string =="
curl -sS -X POST http://localhost:19005/analyze_string \
  -H 'Content-Type: application/json' \
  -d '{"string":"torvalds","uuid":"e2e-probe-001","option":["FindUserProfilesFast"],"output":"json"}' \
  | tee /tmp/sa-analyze.json | head -c 800
echo

echo "== social-analyzer GET /search (current enricher path) =="
curl -sS -o /dev/null -w "status=%{http_code}\n" "http://localhost:19005/search?username=torvalds" || true

echo "== building email-verifier (AfterShip) =="
docker build -t email-verifier:local -f "$SCRIPT_DIR/../docker/Dockerfile.email-verifier" "$SCRIPT_DIR/../docker"
docker run -d --name ev-probe -p 18081:8080 email-verifier:local
sleep 8

echo "== email-verifier GET /v1/health@example.com/verification =="
curl -sS "http://localhost:18081/v1/health@example.com/verification" | head -c 300
echo

docker rm -f gmaps-probe sa-probe ev-probe 2>/dev/null || true
