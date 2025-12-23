# GPT-4o Label Validation Workflow

Complete workflow for validating and merging GPT-4o bug labels into training data.

## Overview

You have **4,664 bugs** labeled by both:
- **SEC-8B** (baseline) - Few-shot inference with FAISS
- **GPT-4o** (proposed) - Context-aware labeling with taxonomy

**84.8% changed** (3,957 bugs) - GPT-4o corrected most labels
**96.5% HIGH confidence** - GPT-4o confident in changes

## Workflow Steps

### 1. View Statistics

Get overview of label changes:

```bash
python validate_gpt4o_labels.py --stats
```

**Output:**
- Total bugs by platform
- Change rate (84.8%)
- Confidence distribution (96.5% HIGH)
- Top added/removed labels

### 2. Interactive Validation

Review and approve/reject label changes:

```bash
# Start with small sample
python validate_gpt4o_labels.py --sample 20

# Review only changed labels
python validate_gpt4o_labels.py --sample 50 --changed

# Focus on specific platform
python validate_gpt4o_labels.py --sample 30 --platform IOS-XE
```

**For each bug, you'll see:**
- Bug ID, platform, summary
- SEC-8B labels (baseline)
- GPT-4o labels (proposed)
- What changed (added/removed/kept)
- GPT-4o reasoning
- Confidence level

**Options:**
- `[a]` Approve - Use GPT-4o labels
- `[r]` Reject - Keep SEC-8B labels
- `[s]` Skip - Review later
- `[v]` View full summary
- `[q]` Quit and save progress

**Output:**
- `validation_decisions_YYYYMMDD_HHMMSS.json`

### 3. Merge Validated Labels

After validation, merge approved labels into training dataset:

```bash
# Create training dataset from validation
python merge_validated_labels.py validation_decisions_20251008_143000.json

# With auto-approval of high-confidence unchanged labels
python merge_validated_labels.py validation_decisions_20251008_143000.json --auto-approve

# Merge with existing PSIRTs
python merge_validated_labels.py validation_decisions_20251008_143000.json --merge-psirts
```

**Auto-approval logic** (when `--auto-approve`):
1. **Manually approved** → Use GPT-4o labels
2. **Manually rejected** → Use SEC-8B labels
3. **Not reviewed + unchanged** → Use GPT-4o (confirmed SEC-8B)
4. **Not reviewed + HIGH confidence** → Use GPT-4o
5. **Not reviewed + MEDIUM/LOW** → Use SEC-8B (conservative)

**Output:**
- `training_data_bugs_YYYYMMDD_HHMMSS.json` - Bugs only
- `training_data_bugs_YYYYMMDD_HHMMSS.csv` - Bugs only (CSV)
- `training_data_combined_YYYYMMDD_HHMMSS.csv` - Bugs + PSIRTs (if --merge-psirts)
- `validation_merge_report.txt` - Summary report

### 4. Rebuild FAISS Index

Update FAISS index with expanded training data:

```bash
# Build index from combined dataset
python build_faiss_index.py --input training_data_combined_20251008_143000.csv

# Or just bugs
python build_faiss_index.py --input training_data_bugs_20251008_143000.json
```

**Output:**
- `models/faiss_index.bin` - Updated FAISS index
- `models/labeled_examples.parquet` - Training examples
- `models/embedder_info.json` - Embedder config

### 5. Test Performance

Test SEC-8B performance with new training data:

```bash
# Quick test on 20 samples
python fewshot_inference.py --test

# Full evaluation
python compare_quantization.py
```

**Metrics to track:**
- Exact match rate
- F1 score per platform
- Confidence score distribution
- Inference time

## Recommended Validation Strategy

### Phase 1: Quick Sample (30 min)

Start with small, representative sample:

```bash
# 20 changed labels, diverse platforms
python validate_gpt4o_labels.py --sample 20 --changed
```

**Goal:** Get feel for GPT-4o quality
**Decision point:** If >90% approval, proceed to Phase 2

