import torch
import pandas as pd
import json
import argparse
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel
from tqdm import tqdm
import re
from collections import defaultdict

# Config
BASE_MODEL = "fdtn-ai/Foundation-Sec-8B"
ADAPTER_PATH = "models/adapters/cot_v4"  # v4 = normalized labels + balanced
GOLD_EVAL_PATH = "models/gold_standard_eval_normalized.jsonl"  # Normalized gold labels
RANDOM_DATA_PATH = "models/labeled_examples_normalized.parquet"  # Normalized training data

def clean_output(text):
    """Extract labels from model output."""
    labels = []

    # Look for "Label: ['XXX', 'YYY']" pattern
    match = re.search(r"Label:\s*\[([^\]]+)\]", text, re.IGNORECASE)
    if match:
        # Extract individual labels
        labels = re.findall(r"'([^']+)'", match.group(1))
        if not labels:
            labels = re.findall(r'"([^"]+)"', match.group(1))

    # Fallback: look for label-like patterns (UPPERCASE_WITH_UNDERSCORES)
    if not labels:
        potential = re.findall(r'\b([A-Z][A-Za-z0-9_]+(?:_[A-Za-z0-9]+)+)\b', text)
        labels = [l for l in potential if len(l) > 5][:3]

    return labels if labels else ["No Label Found"]

def load_gold_eval(path):
    """Load gold standard evaluation set from JSONL."""
    data = []
    with open(path) as f:
        for line in f:
            data.append(json.loads(line))
    return data

def benchmark(use_gold=True, num_samples=None):
    mode = "Gold Standard" if use_gold else "Random Sample"
    print(f"📊 Benchmarking CoT Adapter ({mode})...")

    # 1. Load Data
    if use_gold:
        samples = load_gold_eval(GOLD_EVAL_PATH)
        print(f"   Loaded {len(samples)} gold standard examples")
    else:
        df = pd.read_parquet(RANDOM_DATA_PATH)
        n = num_samples or 20
        samples = df.sample(n).to_dict('records')
        print(f"   Sampled {len(samples)} random examples")
    
    # 2. Load Model
    print("Loading Base Model...")
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
    base_model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL,
        torch_dtype=torch.float16,
        device_map="auto"
    )

    # Load Adapter
    print("Loading Adapter...")
    model = PeftModel.from_pretrained(base_model, ADAPTER_PATH)

    results = []
    confusion_matrix = defaultdict(lambda: defaultdict(int))  # truth -> predicted -> count

    print("🚀 Running Inference...")
    for row in tqdm(samples, total=len(samples)):
        summary = row['summary']
        # Get truth labels
        if 'gold_label' in row:
            true_labels = row['gold_label']
        else:
            truth = row.get('labels_list', row.get('labels', []))
            if isinstance(truth, str):
                truth = truth.replace("[", "").replace("]", "").replace("'", "").replace('"', "")
                true_labels = [t.strip() for t in truth.split(",")] if "," in truth else [truth]
            else:
                true_labels = list(truth) if hasattr(truth, '__iter__') else [str(truth)]
        
        prompt = f"""### Instruction:
Classify the following Cisco Security Advisory into the correct technical feature label.

### Input:
{summary}

### Response:
"""
        inputs = tokenizer(prompt, return_tensors="pt").to(model.device)

        # A) Run WITH Adapter (CoT)
        model.enable_adapter_layers()
        with torch.no_grad():
            out_cot = model.generate(**inputs, max_new_tokens=250, do_sample=False, temperature=0.1)
        text_cot = tokenizer.decode(out_cot[0], skip_special_tokens=True).split("### Response:")[-1].strip()

        # Parse CoT
        has_reasoning = "Reasoning:" in text_cot or "1." in text_cot or "2." in text_cot
        pred_labels_cot = clean_output(text_cot)

        # B) Run WITHOUT Adapter (Base)
        model.disable_adapter_layers()
        with torch.no_grad():
            out_base = model.generate(**inputs, max_new_tokens=100, do_sample=False, temperature=0.1)
        text_base = tokenizer.decode(out_base[0], skip_special_tokens=True).split("### Response:")[-1].strip()
        pred_labels_base = clean_output(text_base)

        # Score - check if any predicted label matches any true label
        correct_cot = any(p in true_labels for p in pred_labels_cot) or any(t in pred_labels_cot for t in true_labels)
        correct_base = any(p in true_labels for p in pred_labels_base) or any(t in pred_labels_base for t in true_labels)

        # Track confusion for hard negatives
        for t in true_labels:
            for p in pred_labels_cot:
                if p != "No Label Found":
                    confusion_matrix[t][p] += 1
        
        results.append({
            "id": row.get('advisoryId', 'unknown'),
            "truth": true_labels,
            "base_pred": pred_labels_base,
            "cot_pred": pred_labels_cot,
            "base_correct": correct_base,
            "cot_correct": correct_cot,
            "has_reasoning": has_reasoning
        })

    # Analysis
    df_res = pd.DataFrame(results)
    acc_base = df_res['base_correct'].mean() * 100
    acc_cot = df_res['cot_correct'].mean() * 100
    reasoning_rate = df_res['has_reasoning'].mean() * 100

    print("\n" + "="*60)
    print("📈 BENCHMARK RESULTS - THE RULER")
    print("="*60)
    print(f"Mode:                   {mode}")
    print(f"Total Examples:         {len(samples)}")
    print("-"*60)
    print(f"Base Model Accuracy:    {acc_base:.1f}%")
    print(f"CoT Adapter Accuracy:   {acc_cot:.1f}%")
    print(f"Improvement:            {acc_cot - acc_base:+.1f}%")
    print("-"*60)
    print(f"Reasoning Generated:    {reasoning_rate:.1f}% of time")
    print("="*60)

    # Confusion analysis for hard negatives
    print("\n🔥 CONFUSION MATRIX (Top Misclassifications)")
    print("-"*60)
    confusion_pairs = []
    for truth, preds in confusion_matrix.items():
        for pred, count in preds.items():
            if truth != pred:  # Only misclassifications
                confusion_pairs.append((truth, pred, count))
    confusion_pairs.sort(key=lambda x: -x[2])

    for truth, pred, count in confusion_pairs[:10]:
        print(f"  {truth} → {pred}: {count} times")

    print("\n🔍 Sample Comparison (First 5):")
    for i, r in df_res.head(5).iterrows():
        print(f"\nID: {r['id']}")
        print(f"TRUTH: {r['truth']}")
        print(f"BASE:  {r['base_pred']} ({'✅' if r['base_correct'] else '❌'})")
        print(f"COT:   {r['cot_pred']} ({'✅' if r['cot_correct'] else '❌'})")

    # Save results
    output_path = "models/benchmark_results.json"
    with open(output_path, 'w') as f:
        json.dump({
            "mode": mode,
            "total_examples": len(samples),
            "base_accuracy": acc_base,
            "cot_accuracy": acc_cot,
            "reasoning_rate": reasoning_rate,
            "confusion_pairs": confusion_pairs[:20],
            "results": results
        }, f, indent=2, default=str)
    print(f"\n💾 Results saved to {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--random", action="store_true", help="Use random samples instead of gold eval")
    parser.add_argument("--n", type=int, default=20, help="Number of random samples")
    args = parser.parse_args()

    benchmark(use_gold=not args.random, num_samples=args.n)
