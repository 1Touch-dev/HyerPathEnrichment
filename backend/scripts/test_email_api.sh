#!/bin/bash
# E2E Email Service Test Script
# Tests the email API endpoint with proper authentication

API_TOKEN="${API_TOKEN:-TXdkoXS5FUlTEicC3b5quxwB3xrto9EpZeGoh_xslvQ7AGTQhdEfQCgUW82XWn-_LQk}"
API_URL="${API_URL:-http://localhost:8000}"
RECIPIENT="${RECIPIENT:-ringtones786110@gmail.com}"

echo "🧪 Testing Email Service E2E"
echo "================================"
echo "API URL: $API_URL"
echo "Recipient: $RECIPIENT"
echo ""

# Test 1: Send test email
echo "📧 Sending test email..."
RESPONSE=$(curl -s -X POST "$API_URL/api/email/test" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_TOKEN" \
  -d "{\"recipient\": \"$RECIPIENT\"}")

echo "Response: $RESPONSE"
echo ""

# Check if successful
if echo "$RESPONSE" | grep -q '"success":true'; then
    echo "✅ Email queued successfully!"
    echo ""
    echo "📥 Check inbox at: $RECIPIENT"
    echo ""
    echo "🔍 To monitor worker processing:"
    echo "   docker compose --env-file ../.env.production logs -f worker-email"
    exit 0
elif echo "$RESPONSE" | grep -q 'UNAUTHORIZED'; then
    echo "❌ Authentication failed - check API_TOKEN"
    exit 1
else
    echo "❌ Request failed - check error above"
    exit 1
fi
