# PSIRT Labeling Pipeline

Automated pipeline for labeling Cisco PSIRTs with platform-specific feature taxonomies using frontier LLMs (Gemini, Claude, or GPT-4).

## Overview

This pipeline processes PSIRT security advisories and assigns platform-specific labels from a closed taxonomy. Key features:

- **Platform-Aware Processing**: Automatically detects platforms (IOS-XE, IOS-XR, ASA, NX-OS, FTD) and uses correct label sets
- **Multi-Platform Support**: PSIRTs affecting multiple platforms are processed separately with platform-specific labels
- **Checkpoint/Resume**: Automatically saves progress and can resume from failures
- **Validation**: Built-in schema and taxonomy validation
- **Token Tracking**: Monitors API usage and costs

## Architecture

```
CSV Input → Platform Detection → Per-Platform Processing → LLM Labeling → Post-Processing → Validation → Output
                                          ↓
                                  Platform-Specific Labels
                                  (IOS-XE, IOS-XR, ASA, etc.)
```

## Installation

### Requirements

```bash
pip install google-generativeai  # For Gemini (default)
# OR
pip install anthropic  # For Claude
# OR
pip install openai     # For GPT-4
```

### API Key Setup

Set your API key as an environment variable:

```bash
# For Gemini (Google AI Studio)
export GOOGLE_API_KEY="your-key-here"

# OR for Claude (Anthropic)
export ANTHROPIC_API_KEY="your-key-here"

# OR for OpenAI
export OPENAI_API_KEY="your-key-here"
```

**Get Gemini API Key:** https://aistudio.google.com/app/apikey

## Usage

### Basic Usage (Gemini - Default)

```bash
python psirt_labeling_pipeline.py gemini_enriched_PSIRTS_mrk1.csv
```

### With Claude

```bash
python psirt_labeling_pipeline.py gemini_enriched_PSIRTS_mrk1.csv --provider anthropic
```

### With OpenAI

```bash
python psirt_labeling_pipeline.py gemini_enriched_PSIRTS_mrk1.csv --provider openai
```

### Process Limited Number (Testing)

```bash
python psirt_labeling_pipeline.py gemini_enriched_PSIRTS_mrk1.csv --limit 10
```

### Custom Output Directory

```bash
python psirt_labeling_pipeline.py gemini_enriched_PSIRTS_mrk1.csv --output-dir results/
```

### Full Options

```bash
python psirt_labeling_pipeline.py \
  gemini_enriched_PSIRTS_mrk1.csv \
  --output-dir results/ \
  --provider gemini \
  --api-key YOUR_KEY \
  --limit 50 \
  --checkpoint checkpoint.json
```

## Output

### Individual Files

Each PSIRT/platform combination generates a separate JSON file:

```
output/
  ├── cisco-sa-curl-libcurl-D9ds39cV_ASA.json
  ├── cisco-sa-curl-libcurl-D9ds39cV_FTD.json
  ├── cisco-sa-asaftd-rsa-key-leak-Ms7UEfZz_ASA.json
  └── ...
```

### Combined Output

All results are also saved to `output/all_results.json`:

```json
[
  {
    "advisory_id": "cisco-sa-asaftd-rsa-key-leak-Ms7UEfZz",
    "platform": "ASA",
    "labels": ["SEC_CoPP", "MGMT_SSH_HTTP"],
    "evidence_spans": [
      "RSA private key vulnerability",
      "hardware-based cryptography"
    ],
    "version_mentions": ["9.16.1", "9.17.1"],
    "fixed_versions": ["9.16.4", "9.17.2"],
    "workaround": {
      "available": false,
      "text": "none"
    }
  },
  ...
]
```

## Validation

Validate outputs against schema and taxonomy:

```bash
python validate_output.py output/
```

Example output:
```
🔍 Validating 25 output files...

✅ cisco-sa-asaftd-rsa-key-leak-Ms7UEfZz_ASA.json: Valid
⚠️  cisco-sa-fw3100-secure-boot-5M8mUh26_FTD.json: Valid with warnings
    - Evidence span 0 is very short (8 chars)
❌ cisco-sa-mlx5-jbPCrqD8_IOSXE.json: Invalid
    - Invalid label 'NVIDIA_DPDK' for platform IOS-XE

============================================================
📊 Validation Summary:
   Total: 25
   Valid: 23
   Invalid: 2
============================================================
```

## Platform Detection

The pipeline detects platforms from the `affected_platforms_from_cve_gemini` CSV column:

