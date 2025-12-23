#!/usr/bin/env python3
"""
Phase 3 v5: Synthesize CoT Reasoning using Gemini 2.5 Flash

Uses batched requests (50 examples per request) to generate high-quality
contrastive reasoning for LoRA training data.

Key improvements over v4:
- Gemini generates accurate reasoning (not hallucinated)
- Production-format prompts (taxonomy + context)
- Batched for efficiency (50 examples = 1 request)
"""

import os
import json
import yaml
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from tqdm import tqdm
import time
import argparse

# Load environment variables
load_dotenv()

# Configuration
INPUT_DATA = "models/labeled_examples_normalized.parquet"
OUTPUT_DATA = "models/cot_dataset_v5.jsonl"
ANTI_DEFINITIONS_PATH = "output/taxonomy_anti_definitions.yml"
TAXONOMY_PATH = "taxonomies/features.yml"

BATCH_SIZE = 10  # Examples per Gemini request (50 causes truncation)
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds

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


def build_batch_prompt(examples: list, taxonomy: list, anti_defs: dict) -> str:
    """
    Build a prompt for batch processing multiple examples.
    """
    taxonomy_str = ", ".join(taxonomy)

    # Build examples section
    examples_text = ""
    for i, ex in enumerate(examples):
        labels_str = json.dumps(ex['labels'])

        # Get anti-definition context for primary label if available
        primary_label = ex['labels'][0] if ex['labels'] else ""
        anti_context = ""
        if primary_label in anti_defs:
            anti_def = anti_defs[primary_label]
            exclusions = anti_def.get('exclusions', [])[:2]
            if exclusions:
                anti_context = f"\nCommon confusions to address: {'; '.join(exclusions)}"

        examples_text += f"""
---
EXAMPLE {i+1} (ID: {ex['idx']}):
Summary: {ex['summary'][:1500]}
Correct Labels: {labels_str}{anti_context}
---
"""

    prompt = f"""You are an expert Cisco network security engineer. Your task is to generate training data for a classification model.

For each example below, write 2-4 sentences of technical reasoning explaining:
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

{examples_text}

OUTPUT FORMAT:
Return a JSON array with one object per example:
[
  {{"id": <example_id>, "reasoning": "<your reasoning>"}},
  ...
]

Return ONLY the JSON array, no other text."""

    return prompt


def parse_gemini_response(response_text: str, expected_count: int) -> list:
    """Parse Gemini's JSON response."""
    try:
        text = response_text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]

        results = json.loads(text.strip())

        if not isinstance(results, list):
            print(f"  Warning: Expected list, got {type(results)}")
            return []

        return results
    except json.JSONDecodeError as e:
        print(f"  JSON parse error: {e}")
        print(f"  Response preview: {response_text[:500]}...")
        return []


def synthesize_batch(client, model_name: str, examples: list, taxonomy: list, anti_defs: dict) -> list:
    """Synthesize reasoning for a batch of examples."""
    prompt = build_batch_prompt(examples, taxonomy, anti_defs)

    for attempt in range(MAX_RETRIES):
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt
            )
            results = parse_gemini_response(response.text, len(examples))

            if len(results) >= len(examples) * 0.8:
                return results
            else:
                print(f"  Incomplete response ({len(results)}/{len(examples)}), retrying...")
                time.sleep(RETRY_DELAY * (attempt + 1))

        except Exception as e:
            error_str = str(e)
            print(f"  API error (attempt {attempt+1}): {error_str[:200]}")

            # Exponential backoff for all errors
            if "503" in error_str or "overloaded" in error_str.lower():
                wait_time = 30 * (attempt + 1)  # 30s, 60s, 90s for overload
                print(f"  API overloaded, waiting {wait_time}s before retry...")
                time.sleep(wait_time)
            elif "429" in error_str or "quota" in error_str.lower():
                wait_time = 60 * (attempt + 1)  # 60s, 120s, 180s for rate limits
                print(f"  Rate limited, waiting {wait_time}s...")
                time.sleep(wait_time)
            elif attempt < MAX_RETRIES - 1:
                wait_time = RETRY_DELAY * (2 ** attempt)  # Exponential: 5s, 10s, 20s
                print(f"  Waiting {wait_time}s before retry...")
                time.sleep(wait_time)

    return []


