#!/usr/bin/env python3
"""
Phase 3 v6: Synthesize CoT Reasoning using OpenAI GPT-5.1

Uses individual requests (not batched) to generate high-quality
contrastive reasoning for LoRA training data.

Rate limits (your account):
- 500 RPM (requests per minute)
- 500,000 TPM (tokens per minute)
"""

import os
import json
import yaml
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
import openai
from tqdm import tqdm
import time
import argparse
from collections import defaultdict
import random

# Load environment variables
load_dotenv()

# Configuration
INPUT_DATA = "models/labeled_examples_normalized.parquet"
OUTPUT_DATA = "models/cot_dataset_v6_openai.jsonl"
ANTI_DEFINITIONS_PATH = "output/taxonomy_anti_definitions.yml"
TAXONOMY_PATH = "taxonomies/features.yml"

MODEL_NAME = "gpt-5.1"
MAX_RETRIES = 3
REQUEST_DELAY = 0.15  # 150ms between requests (conservative for 500 RPM)

# Labels that need extra contrastive focus
CONTRASTIVE_LABELS = {
    "MGMT_SSH_HTTP", "MGMT_AAA_TACACS_RADIUS", "MGMT_SNMP",
    "SEC_CoPP", "RTE_BGP", "RTE_OSPF", "SEC_BGP_ROUTE_FILTERING",
    "SYS_Boot_Upgrade", "SYS_Licensing_Smart"
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


def synthesize_single(client, example: dict, taxonomy: list, anti_defs: dict) -> dict:
    """Synthesize reasoning for a single example."""
    prompt = build_prompt(example, taxonomy, anti_defs)

    for attempt in range(MAX_RETRIES):
        try:
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": "You are an expert Cisco network security engineer generating training data."},
                    {"role": "user", "content": prompt}
                ],
                max_completion_tokens=300,
                temperature=0.3
            )

            reasoning = response.choices[0].message.content.strip()
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }

            return {
                "reasoning": reasoning,
                "usage": usage,
                "success": True
            }

        except openai.RateLimitError as e:
            wait_time = 60 * (attempt + 1)
            print(f"  Rate limited, waiting {wait_time}s...")
            time.sleep(wait_time)

        except openai.APIStatusError as e:
            if e.status_code >= 500:
                wait_time = 30 * (attempt + 1)
                print(f"  API error {e.status_code}, waiting {wait_time}s...")
                time.sleep(wait_time)
            else:
                print(f"  API error: {e}")
                return {"reasoning": "", "success": False, "error": str(e)}

        except Exception as e:
            print(f"  Error: {str(e)[:100]}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(5 * (attempt + 1))
            else:
                return {"reasoning": "", "success": False, "error": str(e)}

    return {"reasoning": "", "success": False, "error": "Max retries exceeded"}


def main(limit: int = None, resume: bool = True):
    """Main synthesis pipeline."""
    print("=" * 60)
    print("Phase 3 v6: OpenAI GPT-5.1 CoT Synthesis")
    print("=" * 60)

    # Check API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: OPENAI_API_KEY not found in environment")
        return

    # Initialize client with retry config
    client = OpenAI(api_key=api_key, max_retries=2)

    print(f"  Model: {MODEL_NAME}")
    print(f"  Request delay: {REQUEST_DELAY}s")

    # Load data
    print(f"\nLoading data...")
    df = pd.read_parquet(INPUT_DATA)
    print(f"  Training examples: {len(df)}")

    taxonomy = load_taxonomy(TAXONOMY_PATH)
    print(f"  Taxonomy labels: {len(taxonomy)}")

    anti_defs = load_anti_definitions(ANTI_DEFINITIONS_PATH)
    print(f"  Anti-definitions: {len(anti_defs)}")

    # Balanced sampling (same as Gemini script)
    random.seed(42)

    rows_by_label = defaultdict(list)
    for idx, row in df.iterrows():
        labels = list(row['labels_list']) if row['labels_list'] is not None else []
        if labels:
            primary_label = labels[0]
            rows_by_label[primary_label].append((idx, row))

    MAX_PER_CONTRASTIVE = 50
    MAX_PER_GENERAL = 30

    balanced_rows = []
    for label, rows in rows_by_label.items():
        cap = MAX_PER_CONTRASTIVE if label in CONTRASTIVE_LABELS else MAX_PER_GENERAL
        random.shuffle(rows)
        balanced_rows.extend(rows[:cap])

    random.shuffle(balanced_rows)
    print(f"  Balanced dataset: {len(balanced_rows)} examples")

    # Resume support
    existing_results = {}
    if resume and os.path.exists(OUTPUT_DATA):
        try:
            with open(OUTPUT_DATA, 'r') as f:
                for line in f:
                    r = json.loads(line)
                    existing_results[r.get('summary_hash', '')] = r
            print(f"  Resuming: {len(existing_results)} existing examples")
        except Exception as e:
            print(f"  Could not resume: {e}")

    # Filter out already processed
    def get_hash(text):
        return str(hash(text[:200]))

    to_process = []
    for idx, row in balanced_rows:
        h = get_hash(row['summary'])
        if h not in existing_results:
            to_process.append((idx, row, h))

    print(f"  To process: {len(to_process)} examples")

    if limit:
        to_process = to_process[:limit]
        print(f"  Limited to: {len(to_process)} examples")

    if not to_process:
        print("\nNothing to process - all examples already synthesized!")
        return

    # Process examples
    results = list(existing_results.values())
    total_tokens = 0
    successes = 0
    failures = 0

    print(f"\nProcessing {len(to_process)} examples...")
    print(f"Estimated time: {len(to_process) * (REQUEST_DELAY + 0.5) / 60:.1f} minutes")

    for i, (idx, row, h) in enumerate(tqdm(to_process, desc="Synthesizing")):
        labels = list(row['labels_list']) if row['labels_list'] is not None else []

        example = {
            'idx': idx,
            'summary': row['summary'],
            'labels': labels
        }

        result = synthesize_single(client, example, taxonomy, anti_defs)

        if result['success'] and result['reasoning']:
            successes += 1
            total_tokens += result.get('usage', {}).get('total_tokens', 0)

            # Build final training record
            label_str = str(labels) if len(labels) > 1 else f"['{labels[0]}']" if labels else "[]"

            final_text = f"""### Instruction:
Classify the following Cisco Security Advisory into the correct technical feature label.

### Input:
{example['summary'][:1500]}

### Response:
{result['reasoning']}

Label: {label_str}"""

            record = {
                'text': final_text,
                'summary_hash': h
            }
            results.append(record)

            # Save checkpoint every 10 examples
            if (i + 1) % 10 == 0:
                with open(OUTPUT_DATA, 'w') as f:
                    for r in results:
                        f.write(json.dumps(r) + "\n")
        else:
            failures += 1
            print(f"  Failed: example {idx}")

        # Rate limiting
        time.sleep(REQUEST_DELAY)

        # Progress check every 50 examples
        if (i + 1) % 50 == 0:
            print(f"\n  Progress: {i+1}/{len(to_process)} | Success: {successes} | Failed: {failures} | Tokens: {total_tokens}")

    # Final save
    with open(OUTPUT_DATA, 'w') as f:
        for r in results:
            f.write(json.dumps(r) + "\n")

    # Final stats
    print("\n" + "=" * 60)
    print("Phase 3 v6 Complete!")
    print("=" * 60)
    print(f"Total examples: {len(results)}")
    print(f"Successes: {successes}")
    print(f"Failures: {failures}")
    print(f"Total tokens used: {total_tokens}")
    print(f"Output: {OUTPUT_DATA}")

    # Estimate cost
    # GPT-5.1: $0.50/1M input, $2.00/1M output
    # Rough estimate assuming 80% input, 20% output
    input_tokens = int(total_tokens * 0.8)
    output_tokens = int(total_tokens * 0.2)
    cost = (input_tokens / 1_000_000 * 0.50) + (output_tokens / 1_000_000 * 2.00)
    print(f"Estimated cost: ${cost:.4f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Phase 3 v6: OpenAI GPT-5.1 CoT Synthesis")
    parser.add_argument("--limit", type=int, default=None, help="Limit examples (for testing)")
    parser.add_argument("--no-resume", action="store_true", help="Start fresh")
    args = parser.parse_args()

    main(limit=args.limit, resume=not args.no_resume)
