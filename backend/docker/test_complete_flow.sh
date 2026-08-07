#!/usr/bin/env bash
set -e

cd /mnt/g/ThunderMarketingCorp/HyerEnrichment/backend/docker

echo "=== Testing Complete Feedback Flow ==="
echo

# Step 1: Login and get session
echo "1. Creating session..."
SESSION_ID=$(curl -X POST http://localhost:8000/sessions \
  -H 'Content-Type: application/json' \
  -d '{"session_type": "interview_practice"}' \
  -b cookies.txt -s | jq -r '.data.id')

echo "   Session ID: $SESSION_ID"
echo

# Step 2: Submit attempt
echo "2. Submitting test attempt..."
ATTEMPT_RESPONSE=$(curl -X POST "http://localhost:8000/sessions/$SESSION_ID/attempts" \
  -H 'Content-Type: application/json' \
  -d '{
    "response_type": "text",
    "text_response": "I have 5 years of experience building scalable microservices with Python and FastAPI. I implemented rate limiting, circuit breakers, and comprehensive monitoring. I led a team that improved our API response time from 2 seconds to 200ms by optimizing database queries and implementing Redis caching."
  }' \
  -b cookies.txt -s)

ATTEMPT_ID=$(echo "$ATTEMPT_RESPONSE" | jq -r '.data.id')
echo "   Attempt ID: $ATTEMPT_ID"
echo

# Step 3: Check queue length
echo "3. Checking feedback queue..."
QUEUE_LENGTH=$(docker compose --env-file ../.env.production exec redis redis-cli LLEN rq:queue:feedback)
echo "   Jobs in queue: $QUEUE_LENGTH"
echo

# Step 4: Monitor worker logs
echo "4. Watching worker logs for 40 seconds..."
echo "   (Looking for feedback generation messages)"
echo
timeout 40s docker compose --env-file ../.env.production logs worker -f --tail 20 2>&1 | grep -E "(feedback|generate_feedback_job|Successfully completed)" || true
echo

# Step 5: Check the result
echo "5. Checking attempt results..."
RESULT=$(curl "http://localhost:8000/sessions/$SESSION_ID" -b cookies.txt -s)

AI_SCORE=$(echo "$RESULT" | jq -r ".data.attempts[] | select(.id == \"$ATTEMPT_ID\") | .ai_score")
HAS_FEEDBACK=$(echo "$RESULT" | jq -r ".data.attempts[] | select(.id == \"$ATTEMPT_ID\") | .ai_feedback != null")

echo "   AI Score: $AI_SCORE"
echo "   Has Feedback: $HAS_FEEDBACK"
echo

# Step 6: Check database directly
echo "6. Checking database..."
docker compose --env-file ../.env.production exec -T postgres psql -U hyrepath -d hyrepath << EOF
SELECT
    id,
    ai_score,
    length(ai_feedback) as feedback_length,
    jsonb_object_keys(score_breakdown) as breakdown_keys
FROM question_attempts
WHERE id = '$ATTEMPT_ID';
EOF

echo
echo "=== Test Complete ==="
echo
if [ "$AI_SCORE" != "null" ]; then
    echo "✅ SUCCESS: Feedback generation is working!"
    echo "   Score: $AI_SCORE"
else
    echo "❌ FAILED: No feedback generated"
    echo "   Check worker logs above for errors"
fi
