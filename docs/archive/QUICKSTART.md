# Quick Start Guide - Gemini PSIRT Labeling

## ✅ PIPELINE ALREADY COMPLETED!

The full pipeline has been run successfully. All outputs are ready.

## What's Available

### Output Files (Already Generated)
```
output/
├── 176 individual JSON files (cisco-sa-xxx_PLATFORM.json)
├── all_results.json (166 combined results)
└── enriched_gemini_with_labels.csv (534 rows - ML TRAINING DATA)
```

### Statistics
- **508 PSIRTs processed**
- **165 successfully labeled** (network infrastructure only)
- **62 unique feature labels**
- **5 platforms:** IOS-XE, IOS-XR, ASA, FTD, NX-OS

## View Results

### Check CSV Training Data
```bash
source venv/bin/activate
python3 << 'EOF'
import pandas as pd
df = pd.read_csv('output/enriched_gemini_with_labels.csv')
print(f"Total rows: {len(df)}")
print(f"Labeled rows: {len(df[df['labels'] != '[]'])}")
print(df[df['labels'] != '[]'].head())
EOF
```

### Validate Outputs
```bash
source venv/bin/activate
python validate_output.py output/
```

## Re-run Pipeline (If Needed)

### Test Run (5 PSIRTs)
```bash
source venv/bin/activate
rm checkpoint.json  # Reset checkpoint
python psirt_labeling_pipeline.py gemini_enriched_PSIRTS_mrk1.csv --limit 5
```

### Full Run
```bash
source venv/bin/activate
rm checkpoint.json
python psirt_labeling_pipeline.py gemini_enriched_PSIRTS_mrk1.csv
python merge_to_csv.py  # Regenerate enriched CSV
```

## Validate Results

```bash
python validate_output.py output/
```

## Output Files

- `output/<advisory_id>_<platform>.json` - Individual PSIRT/platform results
- `output/all_results.json` - Combined results
- `checkpoint.json` - Progress tracking (for resume)

## How It Works

1. **Platform Detection**: Reads `affected_platforms_from_cve_gemini` column
2. **Separate Processing**: Each platform gets its own label set and request
3. **Example**: PSIRT affecting `['ASA', 'FTD', 'IOS-XE']` generates 3 outputs:
   - `cisco-sa-xxx_ASA.json` (with ASA labels)
   - `cisco-sa-xxx_FTD.json` (with FTD/ASA labels)
   - `cisco-sa-xxx_IOSXE.json` (with IOS-XE labels)

## Troubleshooting

### API Key Error
```bash
# Check .env file
cat .env

# Or set directly
export GEMINI_API_KEY="your-key-here"
```

### Resume from Failure
Simply re-run the same command. Checkpoint will resume from last processed PSIRT.

### Reset Checkpoint
```bash
rm checkpoint.json
```

## Expected Output Example

```json
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
}
```

## Actual Performance (Completed Run)

- **Test (5 PSIRTs)**: 30 seconds, 13,953 tokens
- **Full (508 PSIRTs)**: ~45 minutes, 223,538 tokens (~$2-3 cost)
- **Success Rate**: 97% (165/166 processed platforms labeled)

## Next Steps - ML Development

Use the enriched CSV to build your XGBoost/LightGBM model:

```python
import pandas as pd
import json
from sklearn.feature_extraction.text import TfidfVectorizer
from xgboost import XGBClassifier

# Load training data
df = pd.read_csv('output/enriched_gemini_with_labels.csv')
labeled = df[df['labels'] != '[]']

# Features: PSIRT text
X = labeled['summary'].values

# Labels: Parse JSON arrays
y_labels = labeled['labels'].apply(json.loads).values

# Train model (multi-label classification)
vectorizer = TfidfVectorizer(max_features=1000)
X_vec = vectorizer.fit_transform(X)

# Build one classifier per label (one-vs-rest)
# ... your ML training code here
```

**Goal:** New PSIRT → Model → Predicted Labels → Config Check Commands
