import pandas as pd
import re

INPUT_FILE = "models/labeled_examples.parquet"
OUTPUT_FILE = "models/labeled_examples_cleaned.parquet"

def clean_data():
    print(f"Loading {INPUT_FILE}...")
    try:
        df = pd.read_parquet(INPUT_FILE)
    except FileNotFoundError:
        print(f"Error: {INPUT_FILE} not found.")
        return

    initial_count = len(df)
    print(f"Initial row count: {initial_count}")
    
    # 1. Platform Filtering
    # Use 'platform' column if available (it is)
    if 'platform' in df.columns:
        print("Filtering by 'platform' column...")
        
        # Define bad keywords in Platform or ALL TEXT (Summary)
        # Note: 'platform' column might be cleaner, but let's be safe.
        bad_keywords = [
            'Identity Services Engine', 'ISE',
            'Adaptive Security Appliance', 'ASA',
            'Firepower', 'FTD', 'FMC',
            'Data Center Network Manager', 'DCNM',
            'NEXUS', 'NX-OS', 'NDFC',
            'Aironet',
            'NFVIS',
            'APIC',
            'UCS',
            'ClamAV',
            'Webex'
        ]
        
        # Check 'platform' column AND 'summary'
        # Normalize to string first
        mask_drop_platform = df['platform'].astype(str).str.contains('|'.join(bad_keywords), case=False, na=False)
        mask_drop_summary = df['summary'].astype(str).str.contains('|'.join(bad_keywords), case=False, na=False)
        
        # Being aggressive: If summary mentions ISE/ASA prominently, drop it? 
        # But summary might say "IOS-XE affecting ISE clients". 
        # Ideally rely on 'platform' if it's populated. 
        # Column list shows 'platform'. Let's trust it as primary signals.
        
        # Let's inspect unique platforms if we could, but blindly:
        # If 'platform' explicitly says 'Cisco Adaptive Security Appliance', kill it.
        
    # Identfy the non-IOS-XE rows using the masks
    # We used ~mask_drop_platform and ~mask_drop_summary to keep clean data.
    # The dropped data is the inverse.
    # Note: mask_drop_platform is for platform column, mask_drop_summary for summary.
    # We want to catch anything that triggered a drop.
    
    mask_dropped = mask_drop_platform | mask_drop_summary
    df_others = df[mask_dropped].copy()
    
    print(f"Saving {len(df_others)} non-IOS-XE examples to models/labeled_examples_other_platforms.parquet...")
    df_others.to_parquet("models/labeled_examples_other_platforms.parquet")
    
    df_clean = df[~mask_dropped].copy()
    dropped_count = initial_count - len(df_clean)
    print(f"Kept {len(df_clean)} IOS-XE examples.")
    
    # 2. Fix mDNS Contamination (Only on IOS-XE set)
    print("Fixing mDNS Contamination in IOS-XE set...")
    
    def remap_mdns_list(row):
        text = str(row['summary']).lower()
        if 'mdns' in text and ('wireless' in text or 'wlc' in text or 'gateway' in text):
             return ['WIRELESS_MDNS']
        return row['labels_list']

    if 'labels_list' in df_clean.columns:
        df_clean['labels_list'] = df_clean.apply(remap_mdns_list, axis=1)
        df_clean['labels'] = df_clean['labels_list'].apply(lambda l: ','.join(l) if isinstance(l, list) else str(l))
    
    # 3. Deduplication (Only on IOS-XE set)
    print("Deduplicating IOS-XE set...")
    if 'advisoryId' in df_clean.columns:
        df_final = df_clean.drop_duplicates(subset=['advisoryId'])
    else:
        df_final = df_clean.drop_duplicates(subset=['summary'])
        
    final_count = len(df_final)
    print(f"Final Clean Deduplicated count: {final_count}")
    print(f"Removed {len(df_clean) - final_count} duplicates.")
    
    print(f"Saving clean IOS-XE data to {OUTPUT_FILE}...")
    df_final.to_parquet(OUTPUT_FILE)
    print("Cleanup & Segregation Complete.")

if __name__ == "__main__":
    clean_data()
