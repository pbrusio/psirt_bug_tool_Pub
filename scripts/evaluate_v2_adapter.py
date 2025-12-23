#!/usr/bin/env python3
"""
Evaluate LoRA Adapter v2 (trained on cleaned data)

Compares v5 (v2 adapter on cleaned data) to v4b baseline.
"""

import json
import time
import re
from pathlib import Path
from typing import List, Dict
from collections import defaultdict


def load_test_set(path: str = "models/evaluation_test_set.json") -> List[Dict]:
    """Load evaluation test set"""
    with open(path, 'r') as f:
        data = json.load(f)

    if isinstance(data, list):
        examples = data
    else:
        examples = data.get('examples', data)

    normalized = []
    for ex in examples:
        normalized.append({
            'summary': ex.get('summary', ex.get('text', '')),
            'labels': ex.get('ground_truth', ex.get('labels', [])),
            'platform': ex.get('platform', 'IOS-XE'),
            'advisory_id': ex.get('advisory_id', ex.get('advisoryId', None))
        })
    return normalized


def filter_overpredictions(predicted_labels: List[str], summary: str) -> List[str]:
    """
    Filter known false positive patterns based on empirical analysis.

    Patterns identified:
    1. SYS_Licensing_Smart: Triggered by boot/upgrade, privilege, hardware keywords
    2. L2_LACP: Over-predicted for CoPP/QoS issues
    3. L2_Switchport_Trunk: Over-predicted when 'trunk' appears in error messages
    """
    filtered = predicted_labels.copy()
    summary_lower = summary.lower()

    # SYS_Licensing_Smart over-prediction filter
    if 'SYS_Licensing_Smart' in filtered:
        boot_indicators = ['configure replace', 'config replace', 'reimage', 'partition', 'ssd',
                          'rommon', 'install mode', 'bundle mode']
        mgmt_indicators = ['tcl', 'privilege', 'escalation', 'rbac',
                          'role-based', 'interpreter', 'tool command']
        hw_indicators = ['fan', 'sensor', 'temperature', 'power supply',
                        'hotswap', 'inlet']

        has_false_indicator = any(ind in summary_lower for ind in
                                  boot_indicators + mgmt_indicators + hw_indicators)

        if has_false_indicator:
            licensing_keywords = ['license', 'smart account', 'cssm', 'cslu',
                                 'slr', 'registration', 'entitlement', 'smart licensing']
            has_licensing = any(kw in summary_lower for kw in licensing_keywords)

            if not has_licensing:
                filtered.remove('SYS_Licensing_Smart')

    # L2_LACP over-prediction filter: Remove when CoPP/QoS context with no LACP keywords
    if 'L2_LACP' in filtered:
        copp_qos_context = 'copp' in summary_lower or 'control plane' in summary_lower
        has_lacp_keywords = any(kw in summary_lower for kw in ['lacp', 'port-channel', 'lag', 'aggregat'])
        if copp_qos_context and not has_lacp_keywords:
            filtered.remove('L2_LACP')

    # L2_Switchport_Trunk over-prediction filter:
    # Remove when 'trunk' only appears in error message context (e.g., "before switching to mode trunk")
    # and the actual issue is about access port or port-security
    if 'L2_Switchport_Trunk' in filtered:
        has_portsecurity = 'SEC_PortSecurity' in filtered or 'port-security' in summary_lower
        has_access_mode = 'L2_Switchport_Access' in filtered or 'mode access' in summary_lower
        # Only remove if trunk appears in "switching to mode trunk" context (error message)
        trunk_in_error_context = 'switching to mode trunk' in summary_lower or 'before switching to' in summary_lower
        if has_portsecurity and has_access_mode and trunk_in_error_context:
            filtered.remove('L2_Switchport_Trunk')

    return filtered


