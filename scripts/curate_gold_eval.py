import pandas as pd
import json
import os

# Config
INPUT_PATH = "models/labeled_examples_cleaned.parquet"
OUTPUT_PATH = "models/gold_standard_eval.jsonl"

# Label groups to focus on (Hard Negatives)
# Updated based on actual label distribution in labeled_examples_cleaned.parquet
TARGET_GROUPS = [
    # Security confusion: CoPP vs Control Plane Policy vs PACL/VACL
    ["SEC_CoPP", "SEC_CONTROL_PLANE_POLICY", "SEC_PACL_VACL"],
    # Management confusion: SSH/HTTP vs AAA vs SNMP
    ["MGMT_SSH_HTTP", "MGMT_AAA_TACACS_RADIUS", "MGMT_SNMP"],
    # Routing confusion: BGP vs OSPF vs EIGRP
    ["RTE_BGP", "RTE_OSPF", "RTE_EIGRP"],
    # System confusion: Boot/Upgrade vs Licensing
    ["SYS_Boot_Upgrade", "SYSTEM_LICENSE", "SYS_Licensing_Smart"]
]

def load_data(path):
    return pd.read_parquet(path)

def get_label(row):
    """Extracts label from row, handling potential list/string/numpy array formats."""
    import numpy as np
    # Assuming 'labels_list' is the column, or 'labels'
    val = row.get('labels_list', row.get('labels'))
    if val is None:
        return []
    # Handle numpy arrays
    if isinstance(val, np.ndarray):
        return list(val)
    if isinstance(val, str):
        # clean string representation of list
        val = val.replace("[", "").replace("]", "").replace("'", "").replace('"', "").strip()
        if "," in val:
            return [v.strip() for v in val.split(",")]
        return [val] if val else []
    elif isinstance(val, (list, tuple)):
        return list(val)
    return []

def main():
    print(f"Loading data from {INPUT_PATH}...")
    df = load_data(INPUT_PATH)
    print(f"Total rows: {len(df)}")
    
    selected_indices = set()
    rows_to_keep = []
    
    # 1. Target ambiguous groups
    for group in TARGET_GROUPS:
        print(f"Selecting for group: {group}")
        # Find rows that match ANY of these labels
        # We need to parse the label column efficiently
        
        candidates = []
        for idx, row in df.iterrows():
            if idx in selected_indices:
                continue
                
            labels = get_label(row)
            # Check if any label in this row matches our group
            if any(l in group for l in labels):
                candidates.append((idx, row))
                
        # Take up to 5 examples per label in the group to ensure coverage
        # Actually, let's just take 5 random ones for each label in the group
        for label in group:
            label_candidates = [c for c in candidates if label in get_label(c[1])]
            
            # Simple sampling
            take_n = 5
            to_take = label_candidates[:take_n] # Just take first N for reproducibility or shuffle
            
            for idx, row in to_take:
                if idx not in selected_indices:
                    rows_to_keep.append(row)
                    selected_indices.add(idx)

    print(f"Selected {len(rows_to_keep)} targeted examples.")
    
    # 2. Add some random baseline examples if we are under 50
    current_count = len(rows_to_keep)
    target_count = 50
    if current_count < target_count:
        needed = target_count - current_count
        print(f"Adding {needed} random baseline examples...")
        
        remaining = df[~df.index.isin(selected_indices)]
        if len(remaining) > needed:
            random_samples = remaining.sample(n=needed)
            for idx, row in random_samples.iterrows():
                rows_to_keep.append(row)
        else:
            print("Not enough remaining rows to fill target count.")
            for idx, row in remaining.iterrows():
                rows_to_keep.append(row)
                
    # 3. Save to JSONL
    print(f"Saving {len(rows_to_keep)} examples to {OUTPUT_PATH}...")
    
    with open(OUTPUT_PATH, 'w') as f:
        for row in rows_to_keep:
            # Convert row to dict and handle serialization
            d = row.to_dict()
            # clean up labels for the eval file
            d['gold_label'] = get_label(row)
            f.write(json.dumps(d, default=str) + "\n")
            
    print("Done.")

if __name__ == "__main__":
    main()
