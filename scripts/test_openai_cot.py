#!/usr/bin/env python3
"""
OpenAI CoT Synthesis Test Script

Tests GPT-4.1, GPT-4o-mini, and GPT-4o-nano for CoT reasoning generation.
Compares output quality against Gemini baseline.
"""

import os
import json
import yaml
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
import time
import argparse

# Load environment variables
load_dotenv()

# Configuration
INPUT_DATA = "models/labeled_examples_normalized.parquet"
OUTPUT_DIR = "models/openai_test_outputs"
TAXONOMY_PATH = "taxonomies/features.yml"
ANTI_DEFINITIONS_PATH = "output/taxonomy_anti_definitions.yml"

# Models to test (user requested GPT-5.1, GPT-5-mini, GPT-5-nano)
MODELS = {
    "gpt-5.1": "gpt-5.1",
    "gpt-5-mini": "gpt-5-mini",
    "gpt-5-nano": "gpt-5-nano"
}


def load_taxonomy(path: str) -> list:
    """Load taxonomy labels."""
    with open(path, 'r') as f:
        features = yaml.safe_load(f)
    return sorted([f['label'] for f in features])


def load_anti_definitions(path: str) -> dict:
    """Load contrastive anti-definitions."""
    if not os.path.exists(path):
        return {}
    with open(path, 'r') as f:
        return yaml.safe_load(f)


def build_prompt(example: dict, taxonomy: list, anti_defs: dict) -> str:
    """Build prompt for a single example."""
    taxonomy_str = ", ".join(taxonomy)
    labels_str = json.dumps(example['labels'])

    # Get anti-definition context for primary label if available
    primary_label = example['labels'][0] if example['labels'] else ""
    anti_context = ""
    if primary_label in anti_defs:
        anti_def = anti_defs[primary_label]
        exclusions = anti_def.get('exclusions', [])[:2]
        if exclusions:
            anti_context = f"\nCommon confusions to address: {'; '.join(exclusions)}"

    prompt = f"""You are an expert Cisco network security engineer. Your task is to generate training data for a classification model.

For this security advisory, write 2-4 sentences of technical reasoning explaining:
1. WHY the given labels are correct (cite specific technical indicators)
2. WHY similar/adjacent labels are NOT correct (if applicable)

VALID LABELS (closed taxonomy - these are the ONLY valid options):
{taxonomy_str}

CRITICAL GUIDELINES:
- Be specific and technical - mention protocols, features, attack vectors
- For SEC_CoPP: This means "Control Plane Policing" - use when DoS could overwhelm the device CPU/control plane
- For MGMT_SSH_HTTP: Use for SSH/HTTP/HTTPS management interface vulnerabilities
- For RTE_BGP vs SEC_BGP_ROUTE_FILTERING: RTE_BGP is the protocol itself; SEC_BGP_ROUTE_FILTERING is for route-maps/prefix-lists
- Keep reasoning concise (2-4 sentences max)

---
Summary: {example['summary'][:1500]}
Correct Labels: {labels_str}{anti_context}
---

Write ONLY the reasoning (2-4 sentences). Do not include the labels in your response."""

    return prompt


def synthesize_with_openai(client, model_name: str, examples: list, taxonomy: list, anti_defs: dict) -> list:
    """Synthesize reasoning for examples using OpenAI."""
    results = []

    for example in examples:
        prompt = build_prompt(example, taxonomy, anti_defs)

        try:
            # GPT-5-mini and nano don't support temperature, no token limit (reasoning needs room)
            if model_name in ["gpt-5-mini", "gpt-5-nano"]:
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": "You are an expert Cisco network security engineer generating training data."},
                        {"role": "user", "content": prompt}
                    ]
                    # No max_completion_tokens - let reasoning model use what it needs
                )
            elif model_name.startswith("gpt-5"):
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": "You are an expert Cisco network security engineer generating training data."},
                        {"role": "user", "content": prompt}
                    ],
                    max_completion_tokens=300,
                    temperature=0.3
                )
            else:
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": "You are an expert Cisco network security engineer generating training data."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=300,
                    temperature=0.3
                )

            reasoning = response.choices[0].message.content.strip()

            # Track token usage
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }

            results.append({
                "idx": example['idx'],
                "reasoning": reasoning,
                "usage": usage,
                "success": True
            })

            print(f"  Example {example['idx']}: {len(reasoning)} chars, {usage['total_tokens']} tokens")

        except Exception as e:
            print(f"  Example {example['idx']}: ERROR - {str(e)[:100]}")
            results.append({
                "idx": example['idx'],
                "reasoning": "",
                "error": str(e),
                "success": False
            })

        # Small delay between requests
        time.sleep(0.5)

    return results


