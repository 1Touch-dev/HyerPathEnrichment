set -e
export E2E_BASE_URL=http://127.0.0.1:8000
export SOCIAL_ANALYZER_URL=http://social-analyzer:9005
export GMAPS_SCRAPER_URL=http://google-maps-scraper:8080
export EMAIL_VERIFIER_URL=http://email-verifier:8080
export GITRECON_SCRIPT=/opt/gitrecon/gitrecon.py
export GMAPS_JOB_TIMEOUT_SECONDS="${GMAPS_JOB_TIMEOUT_SECONDS:-300}"
export GMAPS_JOB_POLL_SECONDS="${GMAPS_JOB_POLL_SECONDS:-10}"
export E2E_BACKEND_ROOT=/app/backend
cd /app/backend
mkdir -p /app/backend/.e2e-results
test -f "${GITRECON_SCRIPT}"
python /tmp/probe_enrichers.py --canary docs/tier234_canary_set.json --json
