#!/usr/bin/env python3
"""
Ingest Frontier Labels (GPT-4o/Gemini) into the RAG index.
Adds 'reasoning' metadata to the index for future CoT distillation.
"""
import json
import glob
import os
import pandas as pd
import faiss
import numpy as np
import argparse
from sentence_transformers import SentenceTransformer
from datetime import datetime

# Configuration
EMBEDDER_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
INDEX_PATH = "models/faiss_index.bin"
DATA_PATH = "models/labeled_examples.parquet"
FRONTIER_DATA_DIR = "data/Labeled_Bugs"

def load_frontier_data():
    """Load all JSON files from frontier data directory"""
    files = glob.glob(os.path.join(FRONTIER_DATA_DIR, "*.json"))
    all_data = []
    print(f"📂 Found {len(files)} JSON files in {FRONTIER_DATA_DIR}")
    
    for fpath in files:
        try:
            with open(fpath, 'r') as f:
                data = json.load(f)
                print(f"   - {os.path.basename(fpath)}: {len(data)} items")
                # Add source filename
                for item in data:
                    item['_source_file'] = os.path.basename(fpath)
                all_data.extend(data)
        except Exception as e:
            print(f"⚠️  Error reading {fpath}: {e}")
            
    return all_data

def process_item(item):
    """Normalize item to standard format"""
    # Handle different schema variations
    summary = item.get('summary', '') or item.get('psirt_summary', '')
    platform = item.get('platform', 'Unknown')
    
    # Extract labels
    labels = []
    if 'labels_gpt' in item:
        labels = item['labels_gpt']
    elif 'labels' in item:
        labels = item['labels']
    elif 'predicted_labels' in item:
        labels = item['predicted_labels']
        
    # Extract reasoning
    reasoning = item.get('reasoning', '')
    
    # Skip if no summary or no labels
    if not summary or not labels:
        return None
        
    # Skip if labels is empty list
    if isinstance(labels, list) and len(labels) == 0:
        return None
        
    return {
        'summary': summary,
        'platform': platform,
        'labels': labels, # Keep as list for now
        'reasoning': reasoning,
        'source': f"frontier_{item['_source_file']}",
        'timestamp': datetime.now().isoformat()
    }

def main():
    parser = argparse.ArgumentParser(description="Ingest Frontier Labels")
    parser.add_argument('--dry-run', action='store_true', help="Don't save changes")
    args = parser.parse_args()
    
    print("🚀 Starting Frontier Ingestion...")
    
    # 1. Load Data
    raw_data = load_frontier_data()
    processed_data = []
    skipped = 0
    
    for item in raw_data:
        p_item = process_item(item)
        if p_item:
            processed_data.append(p_item)
        else:
            skipped += 1
            
    print(f"✅ Processed {len(processed_data)} valid items (Skipped {skipped})")
    
    if args.dry_run:
        print("\n🔎 DRY RUN PREVIEW (First 3 items):")
        for i, item in enumerate(processed_data[:3]):
            print(f"--- Item {i+1} ---")
            print(f"Summary: {item['summary'][:100]}...")
            print(f"Labels: {item['labels']}")
            print(f"Reasoning: {item['reasoning'][:100]}...")
        print("\n⚠️  Dry run complete. No changes saved.")
        return

    # 2. Update Index
    print("\n📚 Loading Embedder & Index...")
    model = SentenceTransformer(EMBEDDER_MODEL)
    
    # Load existing parquet
    if os.path.exists(DATA_PATH):
        df_base = pd.read_parquet(DATA_PATH)
        print(f"   Loaded existing data: {len(df_base)} rows")
    else:
        df_base = pd.DataFrame()
        print("   No existing data found, creating new dataframe")

    # Load existing FAISS
    if os.path.exists(INDEX_PATH):
        index = faiss.read_index(INDEX_PATH)
        print(f"   Loaded existing index: {index.ntotal} vectors")
    else:
        index = faiss.IndexFlatL2(384)
        print("   Created new FAISS index")
        
    # 3. Compute Embeddings
    print(f"\n🧠 Computing embeddings for {len(processed_data)} new items...")
    summaries = [item['summary'] for item in processed_data]
    embeddings = model.encode(summaries, show_progress_bar=True)
    
    # 4. Add to Index
    print("📥 Adding to FAISS index...")
    index.add(embeddings.astype('float32'))
    
    # 5. Add to DataFrame
    print("📥 Adding to DataFrame...")
    new_rows = []
    for i, item in enumerate(processed_data):
        new_rows.append({
            'source': item['source'],
            'advisoryId': f"gen_{i}_{datetime.now().timestamp()}", # consistent ID
            'platform': item['platform'],
            'summary': item['summary'],
            'labels_list': item['labels'], # Store list directly (parquet supports it)
            'labels': json.dumps(item['labels']), # Legacy string format just in case
            'reasoning': item['reasoning']
        })
        
    df_new = pd.DataFrame(new_rows)
    
    # align columns
    # ensure 'reasoning' column exists in base or adding it
    if 'reasoning' not in df_base.columns and not df_base.empty:
        df_base['reasoning'] = None
        
    df_combined = pd.concat([df_base, df_new], ignore_index=True)
    
    # 6. Save
    print(f"\n💾 Saving {len(df_combined)} rows to {DATA_PATH}...")
    df_combined.to_parquet(DATA_PATH)
    
    print(f"💾 Saving {index.ntotal} vectors to {INDEX_PATH}...")
    faiss.write_index(index, INDEX_PATH)
    
    print("\n✅ Ingestion Complete!")

if __name__ == "__main__":
    main()
