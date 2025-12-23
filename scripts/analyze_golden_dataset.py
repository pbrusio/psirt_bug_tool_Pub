#!/usr/bin/env python3
"""
Analyze Golden Dataset Composition
==================================

Provides deep transparency into the "standardized" dataset:
1. Label Distribution (How many 'RTE_BGP' examples do we have?)
2. Platform Distribution
3. Coverage Gaps (Which taxonomy labels have 0 examples?)
"""

import csv
import ast
import os
import yaml
from collections import Counter, defaultdict

GOLDEN_CSV = "golden_dataset.csv"
TAXONOMY_DIR = "taxonomies"

def load_all_taxonomy_labels():
    """Load the full set of valid identity labels."""
    labels = set()
    files = [f for f in os.listdir(TAXONOMY_DIR) if f.endswith('.yml')]
    for fname in files:
        with open(os.path.join(TAXONOMY_DIR, fname), 'r') as f:
            try:
                data = yaml.safe_load(f)
                if isinstance(data, list):
                    for item in data:
                        if 'label' in item:
                            labels.add(item['label'])
            except: pass
    return labels

def main():
    if not os.path.exists(GOLDEN_CSV):
        print(f"❌ {GOLDEN_CSV} not found.")
        return

    print("📊 Golden Dataset Deep Dive")
    print("="*60)

    # 1. Load Data
    rows = []
    with open(GOLDEN_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    total_examples = len(rows)
    print(f"Total Examples: {total_examples}")

    # 2. Aggregations
    label_counts = Counter()
    platform_counts = Counter()
    examples_per_label = defaultdict(list)

    for row in rows:
        try:
            labels = ast.literal_eval(row['labels_list'])
            platform = row['platform']
            
            platform_counts[platform] += 1
            
            for label in labels:
                label_counts[label] += 1
                if len(examples_per_label[label]) < 3: # Keep a few samples
                    examples_per_label[label].append(row['summary'][:60] + "...")
        except:
            pass

    # 3. Report
    print(f"\n🌍 Platform Breakdown")
    print("-" * 30)
    for plat, count in platform_counts.most_common():
        print(f"{plat:<10}: {count:>3} ({count/total_examples:.1%})")

    print(f"\n🏷️  Label Distribution (Top 20)")
    print("-" * 30)
    for label, count in label_counts.most_common(20):
        print(f"{label:<25}: {count:>3} examples")

    # 4. Coverage Analysis
    all_taxonomy_labels = load_all_taxonomy_labels()
    covered_labels = set(label_counts.keys())
    missing_labels = all_taxonomy_labels - covered_labels
    
    print(f"\n⚠️  Coverage Gaps (Taxonomy labels with 0 examples)")
    print("-" * 30)
    print(f"Covered: {len(covered_labels)} / {len(all_taxonomy_labels)} labels")
    print(f"Missing: {len(missing_labels)}")
    
    if missing_labels:
        print("\nTop Missing Examples (Random 5):")
        for m in list(missing_labels)[:5]:
            print(f" - {m}")

    print("\n" + "="*60)
    print("🧠 ANALYSIS")
    if total_examples < 50:
        print("🔴 CRITICAL: Dataset is too small for robust Few-Shot learning.")
    elif total_examples < 200:
        print("🟡 WARNING: Dataset is lean. Rare categories may mispredict.")
    else:
        print("🟢 STATUS: Baseline volume is acceptable.")
        
    print("To fix gaps: Add regex rules in `scripts/standardize_labels.py` for missing labels.")

if __name__ == "__main__":
    main()
