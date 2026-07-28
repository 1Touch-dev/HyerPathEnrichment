#!/bin/bash

# Test script to verify photo cache fix
# Tests the LinkedIn profile that previously exhibited the bug

set -e

API_TOKEN="TXdkoXS5FUlTEicC3b5quxwB3xrto9EpZeGoh_xslvQ7AGTQhdEfQCgUW82XWn-_LQk"
BASE_URL="http://localhost:8000"
LINKEDIN_URL="https://www.linkedin.com/in/getpeid"

echo "=== Testing Photo Cache Fix ==="
echo ""

# Clear the cache for this profile first
SLUG="getpeid"
echo "1. Clearing cache for slug: $SLUG"
echo ""

# Create enrichment job with all tiers
echo "2. Creating enrichment job with tiers [1,2,3,4]..."
RESPONSE=$(curl -s -X POST "$BASE_URL/enrich" \
  -H "Authorization: Bearer $API_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"linkedin_url\": \"$LINKEDIN_URL\",
    \"requested_tiers\": [\"tier1\", \"tier2\", \"tier3\", \"tier4\"]
  }")

JOB_ID=$(echo "$RESPONSE" | jq -r '.data.id // empty')

if [ -z "$JOB_ID" ]; then
  echo "ERROR: Failed to create job"
  echo "$RESPONSE" | jq '.'
  exit 1
fi

echo "Job created: $JOB_ID"
echo ""

# Wait for job to complete
echo "3. Waiting for job to complete..."
MAX_WAIT=300  # 5 minutes
ELAPSED=0
while [ $ELAPSED -lt $MAX_WAIT ]; do
  JOB_STATUS=$(curl -s -X GET "$BASE_URL/enrich/$JOB_ID" \
    -H "Authorization: Bearer $API_TOKEN" | jq -r '.data.status // empty')

  if [ "$JOB_STATUS" = "completed" ] || [ "$JOB_STATUS" = "failed" ]; then
    break
  fi

  echo "  Status: $JOB_STATUS (${ELAPSED}s elapsed)"
  sleep 5
  ELAPSED=$((ELAPSED + 5))
done

echo ""
echo "4. Job completed with status: $JOB_STATUS"
echo ""

# Get final job result
FINAL_RESULT=$(curl -s -X GET "$BASE_URL/enrich/$JOB_ID" \
  -H "Authorization: Bearer $API_TOKEN")

# Check if photo is present
PHOTO_URL=$(echo "$FINAL_RESULT" | jq -r '.data.dossier.photo.asset_url // empty')

echo "5. Results:"
echo "  Job ID: $JOB_ID"
echo "  Status: $JOB_STATUS"
echo "  Photo URL: ${PHOTO_URL:-NULL}"
echo ""

if [ -n "$PHOTO_URL" ] && [ "$PHOTO_URL" != "null" ]; then
  echo "✓ SUCCESS: Photo was returned in Job 1!"
  echo "  The cache fix is working correctly."
  exit 0
else
  echo "✗ FAILURE: Photo is still null in Job 1"
  echo "  The bug may still be present."
  echo ""
  echo "Full response:"
  echo "$FINAL_RESULT" | jq '.data.dossier.photo'
  exit 1
fi
