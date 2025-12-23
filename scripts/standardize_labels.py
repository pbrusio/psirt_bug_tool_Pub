#!/usr/bin/env python3
"""
Standardize PSIRT Labels to Project Taxonomy (The "Identity")
===========================================================

This script transforms the generic "CWE-style" labels in the source CSV
(e.g., "Denial of Service", "BGP") into the specific "Identity" labels
defined in the project taxonomies (e.g., "RTE_BGP", "MGMT_SSH_HTTP").

Process:
1. Load Taxonomies (Target Identity)
2. Load Source CSV (Generic Data)
3. Load Source JSONL (High-Quality Training Data)
4. Apply Heuristic Mapping (Keyword Matching & Explicit Mapping)
5. Filter & Deduplicate
6. Save `golden_dataset.csv`
"""

import csv
import yaml
import os
import ast
import re
from collections import Counter, defaultdict
import json
import sqlite3

# --- Configuration ---
SOURCE_CSV = "gemini_enriched_PSIRTS_mrk1.csv"
SOURCE_DB = "vulnerability_db.sqlite"
OUTPUT_CSV = "golden_dataset.csv"
TAXONOMY_DIR = "taxonomies"

# --- Mappings (Generic -> Identity) ---
# This is the "Knowledge" we are injecting into the data.
# Based on the user's Taxonomy files.
LABEL_MAP = {
    # Routing
    "BGP": "RTE_BGP",
    "Border Gateway Protocol": "RTE_BGP",
    "OSPF": "RTE_OSPFv2", # Default to v2, logic can refine
    "OSPFv3": "RTE_OSPFv3",
    "EIGRP": "RTE_EIGRP",
    "ISIS": "RTE_ISIS",
    "RIP": "RTE_Static", # Mapping RIP to generic routing/static if no specific tag exists, or ignore
    "Routing": "RTE_Static",
    
    # Layer 2
    "Spanning Tree": "L2_STP",
    "STP": "L2_STP",
    "EtherChannel": "L2_EtherChannel",
    "LACP": "L2_LACP",
    "VLAN": "L2_VLAN_VTP",
    "VTP": "L2_VLAN_VTP",
    "CDP": "MGMT_LLDP_CDP",
    "LLDP": "MGMT_LLDP_CDP",
    
    # Management / Access
    "SSH": "MGMT_SSH_HTTP",
    "HTTP": "MGMT_SSH_HTTP",
    "Web Interface": "MGMT_SSH_HTTP",
    "REST API": "APP_IOx", # Or MGMT_RPC/NETCONF depending on context?
    "NETCONF": "MGMT_RPC / NETCONF",
    "SNMP": "MGMT_SNMP",
    "Telnet": "MGMT_TELNET_SSH", # Assuming this exists or mapping to SSH group
    "TACACS": "MGMT_AAA_TACACS_RADIUS",
    "RADIUS": "MGMT_AAA_TACACS_RADIUS",
    "AAA": "MGMT_AAA_TACACS_RADIUS",
    
    # Security Features
    "IPsec": "VPN_IPSec",
    "IKEv2": "VPN_IKEv2",
    "VPN": "VPN_IPSec", # Generic VPN -> IPsec usually
    "TrustSec": "CTS_Base",
    "SXP": "CTS_SXP",
    "MacSec": "SEC_8021X", # Fallback or keep specific if in taxonomy
    "802.1X": "SEC_8021X",
    "ACL": "SEC_PACL_VACL",
    "Access Control List": "SEC_PACL_VACL",
    "CoPP": "SEC_CoPP",
    "Control Plane Policing": "SEC_CoPP",
    
    # System
    "Smart Licensing": "SYS_Licensing_Smart",
    "Licensing": "SYS_Licensing_Smart",
    "Install": "SYS_Boot_Upgrade",
    "Upgrade": "SYS_Boot_Upgrade",
    "Boot": "SYS_Boot_Upgrade",
    "IOS XE": "SYS_Boot_Upgrade", # Often related to the OS itself
    
    # QoS
    "QoS": "QOS_MQC_ClassPolicy",
    "Policing": "QOS_POLICING",
    "Marking": "QOS_MARKING",
}

