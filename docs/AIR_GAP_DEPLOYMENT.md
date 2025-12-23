# Air-Gap Deployment Guide

**Version:** 4.3 | **Date:** December 21, 2025

This guide explains how to prepare CVE_EVAL_V2 for deployment on an air-gapped (offline) network.

---

## Overview

The system requires ~17GB of AI models that normally download from HuggingFace on first run. For air-gapped deployment, we pre-download everything on an internet-connected machine, package it, and transfer via USB/secure media.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        AIR-GAP DEPLOYMENT FLOW                               │
└─────────────────────────────────────────────────────────────────────────────┘

  INTERNET-CONNECTED MACHINE                    AIR-GAPPED MACHINE
  ─────────────────────────                    ───────────────────

  1. Clone repository
         │
         ▼
  2. Set HF_HOME inside project
         │
         ▼
  3. Download models (~17GB)           USB DRIVE
     • Foundation-Sec-8B (16GB)    ─────────────►   4. Unpack tarball
     • MiniLM embedder (500MB)                            │
         │                                                ▼
         ▼                                         5. Set HF_HOME
  4. Create tarball                                       │
     (~18GB compressed)                                   ▼
                                                   6. Run application
                                                      (fully offline)
```

---

## Phase 1: Prepare on Internet-Connected Machine

### Step 1: Clone and Setup

```bash
# Clone repository
git clone https://github.com/pbrusio/cve_EVAL_V2.git
cd cve_EVAL_V2
git checkout alpha/4.3

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies for YOUR TARGET PLATFORM
# Choose ONE based on where you'll deploy:

# For Mac (Apple Silicon):
pip install -r requirements.txt
pip install -r requirements-mlx.txt

# For Linux (CUDA):
pip install -r requirements.txt
pip install peft

# For Linux (CPU-only):
pip install -r requirements.txt
```

### Step 2: Set Model Cache Inside Project

This is the key step - it makes the model cache portable:

```bash
# Set HuggingFace cache to be INSIDE the project directory
export HF_HOME=$(pwd)/models/hf_cache
mkdir -p models/hf_cache

# Verify it's set
echo $HF_HOME
# Should output: /path/to/cve_EVAL_V2/models/hf_cache
```

### Step 3: Download Models

```bash
# Download Foundation-Sec-8B (~16GB) and embedder (~500MB)
# This will take 10-30 minutes depending on your connection

python3 << 'EOF'
import os
print(f"HF_HOME is set to: {os.environ.get('HF_HOME', 'NOT SET')}")

# For Mac (MLX)
try:
    from mlx_lm import load
    print("\n📥 Downloading Foundation-Sec-8B for MLX...")
    print("   This is ~16GB, please be patient...")
    load('fdtn-ai/Foundation-Sec-8B')
    print("   ✅ Foundation-Sec-8B downloaded")
except ImportError:
    # For Linux (Transformers)
    from transformers import AutoModelForCausalLM, AutoTokenizer
    print("\n📥 Downloading Foundation-Sec-8B for Transformers...")
    print("   This is ~16GB, please be patient...")
    AutoTokenizer.from_pretrained('fdtn-ai/Foundation-Sec-8B')
    AutoModelForCausalLM.from_pretrained('fdtn-ai/Foundation-Sec-8B')
    print("   ✅ Foundation-Sec-8B downloaded")

# Embedder (both platforms)
from sentence_transformers import SentenceTransformer
print("\n📥 Downloading MiniLM embedder (~500MB)...")
SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
print("   ✅ Embedder downloaded")

print("\n✅ All models cached!")
EOF
```

### Step 4: Verify Cache

```bash
# Check cache size (should be ~17GB)
du -sh models/hf_cache/
# Expected: ~17G models/hf_cache/

# List cached models
ls -la models/hf_cache/hub/
# Should show:
#   models--fdtn-ai--Foundation-Sec-8B/
#   models--sentence-transformers--all-MiniLM-L6-v2/
```

### Step 5: Create Air-Gap Package

```bash
# Go to parent directory
cd ..

# Create tarball excluding unnecessary files
# This will be ~18GB (models are not very compressible)
tar -czvf cve_eval_airgap_$(date +%Y%m%d).tar.gz \
    --exclude='.git' \
    --exclude='.env' \
    --exclude='.env.*' \
    --exclude='venv' \
    --exclude='venv_mac' \
    --exclude='*.log' \
    --exclude='__pycache__' \
    --exclude='.DS_Store' \
    --exclude='*.pyc' \
    --exclude='node_modules' \
    cve_EVAL_V2/

# Check package size
ls -lh cve_eval_airgap_*.tar.gz
# Expected: ~18GB

