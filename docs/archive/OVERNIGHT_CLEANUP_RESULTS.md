# CVE-EVAL Data Cleanup Results

**Date:** December 12, 2025
**Status:** Phase 5 Complete - Awaiting Review

---

## Executive Summary

The overnight data cleanup and retraining significantly improved model accuracy:

| Metric | v4b (baseline) | v5 (cleaned) | Change |
|--------|----------------|--------------|--------|
| **Exact Match** | 17.2% | **39.4%** | **+22.2%** ✓ |
| **Partial Match** | 29.3% | **48.5%** | **+19.2%** ✓ |
| **Avg F1 Score** | 0.251 | **0.453** | **+0.202** ✓ |
| Empty Predictions | 0% | 8.1% | -8.1% |
| Avg Time (s) | 1.84 | 1.83 | ~same |

**Key Insight:** Removing contaminated training data more than doubled exact match accuracy.

---

## Phase 1: Data Analysis

**Cleanup Statistics:**
- Original examples: 7,681
- Removed examples: 616 (8.0%)
- Remaining examples: 7,065

**Contamination by Label (100% removed):**
| Label | Count | Issue |
|-------|-------|-------|
| SYS_Boot_Upgrade | 230 | All mislabeled - not boot/upgrade issues |
| SEC_CoPP | 219 | All mislabeled - not Control Plane Policing |
| MGMT_SSH_HTTP | 118 | ISE/DCNM contamination |
| MGMT_NTP | 77 | mDNS gateway mislabeling |
| MGMT_AAA_TACACS_RADIUS | 73 | NFVIS/non-IOS-XE |
| MGMT_SNMP | 59 | ASA/FTD/FMC contamination |
| IP_DHCP_Server | 48 | mDNS gateway mislabeling |
| IF_Physical | 47 | Aironet AP contamination |
| IP_NHRP_DMVPN | 35 | SD-WAN UTD mislabeling |
| IP_NAT | 27 | Non-IOS-XE platforms |
| IP_Unnumbered | 15 | IPv4 fragmentation mislabeling |
| IP_PrefixList | 14 | SD-WAN packet filter mislabeling |

**Report saved:** `cleanup_report_final.txt`

---

## Phase 2: Data Cleanup

**Files created:**
- `models/labeled_examples_cleaned_v2.parquet` - Cleaned training data (7,065 examples)
- `cleanup_report_final.txt` - Detailed cleanup report

**Verification:**
All critically contaminated labels reduced to 0 examples.

---

## Phase 3: CoT Dataset Filtering

**CoT Dataset Statistics:**
- Original: 1,162 examples
- Kept: 1,004 examples
- Removed: 158 examples (contaminated)

**Training splits created in `models/mlx_training_data_v2/`:**
- train.jsonl: 903 examples
- valid.jsonl: 50 examples
- test.jsonl: 51 examples

---

## Phase 4: LoRA Training

**Training Configuration:**
- Model: fdtn-ai/Foundation-Sec-8B
- Adapter: models/lora_adapter_v2
- Iterations: 600
- Batch size: 1
- Learning rate: 0.0001
- Layers: 16

**Training Progress:**
| Iteration | Train Loss | Val Loss |
|-----------|------------|----------|
| 1 | - | 2.958 |
| 100 | 2.126 | 1.966 |
| 200 | 1.837 | 1.825 |
| 300 | 1.704 | 1.738 |
| 400 | 1.702 | 1.761 |
| 500 | 1.631 | 1.594 |
| 600 | 1.632 | **1.550** |

**Final validation loss: 1.550** (down from 2.958)

**Adapter saved:** `models/lora_adapter_v2/adapters.safetensors` (~40MB)

---

## Phase 5: Evaluation

**Test Set:** 99 examples from `models/evaluation_test_set.json`

**Results Comparison:**

