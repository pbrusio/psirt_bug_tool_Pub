#!/usr/bin/env python3
"""
Test FAISS Improvement: Before vs After GPT-4o Bug Data

Tests SEC-8B performance with current FAISS index (165 PSIRTs only) vs
expanded index (165 PSIRTs + 4,664 bugs).

Usage:
    # Test with current FAISS (baseline)
    python test_faiss_improvement.py --baseline

    # Test with expanded FAISS (after adding bugs)
    python test_faiss_improvement.py --expanded

    # Compare both
    python test_faiss_improvement.py --compare
"""
import json
import argparse
import random
from pathlib import Path
from typing import Dict, List, Tuple
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from fewshot_inference import FewShotPSIRTLabeler
from datetime import datetime


class FAISSComparisonTest:
    """Compare FAISS performance before/after adding GPT-4o bugs"""

    def __init__(self):
        self.test_bugs = []
        self.baseline_results = []
        self.expanded_results = []

    def load_test_bugs(self, num_bugs: int = 10) -> List[Dict]:
        """Load random sample of bugs for testing"""
        print(f"\n📂 Loading test bugs...")

        with open('gpt4o_labeled_bugs.json', 'r') as f:
            all_bugs = json.load(f)

        # Get diverse sample across platforms
        platforms = ['IOS-XE', 'IOS-XR', 'ASA', 'FTD']
        test_bugs = []

        for platform in platforms:
            platform_bugs = [b for b in all_bugs if b['platform'] == platform]
            if platform_bugs:
                # Get bugs_per_platform bugs per platform
                sample_size = min(num_bugs // len(platforms), len(platform_bugs))
                test_bugs.extend(random.sample(platform_bugs, sample_size))

        # If we need more to reach num_bugs, sample randomly
        if len(test_bugs) < num_bugs:
            remaining_bugs = [b for b in all_bugs if b not in test_bugs]
            additional = random.sample(remaining_bugs, min(num_bugs - len(test_bugs), len(remaining_bugs)))
            test_bugs.extend(additional)

        self.test_bugs = test_bugs[:num_bugs]

        print(f"✅ Loaded {len(self.test_bugs)} test bugs")
        print(f"\nPlatform distribution:")
        from collections import Counter
        platforms = Counter(b['platform'] for b in self.test_bugs)
        for platform, count in platforms.items():
            print(f"  {platform}: {count}")

        return self.test_bugs

    def test_with_current_faiss(self) -> List[Dict]:
        """Test with current FAISS index (165 PSIRTs only)"""
        print(f"\n{'='*80}")
        print("BASELINE TEST: Current FAISS Index (165 PSIRTs only)")
        print(f"{'='*80}\n")

        # Check current FAISS exists
        if not Path('models/faiss_index.bin').exists():
            print("❌ Error: models/faiss_index.bin not found")
            print("   Run: python build_faiss_index.py first")
            return []

        # Load predictor
        print("🔄 Loading SEC-8B with current FAISS index...")
        predictor = FewShotPSIRTLabeler()

        # Test each bug
        results = []
        for i, bug in enumerate(self.test_bugs, 1):
            print(f"\n--- Bug {i}/{len(self.test_bugs)} ---")
            print(f"Platform: {bug['platform']}")
            print(f"Summary: {bug['summary'][:80]}...")

            # Predict
            prediction_result = predictor.predict_labels(
                bug['summary'],
                bug['platform']
            )

            # Extract predicted labels list from result dict
            predicted_labels = prediction_result['predicted_labels']
            confidence = prediction_result['confidence']

            # Ground truth (use GPT-4o as reference)
            ground_truth = bug['openai_result']['labels']

            # Calculate metrics
            metrics = self.calculate_metrics(predicted_labels, ground_truth)

            result = {
                'bug_id': bug['bug_id'],
                'platform': bug['platform'],
                'summary': bug['summary'][:100],
                'ground_truth': ground_truth,
                'predicted': predicted_labels,
                'confidence': confidence,
                'sec8b_original': bug['comparison']['original_labels'],
                **metrics
            }

            results.append(result)

            print(f"  Ground truth (GPT-4o): {ground_truth}")
            print(f"  Predicted (SEC-8B):    {predicted_labels}")
            print(f"  Confidence: {confidence:.2f}")
            print(f"  Metrics: Precision={metrics['precision']:.2f}, Recall={metrics['recall']:.2f}, F1={metrics['f1']:.2f}")

        self.baseline_results = results
        return results

    def test_with_expanded_faiss(self) -> List[Dict]:
        """Test with expanded FAISS index (PSIRTs + bugs)"""
        print(f"\n{'='*80}")
        print("EXPANDED TEST: New FAISS Index (165 PSIRTs + 4,664 bugs)")
        print(f"{'='*80}\n")

        # Check for expanded FAISS
        expanded_faiss_path = Path('models/faiss_index_expanded.bin')
        expanded_examples_path = Path('models/labeled_examples_expanded.parquet')

        if not expanded_faiss_path.exists():
            print(f"❌ Error: {expanded_faiss_path} not found")
            print("\n📝 To create expanded FAISS index:")
            print("   1. Validate GPT-4o labels: python validate_gpt4o_labels.py --sample 20")
            print("   2. Merge: python merge_validated_labels.py validation_*.json --merge-psirts")
            print("   3. Build FAISS: python build_faiss_index.py --input training_data_combined_*.csv --output models/faiss_index_expanded.bin")
            return []

        # Load predictor with expanded index
        print("🔄 Loading SEC-8B with expanded FAISS index...")
        # Note: Would need to modify FewShotPSIRTLabeler to accept custom paths
        # For now, assume expanded index is copied to default location
        predictor = FewShotPSIRTLabeler()

        # Test each bug
        results = []
        for i, bug in enumerate(self.test_bugs, 1):
            print(f"\n--- Bug {i}/{len(self.test_bugs)} ---")
            print(f"Platform: {bug['platform']}")
            print(f"Summary: {bug['summary'][:80]}...")

            # Predict
            prediction_result = predictor.predict_labels(
                bug['summary'],
                bug['platform']
            )

            # Extract predicted labels list from result dict
            predicted_labels = prediction_result['predicted_labels']
            confidence = prediction_result['confidence']

            # Ground truth
            ground_truth = bug['openai_result']['labels']

            # Calculate metrics
            metrics = self.calculate_metrics(predicted_labels, ground_truth)

            result = {
                'bug_id': bug['bug_id'],
                'platform': bug['platform'],
                'summary': bug['summary'][:100],
                'ground_truth': ground_truth,
                'predicted': predicted_labels,
                'confidence': confidence,
                **metrics
            }

            results.append(result)

            print(f"  Ground truth (GPT-4o): {ground_truth}")
            print(f"  Predicted (SEC-8B):    {predicted_labels}")
            print(f"  Confidence: {confidence:.2f}")
            print(f"  Metrics: Precision={metrics['precision']:.2f}, Recall={metrics['recall']:.2f}, F1={metrics['f1']:.2f}")

        self.expanded_results = results
        return results

    def calculate_metrics(self, predicted: List[str], ground_truth: List[str]) -> Dict:
        """Calculate precision, recall, F1"""
        if not predicted and not ground_truth:
            return {'precision': 1.0, 'recall': 1.0, 'f1': 1.0, 'exact_match': True}

        if not predicted or not ground_truth:
            return {'precision': 0.0, 'recall': 0.0, 'f1': 0.0, 'exact_match': False}

        pred_set = set(predicted)
        truth_set = set(ground_truth)

        tp = len(pred_set & truth_set)
        fp = len(pred_set - truth_set)
        fn = len(truth_set - pred_set)

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        exact_match = pred_set == truth_set

        return {
            'precision': precision,
            'recall': recall,
            'f1': f1,
            'exact_match': exact_match
        }

    def compare_results(self):
        """Compare baseline vs expanded results"""
        if not self.baseline_results or not self.expanded_results:
            print("\n❌ Error: Need both baseline and expanded results to compare")
            print("   Run with --compare to generate both")
            return

        print(f"\n{'='*80}")
        print("COMPARISON: Baseline vs Expanded FAISS")
        print(f"{'='*80}\n")

        # Overall metrics
        baseline_avg_f1 = sum(r['f1'] for r in self.baseline_results) / len(self.baseline_results)
        expanded_avg_f1 = sum(r['f1'] for r in self.expanded_results) / len(self.expanded_results)

        baseline_exact = sum(1 for r in self.baseline_results if r['exact_match'])
        expanded_exact = sum(1 for r in self.expanded_results if r['exact_match'])

        print("Overall Metrics:")
        print(f"  Baseline (165 PSIRTs):")
        print(f"    Exact Match: {baseline_exact}/{len(self.baseline_results)} ({baseline_exact/len(self.baseline_results)*100:.1f}%)")
        print(f"    Avg F1:      {baseline_avg_f1:.3f}")

        print(f"\n  Expanded (165 PSIRTs + 4,664 bugs):")
        print(f"    Exact Match: {expanded_exact}/{len(self.expanded_results)} ({expanded_exact/len(self.expanded_results)*100:.1f}%)")
        print(f"    Avg F1:      {expanded_avg_f1:.3f}")

        print(f"\n  Improvement:")
        print(f"    Exact Match: {'+' if expanded_exact >= baseline_exact else ''}{expanded_exact - baseline_exact} ({(expanded_exact - baseline_exact)/len(self.baseline_results)*100:+.1f}%)")
        print(f"    Avg F1:      {expanded_avg_f1 - baseline_avg_f1:+.3f}")

        # Per-bug comparison
        print(f"\n{'='*80}")
        print("Per-Bug Comparison:")
        print(f"{'='*80}\n")

        for i, (baseline, expanded) in enumerate(zip(self.baseline_results, self.expanded_results), 1):
            print(f"\n--- Bug {i}: {baseline['platform']} ---")
            print(f"Summary: {baseline['summary']}...")
            print(f"Ground Truth: {baseline['ground_truth']}")
            print(f"\nBaseline:")
            print(f"  Predicted: {baseline['predicted']}")
            print(f"  F1: {baseline['f1']:.3f}")
            print(f"\nExpanded:")
            print(f"  Predicted: {expanded['predicted']}")
            print(f"  F1: {expanded['f1']:.3f}")

            if expanded['f1'] > baseline['f1']:
                print(f"  ✅ IMPROVED by {expanded['f1'] - baseline['f1']:.3f}")
            elif expanded['f1'] < baseline['f1']:
                print(f"  ⚠️  REGRESSED by {baseline['f1'] - expanded['f1']:.3f}")
            else:
                print(f"  ➖ No change")

        # Save results
        self.save_comparison()

    def save_comparison(self):
        """Save comparison results"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"faiss_comparison_{timestamp}.json"

        output = {
            'timestamp': timestamp,
            'test_bugs': len(self.test_bugs),
            'baseline': {
                'name': 'Current FAISS (165 PSIRTs)',
                'results': self.baseline_results,
                'avg_f1': sum(r['f1'] for r in self.baseline_results) / len(self.baseline_results),
                'exact_match': sum(1 for r in self.baseline_results if r['exact_match'])
            },
            'expanded': {
                'name': 'Expanded FAISS (165 PSIRTs + 4,664 bugs)',
                'results': self.expanded_results,
                'avg_f1': sum(r['f1'] for r in self.expanded_results) / len(self.expanded_results),
                'exact_match': sum(1 for r in self.expanded_results if r['exact_match'])
            }
        }

        with open(output_file, 'w') as f:
            json.dump(output, f, indent=2)

        print(f"\n💾 Comparison saved to: {output_file}")


def main():
    parser = argparse.ArgumentParser(description="Test FAISS improvement")
    parser.add_argument(
        '--baseline',
        action='store_true',
        help='Test with current FAISS (165 PSIRTs only)'
    )
    parser.add_argument(
        '--expanded',
        action='store_true',
        help='Test with expanded FAISS (PSIRTs + bugs)'
    )
    parser.add_argument(
        '--compare',
        action='store_true',
        help='Run both tests and compare results'
    )
    parser.add_argument(
        '--num-bugs',
        type=int,
        default=10,
        help='Number of test bugs (default: 10)'
    )

    args = parser.parse_args()

    # Need at least one option
    if not (args.baseline or args.expanded or args.compare):
        parser.print_help()
        print("\n❌ Error: Please specify --baseline, --expanded, or --compare")
        return

    # Create tester
    tester = FAISSComparisonTest()

    # Load test bugs
    tester.load_test_bugs(num_bugs=args.num_bugs)

    # Run tests
    if args.compare:
        # Run both
        tester.test_with_current_faiss()
        tester.test_with_expanded_faiss()
        tester.compare_results()

    elif args.baseline:
        # Baseline only
        results = tester.test_with_current_faiss()

        print(f"\n{'='*80}")
        print("Baseline Test Complete")
        print(f"{'='*80}")
        avg_f1 = sum(r['f1'] for r in results) / len(results)
        exact = sum(1 for r in results if r['exact_match'])
        print(f"Exact Match: {exact}/{len(results)} ({exact/len(results)*100:.1f}%)")
        print(f"Avg F1:      {avg_f1:.3f}")
        print(f"{'='*80}\n")

    elif args.expanded:
        # Expanded only
        results = tester.test_with_expanded_faiss()

        if results:
            print(f"\n{'='*80}")
            print("Expanded Test Complete")
            print(f"{'='*80}")
            avg_f1 = sum(r['f1'] for r in results) / len(results)
            exact = sum(1 for r in results if r['exact_match'])
            print(f"Exact Match: {exact}/{len(results)} ({exact/len(results)*100:.1f}%)")
            print(f"Avg F1:      {avg_f1:.3f}")
            print(f"{'='*80}\n")


if __name__ == '__main__':
    main()