echo "✅ Package ready for transfer"
```

---

## Phase 2: Transfer

Transfer the tarball to your air-gapped network using approved secure media:

- USB drive (needs to handle ~18GB)
- Approved file transfer system
- Secure network bridge (if available)

---

## Phase 3: Deploy on Air-Gapped Machine

### Step 1: Unpack

```bash
# Copy tarball from USB
cp /media/USB_DRIVE/cve_eval_airgap_YYYYMMDD.tar.gz ~/

# Unpack
cd ~
tar -xzvf cve_eval_airgap_YYYYMMDD.tar.gz
cd cve_EVAL_V2
```

### Step 2: Set Environment

```bash
# CRITICAL: Set HF_HOME to use the cached models
export HF_HOME=$(pwd)/models/hf_cache

# Add to your shell profile for persistence
echo 'export HF_HOME=$HOME/cve_EVAL_V2/models/hf_cache' >> ~/.bashrc
source ~/.bashrc
```

### Step 3: Create Virtual Environment

```bash
# Create fresh venv on target machine
python3 -m venv venv
source venv/bin/activate

# Install from cached wheels (if you included them)
# OR install from requirements (if target has matching pip cache)
pip install --no-index --find-links=./pip_cache -r requirements.txt

# If no pip cache, you'll need to pre-download wheels too (see Advanced section)
```

### Step 4: Verify Installation

```bash
# Test that models load from local cache (no network needed)
python3 << 'EOF'
import os
print(f"HF_HOME: {os.environ.get('HF_HOME')}")

# Quick test - should load instantly from cache
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
print("✅ Embedder loaded from cache")

# Test database
import sqlite3
conn = sqlite3.connect('vulnerability_db.sqlite')
count = conn.execute("SELECT COUNT(*) FROM vulnerabilities").fetchone()[0]
print(f"✅ Database: {count} vulnerabilities")
conn.close()
EOF
```

### Step 5: Run Application

```bash
# Start backend (background)
source venv/bin/activate
export HF_HOME=$(pwd)/models/hf_cache
nohup python -m uvicorn backend.app:app --host 0.0.0.0 --port 8000 > server.log 2>&1 &

# Verify it's running
sleep 5
curl http://localhost:8000/api/v1/health

# Start frontend (if needed)
cd frontend
npm run dev
```

---

## Package Contents Summary

What's included in the air-gap tarball (~18GB):

```
cve_EVAL_V2/
├── models/
│   ├── hf_cache/                    # ~17GB - HuggingFace model cache
│   │   └── hub/
│   │       ├── models--fdtn-ai--Foundation-Sec-8B/
│   │       └── models--sentence-transformers--all-MiniLM-L6-v2/
│   ├── adapters/                    # ~50MB - LoRA adapters
│   │   ├── mlx_v1/
│   │   └── cuda_v1/
│   ├── faiss_index.bin              # ~11MB - Similarity search
│   └── labeled_examples.parquet     # ~1MB - Few-shot examples
├── vulnerability_db.sqlite          # ~34MB - 9,705 vulnerabilities
├── backend/                         # API server
├── frontend/                        # Web UI
├── requirements.txt                 # Python dependencies
└── docs/                            # Documentation
```

---

## Advanced: Including Python Wheels

If the air-gapped machine can't `pip install` from PyPI, pre-download wheels:

```bash
# On internet-connected machine, after installing requirements:
mkdir pip_cache
pip download -r requirements.txt -d pip_cache/
pip download -r requirements-mlx.txt -d pip_cache/  # For Mac

# Include in tarball (adds ~500MB)
# Then on air-gapped machine:
pip install --no-index --find-links=./pip_cache -r requirements.txt
```

---

## Troubleshooting

### "Model not found" errors

```bash
# Verify HF_HOME is set
echo $HF_HOME
# Should point to: /path/to/cve_EVAL_V2/models/hf_cache

# Verify cache exists
ls -la $HF_HOME/hub/
```

### "Connection refused" on model download

This means it's trying to download instead of using cache:
```bash
# Make sure HF_HOME is set BEFORE running Python
export HF_HOME=$(pwd)/models/hf_cache
python -c "import os; print(os.environ.get('HF_HOME'))"
```

### Different Python version on target

The model cache is Python-version independent. Only the wheels in `pip_cache/` are version-specific. Download wheels for your target Python version.

---

## Quick Reference

| Step | Internet Machine | Air-Gap Machine |
|------|------------------|-----------------|
| 1 | `git clone` + `checkout alpha/4.3` | Unpack tarball |
| 2 | `export HF_HOME=$(pwd)/models/hf_cache` | Same |
| 3 | Download models (~30 min) | N/A (pre-cached) |
| 4 | Create tarball (~18GB) | Create venv |
| 5 | Transfer via USB | Run application |

**Total transfer size:** ~18GB
**Time to prepare:** ~1 hour (mostly download time)
**Time to deploy:** ~10 minutes

---

**Document Version:** 1.0
**Last Updated:** December 21, 2025