```
Metric                 v4b (baseline)     v5 (cleaned)       Change
---------------------------------------------------------------------------
Exact Match            17.2%              39.4%              +22.2% ✓
Partial Match          29.3%              48.5%              +19.2% ✓
Empty Predictions      0.0%               8.1%               -8.1% ✗
Avg F1 Score           0.251              0.453              +0.202 ✓
Avg Precision          0.283              0.476              +0.194 ✓
Avg Recall             0.237              0.446              +0.209 ✓
Avg Time (s)           1.84               1.83               +0.00s ✓
```

**Detailed breakdown:**
- Exact Match Count: 17 → 39 (+22)
- Partial Match Count: 29 → 48 (+19)
- Empty Predictions: N/A → 8

**Results saved:** `models/eval_results_v5_cleaned.json`

---

## Phase 6: Production Update (NOT DONE - Awaiting Review)

**What's ready but NOT promoted:**
1. Cleaned training data: `models/labeled_examples_cleaned_v2.parquet`
2. New LoRA adapter: `models/lora_adapter_v2/`
3. Updated FAISS index: `models/faiss_index.bin` (rebuilt on cleaned data)
4. Backup of original FAISS: `models/faiss_index_original.bin`

**Action required to promote to production:**
```bash
# After your review, if satisfied:

# 1. Backup v1 adapter
mv models/lora_adapter_v1 models/lora_adapter_v1_backup

# 2. Promote v2 adapter
mv models/lora_adapter_v2 models/lora_adapter_v1

# 3. Update training data reference
mv models/labeled_examples.parquet models/labeled_examples_original.parquet
cp models/labeled_examples_cleaned_v2.parquet models/labeled_examples.parquet

# 4. FAISS index is already updated
```

---

## Files Created/Modified

| File | Action | Purpose |
|------|--------|---------|
| `models/labeled_examples_cleaned_v2.parquet` | Created | Cleaned training data |
| `models/cot_dataset_v7_cleaned.jsonl` | Created | Filtered CoT dataset |
| `models/mlx_training_data_v2/` | Created | Training splits |
| `models/lora_adapter_v2/` | Created | New LoRA adapter |
| `models/faiss_index.bin` | Updated | Rebuilt on cleaned data |
| `models/faiss_index_original.bin` | Created | Backup of original |
| `models/faiss_index_cleaned.bin` | Created | Explicit cleaned copy |
| `models/eval_results_v5_cleaned.json` | Created | Evaluation results |
| `cleanup_report_final.txt` | Created | Detailed cleanup report |
| `cleanup_training_data.py` | Created | Cleanup script |
| `evaluate_v2_adapter.py` | Created | Evaluation script |

---

## Observations

1. **Data contamination was severe:** 8% of examples had critical mislabeling
2. **Cleanup significantly improved accuracy:** 17.2% → 39.4% exact match
3. **Empty predictions (8.1%):** Some test examples may not have good matches in the cleaned training data, or the model is being more conservative
4. **FAISS index rebuild was critical:** Without it, evaluation showed worse results

---

## Recommendations

1. **Review before promotion:** Check a sample of the predictions in `eval_results_v5_cleaned.json`
2. **Consider empty predictions:** 8 examples (8.1%) had no predictions - may need investigation
3. **Monitor production:** After promotion, compare inference results to v4b
4. **Future work:** Consider Option B (re-synthesize CoT with OpenAI) for potential further improvement

---

## Quick Commands for Review

```bash
# View cleanup report
cat cleanup_report_final.txt

# Check evaluation results
python -c "import json; d=json.load(open('models/eval_results_v5_cleaned.json')); print(f'Exact: {d[\"exact_match\"]*100:.1f}%, Partial: {d[\"partial_match\"]*100:.1f}%, F1: {d[\"avg_f1\"]:.3f}')"

# Compare adapter sizes
ls -lh models/lora_adapter_v1/adapters.safetensors models/lora_adapter_v2/adapters.safetensors

# View sample predictions (first 5)
python -c "import json; d=json.load(open('models/eval_results_v5_cleaned.json')); [print(f'Truth: {p[\"truth\"]} | Pred: {p[\"pred\"]}') for p in d['predictions'][:5]]"
```

---

**Status:** Ready for your review. Phase 6 (production promotion) will not proceed until you approve.
