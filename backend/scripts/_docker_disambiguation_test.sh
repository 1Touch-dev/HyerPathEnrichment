#!/usr/bin/env bash
# Run stub + litellm disambiguation tests inside Docker api container.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$SCRIPT_DIR/../.." && pwd)"
DOCKER_DIR="$REPO/backend/docker"
ENV_FILE="$REPO/backend/.env"

cd "$DOCKER_DIR"

echo "== branch =="
git -C "$REPO" branch --show-current
git -C "$REPO" log -1 --oneline

echo "== start deps + litellm =="
docker compose --env-file "$ENV_FILE" --profile llm up -d postgres redis litellm

echo "== wait litellm =="
code="000"
for _ in $(seq 1 40); do
  code="$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:4000/v1/models 2>/dev/null || true)"
  [ "$code" = "200" ] && break
  code="$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:4000/health/liveliness 2>/dev/null || true)"
  [ "$code" = "200" ] && break
  sleep 3
done
echo "litellm http=$code"
if [ "$code" != "200" ]; then
  docker compose --env-file "$ENV_FILE" logs litellm --tail 40
  exit 1
fi

echo "== build api =="
docker compose --env-file "$ENV_FILE" up -d --build api
sleep 10

echo "== STUB test inside api =="
docker compose --env-file "$ENV_FILE" exec -T -e LLM_MODE=stub api sh -c 'cd /app/backend && python -' <<'PY'
import asyncio
from unittest.mock import AsyncMock
from app.config import get_settings
get_settings.cache_clear()
from app.models import EnrichmentRequest, SocialHandle
from app.enrichers.pipeline import Pipeline

async def main():
    s = get_settings()
    print("stub mode=", s.llm_mode)
    orch = Pipeline(db=AsyncMock())
    req = EnrichmentRequest(username="jane-doe", email="jane.doe@acme.com")
    handles = [
        SocialHandle(platform="X", username="jane_doe", profile_url="https://x.com/jane_doe", confidence=0.35),
        SocialHandle(platform="GitHub", username="totally-unrelated-bot-xyz-999", profile_url="https://github.com/totally-unrelated-bot-xyz-999", confidence=0.40),
        SocialHandle(platform="GitHub", username="jane-doe", profile_url="https://github.com/jane-doe", confidence=0.9),
    ]
    kept, dropped = await orch._disambiguate_handles(req, handles)
    names = {(h.platform, h.username) for h in kept}
    ok = ("GitHub", "jane-doe") in names and ("GitHub", "totally-unrelated-bot-xyz-999") not in names and ("X", "jane_doe") in names
    print("kept", [(h.platform, h.username, round(h.confidence, 2)) for h in kept], "dropped", dropped)
    print("STUB PASS" if ok else "STUB FAIL")
    raise SystemExit(0 if ok else 1)

asyncio.run(main())
PY

echo "== LITELLM test inside api =="
docker compose --env-file "$ENV_FILE" exec -T \
  -e LLM_MODE=litellm \
  -e LITELLM_API_BASE=http://litellm:4000 \
  -e LITELLM_MODEL=gemini/gemini-2.5-flash \
  -e LITELLM_FALLBACKS= \
  api sh -c 'cd /app/backend && python -c "from app.config import get_settings; get_settings.cache_clear()" && python -' \
  < "$SCRIPT_DIR/_e2e_litellm_disambiguate.py"

echo "== ALL DOCKER TESTS PASSED =="