def extract_labels_from_text(text: str) -> List[str]:
    """Extract labels from model output text"""
    labels = []

    # Format 0: Raw list format ['X', 'Y'] at start (common from our adapter)
    match = re.search(r"^\s*\[([^\]]+)\]", text.strip())
    if match:
        labels = re.findall(r"'([^']+)'", match.group(1))
        if not labels:
            labels = re.findall(r'"([^"]+)"', match.group(1))
        if labels:
            return labels

    # Format 1: Label: ['X', 'Y'] or Labels: ['X', 'Y']
    match = re.search(r"Label[s]?:\s*\[([^\]]+)\]", text, re.IGNORECASE)
    if match:
        labels = re.findall(r"'([^']+)'", match.group(1))
        if not labels:
            labels = re.findall(r'"([^"]+)"', match.group(1))
        if labels:
            return labels

    # Format 2: {"labels": ["X", "Y"]}
    match = re.search(r'"labels"\s*:\s*\[([^\]]+)\]', text)
    if match:
        labels = re.findall(r'"([^"]+)"', match.group(1))
        if labels:
            return labels

    # Format 3: Label-like patterns (UPPERCASE_WITH_UNDERSCORES)
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
    empty_predictions = 0

    label_stats = defaultdict(lambda: {'tp': 0, 'fp': 0, 'fn': 0})

    for pred in predictions:
        pred_set = set(pred['pred'])
        truth_set = set(pred['truth'])

        if not pred_set:
            empty_predictions += 1

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
        'empty_predictions': empty_predictions,
        'empty_rate': empty_predictions / n if n > 0 else 0,
        'avg_f1': total_f1 / n if n > 0 else 0,
        'avg_precision': total_precision / n if n > 0 else 0,
        'avg_recall': total_recall / n if n > 0 else 0,
        'total_examples': n,
        'label_stats': dict(label_stats)
    }


def evaluate_v5_lora_faiss(test_examples: List[Dict], adapter_path: str = "models/lora_adapter_v2") -> Dict:
    """
    Evaluate v5: SEC-8B + LoRA v2 + FAISS (on cleaned data)
    """
    print("\n" + "=" * 70)
    print("EVALUATING V5: SEC-8B + LORA v2 + FAISS (CLEANED DATA)")
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

    # Use the cleaned FAISS index (rebuilt on cleaned data)
    faiss_index = faiss.read_index('models/faiss_index.bin')  # Now using cleaned index
    # Use symlink that points to current versioned file
    labeled_examples = pd.read_parquet('models/labeled_examples.parquet')
    print(f"  FAISS index loaded ({faiss_index.ntotal} vectors)")
    print(f"  Using cleaned labeled examples ({len(labeled_examples)} examples)")

    if faiss_index.ntotal != len(labeled_examples):
        print(f"  WARNING: FAISS index size ({faiss_index.ntotal}) != examples ({len(labeled_examples)})")
        print(f"           The index may not have been rebuilt on cleaned data")

    # Load model with MLX-LM
    model_id = "fdtn-ai/Foundation-Sec-8B"

    print(f"  Loading {model_id} with MLX-LM...")
    print(f"  Loading LoRA adapter from {adapter_path}...")
    model, tokenizer = load(model_id, adapter_path=adapter_path)
    print("  Model loaded successfully")

    # Load taxonomy with descriptions
    print("  Loading taxonomies with definitions...")
    taxonomy = {}
    taxonomy_defs = {}
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
            taxonomy_defs[platform] = {
                feat['label']: feat.get('description', f"Label for {feat['label']}")
                for feat in features
            }
        except:
            taxonomy[platform] = []
            taxonomy_defs[platform] = {}

    def build_taxonomy_context(platform: str, max_desc_len: int = 80) -> str:
        """Build compact definition list for prompt"""
        defs = taxonomy_defs.get(platform, {})
        lines = []
        for label in taxonomy.get(platform, []):
            description = defs.get(label, f"Label for {label}")
            first_sentence = description.split('.')[0] if '.' in description else description
            if len(first_sentence) > max_desc_len:
                first_sentence = first_sentence[:max_desc_len] + "..."
            lines.append(f"- {label}: {first_sentence}")
        return '\n'.join(lines)

    def retrieve_examples(query_text: str, platform: str, k: int = 5):
        """Retrieve similar examples from FAISS"""
        query_embedding = embedder.encode([query_text])
        distances, indices = faiss_index.search(query_embedding.astype('float32'), k=min(k*3, faiss_index.ntotal))

        examples = []
        for idx in indices[0]:
            if idx >= len(labeled_examples):
                continue
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

        # Build few-shot prompt (no taxonomy defs - model already trained on them)
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

        # Apply inference-time filter for known over-predictions
        pred_labels = filter_overpredictions(pred_labels, example['summary'])

        predictions.append({
            'pred': pred_labels,
            'truth': example['labels'],
            'platform': example['platform'],
            'time': elapsed,
            'raw_output': response[:500]  # Save all for debugging
        })

    print(f"\n  Total inference time: {total_time:.1f}s")
    print(f"  Avg time per example: {total_time/len(test_examples):.2f}s")

    metrics = compute_metrics(predictions)
    metrics['avg_time_per_example'] = total_time / len(test_examples)
    metrics['predictions'] = predictions

    # Save results
    output_path = Path("models") / "eval_results_v10_final.json"
    with open(output_path, 'w') as f:
        json.dump({'config': 'v5_lora_v2_faiss_cleaned', **metrics}, f, indent=2)
    print(f"  Results saved to {output_path}")

    # Clean up
    del model

    return metrics


