# OpenAI PSIRT Verification - Deployment Package

## Files Needed

Copy these files to your work network system:

### 1. Core Script
- `openai_psirt_verifier.py` - Main verification script

### 2. Data Files
- `device_verification_results.json` - Results from your C9200L testing
- `output/enriched_gemini_with_labels.csv` - PSIRT dataset with labels

### 3. Dependencies
Install on target system:
```bash
pip install openai pandas
```

## Setup Instructions

### 1. Copy Files
```bash
# Create directory on work system
mkdir psirt_verification
cd psirt_verification

# Copy these 3 files:
# - openai_psirt_verifier.py
# - device_verification_results.json
# - enriched_gemini_with_labels.csv (from output/ directory)
```

### 2. Install Dependencies
```bash
pip install openai pandas
```

### 3. Set API Key
```bash
export OPENAI_API_KEY='your-openai-api-key-here'
```

### 4. Run Verification
```bash
# Using gpt-4o-mini (recommended, ~$0.002 total cost for 10 PSIRTs)
python openai_psirt_verifier.py

# OR using gpt-4o (higher quality, ~$0.02 total cost)
export OPENAI_MODEL='gpt-4o'
python openai_psirt_verifier.py
```

## Expected Output

The script will:
1. Load 10 PSIRTs from `device_verification_results.json`
2. Load full PSIRT details from `enriched_gemini_with_labels.csv`
3. Send each to OpenAI for expert verification
4. Compare OpenAI verdict vs local system verdict
5. Show agreements/disagreements
6. Save results to `openai_verification_gpt_4o_mini.json`

## Cost Estimates

- **gpt-4o-mini**: ~$0.0002 per PSIRT = ~$0.002 total (10 PSIRTs)
- **gpt-4o**: ~$0.002 per PSIRT = ~$0.02 total (10 PSIRTs)

## What to Expect

The script will identify:
- **Agreements**: Where local system and OpenAI both say VULNERABLE or both say NOT VULNERABLE
- **Disagreements**: Where verdicts differ (like the IKEv2 and IOx false positives)

OpenAI should confirm that:
- `cisco-sa-ikev2-ebFrwMPr` - NOT VULNERABLE (no IKEv2 configured)
- `cisco-sa-iox-dos-95Fqnf7b` - NOT VULNERABLE (no IOx configured)

Even though your local system marked them vulnerable due to generic label matching.

## Troubleshooting

### Error: OPENAI_API_KEY not set
```bash
export OPENAI_API_KEY='sk-...'
```

### Error: File not found
Make sure all 3 files are in the same directory:
```bash
ls -la
# Should see:
# openai_psirt_verifier.py
# device_verification_results.json
# enriched_gemini_with_labels.csv
```

### Error: Module 'openai' not found
```bash
pip install openai pandas
```

## Output Files

After running, you'll get:
- `openai_verification_gpt_4o_mini.json` - Full comparison results
- Console output showing all comparisons

Bring back the JSON file for analysis!