### Phase 2: Platform Focus (1-2 hours)

Validate each platform separately:

```bash
python validate_gpt4o_labels.py --sample 30 --platform IOS-XE
python validate_gpt4o_labels.py --sample 30 --platform IOS-XR
python validate_gpt4o_labels.py --sample 30 --platform ASA
python validate_gpt4o_labels.py --sample 30 --platform FTD
```

**Goal:** Ensure quality across all platforms
**Decision point:** If all >85% approval, proceed to merge

### Phase 3: Merge & Test (30 min)

```bash
# Merge with auto-approval
python merge_validated_labels.py validation_decisions_*.json --auto-approve --merge-psirts

# Rebuild FAISS
python build_faiss_index.py --input training_data_combined_*.csv

# Test performance
python fewshot_inference.py --test
```

**Goal:** Validate improvement in SEC-8B performance

## Expected Outcomes

### Before (165 PSIRTs only)
- Training examples: 165
- Coverage: Limited, mostly IOS-XE
- Rare features: Poor coverage

### After (165 PSIRTs + 4,664 bugs)
- Training examples: 4,829
- Coverage: All platforms (30x increase)
- Rare features: Better coverage

### Performance Target
- Exact match: 80% → 85%+ (expected)
- F1 score: 0.93 → 0.95+ (expected)
- Confidence: More consistent scoring
- Rare labels: Better detection

## Quality Checks

### Before Merging
1. **Approval rate >85%** across all platforms
2. **Key label changes validated:**
   - Generic labels removed (e.g., MGMT_SSH_HTTP_ASDM)
   - Specific labels added (e.g., VPN_AnyConnect_SSL_RA)
3. **High confidence changes reviewed** (spot check 10-20)

### After Merging
1. **FAISS index builds successfully**
2. **SEC-8B inference works** on test cases
3. **Performance metrics improve** vs baseline
4. **No regression** on known-good PSIRTs

## Troubleshooting

### High Rejection Rate (>30%)
**Problem:** GPT-4o making systematic errors

**Solutions:**
1. Check PROJECT_CONTEXT.md - ensure guidelines are clear
2. Review rejected examples - identify patterns
3. Consider re-labeling with updated context
4. Use `--no-auto-approve` to be more conservative

### Low Approval Rate (<50%)
**Problem:** SEC-8B baseline actually better

**Solutions:**
1. Keep SEC-8B labels (use `--no-auto-approve`)
2. Focus on HIGH confidence only
3. Validate small subset manually
4. Consider using SEC-8B pseudo-labels directly

### Merge Errors
**Problem:** Data format mismatches

**Solutions:**
1. Check CSV column names match expected format
2. Verify labels are JSON arrays, not strings
3. Ensure platform values are consistent
4. Check for missing required fields

## Files Generated

```
validation_decisions_YYYYMMDD_HHMMSS.json    # Your approval/rejection decisions
training_data_bugs_YYYYMMDD_HHMMSS.json      # Bugs training data
training_data_bugs_YYYYMMDD_HHMMSS.csv       # Bugs training data (CSV)
training_data_combined_YYYYMMDD_HHMMSS.csv   # Bugs + PSIRTs combined
validation_merge_report.txt                   # Summary report
models/faiss_index.bin                        # Updated FAISS index
models/labeled_examples.parquet               # Training examples for FAISS
```

## Next Steps

After completing validation and merge:

1. **Update CLAUDE.md** with new training data stats
2. **Test on real PSIRTs** from production
3. **Deploy to web app** (backend uses updated FAISS index)
4. **Monitor performance** on live queries
5. **Iterate** - collect feedback and improve

## Notes

- **Validation is iterative** - Start small, expand if quality is good
- **Auto-approval is safe** - Only applies to HIGH confidence unchanged labels
- **You can quit anytime** - Progress saves automatically (press 'q')
- **Multiple sessions OK** - Validation decisions accumulate
- **Merge is reversible** - Original files preserved
