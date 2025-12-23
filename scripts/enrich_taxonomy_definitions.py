#!/usr/bin/env python3
"""
Phase 2: The Rules - Generate Contrastive Anti-Definitions

This script generates prompts for a Frontier Model to create "Anti-Definitions"
that explicitly disambiguate confused label pairs.

Based on Phase 1 Ruler results:
- SEC_CoPP ↔ MGMT_SSH_HTTP (4 confusions)
- MGMT_AAA_TACACS_RADIUS ↔ MGMT_SSH_HTTP (8 confusions bidirectional)
- RTE_BGP → SEC_BGP_ROUTE_FILTERING (4 confusions)
- SEC_CONTROL_PLANE_POLICY → MGMT_SSH_HTTP (3 confusions)
- RTE_OSPF → SEC_BGP_ROUTE_FILTERING (3 confusions)
"""

import yaml
import pandas as pd
import json
import argparse
import os
from typing import Dict, List, Tuple

# ============================================================================
# CONFUSION PAIRS FROM PHASE 1 (The Ruler)
# Format: (correct_label, confused_with_label, confusion_count)
# ============================================================================
CONFUSION_PAIRS = [
    # Management Cluster - "Talking to the Box" vs "Authenticating to the Box"
    ("MGMT_SSH_HTTP", "MGMT_AAA_TACACS_RADIUS", 4),
    ("MGMT_AAA_TACACS_RADIUS", "MGMT_SSH_HTTP", 4),

    # Security Cluster - Control Plane Protection vs Management Interfaces
    ("SEC_CoPP", "MGMT_SSH_HTTP", 4),
    ("SEC_CONTROL_PLANE_POLICY", "MGMT_SSH_HTTP", 3),
    ("SEC_CoPP", "MGMT_AAA_TACACS_RADIUS", 2),

    # Routing Cluster - Routing Protocols vs Security Filtering
    ("RTE_BGP", "SEC_BGP_ROUTE_FILTERING", 4),
    ("RTE_OSPF", "SEC_BGP_ROUTE_FILTERING", 3),

    # System Cluster
    ("SYS_Boot_Upgrade", "MGMT_SSH_HTTP", 2),
    ("SYS_Boot_Upgrade", "SEC_8021X", 2),
]

