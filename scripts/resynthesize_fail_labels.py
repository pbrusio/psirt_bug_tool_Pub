#!/usr/bin/env python3
"""
Targeted CoT Re-synthesis for FAIL Labels
==========================================

Re-synthesizes Chain-of-Thought reasoning for training examples containing
labels that have 0% recall despite having training data. The key improvement
is injecting taxonomy definitions and "NOT confused with" constraints.

Usage:
    python scripts/resynthesize_fail_labels.py --dry-run       # Preview
    python scripts/resynthesize_fail_labels.py --limit 10      # Test with 10
    python scripts/resynthesize_fail_labels.py --run           # Full run

Cost estimate: ~$0.50-1.00 for 634 examples using GPT-4o-mini
"""

import json
import yaml
import argparse
import time
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

# Confusion map: what each FAIL label gets confused with
CONFUSION_MAP = {
    'SEC_MAB': ['MGMT_AAA_TACACS_RADIUS'],
    'RTE_OSPF': ['MPLS_STATIC', 'RTE_BGP', 'MCAST_PIM'],
    'SEC_BGP_ROUTE_FILTERING': ['MPLS_STATIC', 'L2_STP', 'RTE_BGP'],
    'RTE_Static': ['MPLS_STATIC', 'MPLS_TE'],
    'HA_Redundancy_SSO': ['SYS_Licensing_Smart'],
    'VPN_IKEv2': ['MPLS_STATIC'],
    'MGMT_RPC / NETCONF': ['MGMT_SNMP', 'MGMT_SSH_HTTP'],
    'MGMT_RPC_NETCONF': ['MGMT_SNMP', 'MGMT_SSH_HTTP'],
    'HA_StackPower': ['L2_L2ProtocolTunneling', 'HA_StackWise'],
    'SYS_Licensing_Smart': ['MPLS_STATIC', 'SYS_Boot_Upgrade'],
    'CTS_Base': ['SEC_8021X', 'SEC_MAB'],
    'MPLS_TE': ['MPLS_STATIC', 'MPLS_LDP', 'MCAST_PIM'],
}


def load_taxonomy_definitions(platform: str = 'IOS-XE') -> Dict[str, str]:
    """Load taxonomy definitions from features.yml"""
    taxonomy_files = {
        'IOS-XE': 'taxonomies/features.yml',
        'IOS-XR': 'taxonomies/features_iosxr.yml',
        'ASA': 'taxonomies/features_asa.yml',
        'FTD': 'taxonomies/features_asa.yml',
        'NX-OS': 'taxonomies/features_nxos.yml',
    }

    filepath = taxonomy_files.get(platform, 'taxonomies/features.yml')
    definitions = {}

    try:
        with open(filepath, 'r') as f:
            features = yaml.safe_load(f)

        for feat in features:
            label = feat.get('label', '')
            desc = feat.get('description', '')
            if label and desc:
                definitions[label] = desc
    except Exception as e:
        print(f"Warning: Could not load taxonomy for {platform}: {e}")

    return definitions


def build_contrastive_prompt(example: Dict, taxonomy_defs: Dict) -> str:
    """Build a prompt that emphasizes correct vs confused labels"""

    summary = example['summary']
    labels = example['labels']
    platform = example.get('platform', 'IOS-XE')
    fail_label = example.get('fail_label', labels[0] if labels else '')

    # Get definition for the correct label
    correct_def = taxonomy_defs.get(fail_label, f"Label for {fail_label} features")

    # Get confused labels and their definitions
    confused_labels = CONFUSION_MAP.get(fail_label, [])

    confused_section = ""
    if confused_labels:
        confused_section = "\n\nCOMMONLY CONFUSED WITH (but INCORRECT for this case):\n"
        for conf_label in confused_labels:
            conf_def = taxonomy_defs.get(conf_label, f"Label for {conf_label} features")
            confused_section += f"- {conf_label}: {conf_def[:200]}...\n"

    prompt = f"""You are a Cisco security advisory labeling expert. Generate step-by-step reasoning that explains why the given labels are correct.

ADVISORY SUMMARY:
{summary}

PLATFORM: {platform}

CORRECT LABELS: {json.dumps(labels)}

LABEL DEFINITIONS:
"""

    # Add definitions for all correct labels
    for label in labels:
        label_def = taxonomy_defs.get(label, f"Label for {label} features")
        prompt += f"- {label}: {label_def[:300]}\n"

    prompt += confused_section

    prompt += f"""

TASK: Write a concise technical reasoning (2-4 sentences) that:
1. Identifies the specific technical indicators in the summary that point to {fail_label}
2. Explains WHY the correct labels apply (cite specific keywords, protocols, or behaviors)
3. If applicable, explains why commonly confused labels do NOT apply

Output format:
The advisory describes [specific technical behavior]. This indicates [feature/protocol] because [technical reason]. The correct label is {fail_label} because [specific indicator]. [If confused labels exist: This is NOT [confused_label] because [distinguishing factor].]

Generate the reasoning now:"""

    return prompt


