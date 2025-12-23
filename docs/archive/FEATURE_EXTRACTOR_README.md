# Device Feature Extractor - Sidecar Script

**Purpose:** Extract feature presence from Cisco devices WITHOUT capturing sensitive data.

This standalone script allows you to analyze devices in air-gapped or segmented networks, then transfer the sanitized feature snapshot for PSIRT analysis.

## 🔒 Security Features

**What is extracted:**
- Feature labels (e.g., `SEC_CoPP`, `MGMT_SSH_HTTP`, `MPLS_TE`)
- Platform type (IOS-XE, IOS-XR, ASA, FTD, NX-OS)
- Feature count and extraction timestamp

**What is NOT extracted:**
- ❌ No IP addresses
- ❌ No hostnames
- ❌ No passwords or secrets
- ❌ No usernames
- ❌ No configuration snippets
- ❌ No command outputs
- ❌ No device identifiers

## 📦 Installation

```bash
# Optional: Install netmiko for live device support
pip install netmiko

# PyYAML required (already in requirements.txt)
pip install pyyaml
```

## 🚀 Usage

### Live Device Mode

Extract features from a device via SSH:

```bash
# Basic usage (will prompt for password)
python extract_device_features.py \
  --host 192.168.1.1 \
  --username admin \
  --output device-snapshot.json

# With platform override
python extract_device_features.py \
  --host 192.168.1.1 \
  --username admin \
  --platform IOS-XR \
  --output device-snapshot.json

# With password in command (not recommended for production)
python extract_device_features.py \
  --host 192.168.1.1 \
  --username admin \
  --password MyPass123 \
  --output device-snapshot.json
```

### Offline Config Mode

Extract features from a saved config file:

```bash
# Offline analysis (no network connection needed)
python extract_device_features.py \
  --config running-config.txt \
  --platform IOS-XE \
  --output device-snapshot.json

# From a different directory
python extract_device_features.py \
  --config /path/to/config.txt \
  --platform ASA \
  --features-dir /path/to/cve_EVAL_V2 \
  --output snapshot.json
```

## 📄 Output Format

The script generates a sanitized JSON snapshot:

```json
{
  "snapshot_id": "snapshot-20251009-123000",
  "platform": "IOS-XE",
  "extracted_at": "2025-10-09T12:30:00.123456",
  "features_present": [
    "L2_STP",
    "MGMT_SSH_HTTP",
    "RTE_BGP",
    "SEC_CoPP"
  ],
  "feature_count": 4,
  "total_checked": 66,
  "extractor_version": "1.0.0"
}
```

## 🔄 Workflow for Air-Gapped Networks

1. **In Secure Network:**
   ```bash
   # Copy script to bastion host
   scp extract_device_features.py bastion:/tmp/

   # SSH to bastion
   ssh bastion

   # Run extraction
   python extract_device_features.py \
     --host 10.0.0.1 \
     --username admin \
     --output device1-snapshot.json
   ```

2. **Transfer Snapshot:**
   ```bash
   # Copy snapshot out (it's safe - no sensitive data!)
   scp device1-snapshot.json analyst-workstation:/tmp/
   ```

3. **Analyze with Web UI:**
   - Open PSIRT analyzer web UI
   - Paste snapshot JSON into "Pre-extracted Features" field
   - System compares PSIRT labels against snapshot
   - Get vulnerability assessment without live device access

## 🧪 Testing

Test with a sample config file:

```bash
# Create test config
cat > test-config.txt << 'EOF'
hostname TEST-SWITCH
!
spanning-tree mode rapid-pvst
!
interface GigabitEthernet1/0/1
 switchport mode access
 switchport access vlan 10
!
ip ssh version 2
!
router bgp 65000
 bgp log-neighbor-changes
 neighbor 10.0.0.1 remote-as 65001
!
control-plane
 service-policy input COPP-POLICY
!
end
EOF

# Extract features
python extract_device_features.py \
  --config test-config.txt \
  --platform IOS-XE \
  --output test-snapshot.json

# View results
cat test-snapshot.json
```

Expected output:
```json
{
  "snapshot_id": "snapshot-20251009-123456",
  "platform": "IOS-XE",
  "extracted_at": "2025-10-09T12:34:56.789012",
  "features_present": [
    "IF_Physical",
    "L2_STP",
    "L2_Switchport_Access",
    "MGMT_SSH_HTTP",
    "RTE_BGP",
    "SEC_CoPP"
  ],
  "feature_count": 6,
  "total_checked": 66,
  "extractor_version": "1.0.0"
}
```

## 🎯 Use Cases

### 1. Air-Gapped Production Networks
- Extract features on isolated network
- Transfer sanitized snapshot via approved channels
- Analyze PSIRTs offline

### 2. Batch Analysis
- Extract features from multiple devices
- Store snapshots in repository
- Analyze against new PSIRTs as they're published

### 3. Change Tracking
- Extract snapshots before/after config changes
- Compare feature drift over time
- Audit feature enablement

### 4. Compliance Validation
- Extract features from audit devices
- Verify required security features (CoPP, port-security, etc.)
- Generate compliance reports

## 🔧 Advanced Options

### Custom Features Directory

If features_*.yml files are in a different location:

```bash
python extract_device_features.py \
  --config config.txt \
  --platform IOS-XE \
  --features-dir /opt/psirt-analyzer \
  --output snapshot.json
```

### Different SSH Port

```bash
python extract_device_features.py \
  --host 192.168.1.1 \
  --username admin \
  --port 2222 \
  --output snapshot.json
```

### Different Device Type

For IOS-XR devices:

```bash
python extract_device_features.py \
  --host 192.168.1.1 \
  --username admin \
  --device-type cisco_xr \
  --platform IOS-XR \
  --output snapshot.json
```

## 📊 Supported Platforms

| Platform | Feature File | Label Count |
|----------|--------------|-------------|
| IOS-XE | features.yml | 66 |
| IOS-XR | features_iosxr.yml | 22 |
| ASA | features_asa.yml | 46 |
| FTD | features_ftd.yml | 46 |
| NX-OS | features_nxos.yml | 25 |

## ❓ Troubleshooting

### "netmiko not installed"

Install netmiko for live device support:
```bash
pip install netmiko
```

Or use offline mode with config files (no netmiko needed).

### "Feature file not found"

Ensure you're in the correct directory or use `--features-dir`:
```bash
python extract_device_features.py \
  --config config.txt \
  --platform IOS-XE \
  --features-dir /path/to/cve_EVAL_V2 \
  --output snapshot.json
```

### SSH Connection Timeout

Increase netmiko timeout by modifying the script (future enhancement) or save config to file first:
```bash
# On device
copy running-config tftp://server/config.txt

# Then use offline mode
python extract_device_features.py \
  --config config.txt \
  --platform IOS-XE \
  --output snapshot.json
```

## 🔗 Integration with Main Project

This sidecar script is part of the PSIRT Analysis System. See main project documentation for:
- Web UI integration (upload snapshot feature - coming soon)
- Backend API updates (accept pre-extracted features - coming soon)
- Complete vulnerability verification workflow

## 📝 Next Steps (Development)

1. ✅ Feature extractor script implemented
2. ⏳ Backend API endpoint to accept snapshots
3. ⏳ Frontend UI for snapshot upload/paste
4. ⏳ Batch processing for multiple devices
5. ⏳ Snapshot comparison and diff tools
