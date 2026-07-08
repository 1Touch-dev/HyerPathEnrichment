#!/usr/bin/env bash
set -euo pipefail
service docker start >/dev/null 2>&1 || true
docker rm -f gmaps-probe 2>/dev/null || true
docker run -d --name gmaps-probe -p 18080:8080 gosom/google-maps-scraper:latest -web -addr 0.0.0.0:8080
sleep 5
CREATE=$(curl -sS -X POST http://localhost:18080/api/v1/jobs \
  -H 'Content-Type: application/json' \
  -d '{"name":"e2e-probe","keywords":["starbucks san francisco"],"depth":1,"lang":"en","max_time":180000000000,"fast_mode":true}')
echo "create=$CREATE"
JOB=$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["id"])' "$CREATE")
echo "job=$JOB"
for i in $(seq 1 36); do
  STATUS_JSON=$(curl -sS "http://localhost:18080/api/v1/jobs/$JOB")
  STATUS=$(python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("Status", d.get("status", "?")))' <<<"$STATUS_JSON")
  echo "poll $i status=$STATUS"
  if [ "$STATUS" != "pending" ] && [ "$STATUS" != "working" ]; then
    echo "$STATUS_JSON" | python3 -m json.tool | head -60
    echo "--- download head ---"
    curl -sS "http://localhost:18080/api/v1/jobs/$JOB/download" | head -5
    break
  fi
  sleep 10
done