| CSV Value | Detected Platforms | Label Files Used |
|-----------|-------------------|------------------|
| `['ASA OS', 'FTD']` | ASA, FTD | `labels_asa_v1.json` (both) |
| `['IOS-XE']` | IOS-XE | `label_pack.json` |
| `['IOS-XR']` | IOS-XR | `labels_iosxr_v1.json` |
| `['NX-OS', 'Nexus']` | NX-OS | `labels_nxos_v1.json` |

## Checkpoint/Resume

The pipeline automatically saves progress to `checkpoint.json`. If interrupted, simply re-run the same command and it will resume from the last processed PSIRT.

To start fresh:
```bash
rm checkpoint.json
python psirt_labeling_pipeline.py gemini_enriched_PSIRTS_mrk1.csv
```

## Platform-Specific Label Sets

### IOS-XE (70 labels)
- L2 Switching (STP, VLANs, EtherChannel, etc.)
- L3 Routing (OSPF, BGP, EIGRP, etc.)
- Security (802.1X, TrustSec, ACLs, etc.)
- Management (SNMP, NetFlow, AAA, etc.)

### IOS-XR (22 labels)
- Routing (OSPF, BGP, IS-IS, Static)
- MPLS/TE (LDP, TE, VPN, Static)
- VPN (IKEv2, IPsec, DMVPN)
- Security (Route filtering, Control plane, DHCP snoop)

### ASA/FTD (Platform-specific firewall labels)

### NX-OS (Data center networking labels)

## Platform Coverage

### ✅ Supported Platforms (Network Infrastructure)
- **IOS-XE** - 70 labels (Catalyst switches/routers)
- **IOS-XR** - 22 labels (Carrier/service routers)
- **ASA** - 46 labels (Adaptive Security Appliance)
- **FTD** - 46 labels (Firepower Threat Defense)
- **NX-OS** - 25 labels (Nexus data center switches)

### ⚠️ Excluded Platforms (By Design)
Application-level platforms not relevant for field config verification:
- **WLC** (Wireless LAN Controller)
- **CUCM** (Unified Communications Manager)
- **ACI** (Application Centric Infrastructure)
- **UCS** (Unified Computing System)
- **ISE** (Identity Services Engine)
- **Meraki**
- **Generic "Application"** bugs

**Why excluded?** These are pre-ship/application-level vulnerabilities. The goal is field-verifiable device configuration checks, not application development issues.

## Troubleshooting

### No platforms detected
Check `affected_platforms_from_cve_gemini` column format. Should be a list like `['IOS-XE']` or comma-separated values.

### API rate limits
Adjust the sleep time in `psirt_labeling_pipeline.py` line 217:
```python
time.sleep(1)  # Increase to 2-3 seconds if hitting rate limits
```

### Invalid labels in output
Labels must exist in the platform's taxonomy. Run validation:
```bash
python validate_output.py output/
```

## Statistics (Actual Full Run)

```
📊 Pipeline Complete!
   Total PSIRTs: 508
   Total LLM Requests: 499
   Successful: 166 platform instances
   Labeled: 165 (97% success rate for processed platforms)
   Tokens Used: 223,538 (~$2-3 cost)
   Output: output/all_results.json

   CSV Output: 534 rows (165 with labels)
   Unique Labels: 62
   Total Assignments: 325
   Platforms: IOS-XE(66), FTD(44), ASA(31), IOS-XR(20), NX-OS(15)
```

## Files

- `psirt_labeling_pipeline.py` - Main pipeline script
- `validate_output.py` - Output validation
- `Prompt.txt` - Platform-aware prompt template
- `normalize_labels.py` - Label normalization utilities
- `extract_psirt_meta.py` - Version/workaround extraction
- `label_pack.json` - IOS-XE labels
- `labels_iosxr_v1.json` - IOS-XR labels
- `labels_asa_v1.json` - ASA/FTD labels
- `labels_nxos_v1.json` - NX-OS labels

## Next Steps

1. **Test Run**: Process 10 PSIRTs to verify setup
   ```bash
   python psirt_labeling_pipeline.py gemini_enriched_PSIRTS_mrk1.csv --limit 10
   ```

2. **Validate**: Check outputs
   ```bash
   python validate_output.py output/
   ```

3. **Full Run**: Process all PSIRTs
   ```bash
   python psirt_labeling_pipeline.py gemini_enriched_PSIRTS_mrk1.csv
   ```

4. **Analyze**: Review `output/all_results.json` for insights
