#!/bin/bash
cd /mnt/g/ThunderMarketingCorp/HyerEnrichment/backend/docker

echo "=== Creating session and attempt ==="
SESSION_ID=$(curl -X POST http://localhost:8000/sessions \
  -H "Content-Type: application/json" \
  -d '{"session_type": "interview_practice"}' \
  -b cookies.txt -s | jq -r '.data.id')

echo "Session: $SESSION_ID"

ATTEMPT_ID=$(curl -X POST "http://localhost:8000/sessions/$SESSION_ID/attempts" \
  -H "Content-Type: application/json" \
  -d '{"response_type": "text", "text_response": "I have 5 years of Python experience building scalable microservices with FastAPI and Redis."}' \
  -b cookies.txt -s | jq -r '.data.id')

echo "Attempt: $ATTEMPT_ID"
echo
echo "Waiting 35 seconds for feedback generation..."
sleep 35

echo
echo "=== Result ==="
curl "http://localhost:8000/sessions/$SESSION_ID" -b cookies.txt -s | jq ".data.attempts[] | select(.id == \"$ATTEMPT_ID\") | {id, ai_score, has_feedback: (.ai_feedback != null)}"
