#!/usr/bin/env python3
"""
Per-Label Performance Analysis Script
======================================

Generates a detailed report showing precision, recall, and F1 for each label.
Helps identify which labels need more training data or have issues.

Usage:
    python scripts/analyze_label_performance.py
    python scripts/analyze_label_performance.py --eval-results models/eval_results_v5_cleaned.json
    python scripts/analyze_label_performance.py --output label_performance_report.md
"""

import json
import argparse
import pandas as pd
from pathlib import Path
from collections import defaultdict
from datetime import datetime


def load_eval_results(path: str) -> dict:
    """Load evaluation results"""
    with open(path, 'r') as f:
        return json.load(f)


def load_training_data(path: str) -> pd.DataFrame:
    """Load training data to count examples per label"""
    return pd.read_parquet(path)


def count_training_labels(df: pd.DataFrame) -> dict:
    """Count occurrences of each label in training data"""
    label_counts = defaultdict(int)
    for _, row in df.iterrows():
        labels = row.get('labels_list', row.get('labels', []))
        if labels is None:
            continue
        if hasattr(labels, 'tolist'):
            labels = labels.tolist()
        for label in labels:
            label_counts[label] += 1
    return dict(label_counts)


def count_test_labels(predictions: list) -> dict:
    """Count occurrences of each label in test set"""
    label_counts = defaultdict(int)
    for pred in predictions:
        for label in pred.get('truth', []):
            label_counts[label] += 1
    return dict(label_counts)


def compute_per_label_metrics(predictions: list) -> dict:
    """Compute precision, recall, F1 for each label"""
    label_stats = defaultdict(lambda: {'tp': 0, 'fp': 0, 'fn': 0})

    for pred in predictions:
        pred_set = set(pred.get('pred', []))
        truth_set = set(pred.get('truth', []))

        for label in pred_set & truth_set:
            label_stats[label]['tp'] += 1
        for label in pred_set - truth_set:
            label_stats[label]['fp'] += 1
        for label in truth_set - pred_set:
            label_stats[label]['fn'] += 1

    metrics = {}
    for label, stats in label_stats.items():
        tp = stats['tp']
        fp = stats['fp']
        fn = stats['fn']

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

        metrics[label] = {
            'precision': precision,
            'recall': recall,
            'f1': f1,
            'tp': tp,
            'fp': fp,
            'fn': fn,
        }

    return metrics


