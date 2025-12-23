import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fewshot_inference import FewShotPSIRTLabeler
import pandas as pd

def main():
    print("🚀 Verifying Ingestion...")
    
    # Initialize labeler (will load new index)
    labeler = FewShotPSIRTLabeler()
    
    print(f"\n✅ Index Size: {labeler.index.ntotal}")
    print(f"✅ Data Size: {len(labeler.labeled_examples)}")
    
    # Check if reasoning column exists
    if 'reasoning' not in labeler.labeled_examples.columns:
        print("❌ 'reasoning' column MISSING from dataframe!")
        exit(1)
    else:
        print("✅ 'reasoning' column present")
        
    # Check retrieval with a query known to be in the new dataset
    query = "Cat9300X"
    print(f"\n🔍 Querying: '{query}'")
    
    examples, scores = labeler.retrieve_similar_examples(query, k=3)
    
    for i, ex in enumerate(examples):
        print(f"\n--- Result {i+1} ---")
        print(f"Summary: {ex['summary'][:100]}...")
        print(f"Reasoning: {ex.get('reasoning', 'N/A')}")
        
        if ex.get('reasoning'):
             print("✅ Reasoning found!")
        else:
             print("⚠️  No reasoning (might be old data)")

if __name__ == "__main__":
    main()
