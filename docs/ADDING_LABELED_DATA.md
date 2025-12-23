# Adding Labeled Bugs & PSIRTs Guide

**Version:** 4.3 | **Date:** December 21, 2025

This guide explains how to add new labeled vulnerabilities to CVE_EVAL_V2's knowledge base.

---

## Overview

The system uses three data stores that must stay synchronized:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DATA ARCHITECTURE                                    │
└─────────────────────────────────────────────────────────────────────────────┘

  1. vulnerability_db.sqlite     Primary database (9,705 records)
           │                     - bug_id, advisory_id, summary, platform, labels
           │
           ▼
  2. models/labeled_examples.parquet    Training/RAG data (7,065 examples)
           │                            - Used for few-shot retrieval
           │
           ▼
  3. models/faiss_index.bin      Vector similarity search
                                 - Embeddings of all labeled examples
```

**Key Insight:** New data flows through multiple stages before it's "live":
1. **Fetch** - Raw PSIRTs/Bugs from Cisco APIs
2. **Label** - Apply taxonomy labels (manual or AI-assisted)
3. **Standardize** - Map to canonical label names
4. **Ingest** - Add to database + rebuild indexes

---

## Quick Reference: Which Script Does What

| Task | Script | Input | Output |
|------|--------|-------|--------|
| Fetch new PSIRTs/Bugs | `cisco_vuln_fetcher.py` | Cisco API credentials | `vuln_data.json` |
| Label with GPT-4o | `synthesize_reasoning_openai.py` | Unlabeled JSONL | Labeled JSONL |
| Label with Gemini | `synthesize_reasoning_gemini.py` | Unlabeled JSONL | Labeled JSONL |
| Standardize labels | `standardize_labels.py` | Various sources | `golden_dataset.csv` |
| Rebuild FAISS index | `build_faiss_index.py` | `golden_dataset.csv` | `faiss_index.bin` + parquet |
| Ingest frontier labels | `ingest_frontier_labels.py` | JSON files | Updates index + parquet |

---

## Method 1: Fetch & Label New Data (Full Pipeline)

Use this when you want to pull fresh vulnerabilities from Cisco and label them.

### Step 1: Fetch New Vulnerabilities

```bash
cd cve_EVAL_V2
source venv/bin/activate

# Set Cisco API credentials
export CISCO_CLIENT_ID="your-client-id"
export CISCO_CLIENT_SECRET="your-client-secret"

# Fetch PSIRTs from last 30 days (with dedup against existing DB)
python scripts/cisco_vuln_fetcher.py \
    --mode all \
    --days 30 \
    --dedup \
    --db vulnerability_db.sqlite \
    --jsonl \
    -o data/new_vulns.jsonl

# Output shows:
#   FINAL OUTPUT
#   Items to export: 47
#   PSIRTs: 12
#   Bugs: 35
#   Needs labeling: 47
```

### Step 2: Label with AI (Choose One)

**Option A: OpenAI GPT-4o** (recommended for quality)
```bash
export OPENAI_API_KEY="sk-..."

python scripts/synthesize_reasoning_openai.py \
    --input data/new_vulns.jsonl \
    --output data/new_vulns_labeled.jsonl \
    --model gpt-4o
```

**Option B: Google Gemini** (cost-effective alternative)
```bash
export GOOGLE_API_KEY="..."

python scripts/synthesize_reasoning_gemini.py \
    --input data/new_vulns.jsonl \
    --output data/new_vulns_labeled.jsonl
```

**Option C: Local LLM** (air-gapped environments)
```bash
# Uses Foundation-Sec-8B with LoRA adapter
python scripts/synthesize_reasoning_cuda.py \
    --input data/new_vulns.jsonl \
    --output data/new_vulns_labeled.jsonl
```

### Step 3: Standardize Labels

The labeling step produces raw labels that may not exactly match your taxonomy. Standardize them:

```bash
# Copy labeled data to expected location
cp data/new_vulns_labeled.jsonl llama_training_data/train.jsonl

# Run standardization (pulls from multiple sources)
python scripts/standardize_labels.py

# Output: golden_dataset.csv
```

### Step 4: Rebuild Indexes

```bash
# Rebuild FAISS index from golden dataset
python scripts/build_faiss_index.py --input golden_dataset.csv

# Outputs:
#   models/faiss_index.bin (vector store)
#   models/labeled_examples.parquet (metadata)
#   models/embedder_info.json (config)
```

### Step 5: Verify

```bash
# Quick sanity check
python -c "
import faiss
import pandas as pd

index = faiss.read_index('models/faiss_index.bin')
df = pd.read_parquet('models/labeled_examples.parquet')

