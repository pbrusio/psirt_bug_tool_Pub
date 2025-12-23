#!/usr/bin/env python3
"""
Comprehensive LoRA Adapter Evaluation Script

Tests three configurations:
1. v3: SEC-8B + FAISS few-shot (current production baseline)
2. v4a: SEC-8B + LoRA (standalone, no FAISS)
3. v4b: SEC-8B + LoRA + FAISS (combined - likely production config)

Metrics:
- Exact Match: All predicted labels match truth exactly
- F1 Score: Label-level precision/recall balance
- Partial Match: At least one label matches
"""

import json
import time
import re
from pathlib import Path
from typing import List, Dict, Set, Tuple
from collections import defaultdict


def load_test_set(path: str = "models/evaluation_test_set.json") -> List[Dict]:
    """Load evaluation test set"""
    with open(path, 'r') as f:
        data = json.load(f)

    # Handle both formats: list or dict with 'examples' key
    if isinstance(data, list):
        examples = data
    else:
        examples = data.get('examples', data)

    # Normalize field names
    normalized = []
    for ex in examples:
        normalized.append({
            'summary': ex.get('summary', ex.get('text', '')),
            'labels': ex.get('ground_truth', ex.get('labels', [])),
            'platform': ex.get('platform', 'IOS-XE'),
            'advisory_id': ex.get('advisory_id', ex.get('advisoryId', None))
        })
    return normalized


def extract_labels_from_text(text: str) -> List[str]:
    """Extract labels from model output text"""
    labels = []

    # Format 1: Label: ['X', 'Y'] or Labels: ['X', 'Y']
    match = re.search(r"Label[s]?:\s*\[([^\]]+)\]", text, re.IGNORECASE)
    if match:
        labels = re.findall(r"'([^']+)'", match.group(1))
        if not labels:
            labels = re.findall(r'"([^"]+)"', match.group(1))

    # Format 2: {"labels": ["X", "Y"]}
    if not labels:
        match = re.search(r'"labels"\s*:\s*\[([^\]]+)\]', text)
        if match:
            labels = re.findall(r'"([^"]+)"', match.group(1))

    # Format 3: Label-like patterns (UPPERCASE_WITH_UNDERSCORES)
    if not labels:
        potential = re.findall(r'\b([A-Z][A-Z0-9_]+(?:_[A-Z0-9]+)+)\b', text)
        labels = [l for l in potential if len(l) > 5 and '_' in l][:3]

    return labels


def compute_metrics(predictions: List[Dict]) -> Dict:
    """Compute evaluation metrics"""
    exact_matches = 0
    partial_matches = 0
    total_f1 = 0.0
    total_precision = 0.0
    total_recall = 0.0

    label_stats = defaultdict(lambda: {'tp': 0, 'fp': 0, 'fn': 0})

    for pred in predictions:
        pred_set = set(pred['pred'])
        truth_set = set(pred['truth'])

        # Exact match
        if pred_set == truth_set:
            exact_matches += 1

        # Partial match
        if pred_set & truth_set:
            partial_matches += 1

        # F1 score (label-level)
        if pred_set or truth_set:
            tp = len(pred_set & truth_set)
            fp = len(pred_set - truth_set)
            fn = len(truth_set - pred_set)

            precision = tp / (tp + fp) if (tp + fp) > 0 else 0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0
            f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

            total_f1 += f1
            total_precision += precision
            total_recall += recall

            # Track per-label stats
            for label in pred_set & truth_set:
                label_stats[label]['tp'] += 1
            for label in pred_set - truth_set:
                label_stats[label]['fp'] += 1
            for label in truth_set - pred_set:
                label_stats[label]['fn'] += 1

    n = len(predictions)
    return {
        'exact_match': exact_matches / n if n > 0 else 0,
        'exact_match_count': exact_matches,
        'partial_match': partial_matches / n if n > 0 else 0,
        'partial_match_count': partial_matches,
        'avg_f1': total_f1 / n if n > 0 else 0,
        'avg_precision': total_precision / n if n > 0 else 0,
        'avg_recall': total_recall / n if n > 0 else 0,
        'total_examples': n,
        'label_stats': dict(label_stats)
    }