def print_comparison(v4b_results: Dict, v5_results: Dict):
    """Print comparison table"""
    print("\n" + "=" * 80)
    print("EVALUATION COMPARISON: v4b (baseline) vs v5 (cleaned)")
    print("=" * 80)

    metrics_to_compare = [
        ('exact_match', 'Exact Match', '{:.1%}'),
        ('partial_match', 'Partial Match', '{:.1%}'),
        ('empty_rate', 'Empty Predictions', '{:.1%}'),
        ('avg_f1', 'Avg F1 Score', '{:.3f}'),
        ('avg_precision', 'Avg Precision', '{:.3f}'),
        ('avg_recall', 'Avg Recall', '{:.3f}'),
        ('avg_time_per_example', 'Avg Time (s)', '{:.2f}'),
    ]

    print(f"\n{'Metric':<22} {'v4b (baseline)':<18} {'v5 (cleaned)':<18} {'Change':<15}")
    print("-" * 75)

    for key, name, fmt in metrics_to_compare:
        v4b = v4b_results.get(key, 0)
        v5 = v5_results.get(key, 0)

        # Calculate change
        if key == 'avg_time_per_example' or key == 'empty_rate':
            # Lower is better
            change = v4b - v5
            better = change > 0
        else:
            # Higher is better
            change = v5 - v4b
            better = change > 0

        if key in ['exact_match', 'partial_match', 'empty_rate']:
            change_str = f"{change:+.1%}"
        elif key == 'avg_time_per_example':
            change_str = f"{change:+.2f}s"
        else:
            change_str = f"{change:+.3f}"

        indicator = "✓" if better else "✗" if change != 0 else "-"

        print(f"{name:<22} {fmt.format(v4b):<18} {fmt.format(v5):<18} {change_str} {indicator}")

    # Print counts
    print("-" * 75)
    print(f"{'Exact Match Count':<22} {v4b_results.get('exact_match_count', 0):<18} {v5_results.get('exact_match_count', 0):<18}")
    print(f"{'Partial Match Count':<22} {v4b_results.get('partial_match_count', 0):<18} {v5_results.get('partial_match_count', 0):<18}")
    print(f"{'Empty Predictions':<22} {v4b_results.get('empty_predictions', 'N/A'):<18} {v5_results.get('empty_predictions', 0):<18}")
    print(f"{'Total Examples':<22} {v4b_results.get('total_examples', 0):<18} {v5_results.get('total_examples', 0):<18}")

    print("\n" + "=" * 80)


def main():
    print("=" * 70)
    print("V5 EVALUATION: LoRA v2 Adapter (Trained on Cleaned Data)")
    print("=" * 70)

    # Load test set (use cleaned version without GAP labels)
    print("\nLoading test set...")
    test_set_path = "models/evaluation_test_set_cleaned.json"
    test_examples = load_test_set(test_set_path)
    print(f"Loaded {len(test_examples)} test examples from {test_set_path}")

    # Load v4b baseline results
    print("\nLoading v4b baseline results...")
    try:
        with open('models/eval_results_v4b_lora_faiss.json', 'r') as f:
            v4b_results = json.load(f)
        print(f"  v4b exact match: {v4b_results.get('exact_match', 0):.1%}")
    except FileNotFoundError:
        print("  Warning: v4b results not found, will skip comparison")
        v4b_results = {}

    # Run v5 evaluation (now using v3 adapter with FAIL label re-synthesis)
    v5_results = evaluate_v5_lora_faiss(test_examples, adapter_path="models/lora_adapter")

    # Print comparison
    if v4b_results:
        print_comparison(v4b_results, v5_results)

    print("\n" + "=" * 70)
    print("EVALUATION COMPLETE")
    print("=" * 70)
    print(f"\nv5 Results Summary:")
    print(f"  Exact Match:    {v5_results['exact_match']:.1%} ({v5_results['exact_match_count']}/{v5_results['total_examples']})")
    print(f"  Partial Match:  {v5_results['partial_match']:.1%} ({v5_results['partial_match_count']}/{v5_results['total_examples']})")
    print(f"  Empty Preds:    {v5_results['empty_rate']:.1%} ({v5_results['empty_predictions']}/{v5_results['total_examples']})")
    print(f"  Avg F1:         {v5_results['avg_f1']:.3f}")
    print(f"  Avg Time:       {v5_results['avg_time_per_example']:.2f}s")


if __name__ == "__main__":
    main()
