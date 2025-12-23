# IOS-XE Feature Extractor - Air-Gapped Sidecar

## 🎯 Purpose

Standalone, single-file script for extracting IOS-XE feature presence in **completely air-gapped environments**.

## ✅ Key Features

- **✨ ZERO external dependencies** (no YAML files, no PyYAML library)
- **📦 Single file** - just copy and run
- **🔒 Air-gapped ready** - works 100% offline
- **🚫 No sensitive data** - only feature labels extracted
- **66 IOS-XE features** embedded in script
- **Only requires Python 3.6+** (already on most systems)

## 🚀 Quick Start

### Air-Gapped Deployment

```bash
# 1. Copy single file to air-gapped network
scp extract_iosxe_features_standalone.py bastion:/tmp/

# 2. SSH to bastion
ssh bastion

# 3. Extract features from device config
python3 extract_iosxe_features_standalone.py \
  --config running-config.txt \
  --output device-snapshot.json

# 4. Transfer sanitized snapshot out (safe - no secrets!)
scp device-snapshot.json analyst-workstation:/tmp/
```

### Usage Examples

**Offline Mode (NO dependencies!):**
```bash
# From saved config file
python3 extract_iosxe_features_standalone.py \
  --config /path/to/running-config.txt \
  --output snapshot.json
```

**Live Device Mode (requires netmiko):**
```bash
# If netmiko is available
python3 extract_iosxe_features_standalone.py \
  --host 192.168.1.1 \
  --username admin \
  --output snapshot.json
```

## 📦 What's Included

```
sidecar_extractor/
├── extract_iosxe_features_standalone.py    # ← THE ONLY FILE YOU NEED
├── iosxe_taxonomy_embedded.json            # Reference (already embedded in script)
└── README.md                               # This file
```

## 🔍 What Gets Extracted

**Output Format:**
```json
{
  "snapshot_id": "snapshot-20251009-140919",
  "platform": "IOS-XE",
  "extracted_at": "2025-10-09T14:09:19",
  "features_present": [
    "MGMT_SSH_HTTP",
    "SEC_CoPP",
    "RTE_BGP",
    "L2_STP"
  ],
  "feature_count": 4,
  "total_checked": 66,
  "extractor_version": "1.0.0-standalone"
}
```

**What's Extracted:**
- ✅ Feature labels (e.g., `MGMT_SSH_HTTP`, `SEC_CoPP`)
- ✅ Platform (always `IOS-XE` for this script)
- ✅ Feature count and timestamp

**What's NOT Extracted:**
- ❌ No IP addresses
- ❌ No hostnames
- ❌ No passwords
- ❌ No usernames
- ❌ No configuration snippets
- ❌ No command outputs

## 💡 Use Cases

### 1. Air-Gapped Production Network
```
SECURE NETWORK             ANALYST WORKSTATION
┌─────────────┐
│  Device     │  Extract          Upload snapshot
│  Config     │  Features         to PSIRT analyzer
│             │      ↓
└─────────────┘      │            Analyze offline
         ↓           │                ↓
    running-config   │           VULNERABLE?
         ↓           │
    extract_iosxe... │
         ↓           │
    snapshot.json ───┘
    (no secrets!)
```

### 2. Compliance Audit
- Extract features from audit devices
- Store as evidence of configuration state
- No sensitive data in snapshot
- Can be shared with auditors

### 3. Batch Analysis
- Extract from 100 devices
- Store snapshots in repository
- Analyze against new PSIRTs as published
- No repeated SSH connections

### 4. Change Tracking
- Extract before/after config changes
- Compare feature drift
- Audit feature enablement

## 🧪 Testing

```bash
# Create test config
cat > test-config.txt << 'EOF'
hostname TEST-SWITCH
!
spanning-tree mode rapid-pvst
router bgp 65000
 neighbor 10.0.0.1 remote-as 65001
!
ip ssh version 2
control-plane
 service-policy input COPP-POLICY
!
end
EOF

# Test extractor
python3 extract_iosxe_features_standalone.py \
  --config test-config.txt \
  --output test-snapshot.json

# View results
cat test-snapshot.json
```

**Expected Output:**
```json
{
  "features_present": [
    "L2_STP",
    "RTE_BGP",
    "MGMT_SSH_HTTP",
    "SEC_CoPP"
  ],
  "feature_count": 4
}
```

## 📊 Embedded Features (66 Total)

The script has 66 IOS-XE features embedded, organized by domain:

- **L2 Switching** (13): STP, EtherChannel, LACP, VLANs, etc.
- **L3 Routing** (8): OSPF, EIGRP, BGP, BFD, Static routes, etc.
- **L3/FHRP** (3): HSRP, VRRP, GLBP
- **IP Services** (7): DHCP, NAT, NHRP/DMVPN, WCCP, etc.
- **Multicast** (3): PIM, IGMP Snooping, SSM
- **QoS** (3): MQC, Marking, Queuing
- **Security** (9): 802.1X, Port Security, DHCP Snooping, CoPP, etc.
- **TrustSec** (2): CTS, SXP
- **Management** (8): SNMP, SSH, AAA, NTP, NetFlow, etc.
- **HA** (4): StackWise, Redundancy SSO, NSF/GR
- **System** (2): Boot/Upgrade, Smart Licensing
- **Interfaces** (3): Physical, Templates, Speed/Duplex
- **Application Hosting** (1): IOx

