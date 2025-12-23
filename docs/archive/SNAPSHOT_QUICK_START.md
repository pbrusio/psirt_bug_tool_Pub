# Feature Snapshot - Quick Start Guide

## 30-Second Overview

Extract features from a device in a **secure network**, transfer the **sanitized snapshot** (no secrets!), and verify PSIRTs **offline**.

## Quick Example

### 1. Extract Features (in secure network)

```bash
# Live device
python extract_device_features.py \
  --host 10.0.0.1 \
  --username admin \
  --output device1-snapshot.json

# OR offline config
python extract_device_features.py \
  --config /path/to/running-config.txt \
  --platform IOS-XE \
  --output device1-snapshot.json
```

**Output:** `device1-snapshot.json` (405 bytes, no sensitive data)

### 2. Transfer Snapshot Out

```bash
# Safe to transfer - contains only feature labels!
scp device1-snapshot.json analyst-workstation:/tmp/
```

### 3. Verify Against PSIRT (offline)

```bash
# Step A: Analyze PSIRT
curl -X POST http://localhost:8000/api/v1/analyze-psirt \
  -H "Content-Type: application/json" \
  -d '{
    "summary": "SSH vulnerability in IOS XE...",
    "platform": "IOS-XE"
  }'
# Returns: analysis_id

# Step B: Verify snapshot
curl -X POST http://localhost:8000/api/v1/verify-snapshot \
  -H "Content-Type: application/json" \
  -d '{
    "analysis_id": "YOUR-ANALYSIS-ID",
    "snapshot": '$(cat device1-snapshot.json)'
  }'
```

**Result:** `POTENTIALLY VULNERABLE` or `LIKELY NOT VULNERABLE`

## What's in a Snapshot?

```json
{
  "snapshot_id": "snapshot-20251009-133649",
  "platform": "IOS-XE",
  "extracted_at": "2025-10-09T13:36:49",
  "features_present": [
    "MGMT_SSH_HTTP",
    "SEC_CoPP",
    "RTE_BGP"
  ],
  "feature_count": 3,
  "total_checked": 66
}
```

**Contains:** Feature labels only
**Does NOT contain:** IPs, passwords, hostnames, configs

## Use Cases

| Use Case | Why Snapshot? |
|----------|---------------|
| **Air-gapped network** | Can't SSH from analyst workstation |
| **Compliance audit** | Need evidence of config state |
| **Batch analysis** | Analyze 100 devices against 50 PSIRTs |
| **Quick check** | Filter out safe devices before live SSH |

## Workflow

```
SECURE NETWORK              ANALYST WORKSTATION
┌───────────┐
│  Device   │  Extract          Analyze PSIRT
│           │  Features         ↓
└─────┬─────┘      ↓           Compare Labels
      │      snapshot.json     ↓
      └─────────────────────> VULNERABLE?
         (no secrets!)
```

## Installation

```bash
# For live device extraction
pip install netmiko pyyaml

# For offline extraction (no netmiko needed)
pip install pyyaml
```

## Testing

```bash
# Test extractor
python extract_device_features.py --config /tmp/test-config.txt --platform IOS-XE -o /tmp/snapshot.json

# Test API
./test_snapshot_api.sh
```

## Full Documentation

- **`FEATURE_EXTRACTOR_README.md`** - Complete extractor guide
- **`FEATURE_SNAPSHOT_IMPLEMENTATION.md`** - Technical details
- **API docs:** http://localhost:8000/docs

## Next Steps

1. **Extract snapshots** from your devices
2. **Store snapshots** in repository for reuse
3. **Analyze PSIRTs** as they're published
4. **Recommend live SSH** if features present

## Questions?

- **Q:** Is the snapshot safe to share?
  **A:** Yes! It contains only feature labels (no IPs, passwords, configs).

- **Q:** What about version checking?
  **A:** Snapshot mode does feature-only checks. For complete verification, use live SSH.

- **Q:** Can I extract from offline configs?
  **A:** Yes! Use `--config` flag (no netmiko required).

- **Q:** How do I update the UI?
  **A:** See "Frontend Integration" section in `FEATURE_SNAPSHOT_IMPLEMENTATION.md`
