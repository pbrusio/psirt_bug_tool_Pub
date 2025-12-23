#!/usr/bin/env python3
"""
Close the Loop: Merge Silver Labels into RAG Index
Safe execution with deduplication.
"""
import pandas as pd
import os
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

def main():
    print("🔄 Closing the Loop...")
    
    # Paths
    silver_path = PROJECT_ROOT / 'models' / 'silver_labels.parquet'
    main_parquet = PROJECT_ROOT / 'models' / 'labeled_examples.parquet'
    
    if not silver_path.exists():
        print("❌ No silver labels found!")
        sys.exit(1)
        
    if not main_parquet.exists():
        print("❌ Main index parquet missing!")
        sys.exit(1)
        
    # Load Data
    silver_df = pd.read_parquet(silver_path)
    main_df = pd.read_parquet(main_parquet)
    
    print(f"📊 Silver Labels: {len(silver_df)}")
    print(f"📊 Main Index (Before): {len(main_df)}")
    
    # DEDUPLICATION & SCHEMA ALIGNMENT
    
    # 1. Prepare Silver Data to match Main Schema
    # Main schema: ['advisoryId', 'summary', 'platform', 'original_labels', 'labels_list', 'labels_count', 'source', 'reasoning', 'labels']
    
    silver_df['advisoryId'] = silver_df['bug_id']
    silver_df['labels_list'] = silver_df['labels'] # Ensure it's list
    silver_df['original_labels'] = silver_df['labels'].apply(lambda x: x if isinstance(x, list) else [])
    silver_df['labels_count'] = silver_df['labels'].apply(len)
    silver_df['reasoning'] = None # Silver labels don't have reasoning yet
    
    # Ensure columns exist
    for col in ['summary', 'platform', 'source']:
        if col not in silver_df.columns:
            silver_df[col] = ''
            
    # Select only matching columns
    cols_to_use = [c for c in main_df.columns if c in silver_df.columns]
    silver_ready = silver_df[cols_to_use].copy()
    
    # 2. Check for Duplicates (by advisoryId)
    existing_ids = set(main_df['advisoryId'].astype(str))
    silver_ids = silver_ready['advisoryId'].astype(str)
    
    new_mask = ~silver_ids.isin(existing_ids)
    new_rows = silver_ready[new_mask]
    
    duplicates = len(silver_ready) - len(new_rows)
    if duplicates > 0:
        print(f"⚠️  Found {duplicates} duplicates (already in index). Skipping them.")
    
    if len(new_rows) == 0:
        print("✅ No new unique rows to add. Loop is already closed!")
        return

    # 3. Merge
    print(f"📥 Adding {len(new_rows)} new rows...")
    combined_df = pd.concat([main_df, new_rows], ignore_index=True)
    combined_df.to_parquet(main_parquet)
    print(f"✅ Main Index (After): {len(combined_df)}")
    
    # 4. Update FAISS Index
    print("\n🧠 Updating FAISS Index...")
    import faiss
    import numpy as np
    from sentence_transformers import SentenceTransformer
    
    # Load model
    print("   Loading embedder...")
    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    
    # Compute embeddings for NEW rows only
    print(f"   Computing embeddings for {len(new_rows)} new items...")
    new_summaries = new_rows['summary'].fillna('').tolist()
    new_embeddings = model.encode(new_summaries, show_progress_bar=True)
    
    # Load output path
    index_path = PROJECT_ROOT / 'models' / 'faiss_index.bin'
    
    if index_path.exists():
        index = faiss.read_index(str(index_path))
        print(f"   Loaded existing index: {index.ntotal}")
    else:
        index = faiss.IndexFlatL2(384)
        print("   Created new index")
        
    # Add to index
    print("   Adding vectors...")
    index.add(new_embeddings.astype('float32'))
    
    # Save
    print(f"💾 Saving updated index ({index.ntotal} vectors)...")
    faiss.write_index(index, str(index_path))
    
    print("\n✅ Loop Closed Successfully! The model is now smarter.") 

if __name__ == "__main__":
    main()
