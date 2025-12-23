#!/bin/bash
# Test the new snapshot verification API endpoint

set -e

echo "=================================="
echo "Testing Snapshot Verification API"
echo "=================================="

# Step 1: Analyze a PSIRT
echo -e "\n📊 Step 1: Analyzing PSIRT..."
ANALYSIS_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/analyze-psirt \
  -H "Content-Type: application/json" \
  -d '{
    "summary": "A vulnerability in the SSH and SNMP subsystem of Cisco IOS XE Software could allow an authenticated attacker to cause a denial of service.",
    "platform": "IOS-XE",
    "advisory_id": "TEST-SNAPSHOT-001"
  }')

ANALYSIS_ID=$(echo "$ANALYSIS_RESPONSE" | python3 -c "import json, sys; print(json.load(sys.stdin)['analysis_id'])")
LABELS=$(echo "$ANALYSIS_RESPONSE" | python3 -c "import json, sys; print(json.load(sys.stdin)['predicted_labels'])")

echo "✅ Analysis ID: $ANALYSIS_ID"
echo "✅ Predicted Labels: $LABELS"

# Step 2: Load test snapshot
echo -e "\n📂 Step 2: Loading test snapshot..."
SNAPSHOT=$(cat /tmp/test-snapshot.json)
echo "✅ Snapshot loaded"

# Step 3: Verify snapshot against PSIRT
echo -e "\n🔍 Step 3: Verifying snapshot against PSIRT..."
VERIFY_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/verify-snapshot \
  -H "Content-Type: application/json" \
  -d "{
    \"analysis_id\": \"$ANALYSIS_ID\",
    \"snapshot\": $SNAPSHOT
  }")

echo "$VERIFY_RESPONSE" | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(f\"✅ Verification ID: {data['verification_id']}\")
print(f\"✅ Status: {data['overall_status']}\")
print(f\"✅ Reason: {data['reason']}\")
print(f\"✅ Features Present: {data['feature_check']['present']}\")
print(f\"✅ Features Absent: {data['feature_check']['absent']}\")
"

echo -e "\n✅ Test complete!"
