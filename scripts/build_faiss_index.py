#!/usr/bin/env python3
"""
Build FAISS Index from Golden Dataset (Standardized Identity)
=============================================================

This script consumes the `golden_dataset.csv` (produced by standardize_labels.py)
and updates the RAG knowledge base used by the Few-Shot Labeler.

Outputs:
- models/faiss_index.bin: Vector store
- models/labeled_examples.parquet: Metadata store
- models/embedder_info.json: Config
"""

import os
import json
import logging
import argparse
import ast
import pandas as pd
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def parse_labels(labels_str):
    """Safely parse stringified list of labels."""
    try:
        # It might already be a list if pandas inferred it, or a string
        if isinstance(labels_str, list):
            return labels_str
        return ast.literal_eval(labels_str)
    except:
        return []

def main():
    parser = argparse.ArgumentParser(description='Build FAISS index from Golden Dataset')
    parser.add_argument('--input', type=str, default='golden_dataset.csv', help='Path to golden dataset CSV')
    parser.add_argument('--model', type=str, default='sentence-transformers/all-MiniLM-L6-v2', help='HuggingFace model name for embeddings')
    args = parser.parse_args()

    if not os.path.exists(args.input):
        logger.error(f"Input file not found: {args.input}")
        return

    # 1. Load Data
    logger.info(f"📊 Loading dataset: {args.input}")
    df = pd.read_csv(args.input)
    logger.info(f"   Loaded {len(df)} records")

    # Ensure labels are parsed correctly
    # The 'labels_list' column should exist from standardization script
    if 'labels_list' not in df.columns:
        logger.error("Column 'labels_list' missing. Is this the output of standardize_labels.py?")
        return

    df['labels_list'] = df['labels_list'].apply(parse_labels)
    
    # Filter out empty label sets just in case
    df = df[df['labels_list'].apply(len) > 0].reset_index(drop=True)
    logger.info(f"   Valid records after label check: {len(df)}")

    # 2. Embed Summaries
    logger.info(f"🤖 Loading embedder: {args.model}")
    embedder = SentenceTransformer(args.model)

    logger.info("⚡ Generating embeddings...")
    # Fill NaN summaries with empty string
    summ_texts = df['summary'].fillna('').tolist()
    embeddings = embedder.encode(summ_texts, show_progress_bar=True, batch_size=32)
    
    dimension = embeddings.shape[1]
    logger.info(f"   Embedding dimension: {dimension}")

    # 3. Build Index
    logger.info("🔍 Building FAISS index...")
    index = faiss.IndexFlatL2(dimension)
    index.add(embeddings.astype('float32'))
    logger.info(f"   Index built with {index.ntotal} vectors")

    # 4. Save Artifacts
    os.makedirs('models', exist_ok=True)
    
    index_path = 'models/faiss_index.bin'
    faiss.write_index(index, index_path)
    logger.info(f"💾 Saved Index: {index_path}")
    
    parquet_path = 'models/labeled_examples.parquet'
    df.to_parquet(parquet_path)
    logger.info(f"💾 Saved Metadata: {parquet_path}")
    
    config_path = 'models/embedder_info.json'
    with open(config_path, 'w') as f:
        json.dump({
            'model_name': args.model,
            'dimension': dimension,
            'num_examples': len(df),
            'source_file': args.input
        }, f, indent=2)
    logger.info(f"💾 Saved Config: {config_path}")

    # 5. Test Retrieval
    logger.info("\n🧪 Testing Retrieval (Sanity Check)...")
    test_query = "BGP session dropping on IOS-XR router"
    query_vec = embedder.encode([test_query]).astype('float32')
    D, I = index.search(query_vec, k=1)
    
    logger.info(f"Query: '{test_query}'")
    try:
        match_idx = I[0][0]
        match_row = df.iloc[match_idx]
        logger.info(f"Match: [{match_row['platform']}] {match_row['summary'][:60]}...")
        logger.info(f"Labels: {match_row['labels_list']}")
    except Exception as e:
        logger.error(f"Retrieval test failed: {e}")

    logger.info("\n✅ Index Refresh Complete. The Few-Shot Labeler is now updated.")

if __name__ == "__main__":
    main()
