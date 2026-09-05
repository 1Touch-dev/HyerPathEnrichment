#!/usr/bin/env bash
# Stripe billing QA checklist — run AFTER test-mode credentials are configured.
# This script does not require live credentials to print the checklist; it only
# attempts Stripe CLI steps when STRIPE_* env vars are set and `stripe` is installed.
#
# Usage:
#   bash backend/scripts/billing_qa_when_keys_ready.sh
#   # or with env already exported:
#   ENABLE_BILLING=true STRIPE_SECRET_KEY=sk_test_... \
#     STRIPE_WEBHOOK_SECRET=whsec_... STRIPE_PRICE_ID_PREMIUM=price_... \
#     bash backend/scripts/billing_qa_when_keys_ready.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BACKEND="$ROOT/backend"

echo "=== Machine 2 Stripe Billing — credential QA checklist ==="
echo
echo "1) Configure backend/.env (or export):"
echo "   ENABLE_BILLING=true"
echo "   STRIPE_SECRET_KEY=sk_test_..."
echo "   STRIPE_WEBHOOK_SECRET=whsec_...   # from: stripe listen"
echo "   STRIPE_PRICE_ID_PREMIUM=price_..."
echo
echo "2) Start API (billing validation requires keys when ENABLE_BILLING=true)."
echo "3) Terminal A — forward webhooks:"
echo "   stripe listen --forward-to localhost:8000/api/billing/webhooks/stripe"
echo "4) Terminal B — trigger a test event:"
echo "   stripe trigger checkout.session.completed"
echo "5) Human smoke:"
echo "   - Free candidate: GET /api/job-matching/matches → is_blurred=true, no real explanation in JSON"
echo "   - Settings → Upgrade → Stripe Checkout test card 4242..."
echo "   - After webhook: matches show full explanation"
echo "   - Manage billing → cancel → next request blurred again"
echo "6) DevTools Network tab: blurred response body must not contain real match text"
echo

missing=0
for key in ENABLE_BILLING STRIPE_SECRET_KEY STRIPE_WEBHOOK_SECRET STRIPE_PRICE_ID_PREMIUM; do
  if [[ -z "${!key:-}" ]]; then
    echo "MISSING: $key"
    missing=1
  else
    echo "OK: $key is set"
  fi
done

if [[ "${ENABLE_BILLING:-}" != "true" ]]; then
  echo
  echo "ENABLE_BILLING is not 'true' — stopping before Stripe CLI steps."
  echo "Set credentials, then re-run this script."
  exit 0
fi

if [[ "$missing" -ne 0 ]]; then
  echo
  echo "Stripe keys incomplete — credential QA deferred. Re-run after filling env."
  exit 0
fi

if ! command -v stripe >/dev/null 2>&1; then
  echo
  echo "Stripe CLI not installed. Install from https://stripe.com/docs/stripe-cli"
  echo "then run: stripe listen --forward-to localhost:8000/api/billing/webhooks/stripe"
  exit 0
fi

echo
echo "Running: stripe trigger checkout.session.completed"
# Note: CLI fixtures may not include our client_reference_id; prefer human Checkout
# for full E2E. This still verifies the listen/forward path is healthy.
stripe trigger checkout.session.completed || {
  echo "stripe trigger failed — ensure you are logged in (stripe login) and keys match."
  exit 1
}

echo
echo "Credential smoke trigger sent. Complete the human checklist above in the UI."
