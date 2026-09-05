#!/bin/bash
set -e

cd /mnt/g/ThunderMarketingCorp/HyerEnrichment/backend/docker

echo "=== Creating new session and attempt ==="
SESSION_ID=$(curl -X POST http://localhost:8000/sessions \
  -H 'Content-Type: application/json' \
  -d '{"session_type": "interview_practice"}' \
  -b cookies.txt -s | jq -r '.data.id')

echo "Session ID: $SESSION_ID"

echo -e "\n=== Submitting attempt ==="
curl -X POST "http://localhost:8000/sessions/$SESSION_ID/attempts" \
  -H 'Content-Type: application/json' \
  -d '{
    "response_type": "text",
    "text_response": "I have strong problem-solving skills and 3 years of Python experience. I built APIs with FastAPI and worked on microservices architecture."
  }' \
  -b cookies.txt -s | jq .

echo -e "\n=== Waiting 35 seconds for feedback generation ==="
sleep 35

echo -e "\n=== Checking for feedback ==="
curl "http://localhost:8000/sessions/$SESSION_ID" \
  -b cookies.txt -s | jq '.data.attempts[] | select(.ai_score != null)'