def evaluate_v3_fewshot(test_examples: List[Dict], output_dir: str = "models") -> Dict:
    """
    Evaluate v3: SEC-8B + FAISS few-shot (current production)

    Uses the FewShotPSIRTLabeler from fewshot_inference.py
    """
    print("\n" + "=" * 70)
    print("EVALUATING V3: SEC-8B + FAISS FEW-SHOT")
    print("=" * 70)

    # Import here to avoid loading model if not needed
    import sys
    sys.path.insert(0, '.')
    from fewshot_inference import FewShotPSIRTLabeler

    labeler = FewShotPSIRTLabeler()

    predictions = []
    total_time = 0

    for i, example in enumerate(test_examples):
        print(f"\r  Processing {i+1}/{len(test_examples)}...", end='', flush=True)

        start = time.time()
        try:
            result = labeler.predict_labels(
                psirt_summary=example['summary'],
                platform=example['platform'],
                advisory_id=example.get('advisory_id'),
                k=5,
                max_new_tokens=300
            )
            elapsed = time.time() - start
            total_time += elapsed

            pred_labels = result.get('predicted_labels', [])

        except Exception as e:
            print(f"\n  Error on example {i}: {e}")
            pred_labels = []
            elapsed = 0

        predictions.append({
            'pred': pred_labels,
            'truth': example['labels'],
            'platform': example['platform'],
            'time': elapsed
        })

    print(f"\n  Total inference time: {total_time:.1f}s")
    print(f"  Avg time per example: {total_time/len(test_examples):.2f}s")

    metrics = compute_metrics(predictions)
    metrics['avg_time_per_example'] = total_time / len(test_examples)
    metrics['predictions'] = predictions

    # Save results
    output_path = Path(output_dir) / "eval_results_v3_fewshot.json"
    with open(output_path, 'w') as f:
        json.dump({'config': 'v3_faiss_fewshot', **metrics}, f, indent=2)
    print(f"  Results saved to {output_path}")

    return metrics


def evaluate_v4a_lora_only(test_examples: List[Dict], output_dir: str = "models") -> Dict:
    """
    Evaluate v4a: SEC-8B + LoRA (standalone, no FAISS)

    Direct inference with LoRA adapter using MLX-LM, no few-shot retrieval
    """
    print("\n" + "=" * 70)
    print("EVALUATING V4A: SEC-8B + LORA (STANDALONE)")
    print("=" * 70)

    from mlx_lm import load, generate
    import yaml

    # Load model with MLX-LM
    model_id = "fdtn-ai/Foundation-Sec-8B"
    adapter_path = "models/lora_adapter_v1"

    print(f"  Loading {model_id} with MLX-LM...")
    print(f"  Loading LoRA adapter from {adapter_path}...")
    model, tokenizer = load(model_id, adapter_path=adapter_path)
    print("  Model loaded successfully")

    # Load taxonomy for validation
    print("  Loading taxonomies...")
    taxonomy = {}
    for platform, filepath in [
        ('IOS-XE', 'taxonomies/features.yml'),
        ('IOS-XR', 'taxonomies/features_iosxr.yml'),
        ('ASA', 'taxonomies/features_asa.yml'),
        ('FTD', 'taxonomies/features_asa.yml'),
        ('NX-OS', 'taxonomies/features_nxos.yml'),
    ]:
        try:
            with open(filepath) as f:
                features = yaml.safe_load(f)
            taxonomy[platform] = [feat['label'] for feat in features]
        except:
            taxonomy[platform] = []

    predictions = []
    total_time = 0

    for i, example in enumerate(test_examples):
        print(f"\r  Processing {i+1}/{len(test_examples)}...", end='', flush=True)

        # Build prompt (CoT format)
        prompt = f"""### Instruction:
Classify the following Cisco Security Advisory into the correct technical feature label.

### Input:
{example['summary']}

### Response:
"""

        start = time.time()
        response = generate(
            model,
            tokenizer,
            prompt=prompt,
            max_tokens=250,
            verbose=False
        )
        elapsed = time.time() - start
        total_time += elapsed

        # Extract labels
        pred_labels = extract_labels_from_text(response)

        # Validate against taxonomy
        valid_labels = taxonomy.get(example['platform'], [])
        pred_labels = [l for l in pred_labels if l in valid_labels]

        predictions.append({
            'pred': pred_labels,
            'truth': example['labels'],
            'platform': example['platform'],
            'time': elapsed,
            'raw_output': response[:500]
        })

    print(f"\n  Total inference time: {total_time:.1f}s")
    print(f"  Avg time per example: {total_time/len(test_examples):.2f}s")

    metrics = compute_metrics(predictions)
    metrics['avg_time_per_example'] = total_time / len(test_examples)
    metrics['predictions'] = predictions

    # Save results
    output_path = Path(output_dir) / "eval_results_v4a_lora_only.json"
    with open(output_path, 'w') as f:
        json.dump({'config': 'v4a_lora_only', **metrics}, f, indent=2)
    print(f"  Results saved to {output_path}")

    # Clean up
    del model

    return metrics


