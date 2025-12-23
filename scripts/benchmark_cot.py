#!/usr/bin/env python3
"""
Benchmark CoT Model on Test Set

Evaluates the LoRA-adapted model on held-out test examples,
measuring accuracy, reasoning quality, and comparing to baseline.

Usage:
    python scripts/benchmark_cot.py --adapter adapters/pilot_cot_v1
    python scripts/benchmark_cot.py --no-adapter  # Baseline comparison
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def parse_args():
    parser = argparse.ArgumentParser(description='Benchmark CoT model')
    parser.add_argument('--adapter', default='adapters/pilot_cot_v1', help='LoRA adapter path')
    parser.add_argument('--no-adapter', action='store_true', help='Run without adapter (baseline)')
    parser.add_argument('--test-file', default='llama_training_data/pilot/test.jsonl', help='Test data file')
    parser.add_argument('--limit', type=int, default=None, help='Limit number of test examples')
    parser.add_argument('--output', default='output/benchmark_results.json', help='Output file')
    parser.add_argument('--verbose', action='store_true', help='Print each prediction')
    return parser.parse_args()


def load_test_data(test_file: str, limit: int = None):
    """Load test examples from JSONL file"""
    examples = []
    with open(test_file) as f:
        for line in f:
            if line.strip():
                entry = json.loads(line)
                # Parse the text field to extract platform, summary, and expected output
                text = entry['text']

                # Extract input (platform: summary)
                input_match = text.split('### Input:\n')[1].split('\n\n### Response:')[0]
                platform = input_match.split(':')[0].strip()
                summary = ':'.join(input_match.split(':')[1:]).strip()

                # Extract expected output (reasoning + labels)
                output = text.split('### Response:\n')[1]

                # Parse expected labels
                labels_match = output.split('Labels:\n')[1] if 'Labels:\n' in output else '[]'
                try:
                    expected_labels = json.loads(labels_match.strip())
                except:
                    expected_labels = []

                examples.append({
                    'platform': platform,
                    'summary': summary[:500],  # Truncate long summaries
                    'expected_labels': expected_labels,
                    'expected_output': output
                })

                if limit and len(examples) >= limit:
                    break

    return examples


def calculate_metrics(predictions: list):
    """Calculate accuracy metrics"""
    exact_matches = 0
    partial_matches = 0
    total_predicted = 0
    total_expected = 0
    has_reasoning = 0

    for p in predictions:
        predicted = set(p['predicted_labels'])
        expected = set(p['expected_labels'])

        if predicted == expected:
            exact_matches += 1

        overlap = predicted & expected
        if overlap:
            partial_matches += 1

        total_predicted += len(predicted)
        total_expected += len(expected)

        if p.get('reasoning') and len(p['reasoning']) > 20:
            has_reasoning += 1

    n = len(predictions)
    return {
        'total_examples': n,
        'exact_match_accuracy': exact_matches / n if n > 0 else 0,
        'partial_match_rate': partial_matches / n if n > 0 else 0,
        'reasoning_rate': has_reasoning / n if n > 0 else 0,
        'avg_predicted_labels': total_predicted / n if n > 0 else 0,
        'avg_expected_labels': total_expected / n if n > 0 else 0,
    }


def main():
    args = parse_args()

    print("=" * 60)
    print("  CoT Model Benchmark")
    print("=" * 60)
    print()

    # Load test data
    print(f"Loading test data from: {args.test_file}")
    test_examples = load_test_data(args.test_file, limit=args.limit)
    print(f"Loaded {len(test_examples)} test examples")
    print()

    # Initialize model
    adapter_path = None if args.no_adapter else args.adapter
    print(f"Initializing model...")
    print(f"  Adapter: {adapter_path or 'None (baseline)'}")

    from mlx_inference import MLXPSIRTLabeler
    labeler = MLXPSIRTLabeler(adapter_path=adapter_path)
    print()

    # Run predictions
    print("Running predictions...")
    print("-" * 40)

    predictions = []
    for i, example in enumerate(test_examples, 1):
        result = labeler.predict_labels(
            example['summary'],
            example['platform'],
            max_tokens=600
        )

        prediction = {
            'index': i,
            'platform': example['platform'],
            'summary': example['summary'][:100] + '...',
            'expected_labels': example['expected_labels'],
            'predicted_labels': result['predicted_labels'],
            'reasoning': result['reasoning'],
            'confidence': result['confidence'],
            'match': set(result['predicted_labels']) == set(example['expected_labels'])
        }
        predictions.append(prediction)

        if args.verbose:
            status = "✅" if prediction['match'] else "❌"
            print(f"[{i}/{len(test_examples)}] {status} {example['platform']}")
            print(f"  Expected: {example['expected_labels']}")
            print(f"  Predicted: {result['predicted_labels']}")
            if result['reasoning']:
                print(f"  Reasoning: {result['reasoning'][:100]}...")
            print()
        else:
            status = "✅" if prediction['match'] else "❌"
            print(f"[{i}/{len(test_examples)}] {status}", end=" ")
            if i % 10 == 0:
                print()

    print()
    print("-" * 40)

    # Calculate metrics
    metrics = calculate_metrics(predictions)

    print("\n" + "=" * 60)
    print("  Results Summary")
    print("=" * 60)
    print(f"Total examples: {metrics['total_examples']}")
    print(f"Exact match accuracy: {metrics['exact_match_accuracy']:.1%}")
    print(f"Partial match rate: {metrics['partial_match_rate']:.1%}")
    print(f"Reasoning generation rate: {metrics['reasoning_rate']:.1%}")
    print(f"Avg predicted labels: {metrics['avg_predicted_labels']:.2f}")
    print(f"Avg expected labels: {metrics['avg_expected_labels']:.2f}")

    # Save results
    output_path = Path(args.output)
    output_path.parent.mkdir(exist_ok=True)

    results = {
        'timestamp': datetime.utcnow().isoformat(),
        'adapter_path': adapter_path,
        'test_file': args.test_file,
        'metrics': metrics,
        'predictions': predictions
    }

    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\nResults saved to: {output_path}")


if __name__ == '__main__':
    main()