def generate_report(metrics: dict, train_counts: dict, test_counts: dict,
                    overall_metrics: dict, output_path: str = None) -> str:
    """Generate the performance report"""

    lines = []
    lines.append("# Per-Label Performance Report")
    lines.append("")
    lines.append(f"Generated: {datetime.now().isoformat()}")
    lines.append("")

    # Overall summary
    lines.append("## Overall Metrics")
    lines.append("")
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Exact Match | {overall_metrics.get('exact_match', 0)*100:.1f}% |")
    lines.append(f"| Partial Match | {overall_metrics.get('partial_match', 0)*100:.1f}% |")
    lines.append(f"| Avg F1 | {overall_metrics.get('avg_f1', 0):.3f} |")
    lines.append(f"| Avg Precision | {overall_metrics.get('avg_precision', 0):.3f} |")
    lines.append(f"| Avg Recall | {overall_metrics.get('avg_recall', 0):.3f} |")
    lines.append(f"| Total Test Examples | {overall_metrics.get('total_examples', 0)} |")
    lines.append("")

    # Combine all labels
    all_labels = set(metrics.keys()) | set(test_counts.keys())

    # Build table data
    table_data = []
    for label in all_labels:
        m = metrics.get(label, {'precision': 0, 'recall': 0, 'f1': 0, 'tp': 0, 'fp': 0, 'fn': 0})
        train_count = train_counts.get(label, 0)
        test_count = test_counts.get(label, 0)

        # Determine status
        if test_count == 0:
            status = "-"  # Not in test set
        elif m['recall'] == 0 and train_count == 0:
            status = "GAP"  # No training data
        elif m['recall'] == 0 and train_count > 0:
            status = "FAIL"  # Has training but not predicting
        elif m['f1'] < 0.3:
            status = "LOW"  # Poor performance
        elif m['f1'] >= 0.7:
            status = "OK"  # Good
        else:
            status = "MED"  # Medium

        table_data.append({
            'label': label,
            'precision': m['precision'],
            'recall': m['recall'],
            'f1': m['f1'],
            'train_count': train_count,
            'test_count': test_count,
            'tp': m['tp'],
            'fp': m['fp'],
            'fn': m['fn'],
            'status': status,
        })

    # Sort by F1 score (ascending to show problems first)
    table_data.sort(key=lambda x: (x['status'] != 'GAP', x['status'] != 'FAIL', x['f1']))

    # Per-label table
    lines.append("## Per-Label Performance")
    lines.append("")
    lines.append("Status: GAP=no training data, FAIL=has data but 0 recall, LOW=F1<0.3, MED=0.3-0.7, OK=F1>=0.7")
    lines.append("")
    lines.append("| Label | Precision | Recall | F1 | Train | Test | TP | FP | FN | Status |")
    lines.append("|-------|-----------|--------|-----|-------|------|----|----|----|----|")

    for row in table_data:
        if row['test_count'] == 0:
            continue  # Skip labels not in test set
        lines.append(
            f"| {row['label']} | {row['precision']:.2f} | {row['recall']:.2f} | "
            f"{row['f1']:.2f} | {row['train_count']} | {row['test_count']} | "
            f"{row['tp']} | {row['fp']} | {row['fn']} | {row['status']} |"
        )

    lines.append("")

    # Problem labels section
    gap_labels = [r for r in table_data if r['status'] == 'GAP' and r['test_count'] > 0]
    fail_labels = [r for r in table_data if r['status'] == 'FAIL']
    low_labels = [r for r in table_data if r['status'] == 'LOW']

    lines.append("## Labels Needing Attention")
    lines.append("")

    if gap_labels:
        lines.append("### GAP: Labels in test set with NO training data")
        lines.append("")
        for r in gap_labels:
            lines.append(f"- **{r['label']}**: {r['test_count']} test examples, 0 training examples")
        lines.append("")

    if fail_labels:
        lines.append("### FAIL: Labels with training data but 0% recall")
        lines.append("")
        for r in fail_labels:
            lines.append(f"- **{r['label']}**: {r['train_count']} training, {r['test_count']} test, recall=0")
        lines.append("")

    if low_labels:
        lines.append("### LOW: Labels with F1 < 0.3")
        lines.append("")
        for r in low_labels:
            lines.append(f"- **{r['label']}**: F1={r['f1']:.2f}, precision={r['precision']:.2f}, recall={r['recall']:.2f}")
        lines.append("")

    # Recommendations
    lines.append("## Recommendations")
    lines.append("")
    if gap_labels:
        lines.append(f"1. **Add training data** for {len(gap_labels)} labels with no examples")
    if fail_labels:
        lines.append(f"2. **Investigate** {len(fail_labels)} labels that have training data but aren't being predicted")
    if low_labels:
        lines.append(f"3. **Improve** {len(low_labels)} labels with low F1 scores")
    lines.append("")

    report = '\n'.join(lines)

    if output_path:
        with open(output_path, 'w') as f:
            f.write(report)
        print(f"Report saved to: {output_path}")

    return report


def main():
    parser = argparse.ArgumentParser(description='Analyze per-label performance')
    parser.add_argument('--eval-results', default='models/eval_results_v5_cleaned.json',
                        help='Path to evaluation results JSON')
    parser.add_argument('--training-data', default='models/labeled_examples_cleaned_v2.parquet',
                        help='Path to training data parquet')
    parser.add_argument('--output', '-o', default='label_performance_report.md',
                        help='Output path for report')
    parser.add_argument('--print', action='store_true', help='Print report to stdout')
    args = parser.parse_args()

    print("Loading evaluation results...")
    eval_results = load_eval_results(args.eval_results)
    predictions = eval_results.get('predictions', [])

    print("Loading training data...")
    train_df = load_training_data(args.training_data)

    print("Computing metrics...")
    train_counts = count_training_labels(train_df)
    test_counts = count_test_labels(predictions)
    per_label_metrics = compute_per_label_metrics(predictions)

    overall_metrics = {k: v for k, v in eval_results.items() if k != 'predictions' and k != 'label_stats'}

    print("Generating report...")
    report = generate_report(
        per_label_metrics,
        train_counts,
        test_counts,
        overall_metrics,
        args.output
    )

    if args.print:
        print("\n" + report)

    print("\nDone!")


if __name__ == '__main__':
    main()
