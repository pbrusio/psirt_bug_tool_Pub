# MPLS Training Data Enhancement - Summary

## Package Created: `mpls_labeling_package/`

**Ready to copy to other network for GPT-4o labeling**

---

## What's in the Package

```
mpls_labeling_package/
├── README.md                           # Overview
├── MPLS_LABELING_INSTRUCTIONS.md       # Step-by-step guide
├── label_mpls_bugs.py                  # Labeling script with checkpoint/resume
├── mpls_bugs_input.json                # 801 MPLS bugs (INPUT)
├── PROJECT_CONTEXT.md                  # GPT-4o guidelines
├── features.yml                        # IOS-XE taxonomy
└── features_iosxr.yml                  # IOS-XR taxonomy
```

**Size:** 256 KB (easily transferable)

---

## The Problem We're Solving

Current test results (10 bugs):
- **Exact Match:** 40% (4/10)
- **Avg F1:** 0.533
- **Partial/Better:** 60% (6/10)

**Key failures - all MPLS/routing related:**

| Bug | Ground Truth | Predicted | Issue |
|-----|--------------|-----------|-------|
| "AS Path Prepend limit" | RTE_BGP | MGMT_SNMP, SEC_PACL_VACL | BGP not recognized |
| "sr-mpls via mapping server" | MPLS_STATIC | SEC_BGP_ROUTE_FILTERING | MPLS confused with BGP |
| "MLD Queries Disrupt" | MCAST_IGMP_MLD_Snoop | MGMT_SNMP | SNMP false positive |

**Root cause:** Training data imbalance

| Label | Count | % of Dataset |
|-------|-------|--------------|
| HA_Failover | 209 | 11.0% |
| MGMT_SNMP | 160 | 8.4% ← Keeps showing up incorrectly |
| RTE_BGP | 100 | 5.3% |
| **MPLS_LDP** | **37** | **1.9%** ← Severely underrepresented |
| **MPLS_TE** | **30** | **1.6%** |
| **MPLS_VPN** | **11** | **0.6%** |
| **Total MPLS** | **78** | **4.1%** ← Need 11x more! |

---

## The Solution

**Label 801 high-quality MPLS bugs:**
- 41 IOS-XE (Sev 1-2 only)
- 760 IOS-XR (Sev 1-2 only)

**Expected result:**
- MPLS examples: 78 → ~879 (11x increase)
- Total dataset: 1,900 → ~2,700 (+42%)
- MPLS becomes 32.5% of dataset (vs 4.1% currently)

---

## Instructions for Other Network

### Quick Start (2 commands)

```bash
# Session 1 (0-60 min)
export OPENAI_API_KEY="token-here"
python label_mpls_bugs.py --batch-size 100

# Session 2+ (after token expiry)
export OPENAI_API_KEY="new-token"
python label_mpls_bugs.py --resume
```

**Time:** ~40 minutes for 801 bugs (may need 1-2 token refreshes)

**Cost:** ~$0.40 (GPT-4o-mini)

### Full Instructions

See `mpls_labeling_package/MPLS_LABELING_INSTRUCTIONS.md` for:
- Prerequisites
- Step-by-step process
- Troubleshooting
- What to copy back

---

## What You'll Get Back

**File to copy back:** `mpls_labeled_bugs.json`

**Structure:**
```json
[
  {
    "bug_id": "CSCva66225",
    "summary": "Crash While Updating FIB/RIB Table...",
    "platform": "IOS-XE",
    "openai_result": {
      "labels": ["MPLS_LDP", "RTE_BGP"],
      "reasoning": "...",
      "confidence": "HIGH"
    }
  },
  ...
]
```

---

## Integration (After Getting File Back)

### Step 1: Merge MPLS labels

```bash
# Copy mpls_labeled_bugs.json to project root
cp /path/from/other/network/mpls_labeled_bugs.json .

# Merge with existing training data
python merge_mpls_labels.py
```

**Output:** `training_data_with_mpls_YYYYMMDD_HHMMSS.csv`

### Step 2: Rebuild FAISS