Full list available in embedded taxonomy or `iosxe_taxonomy_embedded.json`

## 🔧 Advanced Usage

### Custom Output Directory

```bash
python3 extract_iosxe_features_standalone.py \
  --config config.txt \
  --output /path/to/snapshots/device1-snapshot.json
```

### Batch Processing

```bash
# Extract from multiple configs
for config in configs/*.txt; do
  device=$(basename "$config" .txt)
  python3 extract_iosxe_features_standalone.py \
    --config "$config" \
    --output "snapshots/${device}-snapshot.json"
done
```

### Live Device with netmiko

```bash
# Install netmiko first (if not air-gapped)
pip install netmiko

# Then extract from live device
python3 extract_iosxe_features_standalone.py \
  --host 192.168.1.1 \
  --username admin \
  --output snapshot.json
```

## 🔒 Security

**Safe to Transfer:**
The snapshot contains ONLY feature labels - no sensitive data.

**Example of what's safe:**
```json
{
  "features_present": ["MGMT_SSH_HTTP", "SEC_CoPP", "RTE_BGP"]
}
```

This can be safely:
- Transferred via email
- Stored in version control
- Shared with external analysts
- Used for compliance reporting

## 🆚 Comparison: Standalone vs. Original

| Feature | Standalone | Original |
|---------|-----------|----------|
| **External Files** | None | Requires features.yml |
| **Libraries** | None (Python 3.6+ only) | Requires PyYAML |
| **Platforms** | IOS-XE only | All 5 platforms |
| **File Size** | 47 KB (single file) | 3 KB + 15 KB YAMLs |
| **Air-Gapped** | ✅ 100% offline | ⚠️ Needs YAML files |
| **Deployment** | Copy 1 file | Copy script + 5 YAMLs |

**When to use standalone:**
- ✅ Air-gapped networks
- ✅ IOS-XE devices only
- ✅ Zero-dependency requirement
- ✅ Simple deployment

**When to use original:**
- ✅ Multi-platform support
- ✅ Easy taxonomy updates
- ✅ Development environment

## 📝 Output Compatibility

Snapshots from standalone script are **100% compatible** with the main PSIRT analyzer API:

```bash
# 1. Extract with standalone
python3 extract_iosxe_features_standalone.py --config config.txt -o snapshot.json

# 2. Upload to PSIRT analyzer
curl -X POST http://analyzer:8000/api/v1/verify-snapshot \
  -H "Content-Type: application/json" \
  -d '{
    "analysis_id": "YOUR-ANALYSIS-ID",
    "snapshot": '$(cat snapshot.json)'
  }'
```

The `extractor_version: "1.0.0-standalone"` field identifies it as from the standalone script.

## 🐛 Troubleshooting

### "netmiko not installed" (live mode)

**Solution:** Use offline mode instead:
```bash
# Save config first
ssh admin@device "show running-config" > config.txt

# Then extract offline
python3 extract_iosxe_features_standalone.py --config config.txt -o snapshot.json
```

### "Config file not found"

**Solution:** Check path and permissions:
```bash
ls -la /path/to/config.txt
python3 extract_iosxe_features_standalone.py --config "$(pwd)/config.txt" -o snapshot.json
```

### Python version too old

**Solution:** Check Python version (need 3.6+):
```bash
python3 --version
# Should show Python 3.6 or higher
```

## 📚 Related Documentation

- **Main Project**: `../CLAUDE.md`
- **Feature Extractor Guide**: `../FEATURE_EXTRACTOR_README.md`
- **Snapshot Implementation**: `../FEATURE_SNAPSHOT_IMPLEMENTATION.md`
- **Quick Start**: `../SNAPSHOT_QUICK_START.md`
- **Taxonomy Fix**: `../TAXONOMY_FIX_SNMP_TRAPS.md`

## 🔄 Updating the Embedded Taxonomy

If features.yml is updated in the main project, regenerate the standalone script:

```bash
# From main project directory
cd ..
python3 << 'EOF'
import yaml, json
with open('features.yml') as f:
    features = yaml.safe_load(f)
with open('sidecar_extractor/iosxe_taxonomy_embedded.json', 'w') as f:
    json.dump(features, f, indent=2)
print(f"✅ Updated embedded taxonomy ({len(features)} features)")
EOF

# Then manually update the IOSXE_FEATURES constant in extract_iosxe_features_standalone.py
```

## ✨ Benefits Summary

**For Air-Gapped Networks:**
- ✅ No internet required
- ✅ No external file dependencies
- ✅ Single Python file
- ✅ Works on any system with Python 3.6+

**For Security:**
- ✅ No sensitive data extracted
- ✅ Safe to transfer out of secure networks
- ✅ Can be reviewed by security team
- ✅ Minimal attack surface (single file)

**For Operations:**
- ✅ Simple deployment (copy 1 file)
- ✅ Easy to use (2 commands)
- ✅ Fast execution (< 1 second)
- ✅ Compatible with main analyzer

## 📞 Support

For issues or questions:
1. Check troubleshooting section above
2. Review main project documentation
3. Test with provided example config
4. Verify Python version (3.6+ required)
