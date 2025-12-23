#!/usr/bin/env python3
"""
Phase 3: The Teacher - Contrastive CoT Generation

This script generates training data with EXPLICIT contrastive reasoning.
It injects anti-definitions from Phase 2 to force the model to explain
WHY a label is correct AND WHY adjacent labels are NOT correct.

Key Innovation: The prompt includes the definition AND exclusion clauses,
forcing the generated reasoning to address the confusion pairs directly.
"""

import os
import json
import yaml
import torch
import pandas as pd
from transformers import AutoModelForCausalLM, AutoTokenizer
from tqdm import tqdm
from typing import Dict, List, Optional
import argparse

# --- Configuration ---
MODEL_NAME = "fdtn-ai/Foundation-Sec-8B"
ANTI_DEFINITIONS_PATH = "output/taxonomy_anti_definitions.yml"
INPUT_DATA = "models/labeled_examples_normalized.parquet"  # v4 = normalized labels
OUTPUT_DATA = "models/cot_dataset_v4.jsonl"  # v4 = normalized + balanced

# Labels that need contrastive reasoning (from Phase 1 confusion matrix)
# Updated to use canonical label names after normalization
CONTRASTIVE_LABELS = {
    "MGMT_SSH_HTTP", "MGMT_AAA_TACACS_RADIUS", "MGMT_SNMP",
    "SEC_CoPP",  # SEC_CONTROL_PLANE_POLICY merged into this
    "RTE_BGP", "RTE_OSPF", "SEC_BGP_ROUTE_FILTERING",
    "SYS_Boot_Upgrade", "SYS_Licensing_Smart"  # SYSTEM_LICENSE merged into this
}


def load_anti_definitions(path: str) -> Dict:
    """Load the contrastive anti-definitions from Phase 2."""
    with open(path, 'r') as f:
        return yaml.safe_load(f)


def load_training_data(path: str) -> pd.DataFrame:
    """Load the labeled examples."""
    return pd.read_parquet(path)


def build_contrastive_context(label: str, anti_defs: Dict) -> str:
    """
    Build the contrastive context string for a label.
    This includes the definition AND the exclusion clauses.
    """
    if label not in anti_defs:
        return ""

    definition = anti_defs[label]
    context = f"""
**Definition for {label}:**
USE WHEN: {definition.get('description', 'N/A')}

**Critical Exclusions (DO NOT confuse with):**
"""
    for exclusion in definition.get('exclusions', []):
        context += f"- {exclusion}\n"

    context += f"""
**Key Signals:** {', '.join(definition.get('key_signals', []))}
"""
    return context


def get_confused_label(label: str, anti_defs: Dict) -> Optional[str]:
    """Get the most likely confused label for contrastive reasoning."""
    if label not in anti_defs:
        return None

    exclusions = anti_defs[label].get('exclusions', [])
    if exclusions:
        # Extract the first confused label from the exclusion text
        # Format: "Do NOT use for LABEL_NAME: reason..."
        first_exclusion = exclusions[0]
        if "Do NOT use for " in first_exclusion:
            confused = first_exclusion.split("Do NOT use for ")[1].split(":")[0]
            return confused
    return None


def build_contrastive_prompt(summary: str, label: str, anti_defs: Dict) -> str:
    """
    Build the prompt that forces contrastive reasoning.
    The model must explain WHY it's X and WHY it's NOT Y.
    """
    contrastive_context = build_contrastive_context(label, anti_defs)
    confused_label = get_confused_label(label, anti_defs)

    # System prompt with strong contrastive instruction
    system_prompt = """You are an expert Cisco Security Engineer performing vulnerability classification.
Your task is to analyze a Security Advisory and explain the classification reasoning.

CRITICAL REQUIREMENT: Your reasoning MUST include:
1. WHY the correct label applies (cite specific technical indicators)
2. WHY similar/adjacent labels do NOT apply (use the exclusion rules provided)

This "contrastive reasoning" is essential - you must explicitly rule out confusable labels."""

    if confused_label and contrastive_context:
        prompt = f"""### Instruction:
{system_prompt}

{contrastive_context}

### Input:
{summary}

### Target Label:
{label}

### Task:
Generate step-by-step reasoning that:
1. Identifies the key technical indicators in the advisory
2. Explains why '{label}' is correct based on the definition
3. EXPLICITLY explains why this is NOT '{confused_label}' (cite the exclusion rule)

Keep reasoning to 3-5 sentences. Be specific and technical.

### Response:
Reasoning:"""
    else:
        # Fallback for labels without anti-definitions
        prompt = f"""### Instruction:
{system_prompt}

### Input:
{summary}

### Target Label:
{label}

### Task:
Generate step-by-step reasoning explaining why '{label}' is the correct classification.
Identify the key technical indicators that led to this label.
Keep reasoning to 2-3 sentences.

### Response:
Reasoning:"""

    return prompt