```bash
# Backup current FAISS
cp models/faiss_index.bin models/faiss_index_before_mpls.bin

# Rebuild with MPLS-enhanced data
python build_faiss_index.py --input training_data_with_mpls_*.csv
```

**Output:** Updated `models/faiss_index.bin` (1,900 → ~2,700 examples)

### Step 3: Re-test

```bash
# Test on same 10 bugs
python test_faiss_improvement.py --baseline --num-bugs 10
```

**Compare:**
- Before: 40% exact match, 0.533 F1
- Expected: 50-60% exact match, 0.65+ F1

---

## Expected Improvements

### Overall Metrics

| Metric | Current | Expected After MPLS |
|--------|---------|---------------------|
| Exact Match | 40% (4/10) | 50-60% (5-6/10) |
| Avg F1 | 0.533 | 0.65+ |
| Partial/Better | 60% (6/10) | 70-80% (7-8/10) |

### Specific Fixes

| Bug Type | Current | Expected |
|----------|---------|----------|
| "AS Path Prepend" | SNMP/ACL ❌ | RTE_BGP ✅ |
| "sr-mpls mapping" | BGP_FILTERING ❌ | MPLS_STATIC ✅ |
| "MPLS LDP crash" | SNMP/Generic ❌ | MPLS_LDP ✅ |
| "MPLS TE tunnel" | Generic ❌ | MPLS_TE ✅ |

### False Positive Reduction

**MGMT_SNMP showing up incorrectly will decrease because:**
- Currently 160 SNMP examples (8.4%)
- After MPLS: ~160 SNMP vs ~879 MPLS (ratio improved 5:1)
- FAISS will find more relevant MPLS examples instead of generic SNMP

---

## Files Created

**In `mpls_labeling_package/`:**
- ✅ `label_mpls_bugs.py` - Main labeling script
- ✅ `mpls_bugs_input.json` - 801 bugs to label
- ✅ `MPLS_LABELING_INSTRUCTIONS.md` - Detailed guide
- ✅ `README.md` - Package overview
- ✅ `PROJECT_CONTEXT.md` - GPT-4o guidelines
- ✅ `features.yml` - IOS-XE taxonomy
- ✅ `features_iosxr.yml` - IOS-XR taxonomy

**In project root:**
- ✅ `merge_mpls_labels.py` - Merge script for when data returns
- ✅ `MPLS_ENHANCEMENT_SUMMARY.md` - This file

---

## Next Steps

1. **Copy package to other network:**
   ```bash
   scp -r mpls_labeling_package/ user@other-network:/destination/
   ```

2. **On other network:** Follow `MPLS_LABELING_INSTRUCTIONS.md`
   - Estimated time: 40 minutes
   - May need 1-2 token refreshes

3. **Copy results back:**
   ```bash
   scp user@other-network:/path/mpls_labeled_bugs.json .
   ```

4. **Integrate and test:**
   ```bash
   python merge_mpls_labels.py
   python build_faiss_index.py --input training_data_with_mpls_*.csv
   python test_faiss_improvement.py --baseline --num-bugs 10
   ```

5. **Compare results** and document improvement

---

## Questions?

- **Package issues:** Check `mpls_labeling_package/README.md`
- **Labeling issues:** Check `MPLS_LABELING_INSTRUCTIONS.md`
- **Integration issues:** Review `merge_mpls_labels.py` comments
- **Testing issues:** Use same 10-bug test for apples-to-apples comparison

---

## Context: Training Data Expansion Journey

**Phase 1:** Added 4,664 bugs
- Before: 145 PSIRTs (0% bug accuracy)
- After: 1,900 examples (40% bug accuracy)
- Result: ✅ Significant improvement, but MPLS underrepresented

**Phase 2:** Add 801 MPLS bugs (current)
- Before: 78 MPLS examples (4.1%)
- After: ~879 MPLS examples (32.5%)
- Goal: Fix MPLS/routing protocol confusion

**Phase 3:** Production feedback loop
- Collect real device verification results
- Add validated examples back to training
- Continuous improvement