print(f'FAISS vectors: {index.ntotal}')
print(f'Parquet rows: {len(df)}')
print(f'Should match: {index.ntotal == len(df)}')
"
```

---

## Method 2: Manual Labeling (Small Batches)

For adding hand-curated labels or correcting existing ones.

### Step 1: Create a Label Batch File

Create a JSON file in `data/Labeled_Bugs/`:

```bash
cat > data/Labeled_Bugs/manual_batch_2025_01.json << 'EOF'
[
  {
    "advisoryId": "CSCwk12345",
    "summary": "BGP session flaps when ECMP paths exceed 32 on Catalyst 9500",
    "platform": "IOS-XE",
    "labels": ["RTE_BGP", "RTE_ECMP"],
    "reasoning": "BGP routing protocol with ECMP load balancing issue"
  },
  {
    "advisoryId": "cisco-sa-ise-xss-2024",
    "summary": "Cross-site scripting vulnerability in ISE admin portal",
    "platform": "ISE",
    "labels": ["MGMT_SSH_HTTP", "SEC_8021X"],
    "reasoning": "Web management interface security issue affecting 802.1X deployment"
  }
]
EOF
```

### Step 2: Ingest the Batch

```bash
# Preview without saving (dry run)
python scripts/ingest_frontier_labels.py --dry-run

# If preview looks good, run for real
python scripts/ingest_frontier_labels.py

# Output:
#   Processed 2 valid items
#   Saving 7067 rows to models/labeled_examples.parquet
#   Saving 7067 vectors to models/faiss_index.bin
```

---

## Method 3: Database Direct Insert (API/Programmatic)

For integrating with external systems or automation.

### Using the REST API

```bash
# Start the backend
uvicorn backend.app:app --host 0.0.0.0 --port 8000

# Insert via API (requires admin key if configured)
curl -X POST http://localhost:8000/api/v1/vulnerabilities \
  -H "Content-Type: application/json" \
  -d '{
    "bug_id": "CSCwk99999",
    "summary": "Memory leak in OSPF SPF calculation",
    "platform": "IOS-XE",
    "labels": ["RTE_OSPFv2", "SYS_Memory"],
    "severity": "high"
  }'
```

### Direct SQLite Insert (Scripted)

```python
#!/usr/bin/env python3
"""Add vulnerabilities directly to SQLite database."""
import sqlite3
import json