def main(limit: int = None, batch_size: int = BATCH_SIZE, resume: bool = True,
         model_name: str = None):
    """Main synthesis pipeline."""
    print("=" * 60)
    print("Phase 3 v5: Gemini CoT Synthesis")
    print("=" * 60)

    # Check API key
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("ERROR: GOOGLE_API_KEY not found in environment")
        print("Create .env file with: GOOGLE_API_KEY=your_key_here")
        return

    # Configure Gemini with new SDK
    client = genai.Client(api_key=api_key)

    # Use provided model or default
    model_name = model_name or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    print(f"  Model: {model_name}")
    print(f"  Batch size: {batch_size} examples/request")

    # Load data
    print(f"\nLoading data...")
    df = pd.read_parquet(INPUT_DATA)
    print(f"  Training examples: {len(df)}")

    taxonomy = load_taxonomy(TAXONOMY_PATH)
    print(f"  Taxonomy labels: {len(taxonomy)}")

    anti_defs = load_anti_definitions(ANTI_DEFINITIONS_PATH)
    print(f"  Anti-definitions: {len(anti_defs)}")

    # Balanced sampling (same as v4)
    import random
    from collections import defaultdict
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

    # Process in batches
    results = list(existing_results.values())
    num_batches = (len(to_process) + batch_size - 1) // batch_size

    print(f"\nProcessing {len(to_process)} examples in {num_batches} batches...")
    print(f"Estimated API calls: {num_batches}")

    for batch_idx in tqdm(range(num_batches), desc="Batches"):
        start = batch_idx * batch_size
        end = min(start + batch_size, len(to_process))
        batch = to_process[start:end]

        # Prepare batch data
        batch_examples = []
        batch_meta = []

        for idx, row, h in batch:
            labels = list(row['labels_list']) if row['labels_list'] is not None else []
            batch_examples.append({
                'idx': idx,
                'summary': row['summary'],
                'labels': labels
            })
            batch_meta.append({
                'idx': idx,
                'row': row,
                'hash': h
            })

        # Call Gemini
        batch_results = synthesize_batch(client, model_name, batch_examples, taxonomy, anti_defs)

        # Track fallback count for this batch
        batch_fallback_count = 0
        batch_new_results = []

        # Match results back to examples - prefer position-based matching (more reliable)
        for i, (meta, ex) in enumerate(zip(batch_meta, batch_examples)):
            reasoning = ""

            # Try position-based matching first (most reliable)
            if i < len(batch_results) and 'reasoning' in batch_results[i]:
                reasoning = batch_results[i]['reasoning']

            # Fallback to ID matching
            if not reasoning:
                results_by_id = {r.get('id'): r.get('reasoning', '') for r in batch_results if 'id' in r}
                reasoning = results_by_id.get(meta['idx'], results_by_id.get(str(meta['idx']), ""))

            # Last resort: generic fallback
            if not reasoning:
                reasoning = f"This advisory relates to {ex['labels'][0] if ex['labels'] else 'unknown'} functionality."
                batch_fallback_count += 1
                print(f"  Warning: Using fallback for example {meta['idx']}")

            # Build final training record
            labels = ex['labels']
            label_str = str(labels) if len(labels) > 1 else f"['{labels[0]}']" if labels else "[]"

            final_text = f"""### Instruction:
Classify the following Cisco Security Advisory into the correct technical feature label.

### Input:
{ex['summary'][:1500]}

### Response:
{reasoning}

Label: {label_str}"""

            batch_new_results.append({
                'text': final_text,
                'summary_hash': meta['hash']
            })

        # Quality gate: reject batches with >20% fallbacks (waste of quota)
        fallback_rate = batch_fallback_count / len(batch_new_results) if batch_new_results else 0
        if fallback_rate > 0.2:
            print(f"  ⚠️ BATCH REJECTED: {batch_fallback_count}/{len(batch_new_results)} fallbacks ({fallback_rate:.0%})")
            print(f"  Skipping save - these examples will be retried next run")
            continue  # Don't save bad results, they'll be retried

        # Add good results
        results.extend(batch_new_results)
        print(f"  ✓ Batch OK: {len(batch_new_results) - batch_fallback_count}/{len(batch_new_results)} good")

        # Save checkpoint after each batch
        with open(OUTPUT_DATA, 'w') as f:
            for r in results:
                f.write(json.dumps(r) + "\n")

        # Rate limiting - 5s between batches (paid tier has higher RPM)
        if batch_idx < num_batches - 1:
            time.sleep(5)

    # Final stats
    print("\n" + "=" * 60)
    print("Phase 3 v5 Complete!")
    print("=" * 60)
    print(f"Total examples: {len(results)}")
    print(f"Output: {OUTPUT_DATA}")
    print(f"\nNext: Run Phase 4 (train_lora_cuda.py) with this dataset")
    print(f"  Update DATA_FILE in train_lora_cuda.py to: {OUTPUT_DATA}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Phase 3 v5: Gemini CoT Synthesis")
    parser.add_argument("--limit", type=int, default=None, help="Limit examples (for testing)")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE, help="Examples per request")
    parser.add_argument("--no-resume", action="store_true", help="Start fresh")
    parser.add_argument("--model", type=str, default=None, help="Gemini model (default: gemini-2.5-flash)")
    args = parser.parse_args()

    main(limit=args.limit, batch_size=args.batch_size, resume=not args.no_resume,
         model_name=args.model)