def load_existing_progress(output_path: str) -> set:
    """Load advisory IDs that have already been processed."""
    processed_ids = set()
    if os.path.exists(output_path):
        try:
            with open(output_path, 'r') as f:
                for line in f:
                    # Extract advisory ID from the text field if possible
                    # We'll track by line count instead for simplicity
                    processed_ids.add(len(processed_ids))
            print(f"  Found {len(processed_ids)} previously processed examples")
        except Exception as e:
            print(f"  Warning: Could not read existing progress: {e}")
    return processed_ids


def synthesize_mac(input_path: str = None, output_path: str = None,
                   definitions_path: str = None, limit: int = None,
                   resume: bool = True):
    """Mac MPS version - uses float16 without quantization.

    Args:
        input_path: Path to normalized parquet file
        output_path: Path to output JSONL file
        definitions_path: Path to anti-definitions YAML
        limit: Limit number of examples (for testing)
        resume: If True, append to existing output file instead of overwriting
    """
    input_path = input_path or INPUT_DATA
    output_path = output_path or OUTPUT_DATA
    definitions_path = definitions_path or ANTI_DEFINITIONS_PATH

    print("=" * 60)
    print("Phase 3: The Teacher - Contrastive CoT Generation (Mac MPS)")
    print("=" * 60)

    # Load anti-definitions
    print(f"\nLoading anti-definitions from {definitions_path}...")
    anti_defs = load_anti_definitions(definitions_path)
    print(f"  Loaded definitions for {len(anti_defs)} labels")

    # Load training data
    print(f"\nLoading training data from {input_path}...")
    df = load_training_data(input_path)
    print(f"  Loaded {len(df)} examples")

    # BALANCED SAMPLING: Group rows by their PRIMARY label
    # This prevents any single label from dominating the training set
    import random
    from collections import defaultdict
    random.seed(42)

    rows_by_label = defaultdict(list)
    for idx, row in df.iterrows():
        labels = list(row['labels_list']) if row['labels_list'] is not None else []
        if labels:
            primary_label = labels[0]
            rows_by_label[primary_label].append(row)

    print(f"  Found {len(rows_by_label)} unique primary labels")

    # CAP EACH LABEL to prevent domination
    # Contrastive labels get higher caps since they need more training focus
    MAX_PER_CONTRASTIVE_LABEL = 50  # Reduced from unlimited to ensure balance
    MAX_PER_GENERAL_LABEL = 30

    balanced_rows = []
    contrastive_count = 0
    general_count = 0

    for label, rows in rows_by_label.items():
        if label in CONTRASTIVE_LABELS:
            cap = MAX_PER_CONTRASTIVE_LABEL
            random.shuffle(rows)
            selected = rows[:cap]
            balanced_rows.extend(selected)
            contrastive_count += len(selected)
            if len(rows) > cap:
                print(f"    {label}: capped {len(rows)} -> {cap}")
        else:
            cap = MAX_PER_GENERAL_LABEL
            random.shuffle(rows)
            selected = rows[:cap]
            balanced_rows.extend(selected)
            general_count += len(selected)

    print(f"  Balanced contrastive examples: {contrastive_count}")
    print(f"  Balanced general examples: {general_count}")
    print(f"  Total balanced dataset: {len(balanced_rows)}")

    # Shuffle to mix labels
    random.shuffle(balanced_rows)
    all_rows = balanced_rows

    # Check for existing progress (resume support)
    start_idx = 0
    existing_results = []
    if resume and os.path.exists(output_path):
        try:
            with open(output_path, 'r') as f:
                for line in f:
                    existing_results.append(json.loads(line))
            start_idx = len(existing_results)
            if start_idx > 0:
                print(f"\n  RESUMING from {start_idx} existing examples")
                all_rows = all_rows[start_idx:]
        except Exception as e:
            print(f"  Warning: Could not resume - starting fresh: {e}")
            existing_results = []
            start_idx = 0

    # Apply limit if specified (for testing)
    if limit and limit < len(all_rows):
        all_rows = all_rows[:limit]
        print(f"  Limited to {len(all_rows)} examples for testing")
    else:
        print(f"  Total to process: {len(all_rows)}")

    # Load model
    print(f"\nLoading model: {MODEL_NAME}...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)

    # Detect device
    if torch.backends.mps.is_available():
        device = torch.device("mps")
        print("  Using Apple MPS")
        model = AutoModelForCausalLM.from_pretrained(
            MODEL_NAME,
            torch_dtype=torch.float16,
            low_cpu_mem_usage=True
        )
        model = model.to(device)
    elif torch.cuda.is_available():
        device = torch.device("cuda")
        print("  Using NVIDIA CUDA")
        from transformers import BitsAndBytesConfig
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.float16,
        )
        model = AutoModelForCausalLM.from_pretrained(
            MODEL_NAME,
            quantization_config=bnb_config,
            device_map="auto"
        )
    else:
        device = torch.device("cpu")
        print("  Using CPU (will be slow)")
        model = AutoModelForCausalLM.from_pretrained(
            MODEL_NAME,
            torch_dtype=torch.float32,
            low_cpu_mem_usage=True
        )

    model.eval()

    # Generate reasoning
    print(f"\nGenerating contrastive reasoning...")
    results = existing_results.copy()  # Start with any existing results
    errors = 0
    processed_this_run = 0

    for row in tqdm(all_rows, desc="Synthesizing"):
        try:
            summary = row['summary']
            labels = list(row['labels_list']) if row['labels_list'] is not None else []

            if not labels or not summary:
                continue

            # Use the first label for primary reasoning
            primary_label = labels[0]
            label_str = str(labels) if len(labels) > 1 else f"['{primary_label}']"

            # Build contrastive prompt
            prompt = build_contrastive_prompt(summary, primary_label, anti_defs)

            # Generate
            inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=2048)
            inputs = {k: v.to(device) for k, v in inputs.items()}

            with torch.no_grad():
                outputs = model.generate(
                    **inputs,
                    max_new_tokens=200,
                    temperature=0.7,
                    do_sample=True,
                    top_p=0.9,
                    pad_token_id=tokenizer.eos_token_id
                )

            full_output = tokenizer.decode(outputs[0], skip_special_tokens=True)

            # Extract reasoning
            if "### Response:" in full_output:
                reasoning = full_output.split("### Response:")[-1]
                reasoning = reasoning.replace("Reasoning:", "").strip()
            else:
                reasoning = full_output.split("Reasoning:")[-1].strip() if "Reasoning:" in full_output else ""

            # Clean up reasoning (take first 3-5 sentences)
            sentences = reasoning.split(". ")
            reasoning = ". ".join(sentences[:5])
            if not reasoning.endswith("."):
                reasoning += "."

            # Construct final training record
            # Format: Instruction -> Input -> Response (Reasoning + Label)
            final_text = f"""### Instruction:
Classify the following Cisco Security Advisory into the correct technical feature label.

### Input:
{summary[:1500]}

### Response:
{reasoning}

Label: {label_str}"""

            results.append({"text": final_text})
            processed_this_run += 1

            # Periodic save (every 50 examples for safety)
            if processed_this_run % 50 == 0:
                with open(output_path, 'w') as f:
                    for r in results:
                        f.write(json.dumps(r) + "\n")
                print(f"  Checkpoint: {len(results)} total ({processed_this_run} this run)")

        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"  Error processing row: {e}")
            # Save on error too, to preserve progress
            if errors % 10 == 0:
                with open(output_path, 'w') as f:
                    for r in results:
                        f.write(json.dumps(r) + "\n")
            continue

    # Final save
    with open(output_path, 'w') as f:
        for r in results:
            f.write(json.dumps(r) + "\n")

    print("\n" + "=" * 60)
    print("Phase 3 Complete!")
    print("=" * 60)
    print(f"Total examples: {len(results)}")
    print(f"Generated this run: {processed_this_run}")
    print(f"Resumed from: {start_idx}")
    print(f"Errors: {errors}")
    print(f"Output: {output_path}")
    print("\nNext: Run Phase 4 (train_lora_cuda.py) with this dataset")


def main():
    parser = argparse.ArgumentParser(description="Phase 3: Generate Contrastive CoT Training Data")
    parser.add_argument("--input", default=INPUT_DATA, help="Input parquet file")
    parser.add_argument("--output", default=OUTPUT_DATA, help="Output JSONL file")
    parser.add_argument("--definitions", default=ANTI_DEFINITIONS_PATH, help="Anti-definitions YAML")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of examples (for testing)")
    parser.add_argument("--no-resume", action="store_true", help="Start fresh instead of resuming")
    args = parser.parse_args()

    synthesize_mac(
        input_path=args.input,
        output_path=args.output,
        definitions_path=args.definitions,
        limit=args.limit,
        resume=not args.no_resume
    )


if __name__ == "__main__":
    main()