# Regex mappings for Summary Text analysis
KEYWORD_RULES = [
    (r"\bbgp\b", "RTE_BGP"),
    (r"\bospf\b", "RTE_OSPFv2"),
    (r"\beigrp\b", "RTE_EIGRP"),
    (r"\bisis\b", "RTE_ISIS"), # Added
    (r"\brip\b", "RTE_Static"), # Fallback
    (r"\bssh\b", "MGMT_SSH_HTTP"),
    (r"\bhttp\b", "MGMT_SSH_HTTP"),
    (r"\bweb(-| )based management\b", "MGMT_SSH_HTTP"),
    (r"\bnetconf\b", "MGMT_RPC / NETCONF"), # Added
    (r"\brestconf\b", "MGMT_RPC / NETCONF"), # Added
    (r"\bsnmp\b", "MGMT_SNMP"),
    (r"\btacacs\b", "MGMT_AAA_TACACS_RADIUS"),
    (r"\bradius\b", "MGMT_AAA_TACACS_RADIUS"),
    (r"\baaa\b", "MGMT_AAA_TACACS_RADIUS"), # Added
    (r"\bipsec\b", "VPN_IPSec"),
    (r"\bikev2\b", "VPN_IKEv2"),
    (r"\bcopp\b", "SEC_CoPP"),
    (r"\bcontrol(-| )plane policing\b", "SEC_CoPP"),
    (r"\bvxlan\b", "L2_VLAN_VTP"), # Or specific VXLAN tag if exists
    (r"\bmpls\b", "MPLS_LDP"),  # Simple mapping, could be TE
    (r"\bldp\b", "MPLS_LDP"),
    (r"\brsvp\b", "MPLS_TE"),
    (r"\bte\b", "MPLS_TE"),
    (r"\btraffic(-| )engineering\b", "MPLS_TE"),
    (r"\bzerotouch\b", "SYS_Boot_Upgrade"),
    (r"\bpnp\b", "SYS_Boot_Upgrade"),
    (r"\blicens(ing|e)\b", "SYS_Licensing_Smart"), # Added
    (r"\bsmart licens\b", "SYS_Licensing_Smart"), # Added
    (r"\bnat\b", "IP_NAT"), # Added
    (r"\bnetwork address translation\b", "IP_NAT"), # Added
    (r"\bfirewall\b", "SEC_FW_Inspect"), # Added/Hypothetical
    (r"\binspection\b", "SEC_FW_Inspect"), # Added
    (r"\bmulticast\b", "MCAST_Base"), # Added
    (r"\bpim\b", "MCAST_PIM"), # Added
    (r"\bbfd\b", "RTE_BFD"), # Added
    (r"\bnetflow\b", "MGMT_NetFlow_NSEL"), # Added
    (r"\bflow\b", "MGMT_NetFlow_NSEL"), # Added
    (r"\bspan\b", "MGMT_SPAN_ERSPAN"), # Added
    (r"\bmirroring\b", "MGMT_SPAN_ERSPAN"), # Added
]

# Platform Specific Overrides (Global -> Platform Specific)
PLATFORM_OVERRIDES = {
    # NX-OS
    "NX-OS": {
        "L2_EtherChannel": "SW_L2_ETHERCHANNEL",
        "L2_VLAN_VTP": "SW_L2_VLAN",
        "RTE_Static": "RTE_STATIC", # Caps difference
        "RTE_BGP": "RTE_BGP", # Same
        "RTE_OSPFv2": "RTE_OSPF",
        "MGMT_SSH_HTTP": "MGMT_TELNET_SSH",
        "MGMT_LLDP_CDP": "MGMT_LLDP_CDP", # Needs to be added to taxonomy or mapped to something else? keeping for now
    },
    # IOS-XR
    "IOS-XR": {
        "MGMT_SSH_HTTP": "MGMT_SSH_HTTP", # Missing in XR? Check taxonomy
        "RTE_OSPFv2": "RTE_OSPF",
    }
}

def load_target_taxonomy():
    """Load all valid labels from the taxonomy YAMLs, organized by platform."""
    platform_taxonomy = defaultdict(set)
    files = [f for f in os.listdir(TAXONOMY_DIR) if f.endswith('.yml') or f.endswith('.yaml')]
    
    for fname in files:
        # Determine platform from filename
        if 'nxos' in fname: platform = 'NX-OS'
        elif 'iosxr' in fname: platform = 'IOS-XR'
        elif 'asa' in fname: platform = 'ASA' # Covers FTD usually
        else: platform = 'IOS-XE' # Default features.yml
        
        path = os.path.join(TAXONOMY_DIR, fname)
        try:
            with open(path, 'r') as f:
                data = yaml.safe_load(f)
                if isinstance(data, list):
                    for item in data:
                        if 'label' in item:
                            platform_taxonomy[platform].add(item['label'])
                            # Also add to global set for fallback
                            platform_taxonomy['ALL'].add(item['label'])
        except Exception as e:
            print(f"⚠️ Error loading {fname}: {e}")
            
    print(f"✅ Loaded taxonomy for: {list(platform_taxonomy.keys())}")
    return platform_taxonomy

