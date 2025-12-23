#!/bin/bash
# Launch Llama 3.1 fine-tuning after pseudo-labeling completes

echo "🚀 Starting Llama 3.1 8B Fine-Tuning"
echo "=================================="
echo ""

# Check if pseudo-labeled bugs exist
if [ ! -f "pseudo_labeled_5k_bugs.json" ]; then
    echo "❌ Error: pseudo_labeled_5k_bugs.json not found!"
    echo "   Make sure pseudo-labeling job has completed."
    exit 1
fi

# Count pseudo-labeled bugs
bug_count=$(python3 -c "import json; print(len(json.load(open('pseudo_labeled_5k_bugs.json'))))")
echo "✅ Found $bug_count pseudo-labeled bugs"
echo ""

# Activate venv and run training
source venv/bin/activate

echo "Starting fine-tuning (this will take 2-4 hours)..."
echo "Log file: llama_finetuning.log"
echo ""

nohup python finetune_llama.py > llama_finetuning.log 2>&1 &

PID=$!
echo "✅ Fine-tuning started in background (PID: $PID)"
echo ""
echo "Monitor progress with:"
echo "  tail -f llama_finetuning.log"
echo ""
echo "Check if still running:"
echo "  ps aux | grep $PID"
