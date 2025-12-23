#!/bin/bash

set -e

echo "🧪 Testing Snapshot Verification API"
echo "===================================="
echo ""

# Step 1: Analyze PSIRT
echo "📊 Step 1: Analyzing PSIRT..."
ANALYSIS_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/analyze-psirt \
  -H "Content-Type: application/json" \
  -d '{
    "summary": "A vulnerability in the SNMP subsystem allows DoS",
    "platform": "IOS-XE",
    "advisory_id": "test-snapshot-001"
  }')

ANALYSIS_ID=$(echo "$ANALYSIS_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['analysis_id'])")
PREDICTED_LABELS=$(echo "$ANALYSIS_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['predicted_labels'])")

echo "✅ Analysis ID: $ANALYSIS_ID"
echo "✅ Predicted labels: $PREDICTED_LABELS"
echo ""

# Step 2: Verify with snapshot
echo "📦 Step 2: Verifying with snapshot..."
VERIFY_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/verify-snapshot \
  -H "Content-Type: application/json" \
  -d "{
    \"analysis_id\": \"$ANALYSIS_ID\",
    \"snapshot\": {
      \"snapshot_id\": \"snapshot-test-20251010\",
      \"platform\": \"IOS-XE\",
      \"extracted_at\": \"2025-10-10T14:00:00.000000\",
      \"features_present\": [\"MGMT_SSH_HTTP\", \"SEC_CoPP\", \"MGMT_SNMP\"],
      \"feature_count\": 3,
      \"total_checked\": 66,
      \"extractor_version\": \"1.0.0-standalone\"
    }
  }")

echo "$VERIFY_RESPONSE" | python3 -m json.tool

echo ""
echo "✅ Snapshot verification test complete!"
