import pandas as pd
import faiss
import json
import torch
from sentence_transformers import SentenceTransformer
import sys

def verify_synthetic_impact():
    print("🚀 Verifying Synthetic Data Impact on Retrieval System")
    print("====================================================")

    # 1. Load Resources (Skip LLM)
    print("📚 Loading FAISS Index and Embedder...")
    try:
        index = faiss.read_index('models/faiss_index.bin')
        df = pd.read_parquet('models/labeled_examples.parquet')
        
        with open('models/embedder_info.json', 'r') as f:
            info = json.load(f)
            model_name = info['model_name']
            
        embedder = SentenceTransformer(model_name)
        print(f"✅ Resources loaded. Index contains {index.ntotal} vectors.")
    except Exception as e:
        print(f"❌ Failed to load resources: {e}")
        sys.exit(1)

    # 2. Define Test Scenarios
    # Queries targeted at the previously missing labels
    test_cases = [
        {
            "label": "FHRP_GLBP",
            "query": "GLBP average gateway election vulnerability allow attacker to become active gateway",
            "expected_id_prefix": "SYNTH-FHRP_GLBP"
        },
        {
            "label": "VPN_IPSec",
            "query": "IPsec VPN denial of service via malformed ESP packets",
            "expected_id_prefix": "SYNTH-VPN_IPSec"
        },
        {
            "label": "SEC_DHCP_SNOOP",
            "query": "DHCP snooping bypass using crafted option 82 packets",
            "expected_id_prefix": "SYNTH-SEC_DHCP_SNOOP"
        },
        {
            "label": "FW_Connection_Policing_Limits",
            "query": "ASA connection limit bypass using embryonic connection flood",
            "expected_id_prefix": "SYNTH-FW_Connection_Policing_Limits"
        },
        {
            "label": "RTE_STATIC", 
            "query": "Static route manipulation causing traffic blackhole",
            "expected_id_prefix": "SYNTH-RTE_STATIC"
        },
        {
            "label": "MPLS_TE",
            "query": "MPLS Traffic Engineering tunnel setup failure causing DoS",
            "expected_id_prefix": "SYNTH-MPLS_TE"
        },
        {
            "label": "QOS_POLICING",
            "query": "QoS policing rate limit bypass allow traffic exceeding conform rate",
            "expected_id_prefix": "SYNTH-QOS_POLICING"
        },
         {
            "label": "NAT_PolicyNAT",
            "query": "Policy NAT rule bypass allowing unauthorized traffic flow",
            "expected_id_prefix": "SYNTH-NAT_PolicyNAT"
        }
    ]

    print("\n🧪 Running 8 Targeted Test Cases...")
    print(f"{'Target Label':<30} | {'Found ID':<25} | {'Status':<10}")
    print("-" * 75)

    passed = 0
    
    # 3. specific Retrieval logic
    for test in test_cases:
        query_embedding = embedder.encode([test['query']])
        
        # Search Top 5
        D, I = index.search(query_embedding, 5)
        
        # Check results
        found = False
        top_match_id = "None"
        
        # iterate through top 5 to find relevant match
        for idx in I[0]:
            if idx < 0: continue
            record = df.iloc[idx]
            advisory_id = record['advisoryId']
            
            # Check if we hit the synthetic example we generated for this label
            if advisory_id.startswith(test['expected_id_prefix']):
                found = True
                top_match_id = advisory_id
                break
                
        status = "✅ PASS" if found else "❌ FAIL"
        if found: passed += 1
        
        print(f"{test['label']:<30} | {top_match_id:<25} | {status:<10}")

    print("-" * 75)
    print(f"\n📈 Results: {passed}/{len(test_cases)} Passed")
    
    if passed == len(test_cases):
        print("🎉 SUCCESS: Synthetic data is effectively discoverable by the retrieval engine.")
    else:
        print("⚠️  WARNING: Some synthetic examples were not top-ranked.")

if __name__ == "__main__":
    verify_synthetic_impact()
