#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCKER_DIR="$(cd "$SCRIPT_DIR/../docker" && pwd)"

service docker start >/dev/null 2>&1 || true
docker rm -f gmaps-probe sa-probe ev-probe 2>/dev/null || true

echo "== building google-maps-scraper (same Dockerfile as compose) =="
docker build -t google-maps-scraper:local -f "$DOCKER_DIR/Dockerfile.google-maps-scraper" "$DOCKER_DIR"
docker run -d --name gmaps-probe -p 18080:8080 google-maps-scraper:local -web -addr 0.0.0.0:8080 -data-folder /gmapsdata
sleep 5

echo "== gmaps POST /api/v1/jobs (enricher path) =="
curl -sS -X POST http://localhost:18080/api/v1/jobs \
  -H 'Content-Type: application/json' \
  -d '{"name":"e2e-probe","keywords":["coffee shop San Francisco"],"depth":1,"lang":"en","max_time":180000000000}' | tee /tmp/gmaps-create.json
echo

JOB_ID=$(python3 -c 'import json;print(json.load(open("/tmp/gmaps-create.json"))["id"])')
echo "job_id=$JOB_ID"

echo "== gmaps GET /api/v1/jobs/$JOB_ID (enricher path) =="
curl -sS "http://localhost:18080/api/v1/jobs/$JOB_ID" | tee /tmp/gmaps-status.json
echo

echo "== gmaps GET /search (legacy endpoint — not used by enricher) =="
curl -sS -o /dev/null -w "status=%{http_code}\n" "http://localhost:18080/search?q=coffee&depth=1" || true

echo "== building social-analyzer =="
rm -rf /tmp/social-analyzer-src
git clone --depth 1 https://github.com/qeeqbox/social-analyzer.git /tmp/social-analyzer-src
docker build -t social-analyzer:local /tmp/social-analyzer-src
docker run -d --name sa-probe -p 19005:9005 social-analyzer:local
sleep 15

echo "== social-analyzer GET /get_settings (enricher path) =="
curl -sS http://localhost:19005/get_settings | head -c 300 || true
echo

echo "== social-analyzer POST /analyze_string (enricher path) =="
curl -sS -X POST http://localhost:19005/analyze_string \
  -H 'Content-Type: application/json' \
  -d '{"string":"torvalds","uuid":"e2e-probe-001","option":["FindUserProfilesFast"],"output":"json"}' \
  | tee /tmp/sa-analyze.json | head -c 800 || true
echo

echo "== social-analyzer GET /search (legacy endpoint — not used by enricher) =="
curl -sS -o /dev/null -w "status=%{http_code}\n" "http://localhost:19005/search?username=torvalds" || true

echo "== building email-verifier (AfterShip) =="
docker build -t email-verifier:local -f "$DOCKER_DIR/Dockerfile.email-verifier" "$DOCKER_DIR"
docker run -d --name ev-probe -p 18081:8080 email-verifier:local
sleep 8

echo "== email-verifier GET /v1/health@example.com/verification (enricher path) =="
curl -sS "http://localhost:18081/v1/health@example.com/verification" | head -c 300 || true
echo

docker rm -f gmaps-probe sa-probe ev-probe 2>/dev/null || true