def evaluate_v4b_lora_faiss(test_examples: List[Dict], output_dir: str = "models") -> Dict:
    """
    Evaluate v4b: SEC-8B + LoRA + FAISS (combined)

    Few-shot retrieval with LoRA-enhanced model using MLX-LM
    """
    print("\n" + "=" * 70)
    print("EVALUATING V4B: SEC-8B + LORA + FAISS (COMBINED)")
    print("=" * 70)

    from mlx_lm import load, generate
    from sentence_transformers import SentenceTransformer
    import faiss
    import pandas as pd
    import yaml

    # Load FAISS and embedder
    print("  Loading FAISS index and embedder...")
    with open('models/embedder_info.json', 'r') as f:
        embedder_info = json.load(f)
    embedder = SentenceTransformer(embedder_info['model_name'])

    faiss_index = faiss.read_index('models/faiss_index.bin')
    labeled_examples = pd.read_parquet('models/labeled_examples.parquet')
    print(f"  FAISS index loaded ({faiss_index.ntotal} examples)")

    # Load model with MLX-LM
    model_id = "fdtn-ai/Foundation-Sec-8B"
    adapter_path = "models/lora_adapter_v1"

    print(f"  Loading {model_id} with MLX-LM...")
    print(f"  Loading LoRA adapter from {adapter_path}...")
    model, tokenizer = load(model_id, adapter_path=adapter_path)
    print("  Model loaded successfully")

    # Load taxonomy
    print("  Loading taxonomies...")
    taxonomy = {}
    for platform, filepath in [
        ('IOS-XE', 'taxonomies/features.yml'),
        ('IOS-XR', 'taxonomies/features_iosxr.yml'),
        ('ASA', 'taxonomies/features_asa.yml'),
        ('FTD', 'taxonomies/features_asa.yml'),
        ('NX-OS', 'taxonomies/features_nxos.yml'),
    ]:
        try:
            with open(filepath) as f:
                features = yaml.safe_load(f)
            taxonomy[platform] = [feat['label'] for feat in features]
        except:
            taxonomy[platform] = []

    def retrieve_examples(query_text: str, platform: str, k: int = 5):
        """Retrieve similar examples from FAISS"""
        query_embedding = embedder.encode([query_text])
        distances, indices = faiss_index.search(query_embedding.astype('float32'), k=min(k*3, faiss_index.ntotal))

        examples = []
        for idx in indices[0]:
            row = labeled_examples.iloc[idx]
            if row['platform'] != platform:
                continue
            labels = row['labels_list']
            if hasattr(labels, 'tolist'):
                labels = labels.tolist()
            examples.append({
                'summary': row['summary'],
                'platform': row['platform'],
                'labels': labels
            })
            if len(examples) >= k:
                break
        return examples

    predictions = []
    total_time = 0

    for i, example in enumerate(test_examples):
        print(f"\r  Processing {i+1}/{len(test_examples)}...", end='', flush=True)

        # Retrieve similar examples
        similar_examples = retrieve_examples(example['summary'], example['platform'], k=5)

        # Build few-shot prompt
        valid_labels = taxonomy.get(example['platform'], [])
        prompt = f"""You are a Cisco security advisory labeling expert. Your task is to assign feature labels from a closed taxonomy to PSIRTs based on their summary text.

Platform: {example['platform']}

CRITICAL: You must ONLY use labels from this exact list. Do not invent new labels.
Available labels for {example['platform']}:
{', '.join(sorted(valid_labels))}

Here are some examples of correctly labeled PSIRTs:

"""
        for j, ex in enumerate(similar_examples, 1):
            prompt += f"""Example {j}:
Summary: {ex['summary']}
Labels: {json.dumps(ex['labels'])}

"""

        prompt += f"""Now label this new PSIRT.

Summary: {example['summary']}
Platform: {example['platform']}

Think step by step about which features are affected, then provide your answer.
Label:"""

        start = time.time()
        response = generate(
            model,
            tokenizer,
            prompt=prompt,
            max_tokens=250,
            verbose=False
        )
        elapsed = time.time() - start
        total_time += elapsed

        # Extract labels
        pred_labels = extract_labels_from_text(response)

        # Validate against taxonomy
        pred_labels = [l for l in pred_labels if l in valid_labels]

        predictions.append({
            'pred': pred_labels,
            'truth': example['labels'],
            'platform': example['platform'],
            'time': elapsed
        })

    print(f"\n  Total inference time: {total_time:.1f}s")
    print(f"  Avg time per example: {total_time/len(test_examples):.2f}s")

    metrics = compute_metrics(predictions)
    metrics['avg_time_per_example'] = total_time / len(test_examples)
    metrics['predictions'] = predictions

    # Save results
    output_path = Path(output_dir) / "eval_results_v4b_lora_faiss.json"
    with open(output_path, 'w') as f:
        json.dump({'config': 'v4b_lora_faiss', **metrics}, f, indent=2)
    print(f"  Results saved to {output_path}")

    # Clean up
    del model

    return metrics


