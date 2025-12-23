#!/usr/bin/env python3
"""
Benchmark PSIRT Labeling Accuracy (Standardized Identity Version)
Comparison: Current 'Foundation-Sec-8B' (Few-Shot/RAG) vs *Standardized* Ground Truth

Metrics:
- Exact Match (EM): Prediction perfectly matches ground truth (order agnostic).
- Precision, Recall, F1 (Micro-averaged): For multi-label classification.
"""
import sys
import os
import csv
import ast
import random
import time
from typing import List, Set

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import Labeler
try:
    from transformers_inference import TransformersPSIRTLabeler
except ImportError:
    print("❌ Could not import TransformersPSIRTLabeler. Run this from the project root.")
    sys.exit(1)


def parse_labels(label_str: str) -> Set[str]:
    """Parse stringified list of labels into a set."""
    try:
        # It's already Python object (list) from standardization script?
        # CSV reader reads as string, so we eval.
        if label_str.strip().startswith('['):
            labels = ast.literal_eval(label_str)
            return set([str(l).strip() for l in labels if l])
        return set()
    except:
        return set()

def calculate_metrics(y_true: List[Set[str]], y_pred: List[Set[str]]):
    """Calculate Multi-label metrics."""
    tp = 0
    fp = 0
    fn = 0
    exact_matches = 0
    
    for true, pred in zip(y_true, y_pred):
        # Exact Match
        if true == pred:
            exact_matches += 1
            
        # TP/FP/FN analysis
        tp += len(true.intersection(pred))
        fp += len(pred - true)
        fn += len(true - pred)
        
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
    em_score = exact_matches / len(y_true) if y_true else 0
    
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "exact_match": em_score,
        "total_samples": len(y_true)
    }

def load_csv_sample(filepath, n=20):
    """Load sample from CSV using standard lib."""
    data = []
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        all_rows = list(reader)
        
    # Filter valid rows (must have labels_list from standardization)
    valid_rows = [
        row for row in all_rows 
        if row.get('labels_list') and row.get('summary')
    ]
    
    print(f"   Total valid standardized examples available: {len(valid_rows)}")
    
    if len(valid_rows) > n:
        return random.sample(valid_rows, n)
    return valid_rows

def main():
    print("🚀 Starting Benchmark: SEC-8B PSIRT Labeling (Identity Verification)")
    print("=" * 60)

    # 1. Load Data (Golden Dataset now!)
    csv_path = "golden_dataset.csv"
    if not os.path.exists(csv_path):
        print(f"❌ Data file not found: {csv_path}. Run standardization first!")
        return

    print(f"📥 Loading dataset: {csv_path}...")
    sample_rows = load_csv_sample(csv_path, n=20)
    
    # 3. Initialize Model
    print("\n🤖 Initializing Model (this may take a moment)...")
    labeler = TransformersPSIRTLabeler()
    
    # 4. Run Inference
    print("\n⚡ Running Inference...")
    y_true = []
    y_pred = []
    
    start_time = time.time()
    
    for idx, row in enumerate(sample_rows):
        summary = row['summary']
        # platform is simplified in golden_dataset
        platform = row.get('platform', 'IOS-XE')
        
        # Ground Truth - labels_list is the standardized identity
        true_labels = parse_labels(row.get('labels_list'))
        if not true_labels:
            continue
            
        # Prediction
        print(f"   [{idx+1}] Processing: {summary[:60]}... ({platform})")
        
        # NOTE: We DO NOT pass advisory_id, so it forces retrieval + generation
        result = labeler.predict_labels(summary, platform=platform) 
        pred_labels = set(result['predicted_labels'])
        
        y_true.append(true_labels)
        y_pred.append(pred_labels)
        
        print(f"      True: {true_labels}")
        print(f"      Pred: {pred_labels}")
        
    duration = time.time() - start_time
    
    # 5. Report Results
    if not y_true:
        print("❌ No valid samples found.")
        return

    metrics = calculate_metrics(y_true, y_pred)
    
    print("\n" + "="*60)
    print("📊 BENCHMARK RESULTS (Identity Compliance)")
    print("="*60)
    print(f"Samples:       {metrics['total_samples']}")
    print(f"Time Taken:    {duration:.2f}s ({duration/metrics['total_samples']:.2f}s/item)")
    print("-" * 30)
    print(f"Exact Match:   {metrics['exact_match']:.2%}  (Perfect full-set match)")
    print(f"Precision:     {metrics['precision']:.2%}  (How many predictions were correct)")
    print(f"Recall:        {metrics['recall']:.2%}  (How many true labels were found)")
    print(f"F1 Score:      {metrics['f1']:.2%}  (Harmonic mean)")
    print("="*60)

if __name__ == "__main__":
    main()
