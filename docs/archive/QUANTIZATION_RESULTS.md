# SEC-8B Quantization Comparison Results

Performance comparison of 4-bit vs 8-bit quantization for Foundation-Sec-8B on PSIRT labeling task.

## Test Configuration

**Hardware:** NVIDIA RTX 5080 (16GB VRAM)
**Test Dataset:** 10 diverse PSIRTs from labeled data
**Platforms:** IOS-XE, ASA, FTD, IOS-XR
**Retrieval:** 5 similar examples per PSIRT (FAISS)
**Temperature:** 0.2
**Max Tokens:** 150

---

## Summary Results

| Metric | 4-bit | 8-bit | Winner |
|--------|-------|-------|--------|
| **Exact Match Accuracy** | 80.0% | 80.0% | Tie |
| **Average Precision** | 0.90 | 0.92 | 🏆 8-bit |
| **Average Recall** | 0.85 | 0.95 | 🏆 8-bit |
| **Average F1 Score** | 0.87 | **0.93** | 🏆 8-bit |
| **Avg Inference Time** | 0.84s | 3.42s | 🏆 4-bit |
| **VRAM Usage** | 6 GB | 13 GB | 🏆 4-bit |

---

## Key Findings

### 1. Accuracy Advantage: 8-bit
- **+7% F1 improvement** (0.87 → 0.93)
- **+10% recall improvement** (0.85 → 0.95)
- Better at avoiding **catastrophic failures**

### 2. Speed Advantage: 4-bit
- **4x faster inference** (0.84s vs 3.42s)
- Acceptable for **development and testing**
- **VRAM-efficient** (6GB vs 13GB)

### 3. Critical Failure Case
**Test 7:** Snort inspection vulnerability (FTD)
- **4-bit:** Completely wrong labels (0.00 F1)
- **8-bit:** Perfect match (1.00 F1)
- **Impact:** 8-bit prevents hallucinations

---

## Detailed Test-by-Test Results

### Test 1: SNMP Vulnerability (IOS-XE)
**Summary:** "A vulnerability in the Simple Network Management Protocol (SNMP) of Cisco..."

| Metric | 4-bit | 8-bit |
|--------|-------|-------|
| True Labels | `['MGMT_SNMP']` | `['MGMT_SNMP']` |
| Predicted | `['MGMT_SNMP']` | `['MGMT_SNMP']` |
| F1 Score | 1.00 | 1.00 |
| **Result** | ✅ Tie | ✅ Tie |

---

### Test 2: L2 STP Vulnerability (IOS-XE)
**Summary:** "A vulnerability in the Layer 2 punt code of Cisco IOS XE Software..."

| Metric | 4-bit | 8-bit |
|--------|-------|-------|
| True Labels | `['L2_STP', 'L2_Switchport_Access', 'L2_Switchport_Trunk']` | Same |
| Predicted | `['L2_STP', 'L2_Switchport_Access', 'L2_Switchport_Trunk']` | Same |
| F1 Score | 1.00 | 1.00 |
| **Result** | ✅ Tie | ✅ Tie |

---

### Test 3: ASA Upgrade Vulnerability
**Summary:** "A vulnerability in the upgrade process of Cisco Adaptive Security Appliance..."

| Metric | 4-bit | 8-bit |
|--------|-------|-------|
| True Labels | `['MGMT_SSH_HTTP_ASDM']` | `['MGMT_SSH_HTTP_ASDM']` |
| Predicted | `['MGMT_SSH_HTTP_ASDM']` | `['MGMT_SSH_HTTP_ASDM']` |
| F1 Score | 1.00 | 1.00 |
| **Result** | ✅ Tie | ✅ Tie |

---

### Test 4: VPN Web Services (ASA)
**Summary:** "A vulnerability in the web services interface for remote access VPN..."

| Metric | 4-bit | 8-bit |
|--------|-------|-------|
| True Labels | `['MGMT_SSH_HTTP_ASDM', 'VPN_AnyConnect_SSL_RA']` | Same |
| Predicted | `['MGMT_SSH_HTTP_ASDM', 'VPN_AnyConnect_SSL_RA']` | `['MGMT_SSH_HTTP_ASDM', 'VPN_AnyConnect_SSL_RA', 'SYS_TCP_Timeouts']` |
| F1 Score | 1.00 | 0.80 |
| **Result** | ⚠️ 4-bit better | - |

*Note: 8-bit added extra (incorrect) label*

---

### Test 5: FTD VPN Vulnerability
**Summary:** "A vulnerability in the VPN web server of Cisco Adaptive Security Appliance..."

| Metric | 4-bit | 8-bit |
|--------|-------|-------|
| True Labels | `['MGMT_SSH_HTTP_ASDM']` | `['MGMT_SSH_HTTP_ASDM']` |
| Predicted | `['MGMT_SSH_HTTP_ASDM']` | `['MGMT_SSH_HTTP_ASDM']` |
| F1 Score | 1.00 | 1.00 |
| **Result** | ✅ Tie | ✅ Tie |

---

### Test 6: FTD HTTP Auth (FTD)
**Summary:** "A vulnerability in the handler for HTTP authentication for resources..."