def main(num_examples: int = 5):
    """Main test pipeline."""
    print("=" * 60)
    print("OpenAI CoT Synthesis Test")
    print("=" * 60)

    # Check API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: OPENAI_API_KEY not found in environment")
        return

    # Initialize client
    client = OpenAI(api_key=api_key)

    # Create output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Load data
    print(f"\nLoading data...")
    df = pd.read_parquet(INPUT_DATA)
    print(f"  Training examples available: {len(df)}")

    taxonomy = load_taxonomy(TAXONOMY_PATH)
    print(f"  Taxonomy labels: {len(taxonomy)}")

    anti_defs = load_anti_definitions(ANTI_DEFINITIONS_PATH)
    print(f"  Anti-definitions: {len(anti_defs)}")

    # Sample examples (same ones for all models for fair comparison)
    import random
    random.seed(42)

    sample_indices = random.sample(range(len(df)), min(num_examples, len(df)))
    examples = []

    for idx in sample_indices:
        row = df.iloc[idx]
        labels = list(row['labels_list']) if row['labels_list'] is not None else []
        examples.append({
            'idx': idx,
            'summary': row['summary'],
            'labels': labels
        })

    print(f"\n  Selected {len(examples)} examples for testing")

    # Test each model
    all_results = {}

    for model_key, model_name in MODELS.items():
        print(f"\n{'=' * 60}")
        print(f"Testing: {model_name}")
        print("=" * 60)

        start_time = time.time()
        results = synthesize_with_openai(client, model_name, examples, taxonomy, anti_defs)
        elapsed = time.time() - start_time

        # Calculate stats
        successes = sum(1 for r in results if r['success'])
        total_tokens = sum(r.get('usage', {}).get('total_tokens', 0) for r in results if r['success'])

        print(f"\n  Results: {successes}/{len(examples)} successful")
        print(f"  Total tokens: {total_tokens}")
        print(f"  Time: {elapsed:.1f}s")

        all_results[model_key] = {
            "model": model_name,
            "results": results,
            "successes": successes,
            "total_tokens": total_tokens,
            "elapsed_seconds": elapsed
        }

        # Save individual model results
        output_file = os.path.join(OUTPUT_DIR, f"{model_key}_results.json")
        with open(output_file, 'w') as f:
            json.dump(all_results[model_key], f, indent=2)
        print(f"  Saved to: {output_file}")

    # Print comparison summary
    print("\n" + "=" * 60)
    print("COMPARISON SUMMARY")
    print("=" * 60)

    print(f"\n{'Model':<15} {'Success':<10} {'Tokens':<10} {'Time':<10}")
    print("-" * 45)

    for model_key, data in all_results.items():
        print(f"{model_key:<15} {data['successes']}/{len(examples):<7} {data['total_tokens']:<10} {data['elapsed_seconds']:.1f}s")

    # Print sample outputs for quality comparison
    print("\n" + "=" * 60)
    print("SAMPLE OUTPUTS (First Example)")
    print("=" * 60)

    first_example = examples[0]
    print(f"\nSummary: {first_example['summary'][:200]}...")
    print(f"Labels: {first_example['labels']}")

    for model_key, data in all_results.items():
        print(f"\n--- {model_key} ---")
        if data['results'][0]['success']:
            print(data['results'][0]['reasoning'])
        else:
            print(f"ERROR: {data['results'][0].get('error', 'Unknown error')}")

    # Save combined results
    combined_output = os.path.join(OUTPUT_DIR, "combined_results.json")
    with open(combined_output, 'w') as f:
        json.dump({
            "examples": examples,
            "results": all_results
        }, f, indent=2)
    print(f"\n\nCombined results saved to: {combined_output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test OpenAI models for CoT synthesis")
    parser.add_argument("--num-examples", type=int, default=5, help="Number of examples to test")
    args = parser.parse_args()

    main(num_examples=args.num_examples)