# ============================================================================
# ANTI-DEFINITION TEMPLATES
# These define the discrimination logic for each confused pair
# ============================================================================
ANTI_DEFINITION_RULES = {
    # Management Cluster
    "MGMT_SSH_HTTP": {
        "use_when": "The vulnerability is in the SSH/HTTP/HTTPS *interface* or *service* itself - the transport mechanism for remote management.",
        "do_not_use_for": [
            ("MGMT_AAA_TACACS_RADIUS", "authentication/authorization *server configuration* or credential handling. SSH is HOW you connect; AAA is HOW you authenticate."),
            ("SEC_CoPP", "control plane *protection policies* that rate-limit traffic TO the CPU. CoPP protects the box; SSH/HTTP is a way to talk to the box."),
        ],
        "key_signals": ["web UI", "HTTP server", "SSH server", "management interface", "remote CLI", "webui"],
    },

    "MGMT_AAA_TACACS_RADIUS": {
        "use_when": "The vulnerability is in authentication/authorization logic, credential handling, TACACS+/RADIUS server communication, or user privilege assignment.",
        "do_not_use_for": [
            ("MGMT_SSH_HTTP", "SSH/HTTP *interface* vulnerabilities. AAA is about WHO can access; SSH/HTTP is about HOW they connect."),
        ],
        "key_signals": ["authentication bypass", "credential", "TACACS", "RADIUS", "AAA", "privilege escalation via user roles", "authorization"],
    },

    # Security Cluster
    "SEC_CoPP": {
        "use_when": "The vulnerability involves Control Plane Policing - rate limiting or filtering traffic destined TO the device's CPU/control plane.",
        "do_not_use_for": [
            ("MGMT_SSH_HTTP", "vulnerabilities in management *interfaces*. CoPP protects the control plane from DoS; it's not about SSH/HTTP bugs."),
            ("SEC_CONTROL_PLANE_POLICY", "generic control plane *policies*. CoPP specifically refers to the QoS-based policing mechanism."),
        ],
        "key_signals": ["control plane policing", "CoPP", "rate limit to CPU", "punt traffic", "control-plane host"],
    },

    "SEC_CONTROL_PLANE_POLICY": {
        "use_when": "The vulnerability involves control plane protection mechanisms OTHER than CoPP - such as CPPr (Control Plane Protection) subinterfaces or management-plane policies.",
        "do_not_use_for": [
            ("SEC_CoPP", "CoPP-specific rate limiting. Use SEC_CoPP for QoS-based policing."),
            ("MGMT_SSH_HTTP", "management interface bugs. Control plane policy is about protecting the CPU, not about SSH/HTTP services."),
        ],
        "key_signals": ["control-plane", "management-plane", "CPPr", "punt-cause"],
    },

    # Routing Cluster
    "RTE_BGP": {
        "use_when": "The vulnerability is in BGP protocol *processing* - UPDATE handling, session management, attribute parsing, or route computation.",
        "do_not_use_for": [
            ("SEC_BGP_ROUTE_FILTERING", "route *filtering* or *security policies* applied to BGP (prefix-lists, route-maps for security). RTE_BGP is about the protocol itself crashing or misbehaving."),
        ],
        "key_signals": ["BGP UPDATE", "BGP session", "BGP peer", "AS path", "BGP crash", "BGP DoS", "malformed BGP"],
    },

    "SEC_BGP_ROUTE_FILTERING": {
        "use_when": "The vulnerability is in BGP route *filtering mechanisms* - prefix-lists, AS-path filters, route-maps used for security, or RPKI validation.",
        "do_not_use_for": [
            ("RTE_BGP", "BGP protocol processing bugs (crashes, DoS). This label is for filtering/security controls, not protocol bugs."),
        ],
        "key_signals": ["prefix-list", "route-map", "AS-path filter", "RPKI", "route filtering", "BGP security"],
    },

    "RTE_OSPF": {
        "use_when": "The vulnerability is in OSPF protocol processing - LSA handling, SPF computation, adjacency formation, or area processing.",
        "do_not_use_for": [
            ("SEC_BGP_ROUTE_FILTERING", "this is a BGP-specific label. OSPF has no relation to BGP route filtering."),
            ("RTE_BGP", "BGP protocol issues. OSPF and BGP are different routing protocols."),
        ],
        "key_signals": ["OSPF", "LSA", "SPF", "OSPF neighbor", "OSPF area", "link-state"],
    },

    # System Cluster
    "SYS_Boot_Upgrade": {
        "use_when": "The vulnerability is in the boot process, firmware upgrade mechanism, image verification, or ROMMON.",
        "do_not_use_for": [
            ("MGMT_SSH_HTTP", "management interface bugs. Boot/upgrade is about system initialization, not remote management."),
            ("SEC_8021X", "802.1X port authentication. These are unrelated features."),
        ],
        "key_signals": ["boot", "upgrade", "firmware", "ROMMON", "image", "install", "software update"],
    },
}


def load_taxonomy(yaml_path: str) -> List[Dict]:
    """Load taxonomy YAML file."""
    with open(yaml_path, 'r') as f:
        return yaml.safe_load(f)


def load_examples(parquet_path: str) -> pd.DataFrame:
    """Load labeled examples."""
    return pd.read_parquet(parquet_path)


def get_examples_for_label(df: pd.DataFrame, label: str, n: int = 3) -> List[str]:
    """Get example summaries for a label."""
    relevant = df[df['labels_list'].apply(lambda x: label in list(x) if x is not None else False)]
    examples = relevant['summary'].unique()[:n]
    return [ex[:300] + "..." if len(ex) > 300 else ex for ex in examples]


def generate_contrastive_prompt(label: str, rules: Dict, examples: List[str], confused_pairs: List[Tuple]) -> str:
    """Generate a single contrastive definition prompt."""

    # Build the "DO NOT USE FOR" section
    do_not_use_section = ""
    for confused_label, reason in rules.get("do_not_use_for", []):
        do_not_use_section += f"  - **{confused_label}**: {reason}\n"

    # Build examples section
    examples_section = ""
    for i, ex in enumerate(examples, 1):
        examples_section += f"{i}. {ex}\n"
    if not examples_section:
        examples_section = "(No examples available)"

    # Build key signals
    signals = ", ".join(rules.get("key_signals", []))

    prompt = f"""
## Label: `{label}`

### USE WHEN:
{rules.get("use_when", "No definition provided.")}

### DO NOT USE FOR:
{do_not_use_section if do_not_use_section else "  (No exclusions defined)"}

### KEY SIGNALS (words/phrases that indicate this label):
{signals}

### VERIFIED EXAMPLES (summaries where {label} is CORRECT):
{examples_section}

---

### TASK FOR FRONTIER MODEL:
Given the above context, generate a **single-paragraph expert definition** for `{label}` that:
1. Clearly states what this label covers
2. **Explicitly includes at least one "Do NOT use for X (use Y instead)" clause**
3. Lists 2-3 key trigger words/phrases

**OUTPUT FORMAT:**
```
{label}: <definition with explicit exclusion clause>
Key signals: <comma-separated trigger words>
```
"""
    return prompt


