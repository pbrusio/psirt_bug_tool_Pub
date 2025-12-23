#!/usr/bin/env python3
"""
Prepare Chain-of-Thought (CoT) Training Dataset

Transforms labeled vulnerability data into instruction-tuning format
for LoRA fine-tuning of Foundation-Sec-8B.

Usage:
  # Create full dataset
  python scripts/prepare_cot_dataset.py

  # Create pilot dataset (500 examples)
  python scripts/prepare_cot_dataset.py --pilot

  # Dry run (show stats only)
  python scripts/prepare_cot_dataset.py --dry-run
"""

import argparse
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd


def parse_args():
    parser = argparse.ArgumentParser(description='Prepare CoT training dataset')
    parser.add_argument('--input', default='models/labeled_examples.parquet',
                        help='Input parquet file')
    parser.add_argument('--output', default='llama_training_data/cot_dataset.jsonl',
                        help='Output JSONL file')
    parser.add_argument('--pilot', action='store_true',
                        help='Create pilot dataset (500 examples with reasoning)')
    parser.add_argument('--pilot-size', type=int, default=500,
                        help='Number of examples for pilot (default: 500)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show stats without creating files')
    parser.add_argument('--require-reasoning', action='store_true',
                        help='Only include examples with existing reasoning')
    return parser.parse_args()


def has_valid_reasoning(reasoning):
    """Check if reasoning is non-empty and meaningful"""
    if reasoning is None:
        return False
    if not isinstance(reasoning, str):
        return False
    reasoning = reasoning.strip()
    if len(reasoning) < 20:  # Too short to be useful
        return False
    if reasoning.lower() in ('none', 'null', 'n/a'):
        return False
    return True


def format_labels(labels):
    """Format labels as JSON array string"""
    if isinstance(labels, list):
        return json.dumps(labels)
    if hasattr(labels, 'tolist'):
        return json.dumps(labels.tolist())
    return json.dumps([str(labels)])


def create_cot_entry(row, synthesize_reasoning=False):
    """
    Create a single CoT training entry.

    Format:
    {
      "instruction": "Analyze the following security advisory...",
      "input": "<PLATFORM>: <SUMMARY>",
      "output": "Reasoning:\n1. ...\n\nLabels:\n[...]"
    }
    """
    platform = row['platform']
    summary = row['summary']
    labels = row['labels_list']
    reasoning = row.get('reasoning', '')

    # Clean summary
    if not summary or not isinstance(summary, str):
        return None
    summary = summary.strip()
    if len(summary) < 20:
        return None

    # Format labels
    if hasattr(labels, 'tolist'):
        labels = labels.tolist()
    if not labels or len(labels) == 0:
        return None

    labels_json = json.dumps(labels)

    # Build instruction
    instruction = (
        "Analyze the following security advisory summary and assign valid taxonomy labels. "
        "Explain your reasoning step-by-step before providing the final JSON labels."
    )

    # Build input
    input_text = f"{platform}: {summary}"

    # Build output with reasoning
    if has_valid_reasoning(reasoning):
        # Use existing reasoning
        output = f"Reasoning:\n{reasoning}\n\nLabels:\n{labels_json}"
    elif synthesize_reasoning:
        # Generate simple synthetic reasoning based on labels
        reasoning_lines = []
        for i, label in enumerate(labels[:3], 1):
            # Simple template-based reasoning
            reasoning_lines.append(f"{i}. The summary indicates {label.replace('_', ' ').lower()} functionality is affected.")
        synthetic = "\n".join(reasoning_lines)
        output = f"Reasoning:\n{synthetic}\n\nLabels:\n{labels_json}"
    else:
        # No reasoning available, skip or use labels only
        return None

    return {
        "instruction": instruction,
        "input": input_text,
        "output": output
    }


def main():
    args = parse_args()

    print("=" * 60)
    print("  CoT Dataset Preparation")
    print("=" * 60)
    print()

    # Load data
    input_path = PROJECT_ROOT / args.input
    print(f"Loading: {input_path}")
    df = pd.read_parquet(input_path)
    print(f"Total examples: {len(df)}")
    print()

    # Analyze reasoning availability
    has_reasoning = df.apply(lambda r: has_valid_reasoning(r.get('reasoning')), axis=1)
    print(f"Examples with valid reasoning: {has_reasoning.sum()}")
    print(f"Examples needing synthesis: {(~has_reasoning).sum()}")
    print()

    # Source breakdown
    print("Source distribution:")
    print(df['source'].value_counts().head(10))
    print()

    if args.dry_run:
        print("[DRY RUN] No files created.")
        return

    # Prepare output
    output_path = PROJECT_ROOT / args.output
    if args.pilot:
        output_path = output_path.parent / f"cot_dataset_pilot_{args.pilot_size}.jsonl"

    os.makedirs(output_path.parent, exist_ok=True)

    # Filter and prepare data
    if args.pilot or args.require_reasoning:
        # For pilot/require-reasoning: only use examples WITH reasoning
        df_filtered = df[has_reasoning].copy()
        print(f"Filtered to {len(df_filtered)} examples with reasoning")

        if args.pilot and len(df_filtered) > args.pilot_size:
            # Sample for pilot, stratified by platform if possible
            df_filtered = df_filtered.sample(n=args.pilot_size, random_state=42)
            print(f"Sampled {len(df_filtered)} for pilot")
    else:
        # Full dataset: use all, synthesize reasoning where missing
        df_filtered = df.copy()

    # Create entries
    entries = []
    skipped = 0

    for _, row in df_filtered.iterrows():
        # For full dataset, allow synthesis; for pilot, require real reasoning
        synthesize = not (args.pilot or args.require_reasoning)
        entry = create_cot_entry(row, synthesize_reasoning=synthesize)
        if entry:
            entries.append(entry)
        else:
            skipped += 1

    print(f"Created {len(entries)} training entries")
    print(f"Skipped {skipped} (missing data)")
    print()

    # Platform distribution
    platforms = {}
    for e in entries:
        platform = e['input'].split(':')[0]
        platforms[platform] = platforms.get(platform, 0) + 1
    print("Platform distribution in dataset:")
    for p, c in sorted(platforms.items(), key=lambda x: -x[1]):
        print(f"  {p}: {c}")
    print()

    # Write output
    print(f"Writing to: {output_path}")
    with open(output_path, 'w') as f:
        for entry in entries:
            f.write(json.dumps(entry) + '\n')

    print(f"Done! Dataset ready at {output_path}")
    print()

    # Show sample
    print("Sample entry:")
    print("-" * 40)
    sample = entries[0]
    print(f"Instruction: {sample['instruction'][:80]}...")
    print(f"Input: {sample['input'][:100]}...")
    print(f"Output: {sample['output'][:200]}...")


if __name__ == '__main__':
    main()
