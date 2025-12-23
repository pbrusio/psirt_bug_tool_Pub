# Bug Labeling Instructions (60-Minute Token Expiry)

## Quick Start

The script automatically handles token expiry with checkpoint/resume:

```bash
# Activate environment
source venv/bin/activate

# Start labeling (first run)
python label_bugs_with_checkpoints.py --batch-size 100

# When token expires (~60 minutes), refresh token and resume:
export OPENAI_API_KEY="your-new-token"
python label_bugs_with_checkpoints.py --resume
```

## How It Works

**Checkpoint System:**
- Processes bugs in batches of 100 (~5 minutes per batch)
- Saves progress after each batch to `bug_labeling_checkpoint.json`
- Can resume from any point if interrupted

**For 4,665 bugs:**
- ~47 batches total
- ~4 hours total time
- You'll need to refresh token ~4 times (every 60 minutes)

## Token Refresh Workflow

**Session 1 (0-60 min):**
```bash
export OPENAI_API_KEY="token-1"
python label_bugs_with_checkpoints.py --batch-size 100
# Runs until token expires (~12 batches, 1,200 bugs)
```

**Session 2 (after 60 min):**
```bash
export OPENAI_API_KEY="token-2"  # Get new token
python label_bugs_with_checkpoints.py --resume
# Continues from batch 13 (~1,200 more bugs)
```

**Session 3 (after 120 min):**
```bash
export OPENAI_API_KEY="token-3"
python label_bugs_with_checkpoints.py --resume
# Continues from batch 25 (~1,200 more bugs)
```

**Session 4 (after 180 min):**
```bash
export OPENAI_API_KEY="token-4"
python label_bugs_with_checkpoints.py --resume
# Finishes remaining ~1,000 bugs
```

## Options

```bash
# Use faster gpt-4o-mini (recommended, lower quality but cheaper)
python label_bugs_with_checkpoints.py --model gpt-4o-mini

# Use higher quality gpt-4o (better but slower)
python label_bugs_with_checkpoints.py --model gpt-4o

# Adjust batch size (smaller = more frequent checkpoints)
python label_bugs_with_checkpoints.py --batch-size 50

# Specify different input/output files
python label_bugs_with_checkpoints.py --input my_bugs.json --output labeled_bugs.json
```

## Monitoring Progress

The script shows real-time progress:

```
📦 Batch 12/47 (bugs 1101-1200/4665)
   Estimated time remaining: ~175 minutes
   ⏰ Started at: 14:23:45
   [1/100] CSCwq12345 (FTD)... ✨ CHANGED
   [2/100] CSCwq12346 (ASA)... ✓ kept
   ...
   💾 Checkpoint saved: 1200/4665 bugs
   ⏱️  Batch completed in 4.8s
```

## Output Files

- **`gpt4o_labeled_bugs.json`** - Final labeled bugs (created at end)
- **`bug_labeling_checkpoint.json`** - Checkpoint for resume (created after each batch)

## What to Do If...

**Token expires mid-batch:**
- Checkpoint saves after each batch, so you'll only lose current batch progress
- Get new token and `--resume`

**Need to stop manually:**
- Ctrl+C will stop gracefully after current bug
- Checkpoint should be intact
- Resume with `--resume`

**Want to start over:**
```bash
rm bug_labeling_checkpoint.json
python label_bugs_with_checkpoints.py
```

## Troubleshooting

### Common Issues

**Token Expired Mid-Batch:**
```
Error: Unauthorized (401)
```
**Solution:** Get new token and resume:
```bash
export OPENAI_API_KEY="new-token"
python label_bugs_with_checkpoints.py --resume
```

**Script Crashes:**
```
JSONDecodeError or KeyError
```
**Solution:** Checkpoint should be intact. Resume with `--resume`. If checkpoint is corrupted:
```bash
# Check checkpoint
cat bug_labeling_checkpoint.json | jq '.processed'

# If corrupted, restore from last known good point
# (checkpoint saves after each batch, so max loss is current batch)
```

**Progress Too Slow:**
```
# Reduce batch size for more frequent checkpoints
python label_bugs_with_checkpoints.py --batch-size 50

# Or use faster model (lower quality)
python label_bugs_with_checkpoints.py --model gpt-4o-mini
```

**Invalid Labels in Output:**
The script automatically filters labels against the taxonomy. If you see warnings:
```
Warning: Label 'XYZ' not in taxonomy, filtering...
```
This is normal - GPT-4o sometimes hallucinates labels, script removes them.

**Token Timing:**
- ~100 bugs takes ~5 minutes
- 60-minute token = ~12 batches = ~1,200 bugs per session
- Plan for 4 refresh sessions to complete all 4,665 bugs

### Monitoring Progress

Check checkpoint status anytime:
```bash
python3 << 'EOF'
import json
cp = json.load(open('bug_labeling_checkpoint.json'))
print(f"Progress: {cp['processed']}/{cp['total']} ({cp['processed']/cp['total']*100:.1f}%)")
print(f"Last updated: {cp['last_updated']}")
EOF
```

## Next Steps After Labeling

Once all bugs are labeled:

```bash
# Merge with PSIRTs and rebuild FAISS index
python merge_bugs_and_psirts.py
python build_faiss_index.py --input combined_training_data.csv
```

See main CLAUDE.md for full pipeline documentation.