| Metric | 4-bit | 8-bit |
|--------|-------|-------|
| True Labels | `['VPN_AnyConnect_SSL_RA', 'MGMT_HTTP_ASDM']` | Same |
| Predicted | `['VPN_AnyConnect_SSL_RA']` | `['FW_TCP_Normalization', 'VPN_AnyConnect_SSL_RA']` |
| F1 Score | 0.67 | 0.50 |
| **Result** | ⚠️ 4-bit better | - |

*Note: Both missed one label, 4-bit was closer*

---

### Test 7: Snort Inspection ⚠️ CRITICAL
**Summary:** "Multiple Cisco products are affected by a vulnerability in Snort..."

| Metric | 4-bit | 8-bit |
|--------|-------|-------|
| True Labels | `['MPF_ServicePolicy', 'MPF_Protocol_Inspection']` | Same |
| Predicted | `['FW_AccessGroup_ACL', 'FW_Object_Groups', 'FW_Time_Range']` | `['MPF_ServicePolicy', 'MPF_Protocol_Inspection']` |
| F1 Score | **0.00** | **1.00** |
| **Result** | ❌ Complete failure | ✅ Perfect |

**Analysis:** 4-bit completely hallucinated wrong labels (firewall instead of inspection). 8-bit was perfect.

---

### Test 8: IOS-XE Web UI (IOS-XE)
**Summary:** "A vulnerability in the web UI of Cisco IOS XE Software..."

| Metric | 4-bit | 8-bit |
|--------|-------|-------|
| True Labels | `['MGMT_SSH_HTTP', 'SYS_Boot_Upgrade']` | Same |
| Predicted | `['MGMT_SSH_HTTP', 'SYS_Boot_Upgrade']` | `['MGMT_SSH_HTTP', 'SYS_Boot_Upgrade']` |
| F1 Score | 1.00 | 1.00 |
| **Result** | ✅ Tie | ✅ Tie |

---

### Test 9: IOS-XR Boot Process
**Summary:** "A vulnerability in the boot process of Cisco IOS XR Software..."

| Metric | 4-bit | 8-bit |
|--------|-------|-------|
| True Labels | `['SYSTEM_BOOTSTRAP / UPGRADE', 'SYSTEM_LICENSE']` | Same |
| Predicted | `['SYSTEM_BOOTSTRAP / UPGRADE', 'SYSTEM_LICENSE']` | `['SYSTEM_BOOTSTRAP / UPGRADE', 'SYSTEM_LICENSE']` |
| F1 Score | 1.00 | 1.00 |
| **Result** | ✅ Tie | ✅ Tie |

---

### Test 10: SMB Interaction (FTD)
**Summary:** "A vulnerability in the interaction between Server Message Block (SMB)..."

| Metric | 4-bit | 8-bit |
|--------|-------|-------|
| True Labels | `['MPF_ServicePolicy', 'MPF_Protocol_Inspection']` | Same |
| Predicted | `['MPF_ServicePolicy', 'MPF_Protocol_Inspection']` | `['MPF_ServicePolicy', 'MPF_Protocol_Inspection']` |
| F1 Score | 1.00 | 1.00 |
| **Result** | ✅ Tie | ✅ Tie |

---

## Recommendation

### Use 8-bit for Production ✅

**Reasons:**
1. **Prevents catastrophic failures** (Test 7: 0.00 → 1.00)
2. **Better F1 score** (+7% improvement)
3. **Higher recall** (fewer missed labels)
4. **VRAM is acceptable** (13GB / 16GB = 81% utilization)

**Trade-off:**
- 4x slower (3.4s vs 0.8s) - acceptable for batch processing
- More VRAM (13GB vs 6GB) - RTX 5080 handles it fine

### Use 4-bit for Development ✅

**Reasons:**
1. **4x faster iteration** (0.84s vs 3.42s)
2. **Lower VRAM** (6GB - works on cheaper GPUs)
3. **80% accuracy** is "good enough" for testing

**Risk:**
- Occasional hallucinations (Test 7)
- Lower recall (misses some labels)

---

## Implementation

### Current: 4-bit (Development)
```python
# fewshot_inference.py line 22
quantization_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_compute_dtype=torch.float16
)
```

### Switch to 8-bit (Production)
```python
# fewshot_inference.py line 22
quantization_config = BitsAndBytesConfig(
    load_in_8bit=True
)
```

---

## Cost Analysis

**Hardware:** RTX 5080 16GB (~$1,000)

| Quantization | Throughput | Cost/1000 PSIRTs | Annual Cost (100K PSIRTs) |
|--------------|------------|------------------|---------------------------|
| 4-bit | 4,285 PSIRTs/hour | $0 | $0 |
| 8-bit | 1,053 PSIRTs/hour | $0 | $0 |
| Gemini API | Variable | $15 | $1,500 |

**ROI:** GPU pays for itself after labeling ~67K PSIRTs (vs Gemini)

---

## Files

**Test Results:**
- `quantization_comparison_results.json` - Raw test data
- `compare_quantization.py` - Test script

**To Re-run:**
```bash
python compare_quantization.py
```

---

**Last Updated:** October 2025
**Hardware:** NVIDIA RTX 5080 16GB, CUDA 12.9
