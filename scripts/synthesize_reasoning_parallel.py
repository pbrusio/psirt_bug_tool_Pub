#!/usr/bin/env python3
"""
Parallel Reasoning Synthesis

Splits the dataset into chunks and processes them in parallel.
With 96GB RAM, can run 4 parallel model instances (~20GB each).

Usage:
    python scripts/synthesize_reasoning_parallel.py --workers 4
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime
import pandas as pd
import multiprocessing as mp

PROJECT_ROOT = Path(__file__).parent.parent


def parse_args():
    parser = argparse.ArgumentParser(description='Parallel reasoning synthesis')
    parser.add_argument('--workers', type=int, default=4, help='Number of parallel workers')
    parser.add_argument('--output', default='models/labeled_examples_with_reasoning.parquet', help='Output file')
    return parser.parse_args()


def process_chunk(args):
    """Process a chunk of examples"""
    chunk_id, start_idx, end_idx, total = args

    print(f"[Worker {chunk_id}] Processing examples {start_idx}-{end_idx}")

    # Import here to load model in subprocess
    from mlx_lm import load, generate
    import pandas as pd

    # Load data
    df = pd.read_parquet('models/labeled_examples.parquet')

    # Get chunk
    needs_reasoning = df['reasoning'].isna() | (df['reasoning'].str.len() < 10)
    to_process = df[needs_reasoning].iloc[start_idx:end_idx].copy()

    # Load model
    print(f"[Worker {chunk_id}] Loading model...")
    model, tokenizer = load("fdtn-ai/Foundation-Sec-8B")

    results = []
    for i, (idx, row) in enumerate(to_process.iterrows()):
        labels = row['labels_list']
        if hasattr(labels, 'tolist'):
            labels = labels.tolist()
        if not labels:
            continue

        labels_str = json.dumps(labels)
        prompt = f"""### Instruction:
Given this security advisory and its correct labels, write ONE brief sentence explaining why these labels apply.

### Input:
{row['platform']}: {row['summary'][:1000]}
Labels: {labels_str}

### Response:
The advisory relates to"""

        response = generate(model, tokenizer, prompt=prompt, max_tokens=200, verbose=False)
        reasoning = "The advisory relates to " + response.strip()
        if "\n\n" in reasoning:
            reasoning = reasoning.split("\n\n")[0]
        reasoning = reasoning[:500]

        results.append({'index': idx, 'reasoning': reasoning})

        if (i + 1) % 50 == 0:
            print(f"[Worker {chunk_id}] {i+1}/{len(to_process)} done")

    print(f"[Worker {chunk_id}] Complete: {len(results)} reasoning traces")
    return results


def main():
    args = parse_args()

    print("="*60)
    print(f"  Parallel Reasoning Synthesis ({args.workers} workers)")
    print("="*60)

    # Load data to get counts
    df = pd.read_parquet('models/labeled_examples.parquet')
    needs_reasoning = df['reasoning'].isna() | (df['reasoning'].str.len() < 10)
    total_needed = needs_reasoning.sum()

    print(f"Total examples needing reasoning: {total_needed}")

    # Split into chunks
    chunk_size = total_needed // args.workers
    chunks = []
    for i in range(args.workers):
        start = i * chunk_size
        end = start + chunk_size if i < args.workers - 1 else total_needed
        chunks.append((i, start, end, total_needed))

    print(f"Chunks: {[(c[1], c[2]) for c in chunks]}")
    print()

    # Process in parallel
    start_time = datetime.now()

    with mp.Pool(args.workers) as pool:
        all_results = pool.map(process_chunk, chunks)

    # Merge results
    print("\nMerging results...")
    merged = []
    for chunk_results in all_results:
        merged.extend(chunk_results)

    print(f"Total reasoning traces: {len(merged)}")

    # Update dataframe
    for r in merged:
        df.loc[r['index'], 'reasoning'] = r['reasoning']

    # Save
    output_path = Path(args.output)
    df.to_parquet(output_path, index=False)

    elapsed = (datetime.now() - start_time).total_seconds()
    print(f"\nCompleted in {elapsed/60:.1f} minutes")
    print(f"Saved to: {output_path}")

    # Summary
    has_reasoning = df['reasoning'].notna() & (df['reasoning'].str.len() > 10)
    print(f"Final count with reasoning: {has_reasoning.sum()} / {len(df)}")


if __name__ == '__main__':
    mp.set_start_method('spawn')  # Required for CUDA/MPS
    main()
