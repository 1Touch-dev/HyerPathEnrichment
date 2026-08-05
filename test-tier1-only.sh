#!/bin/bash
# Test script for tier1 ONLY (LinkedIn photo enrichment)
# Tests all 3 profiles with correct API format

API_URL="http://127.0.0.1:8000"
API_TOKEN="TXdkoXS5FUlTEicC3b5quxwB3xrto9EpZeGoh_xslvQ7AGTQhdEfQCgUW82XWn-_LQk"

# Test profiles
PROFILES=(
    "https://www.linkedin.com/in/diwakarmishra4/"
    "https://www.linkedin.com/in/sumit-kumar-24a9a31a2/"
    "https://www.linkedin.com/in/anjali-horo-64166970/"
)

PROFILE_NAMES=(
    "diwakarmishra4"
    "sumit-kumar-24a9a31a2"
    "anjali-horo-64166970"
)

echo "==================================================="
echo "Testing Tier1 ONLY (LinkedIn Photo Enrichment)"
echo "==================================================="
echo ""

SUCCESS_COUNT=0
FAILED_PROFILES=()

for i in "${!PROFILES[@]}"; do
    PROFILE_URL="${PROFILES[$i]}"
    PROFILE_NAME="${PROFILE_NAMES[$i]}"

    echo "---------------------------------------------------"
    echo "Test $((i+1))/3: $PROFILE_NAME"
    echo "URL: $PROFILE_URL"
    echo "---------------------------------------------------"

    # Submit enrichment request - TIER1 ONLY, correct format
    echo "Submitting tier1 enrichment request..."
    RESPONSE=$(curl -s -X POST "$API_URL/enrich" \
        -H "Authorization: Bearer $API_TOKEN" \
        -H "Content-Type: application/json" \
        -d "{
            \"linkedin_url\": \"$PROFILE_URL\",
            \"requested_tiers\": [\"tier1\"],
            \"sync\": false
        }")

    JOB_ID=$(echo "$RESPONSE" | jq -r '.data.id // empty')

    if [ -z "$JOB_ID" ]; then
        echo "❌ FAILED: Could not get job ID"
        echo "Response: $RESPONSE"
        FAILED_PROFILES+=("$PROFILE_NAME: Could not get job ID")
        echo ""
        continue
    fi

    echo "Job ID: $JOB_ID"
    echo "Waiting for job to complete (tier1 only)..."

    # Poll job status (max 2 minutes)
    MAX_ATTEMPTS=24
    ATTEMPT=0
    JOB_STATUS=""

    while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
        sleep 5
        ATTEMPT=$((ATTEMPT + 1))

        JOB_RESPONSE=$(curl -s -X GET "$API_URL/enrich/$JOB_ID" \
            -H "Authorization: Bearer $API_TOKEN")

        JOB_STATUS=$(echo "$JOB_RESPONSE" | jq -r '.data.status // empty')

        echo -n "."

        if [ "$JOB_STATUS" == "completed" ] || [ "$JOB_STATUS" == "failed" ] || [ "$JOB_STATUS" == "suppressed" ]; then
            echo ""
            break
        fi
    done

    echo "Job Status: $JOB_STATUS"

    # Check photo result
    if [ "$JOB_STATUS" == "completed" ]; then
        PHOTO_URL=$(echo "$JOB_RESPONSE" | jq -r '.data.dossier.photo // empty')

        if [ -n "$PHOTO_URL" ] && [ "$PHOTO_URL" != "null" ]; then
            echo "✅ SUCCESS: Photo URL found"
            echo "   Photo: $PHOTO_URL"
            SUCCESS_COUNT=$((SUCCESS_COUNT + 1))

            # Verify photo is accessible
            HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$PHOTO_URL")
            if [ "$HTTP_CODE" == "200" ]; then
                echo "   ✓ Photo is accessible (HTTP 200)"
            else
                echo "   ⚠ Warning: Photo returned HTTP $HTTP_CODE"
            fi
        else
            echo "❌ FAILED: No photo URL in response"
            FAILED_PROFILES+=("$PROFILE_NAME: No photo URL")
        fi
    else
        echo "❌ FAILED: Job status is $JOB_STATUS"
        FAILED_PROFILES+=("$PROFILE_NAME: Job status $JOB_STATUS")
    fi

    echo ""
done

echo "==================================================="
echo "Test Results Summary"
echo "==================================================="
echo "Total Profiles: ${#PROFILES[@]}"
echo "Successful: $SUCCESS_COUNT"
echo "Failed: $((${#PROFILES[@]} - SUCCESS_COUNT))"
echo ""

if [ ${#FAILED_PROFILES[@]} -gt 0 ]; then
    echo "Failed Profiles:"
    for failure in "${FAILED_PROFILES[@]}"; do
        echo "  - $failure"
    done
    echo ""
fi

if [ $SUCCESS_COUNT -eq ${#PROFILES[@]} ]; then
    echo "🎉 ALL TESTS PASSED - Ready to create PR!"
    exit 0
else
    echo "❌ SOME TESTS FAILED - DO NOT create PR yet"
    exit 1
fi
