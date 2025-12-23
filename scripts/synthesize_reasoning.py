#!/usr/bin/env python3
"""
Synthesize Reasoning for Training Data

Uses the Foundation-Sec-8B model to generate reasoning traces for examples
that have labels but lack reasoning explanations.

Usage:
    python scripts/synthesize_reasoning.py --limit 100  # Test run
    python scripts/synthesize_reasoning.py              # Full run
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime
import pandas as pd

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def parse_args():
    parser = argparse.ArgumentParser(description='Synthesize reasoning for training data')
    parser.add_argument('--limit', type=int, default=None, help='Limit number of examples to process')
    parser.add_argument('--batch-size', type=int, default=50, help='Save checkpoint every N examples')
    parser.add_argument('--output', default='models/labeled_examples_with_reasoning.parquet', help='Output file')
    parser.add_argument('--resume', action='store_true', help='Resume from previous run')
    return parser.parse_args()


def build_reasoning_prompt(summary: str, platform: str, labels: list) -> str:
    """Build prompt to generate reasoning for given labels"""
    labels_str = json.dumps(labels)

    prompt = f"""### Instruction:
Given this security advisory and its correct labels, write ONE brief sentence explaining why these labels apply.

### Input:
{platform}: {summary}
Labels: {labels_str}

### Response:
The advisory relates to"""
    return prompt


def main():
    args = parse_args()

    print("="*60)
    print("  Reasoning Synthesis")
    print("="*60)
    print()

    # Load data
    print("Loading labeled examples...")
    df = pd.read_parquet('models/labeled_examples.parquet')
    print(f"Total examples: {len(df)}")

    # Find examples needing reasoning
    needs_reasoning = df['reasoning'].isna() | (df['reasoning'].str.len() < 10)
    to_process = df[needs_reasoning].copy()
    print(f"Examples needing reasoning: {len(to_process)}")

    if args.limit:
        to_process = to_process.head(args.limit)
        print(f"Limited to: {len(to_process)}")

    if len(to_process) == 0:
        print("No examples need reasoning synthesis!")
        return

    # Initialize model
    print("\nInitializing model...")
    from mlx_lm import load, generate
    model, tokenizer = load("fdtn-ai/Foundation-Sec-8B")
    print("Model loaded")

    # Process examples
    print(f"\nProcessing {len(to_process)} examples...")
    print("-"*40)

    results = []
    start_time = datetime.now()

    for i, (idx, row) in enumerate(to_process.iterrows()):
        # Get labels
        labels = row['labels_list']
        if hasattr(labels, 'tolist'):
            labels = labels.tolist()
        if not labels:
            continue

        # Build prompt
        prompt = build_reasoning_prompt(
            row['summary'][:1000],  # Truncate long summaries
            row['platform'],
            labels
        )

        # Generate reasoning
        response = generate(model, tokenizer, prompt=prompt, max_tokens=200, verbose=False)

        # Extract reasoning and add prefix back
        reasoning = "The advisory relates to " + response.strip()
        # Clean up any hallucinated content after first sentence/paragraph
        if "\n\n" in reasoning:
            reasoning = reasoning.split("\n\n")[0]
        # Limit length
        reasoning = reasoning[:500]

        results.append({
            'index': idx,
            'reasoning': reasoning
        })

        # Progress
        if (i + 1) % 10 == 0:
            elapsed = (datetime.now() - start_time).total_seconds()
            rate = (i + 1) / elapsed
            remaining = (len(to_process) - i - 1) / rate if rate > 0 else 0
            print(f"[{i+1}/{len(to_process)}] {rate:.1f} ex/s, ~{remaining/60:.1f} min remaining")

        # Checkpoint
        if (i + 1) % args.batch_size == 0:
            print(f"  Checkpoint: {len(results)} reasoning traces generated")

    print("-"*40)
    print(f"Generated {len(results)} reasoning traces")

    # Update dataframe
    print("\nUpdating dataframe...")
    for r in results:
        df.loc[r['index'], 'reasoning'] = r['reasoning']

    # Save
    output_path = Path(args.output)
    output_path.parent.mkdir(exist_ok=True)
    df.to_parquet(output_path, index=False)
    print(f"Saved to: {output_path}")

    # Summary
    has_reasoning = df['reasoning'].notna() & (df['reasoning'].str.len() > 10)
    print(f"\nFinal count with reasoning: {has_reasoning.sum()} / {len(df)}")


if __name__ == '__main__':
    main()