def generate_all_prompts(taxonomy: List[Dict], df: pd.DataFrame) -> str:
    """Generate all contrastive definition prompts."""

    output = """# Phase 2: The Rules - Contrastive Anti-Definitions

## Purpose
These prompts generate definitions that EXPLICITLY disambiguate confused label pairs.
Each definition must contain "Do NOT use for X" clauses.

## Confusion Pairs Being Addressed (from Phase 1 Ruler):
| Correct Label | Confused With | Count |
|---------------|---------------|-------|
"""

    for correct, confused, count in CONFUSION_PAIRS:
        output += f"| {correct} | {confused} | {count} |\n"

    output += "\n---\n\n"
    output += "## Prompts for Frontier Model\n\n"

    # Generate prompts only for labels in our confusion pairs
    labels_to_process = set()
    for correct, confused, _ in CONFUSION_PAIRS:
        labels_to_process.add(correct)
        labels_to_process.add(confused)

    for label in sorted(labels_to_process):
        if label in ANTI_DEFINITION_RULES:
            rules = ANTI_DEFINITION_RULES[label]
            examples = get_examples_for_label(df, label)

            # Find what this label is confused with
            confused_pairs = [(c, cnt) for cor, c, cnt in CONFUSION_PAIRS if cor == label]

            prompt = generate_contrastive_prompt(label, rules, examples, confused_pairs)
            output += prompt
            output += "\n\n---\n\n"

    return output


def generate_taxonomy_update_yaml(output_path: str):
    """Generate a YAML snippet to update the taxonomy with anti-definitions."""

    updates = {}
    for label, rules in ANTI_DEFINITION_RULES.items():
        exclusions = [f"Do NOT use for {conf}: {reason}"
                      for conf, reason in rules.get("do_not_use_for", [])]

        updates[label] = {
            "description": rules.get("use_when", ""),
            "exclusions": exclusions,
            "key_signals": rules.get("key_signals", []),
        }

    with open(output_path, 'w') as f:
        yaml.dump(updates, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    print(f"Generated taxonomy updates: {output_path}")


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)

    default_taxonomy = os.path.join(project_root, "taxonomies/features.yml")
    default_data = os.path.join(project_root, "models/labeled_examples_cleaned.parquet")
    default_output = os.path.join(project_root, "output/phase2_contrastive_prompts.md")
    default_yaml_output = os.path.join(project_root, "output/taxonomy_anti_definitions.yml")

    parser = argparse.ArgumentParser(description="Phase 2: Generate Contrastive Anti-Definitions")
    parser.add_argument("--taxonomy", default=default_taxonomy, help="Path to taxonomy YAML")
    parser.add_argument("--data", default=default_data, help="Path to labeled data Parquet")
    parser.add_argument("--output", default=default_output, help="Output file for prompts")
    parser.add_argument("--yaml-output", default=default_yaml_output, help="Output YAML for taxonomy updates")
    args = parser.parse_args()

    print("=" * 60)
    print("Phase 2: The Rules - Contrastive Anti-Definitions")
    print("=" * 60)

    # Load data
    print(f"\nLoading taxonomy from {args.taxonomy}...")
    taxonomy = load_taxonomy(args.taxonomy)
    print(f"  Loaded {len(taxonomy)} labels")

    print(f"\nLoading examples from {args.data}...")
    df = load_examples(args.data)
    print(f"  Loaded {len(df)} examples")

    # Generate prompts
    print(f"\nGenerating contrastive prompts for {len(ANTI_DEFINITION_RULES)} confused labels...")
    prompts = generate_all_prompts(taxonomy, df)

    # Write outputs
    os.makedirs(os.path.dirname(args.output), exist_ok=True)

    with open(args.output, 'w') as f:
        f.write(prompts)
    print(f"\n✅ Prompts written to: {args.output}")

    # Generate YAML updates
    generate_taxonomy_update_yaml(args.yaml_output)
    print(f"✅ Taxonomy updates written to: {args.yaml_output}")

    print("\n" + "=" * 60)
    print("NEXT STEPS:")
    print("=" * 60)
    print("1. Review output/phase2_contrastive_prompts.md")
    print("2. Run prompts through Claude/GPT-4 to generate definitions")
    print("3. Merge results into taxonomies/features.yml")
    print("4. Proceed to Phase 3 (The Teacher)")


if __name__ == "__main__":
    main()