def synthesize_with_openai(prompt: str, api_key: str) -> Optional[str]:
    """Call OpenAI API to generate reasoning"""
    import openai

    client = openai.OpenAI(api_key=api_key)

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a Cisco networking expert who provides precise technical analysis of security advisories."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=300,
            temperature=0.3
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"API error: {e}")
        return None


def format_training_example(summary: str, labels: List[str], reasoning: str, platform: str) -> Dict:
    """Format as OpenAI fine-tuning format"""

    user_content = f"""### Instruction:
Classify the following Cisco Security Advisory into the correct technical feature label.

### Input:
{summary}

### Response:"""

    assistant_content = f"""{reasoning}

Label: {json.dumps(labels)}"""

    return {
        "messages": [
            {"role": "user", "content": user_content},
            {"role": "assistant", "content": assistant_content}
        ]
    }


def main():
    parser = argparse.ArgumentParser(description='Re-synthesize CoT for FAIL labels')
    parser.add_argument('--dry-run', action='store_true', help='Preview prompts without API calls')
    parser.add_argument('--run', action='store_true', help='Execute full re-synthesis')
    parser.add_argument('--limit', type=int, default=None, help='Limit number of examples')
    parser.add_argument('--input', default='models/fail_label_examples_for_resynthesis.json',
                        help='Input file with examples')
    parser.add_argument('--output', default='models/cot_resynthesized_fail_labels.jsonl',
                        help='Output JSONL file')
    args = parser.parse_args()

    if not args.dry_run and not args.run:
        print("Please specify --dry-run or --run")
        return

    # Load API key
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key and args.run:
        print("Error: OPENAI_API_KEY environment variable not set")
        return

    # Load examples
    print(f"Loading examples from {args.input}...")
    with open(args.input, 'r') as f:
        examples = json.load(f)

    if args.limit:
        examples = examples[:args.limit]

    print(f"Processing {len(examples)} examples")

    # Load taxonomy definitions
    print("Loading taxonomy definitions...")
    taxonomy_defs = {}
    for platform in ['IOS-XE', 'IOS-XR', 'ASA', 'FTD', 'NX-OS']:
        taxonomy_defs.update(load_taxonomy_definitions(platform))
    print(f"Loaded {len(taxonomy_defs)} label definitions")

    if args.dry_run:
        # Just show sample prompts
        print("\n" + "=" * 80)
        print("DRY RUN: Sample prompts")
        print("=" * 80)

        for i, ex in enumerate(examples[:3]):
            prompt = build_contrastive_prompt(ex, taxonomy_defs)
            print(f"\n--- Example {i+1}: {ex['fail_label']} ---")
            print(prompt[:1500] + "..." if len(prompt) > 1500 else prompt)
            print()

        print(f"\nWould process {len(examples)} examples")
        print(f"Estimated cost: ${len(examples) * 0.001:.2f} (GPT-4o-mini)")
        return

    # Full run
    print("\n" + "=" * 80)
    print(f"RE-SYNTHESIZING COT FOR {len(examples)} FAIL LABEL EXAMPLES")
    print(f"Started: {datetime.now().isoformat()}")
    print("=" * 80)

    results = []
    errors = 0

    for i, ex in enumerate(examples):
        print(f"\rProcessing {i+1}/{len(examples)}...", end='', flush=True)

        prompt = build_contrastive_prompt(ex, taxonomy_defs)
        reasoning = synthesize_with_openai(prompt, api_key)

        if reasoning:
            training_ex = format_training_example(
                ex['summary'],
                ex['labels'],
                reasoning,
                ex.get('platform', 'IOS-XE')
            )
            results.append(training_ex)
        else:
            errors += 1

        # Rate limiting
        time.sleep(0.1)

    print(f"\n\nCompleted: {len(results)} successful, {errors} errors")

    # Save results
    with open(args.output, 'w') as f:
        for r in results:
            f.write(json.dumps(r) + '\n')

    print(f"Saved to: {args.output}")

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Input examples: {len(examples)}")
    print(f"Successful: {len(results)}")
    print(f"Errors: {errors}")
    print(f"Output file: {args.output}")


if __name__ == '__main__':
    main()