def add_vulnerability(db_path, vuln):
    """Insert a single vulnerability record."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT OR REPLACE INTO vulnerabilities
        (bug_id, advisory_id, summary, platform, labels, severity, labels_source)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        vuln.get('bug_id'),
        vuln.get('advisory_id'),
        vuln['summary'],
        vuln['platform'],
        json.dumps(vuln['labels']),
        vuln.get('severity', 'medium'),
        'manual_insert'
    ))

    conn.commit()
    conn.close()
    print(f"Added: {vuln.get('bug_id') or vuln.get('advisory_id')}")

# Example usage
add_vulnerability('vulnerability_db.sqlite', {
    'bug_id': 'CSCwk88888',
    'summary': 'EIGRP stuck-in-active on dual-homed sites',
    'platform': 'IOS-XE',
    'labels': ['RTE_EIGRP'],
    'severity': 'medium'
})
```

**Important:** After direct DB inserts, rebuild the FAISS index:
```bash
python scripts/standardize_labels.py
python scripts/build_faiss_index.py --input golden_dataset.csv
```

---

## Valid Labels (Taxonomy Reference)

Labels must match the taxonomy files in `taxonomies/`:

| Platform | Taxonomy File | Example Labels |
|----------|---------------|----------------|
| IOS-XE | `features.yml` | RTE_BGP, MGMT_SSH_HTTP, SEC_8021X |
| NX-OS | `features_nxos.yml` | SW_L2_VLAN, RTE_OSPF, VPC |
| IOS-XR | `features_iosxr.yml` | RTE_BGP, MPLS_LDP, Segment_Routing |
| ASA/FTD | `features_asa.yml` | VPN_IPSec, SEC_FW_Inspect |

### Quick Label Lookup

```bash
# List all valid labels for IOS-XE
grep "label:" taxonomies/features.yml | sort | uniq

# Search for BGP-related labels
grep -r "BGP" taxonomies/
```

### Common Label Categories

| Category | Labels |
|----------|--------|
| **Routing** | RTE_BGP, RTE_OSPFv2, RTE_OSPFv3, RTE_EIGRP, RTE_ISIS, RTE_Static |
| **Layer 2** | L2_STP, L2_EtherChannel, L2_LACP, L2_VLAN_VTP |
| **Management** | MGMT_SSH_HTTP, MGMT_SNMP, MGMT_AAA_TACACS_RADIUS, MGMT_LLDP_CDP |
| **Security** | SEC_8021X, SEC_CoPP, SEC_PACL_VACL, VPN_IPSec, VPN_IKEv2 |
| **QoS** | QOS_MQC_ClassPolicy, QOS_POLICING, QOS_MARKING |
| **System** | SYS_Boot_Upgrade, SYS_Licensing_Smart, SYS_Memory |

---

## Workflow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    COMPLETE DATA INGESTION WORKFLOW                          │
└─────────────────────────────────────────────────────────────────────────────┘

                    ┌──────────────────┐
                    │   DATA SOURCES   │
                    └────────┬─────────┘
                             │
        ┌────────────────────┼────────────────────┐
        ▼                    ▼                    ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│  Cisco PSIRT  │   │  Cisco Bug    │   │    Manual     │
│     API       │   │     API       │   │   Curation    │
└───────┬───────┘   └───────┬───────┘   └───────┬───────┘
        │                   │                   │
        └─────────┬─────────┘                   │
                  ▼                             │
        ┌─────────────────┐                     │
        │ cisco_vuln_     │                     │
        │ fetcher.py      │                     │
        └────────┬────────┘                     │
                 │                              │
                 ▼                              │
        ┌─────────────────┐                     │
        │  Raw JSONL      │                     │
        │  (unlabeled)    │                     │
        └────────┬────────┘                     │
                 │                              │
    ┌────────────┼────────────┐                 │
    ▼            ▼            ▼                 │
┌────────┐ ┌──────────┐ ┌──────────┐            │
│ GPT-4o │ │ Gemini   │ │ Local    │            │
│        │ │          │ │ LLM      │            │
└───┬────┘ └────┬─────┘ └────┬─────┘            │
    │           │            │                  │
    └─────┬─────┴────────────┘                  │
          ▼                                     │
 ┌─────────────────┐                            │
 │  Labeled JSONL  │                            │
 │  (with labels)  │                            │
 └────────┬────────┘                            │
          │                                     │
          │          ┌──────────────────────────┘
          │          │
          ▼          ▼
 ┌─────────────────────────┐
 │   standardize_labels.py │  <-- Merges all sources
 │   (taxonomy mapping)    │      - CSV, JSONL, SQLite, Manual
 └───────────┬─────────────┘
             │
             ▼
    ┌─────────────────┐
    │ golden_dataset  │
    │     .csv        │
    └────────┬────────┘
             │
             ▼
    ┌─────────────────┐
    │ build_faiss_    │
    │ index.py        │
    └────────┬────────┘
             │
    ┌────────┴────────┐
    ▼                 ▼
┌──────────┐   ┌────────────────┐
│ faiss_   │   │ labeled_       │
│ index.bin│   │ examples.parquet│
└──────────┘   └────────────────┘
    │                 │
    └────────┬────────┘
             ▼
    ┌─────────────────┐
    │  SYSTEM READY   │
    │  FOR INFERENCE  │
    └─────────────────┘
```

---

## Troubleshooting

### "Label not found in taxonomy"

```bash
# Check if label exists
grep -r "YOUR_LABEL" taxonomies/

# If not, add it to the appropriate taxonomy file
# Then re-run standardization
```

### "FAISS index and parquet row count mismatch"

```bash
# Rebuild from scratch
python scripts/standardize_labels.py
python scripts/build_faiss_index.py --input golden_dataset.csv
```

### "Duplicate advisory IDs"

The fetcher automatically deduplicates, but if you have duplicates:
```bash
# Check for duplicates
python -c "
import pandas as pd
df = pd.read_parquet('models/labeled_examples.parquet')
dups = df[df.duplicated(subset=['advisoryId'], keep=False)]
print(f'Duplicates: {len(dups)}')
print(dups[['advisoryId', 'source']].head(10))
"
```

### "API rate limit exceeded"

The `cisco_vuln_fetcher.py` has built-in rate limiting (2 sec delay). If you still hit limits:
```bash
# Use smaller batches
python scripts/cisco_vuln_fetcher.py --mode psirt --days 7 -o batch1.jsonl
# Wait
python scripts/cisco_vuln_fetcher.py --mode psirt --days 14 -o batch2.jsonl
```

---

## Best Practices

1. **Always backup before major updates:**
   ```bash
   cp vulnerability_db.sqlite vulnerability_db.sqlite.bak
   cp models/faiss_index.bin models/faiss_index.bin.bak
   cp models/labeled_examples.parquet models/labeled_examples.parquet.bak
   ```

2. **Use `--dry-run` first** when available

3. **Verify label quality** by spot-checking a few examples after ingestion

4. **Keep sources traceable** - the `source` column tracks where each label came from (csv, jsonl, sqlite, frontier_*, manual_insert)

5. **Rebuild indexes after any DB changes** - the FAISS index must match the parquet which should reflect the DB

---

## Quick Cheat Sheet

```bash
# Fetch new PSIRTs (last 7 days, skip existing)
python scripts/cisco_vuln_fetcher.py --mode psirt --days 7 --dedup --jsonl -o new.jsonl

# Label with GPT-4o
python scripts/synthesize_reasoning_openai.py --input new.jsonl --output labeled.jsonl

# Standardize & rebuild
python scripts/standardize_labels.py
python scripts/build_faiss_index.py --input golden_dataset.csv

# Verify
python -c "import faiss; print(faiss.read_index('models/faiss_index.bin').ntotal)"
```

---

**Document Version:** 1.0
**Last Updated:** December 21, 2025
