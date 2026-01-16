#!/bin/bash

BASE_URL="http://localhost:8000"

echo "=== Gmail Agent API Test (Direct Composio - No OpenAI) ==="
echo ""

# Health check
echo "1. Health Check"
curl -s "$BASE_URL/health" | python3 -m json.tool
echo ""

# Check connection exists
echo "2. Check Connection Exists"
curl -s -X POST "$BASE_URL/connection/exists" | python3 -m json.tool
echo ""

# Fetch emails
echo "3. Fetch Emails"
curl -s -X POST "$BASE_URL/actions/fetch_emails" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "default", "limit": 3}' | python3 -m json.tool
echo ""

# Send email (uncomment to test)
# echo "4. Send Email"
# curl -s -X POST "$BASE_URL/actions/send_email" \
#   -H "Content-Type: application/json" \
#   -d '{
#     "user_id": "default",
#     "recipient_email": "test@example.com",
#     "subject": "Test from Gmail Agent",
#     "body": "This is a test email sent via Composio direct API."
#   }' | python3 -m json.tool

echo "=== Done ==="