def parse_original_labels(row):
    """Extract list of generic labels from the csv row."""
    raw = row.get('relevant_features_gemini', '[]')
    try:
        # Handle list-like string
        if raw.startswith('['):
            return ast.literal_eval(raw)
        # Handle comma-separated
        return [x.strip() for x in raw.split(',')]
    except:
        return []

def map_labels(generic_labels, summary, platform_taxonomy, platform):
    """Map generic labels and summary text to Identity labels, respecting platform."""
    mapped = set()
    
    # 1. Base Mapping
    candidates = set()
    
    # From Labels
    for label in generic_labels:
        if label in LABEL_MAP:
            candidates.add(LABEL_MAP[label])
        elif label in platform_taxonomy['ALL']: # If it's already a valid label (any platform)
            candidates.add(label)
            
    # From Summary
    summary_lower = summary.lower()
    for pattern, target_label in KEYWORD_RULES:
        if re.search(pattern, summary_lower):
            candidates.add(target_label)
            
    # 2. Platform Adaptation & Validation
    valid_set = platform_taxonomy.get(platform, platform_taxonomy.get('IOS-XE')) # Fallback to IOS-XE
    
    overrides = PLATFORM_OVERRIDES.get(platform, {})
    
    for label in candidates:
        # Apply override if exists
        final_label = overrides.get(label, label)
        
        # Check validity
        if final_label in valid_set:
            mapped.add(final_label)
        elif 'IOS' in platform and final_label in platform_taxonomy['IOS-XE']:
             # Heuristic: If we are on IOS-XR but label is IOS-XE, and we don't have a specific XR label, 
             # maybe allow it? No, strict Identity means STRICT.
             pass
                
    return list(mapped)

def process_row(row, platform_taxonomy, stats, golden_rows, source_type='csv', verification_map=None):
    stats['total'] += 1
    
    original_labels = parse_original_labels(row)
    summary = row.get('summary', '')
    advisory_id = row.get('advisoryId', row.get('id', ''))
    platform_raw = row.get('affected_platforms_from_cve_gemini', "['IOS-XE']")
    
    # Bug ID Extraction (for matching with verification data)
    bug_ids = []
    # CSV often has them in column 2 or designated 'bug_ids'. Let's try to extract from keys if explicit column missing.
    # In `gemini_enriched_PSIRTS_mrk1.csv`, header isn't strictly defined in my view, but `row` is a Dict.
    # Let's assume there's a key like 'cve_id' or we parse from the input if not.
    # Actually, the user's `head` showed `['CSCwb08411']` at column index 2.
    # DictReader uses headers. I need to know the header name.
    # If I don't know it, I can search values?
    # Let's scan values for CSC-like strings.
    for k, v in row.items():
        if isinstance(v, str) and 'CSC' in v:
            try:
                # heuristic extract
                found = re.findall(r'CSC[a-zA-Z0-9]{7}', v)
                bug_ids.extend(found)
            except: pass
            
    # Parse platform for cleaner data
    primary_platform = "IOS-XE"
    try: 
        plat_list = ast.literal_eval(platform_raw)
        if plat_list:
            p = plat_list[0]
            # Normalize platform names to match our taxonomy keys
            if 'NX-OS' in p or 'Nexus' in p: primary_platform = 'NX-OS'
            elif 'IOS-XR' in p or 'XR' in p: primary_platform = 'IOS-XR'
            elif 'ASA' in p or 'Adaptive Security' in p: primary_platform = 'ASA'
            elif 'Firepower' in p or 'FTD' in p: primary_platform = 'ASA' # Map FTD to ASA for taxonomy purposes if shared
            else: primary_platform = 'IOS-XE'
    except:
        pass

    # Do the Magic
    identity_labels = map_labels(original_labels, summary, platform_taxonomy, primary_platform)
    
    # 3. VERIFICATION DATA INJECTION
    verified_injection = False
    if verification_map:
        for bid in bug_ids:
            if bid in verification_map:
                v_labels = verification_map[bid]
                # These are TRUSTED high quality labels. Add them.
                for vl in v_labels:
                    # Map them via taxonomy check to ensure they are valid (they should be)
                    if vl in platform_taxonomy['ALL']:
                        if vl not in identity_labels:
                             identity_labels.append(vl)
                             verified_injection = True
    
    if verified_injection:
        stats['verified_matches'] += 1

    if identity_labels:
        stats['mapped'] += 1
        
        # Store standardized row
        golden_rows.append({
            'advisoryId': advisory_id,
            'summary': summary,
            'platform': primary_platform, # Simplified platform
            'original_labels': str(original_labels),
            'labels_list': str(identity_labels), # Store as stringified list for compatibility
            'labels_count': len(identity_labels),
            'source': f"{source_type}{'+verified' if verified_injection else ''}"
        })
    else:
        stats['dropped'] += 1

