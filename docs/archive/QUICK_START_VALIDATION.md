# Quick Start: Validate GPT-4o Bug Labels

Fast track to test if adding 4,664 GPT-4o bug labels improves SEC-8B performance.

## TL;DR - The 10-Bug Test

```bash
# 1. Test current FAISS baseline (10 bugs, ~5 min)
python test_faiss_improvement.py --baseline --num-bugs 10

# 2. Quick validate 20 bugs (~10 min)
python validate_gpt4o_labels.py --sample 20 --changed

# 3. If >90% approval, merge and test (~15 min)
python merge_validated_labels.py validation_decisions_*.json --merge-psirts
python build_faiss_index.py --input training_data_combined_*.csv
python test_faiss_improvement.py --baseline --num-bugs 10  # Test with new FAISS

# 4. Compare results
python test_faiss_improvement.py --compare --num-bugs 10
```

**Total time:** ~30-40 minutes

## What This Does

### Step 1: Baseline Test
Tests SEC-8B with current FAISS (165 PSIRTs only) on 10 random bugs.

**Output:**
- Predicted labels for each bug
- Metrics: Precision, Recall, F1, Exact Match
- Ground truth = GPT-4o labels

**Current Expected Performance:**
- F1: ~0.80-0.85
- Exact Match: ~60-70%

### Step 2: Quick Validation
Review 20 label changes interactively.

**You'll see for each bug:**
- SEC-8B labels (baseline)
- GPT-4o labels (proposed)
- What changed (added/removed)
- GPT-4o reasoning + confidence

**Approve/Reject/Skip each one**

**Decision point:** If approval rate >90%, GPT-4o improvements are good!

### Step 3: Merge & Rebuild
Creates expanded training dataset and rebuilds FAISS index.

**New FAISS:**
- Before: 165 PSIRTs
- After: 165 PSIRTs + 4,664 bugs = 4,829 examples (30x increase!)

### Step 4: Test Improvement
Tests SEC-8B with expanded FAISS on same 10 bugs.

**Compare:**
- Baseline vs Expanded predictions
- F1 improvement per bug
- Overall accuracy gain

## Expected Improvements

**Current (165 PSIRTs):**
- Coverage: Limited, mostly IOS-XE
- Rare features: Poor
- F1: ~0.80-0.85

**After (4,829 examples):**
- Coverage: All platforms
- Rare features: Much better (HA, VPN, specific protocols)
- F1: ~0.90-0.95 (expected +0.05-0.10)

## What You're Testing

**Key hypothesis:**
> More training examples → Better FAISS retrieval → More accurate SEC-8B predictions

**Specifically:**
1. **Better similarity matching**: 30x more examples means FAISS finds more relevant similar bugs
2. **Platform coverage**: Currently IOS-XE heavy, bugs add ASA/FTD/IOS-XR coverage
3. **Rare label detection**: Bugs include many rare features (HA_Clustering, VPN_IKEv2, etc.)

## Quick Decision Tree

```
Run baseline test (10 bugs)
  ↓
Current F1 < 0.80?
  YES → SEC-8B needs help, proceed with validation
  NO  → SEC-8B already good, but still worth trying
  ↓
Validate 20 bugs
  ↓
Approval rate >90%?
  YES → GPT-4o quality is good, proceed to merge
  NO  → Review rejections, maybe validate more samples
  ↓
Merge and rebuild FAISS
  ↓
Test with expanded FAISS
  ↓
F1 improvement >0.05?
  YES → 🎉 Success! Deploy new FAISS
  NO  → Investigate: Check if bugs match test domain
```

## Files Generated

```
# Baseline test
faiss_comparison_YYYYMMDD_HHMMSS.json         # Test results

# Validation
validation_decisions_YYYYMMDD_HHMMSS.json     # Your approvals/rejections

# Merge
training_data_bugs_YYYYMMDD_HHMMSS.json       # Bugs only
training_data_combined_YYYYMMDD_HHMMSS.csv    # Bugs + PSIRTs
validation_merge_report.txt                    # Summary report

# New FAISS
models/faiss_index.bin                         # Updated (backup old one first!)
models/labeled_examples.parquet                # Training examples
```

## Safety Notes

1. **Backup current FAISS before rebuilding:**
   ```bash
   cp models/faiss_index.bin models/faiss_index_backup.bin
   cp models/labeled_examples.parquet models/labeled_examples_backup.parquet
   ```

2. **Start with small sample (10 bugs)** - Quick test before committing

3. **Validation is optional but recommended** - Auto-approval uses HIGH confidence

4. **Can always revert** - Keep backup of original FAISS

## Alternative: Trust GPT-4o

If you trust the 96.5% HIGH confidence rate:

```bash
# Skip validation, merge with auto-approval
python merge_validated_labels.py <(echo '{"metadata": {"reviewed": 0, "approved": 0, "rejected": 0, "skipped": 0}, "decisions": {"approved": [], "rejected": [], "skipped": []}}') --auto-approve --merge-psirts

# Build FAISS
python build_faiss_index.py --input training_data_combined_*.csv

# Test
python test_faiss_improvement.py --compare --num-bugs 10
```

**This uses GPT-4o labels directly (HIGH confidence + unchanged = auto-approved)**

## Troubleshooting

**"FAISS index not found"**
- Run: `python build_faiss_index.py` first

**"GPU out of memory"**
- Use smaller batch: `--num-bugs 5`
- Or run validation only (no GPU needed)

**"Model loading fails"**
- Check: `ls models/` - should have faiss_index.bin, labeled_examples.parquet
- Rebuild if needed: `python build_faiss_index.py`

**"Approval rate < 50%"**
- Review rejected examples
- Check if GPT-4o understanding domain correctly
- Consider not merging, or being more conservative

## Next Steps After Success

1. **Deploy to production** - Backend uses new FAISS automatically
2. **Test on real PSIRTs** - Verify improvement on live data
3. **Monitor performance** - Track metrics over time
4. **Iterate** - Collect more feedback, improve further