def print_comparison(results: Dict[str, Dict]):
    """Print comparison table"""
    print("\n" + "=" * 80)
    print("EVALUATION COMPARISON SUMMARY")
    print("=" * 80)

    headers = ["Metric", "v3 (FAISS)", "v4a (LoRA)", "v4b (LoRA+FAISS)", "Best"]

    metrics_to_compare = [
        ('exact_match', 'Exact Match', '{:.1%}'),
        ('partial_match', 'Partial Match', '{:.1%}'),
        ('avg_f1', 'Avg F1 Score', '{:.3f}'),
        ('avg_precision', 'Avg Precision', '{:.3f}'),
        ('avg_recall', 'Avg Recall', '{:.3f}'),
        ('avg_time_per_example', 'Avg Time (s)', '{:.2f}'),
    ]

    print(f"\n{'Metric':<20} {'v3 (FAISS)':<15} {'v4a (LoRA)':<15} {'v4b (Both)':<15} {'Best':<10}")
    print("-" * 75)

    for key, name, fmt in metrics_to_compare:
        v3 = results.get('v3', {}).get(key, 0)
        v4a = results.get('v4a', {}).get(key, 0)
        v4b = results.get('v4b', {}).get(key, 0)

        # Determine best (for time, lower is better)
        if key == 'avg_time_per_example':
            values = {'v3': v3, 'v4a': v4a, 'v4b': v4b}
            best = min(values, key=lambda x: values[x] if values[x] > 0 else float('inf'))
        else:
            values = {'v3': v3, 'v4a': v4a, 'v4b': v4b}
            best = max(values, key=lambda x: values[x])

        print(f"{name:<20} {fmt.format(v3):<15} {fmt.format(v4a):<15} {fmt.format(v4b):<15} {best:<10}")

    # Print counts
    print("-" * 75)
    total = results.get('v3', {}).get('total_examples', 0)
    print(f"{'Total Examples':<20} {total:<15}")
    print(f"{'Exact Match Count':<20} {results.get('v3', {}).get('exact_match_count', 0):<15} {results.get('v4a', {}).get('exact_match_count', 0):<15} {results.get('v4b', {}).get('exact_match_count', 0):<15}")

    print("\n" + "=" * 80)


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Evaluate LoRA configurations')
    parser.add_argument('--test-set', default='models/evaluation_test_set.json',
                        help='Path to test set JSON')
    parser.add_argument('--v3', action='store_true', help='Evaluate v3 (FAISS only)')
    parser.add_argument('--v4a', action='store_true', help='Evaluate v4a (LoRA only)')
    parser.add_argument('--v4b', action='store_true', help='Evaluate v4b (LoRA + FAISS)')
    parser.add_argument('--all', action='store_true', help='Evaluate all configurations')
    parser.add_argument('--compare-only', action='store_true', help='Only print comparison from existing results')

    args = parser.parse_args()

    # Default to all if no specific option selected
    if not any([args.v3, args.v4a, args.v4b, args.all, args.compare_only]):
        args.all = True

    if args.compare_only:
        # Load existing results and compare
        results = {}
        for name, path in [
            ('v3', 'models/eval_results_v3_fewshot.json'),
            ('v4a', 'models/eval_results_v4a_lora_only.json'),
            ('v4b', 'models/eval_results_v4b_lora_faiss.json'),
        ]:
            try:
                with open(path) as f:
                    results[name] = json.load(f)
            except FileNotFoundError:
                print(f"  Warning: {path} not found")

        print_comparison(results)
        return

    # Load test set
    print(f"Loading test set from {args.test_set}...")
    test_examples = load_test_set(args.test_set)
    print(f"Loaded {len(test_examples)} test examples")

    results = {}

    if args.all or args.v3:
        results['v3'] = evaluate_v3_fewshot(test_examples)

    if args.all or args.v4a:
        results['v4a'] = evaluate_v4a_lora_only(test_examples)

    if args.all or args.v4b:
        results['v4b'] = evaluate_v4b_lora_faiss(test_examples)

    # Print comparison
    if len(results) > 1:
        print_comparison(results)

    print("\nEvaluation complete!")


if __name__ == "__main__":
    main()