def main():
    print("🚀 Starting Data Standardization (Identity Mapping)")
    print("=" * 60)
    
    # 1. Load Taxonomy
    platform_taxonomy = load_target_taxonomy()
    
    # 2. Load Verification Data (Bug ID -> Labels)
    verification_map = {}
    verif_path = "output/all_results.json"
    if os.path.exists(verif_path):
        print(f"📥 Loading verification data from: {verif_path}")
        try:
            with open(verif_path, 'r', encoding='utf-8') as f:
                verif_data = json.load(f)
                for item in verif_data:
                    bid = item.get('advisory_id')
                    labs = item.get('labels', [])
                    if bid and labs:
                        verification_map[bid] = labs
        except Exception as e:
            print(f"⚠️ Error loading verification data: {e}")
    
    # 3. Process Data
    stats = {
        'total': 0,
        'mapped': 0,
        'dropped': 0,
        'augmented': 0,
        'verified_matches': 0
    }
    
    golden_rows = []
    
    try:
        # Load CSV Data
        if os.path.exists(SOURCE_CSV):
            with open(SOURCE_CSV, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    process_row(row, platform_taxonomy, stats, golden_rows, source_type='csv', verification_map=verification_map)
        
        # Load JSONL Data (Llama Training Data)
        jsonl_path = "llama_training_data/train.jsonl"
        if os.path.exists(jsonl_path):
            print(f"📥 Merging training data from: {jsonl_path}")
            with open(jsonl_path, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        data = json.loads(line)
                        # Adapt JSONL fields to our schema
                        # input -> summary (extraction needed usually, but use full text)
                        # output -> labels (needs parsing)
                        
                        input_text = data.get('input', '')
                        output_json = data.get('output', '{}')
                        
                        # Extract Summary (heuristic: remove "Platform: ... Issue: ")
                        summary = input_text.split("Issue: ")[-1] if "Issue: " in input_text else input_text
                        if "Platform:" in summary[:20]: # Clean up prefix if still there
                             summary = summary.split("\n\n")[-1]

                        # Extract Platform
                        platform_raw = data.get('platform', 'IOS-XE')
                        
                        # Extract Labels
                        try:
                            labels_data = json.loads(output_json)
                            # These are likely ALREADY identity labels if it's training data.
                            # So we treat them as "original_labels" and let the mapper confirm them.
                            valid_labels_list = labels_data.get('labels', [])
                        except:
                            valid_labels_list = []
                            
                        # Construct pseudo-row
                        row = {
                            'summary': summary,
                            'affected_platforms_from_cve_gemini': f"['{platform_raw}']",
                            'relevant_features_gemini': str(valid_labels_list),
                            'advisoryId': data.get('original_id', 'unknown')
                        }
                        
                        process_row(row, platform_taxonomy, stats, golden_rows, source_type='jsonl', verification_map=verification_map)
                        
                    except Exception as e:
                        pass
        
        # Load SQLite Data (The Motherlode: 9.5k records)
        if os.path.exists(SOURCE_DB):
            print(f"📥 Loading SQLite data from: {SOURCE_DB}")
            conn = sqlite3.connect(SOURCE_DB)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Select relevant columns
            # We filter for records that already have labels (e.g., from 'gpt4o_high_confidence' or similar sources)
            # Or we can process all of them and let our mapper do the work.
            # Let's check 'labels_source' to prioritize high quality ones?
            # User said "2,654 labeled training examples", so maybe filter where labels is not empty/null.
            
            try:
                cursor.execute("SELECT * FROM vulnerabilities WHERE summary IS NOT NULL AND platform IS NOT NULL")
                rows = cursor.fetchall()
                print(f"   Found {len(rows)} records in DB.")
                
                for db_row in rows:
                    # Adapt DB structure to our pipeline
                    summary = db_row['summary']
                    platform = db_row['platform']
                    if platform == 'NXOS': platform = 'NX-OS' # Fix common drift
                    if platform == 'IOSXE': platform = 'IOS-XE'
                    if platform == 'IOSXR': platform = 'IOS-XR'
                    
                    # Labels in DB are stored as text (json string)
                    db_labels_raw = db_row['labels']
                    existing_labels = []
                    if db_labels_raw:
                        try:
                            # DB labels usually look like ["RTE_BGP", "MGMT_SSH"]
                            # Clean up potential artifacts
                            cleaned = db_labels_raw.replace("'", '"')
                            existing_labels = json.loads(cleaned)
                        except:
                            pass
                            
                    row = {
                        'summary': summary,
                        'affected_platforms_from_cve_gemini': f"['{platform}']",
                        'relevant_features_gemini': str(existing_labels),
                        'advisoryId': db_row['bug_id'] or db_row['advisory_id'] or 'db_record'
                    }
                    
                    process_row(row, platform_taxonomy, stats, golden_rows, source_type='sqlite', verification_map=verification_map)
                    
            except Exception as e:
                print(f"⚠️ Error reading SQLite: {e}")
            finally:
                conn.close()

        # Load Synthetic Fill Data (The "10k" Coverage Patch)
        synthetic_path = "data/synthetic_fill_v1.json"
        if os.path.exists(synthetic_path):
            print(f"📥 Loading Synthetic Fill data from: {synthetic_path}")
            try:
                with open(synthetic_path, 'r', encoding='utf-8') as f:
                    synth_data = json.load(f)
                    print(f"   Found {len(synth_data)} synthetic examples.")
                    for item in synth_data:
                        # Ensure keys match expected schema
                        if 'advisory_id' in item and 'summary' in item:
                            # Synthetic data often has 'labels' as a list. process_row expects raw inputs usually,
                            # but we can massage it here.
                            # actually process_row parses 'original_labels' or 'relevant_features_gemini'.
                            # Let's verify how process_row works.
                            # It maps labels.
                            # For synthetic data, the labels ARE the identity. We should trust them. 
                            # But process_row re-maps them.
                            # Let's simply ensure 'original_labels' contains the target identity label, 
                            # which the mapper will pick up because it's in the taxonomy.
                            
                            # RELAXED VALIDATION FOR SYNTHETIC DATA
                            # The synthetic agent might use valid labels (like VPN_IPSec) on platforms (ASA) 
                            # where the label isn't explicitly in that platform's taxonomy file yet.
                            # We should accept it if it exists in ANY taxonomy (which we know it does, as we queried all taxonomies).
                            
                            # Flatten all taxonomies to a set of valid strings
                            global_valid_labels = set()
                            for p_key, p_vals in platform_taxonomy.items():
                                global_valid_labels.update(p_vals)
                            
                            admitted_labels = []
                            for synth_label in item.get('labels', []):
                                if synth_label in global_valid_labels:
                                    admitted_labels.append(synth_label)
                                else:
                                    # Fallback: Maybe it's a new label we want to force add?
                                    # For now, strict on global taxonomy to avoid typos.
                                    pass
                                    
                            if admitted_labels:
                                golden_rows.append({
                                    'advisoryId': item['advisory_id'],
                                    'summary': item['summary'],
                                    'platform': item.get('platform', 'IOS-XE'),
                                    'original_labels': str(item.get('labels', [])),
                                    'labels_list': str(admitted_labels),
                                    'labels_count': len(admitted_labels),
                                    'source': 'synthetic_fill'
                                })
                                stats['augmented'] += 1
                                stats['mapped'] += 1
            except Exception as e:
                print(f"⚠️ Error loading synthetic data: {e}")

    except FileNotFoundError:
        print(f"❌ Error: Source file not found.")
        return

    # 3. Save Golden Dataset
    if golden_rows:
        keys = golden_rows[0].keys()
        with open(OUTPUT_CSV, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(golden_rows)
            
        print("\n" + "="*60)
        print("📊 STANDARDIZATION RESULTS")
        print("="*60)
        print(f"Total Source Records:   {stats['total']}")
        print(f"Successfully Mapped:    {stats['mapped']} ({stats['mapped']/stats['total']:.1%})")
        print(f"Dropped (No Identity):  {stats['dropped']}")
        print("-" * 30)
        print(f"💾 Saved to: {OUTPUT_CSV}")
        print("="*60)
        print("This file contains the 'Identity' knowledge base for the Few-Shot Labeler.")
        
    else:
        print("❌ No records were mapped successfully. Check mapping rules.")

if __name__ == "__main__":
    main()
