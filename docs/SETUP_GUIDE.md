# CVE_EVAL_V2 Setup Guide

**Version:** 4.1 | **Last Updated:** December 19, 2025

Complete setup instructions for new developers and deployment.

---

## Table of Contents

1. [Hardware Requirements](#1-hardware-requirements)
2. [Software Prerequisites](#2-software-prerequisites)
3. [Installation](#3-installation)
4. [Model Setup](#4-model-setup)
5. [Database Verification](#5-database-verification)
6. [Running the Application](#6-running-the-application)
7. [Verification](#7-verification)
8. [Troubleshooting](#8-troubleshooting)

---

## 1. Hardware Requirements

### Option A: Apple Silicon (Recommended for Development)

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| **Processor** | Apple M1 | M2/M3/M4 Pro/Max/Ultra |
| **RAM** | 16GB | 32GB+ |
| **Storage** | 50GB free | 100GB free |
| **macOS** | 13.0 (Ventura) | 14.0+ (Sonoma) |

**Why Apple Silicon?**
- MLX framework provides 2-3x faster inference than PyTorch
- Unified memory = no GPU memory limits
- Lower power consumption
- Native Metal acceleration

### Option B: NVIDIA GPU (Production/Training)

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| **GPU** | RTX 3080 (10GB) | RTX 4090 / A100 (24GB+) |
| **VRAM** | 10GB | 16GB+ |
| **System RAM** | 16GB | 32GB+ |
| **Storage** | 50GB free | 100GB free |
| **CUDA** | 11.8 | 12.1+ |
| **cuDNN** | 8.6 | 8.9+ |

### Option C: CPU-Only (Testing Only)

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| **CPU** | 8 cores | 16+ cores |
| **RAM** | 32GB | 64GB |
| **Storage** | 50GB free | 100GB free |

> ⚠️ **Warning:** CPU inference is ~15x slower than GPU (~30s vs ~2s per analysis)

---

## 2. Software Prerequisites

### Python

- **Version:** Python 3.10 or 3.11 (3.12 has compatibility issues with some packages)
- **Architecture:** ARM64 for Apple Silicon (NOT x86 via Rosetta)

**Verify Python:**
```bash
python3 --version    # Should be 3.10.x or 3.11.x
python3 -c "import platform; print(platform.machine())"
# Apple Silicon: should output "arm64"
# Intel/AMD: should output "x86_64"
```

### Node.js (for Frontend)

- **Version:** Node.js 18+ (LTS recommended)
- **npm:** Included with Node.js

```bash
node --version   # Should be 18.x or higher
npm --version    # Should be 9.x or higher
```

### Git

```bash
git --version    # Any recent version
```

---

## 3. Installation

### Step 1: Clone the Repository

```bash
git clone https://github.com/pbrusio/cve_EVAL_V2.git
cd cve_EVAL_V2
```

### Step 2: Create Virtual Environment

```bash
# Create venv
python3 -m venv venv

# Activate (Linux/macOS)
source venv/bin/activate

# Activate (Windows)
# venv\Scripts\activate
```

### Step 3: Install Dependencies

**For Apple Silicon Mac:**
```bash
pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-mlx.txt
pip install -r requirements-test.txt  # Optional: for testing
```

**For Linux/NVIDIA GPU:**
```bash
pip install --upgrade pip
pip install -r requirements.txt
pip install peft  # Required: for loading LoRA adapters
pip install -r requirements-test.txt  # Optional: for testing
```

**For CPU-only (testing):**
```bash
pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-test.txt
```

### Step 4: Install Frontend Dependencies

```bash
cd frontend
npm install
cd ..
```

---

## 4. Model Setup

### Foundation-Sec-8B Model

The system uses `fdtn-ai/Foundation-Sec-8B`, an 8-billion parameter security-focused LLM.

**First-time Download (~16GB):**

The model will download automatically on first use, but you can pre-cache it:

**Apple Silicon (MLX):**
```bash
python -c "
from mlx_lm import load
print('Downloading Foundation-Sec-8B for MLX...')
load('fdtn-ai/Foundation-Sec-8B')
print('Done!')
"
```

**Linux/CUDA (Transformers):**
```bash
python -c "
from transformers import AutoModelForCausalLM, AutoTokenizer
model_id = 'fdtn-ai/Foundation-Sec-8B'
print('Downloading tokenizer...')
AutoTokenizer.from_pretrained(model_id)
print('Downloading model (this may take 10-20 minutes)...')
AutoModelForCausalLM.from_pretrained(model_id)
print('Done!')
"
```

### Sentence Transformer Embedder

The embedder downloads automatically (~500MB):
```bash
python -c "
from sentence_transformers import SentenceTransformer
print('Downloading sentence-transformers/all-MiniLM-L6-v2...')
SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
print('Done!')
"
```

### LoRA Adapters (Platform-Specific)

Platform-specific LoRA adapters are included in the repository:

```
models/adapters/
├── mlx_v1/                    # Mac adapter (MLX format, ~71% accuracy)
│   ├── adapter_config.json
│   └── adapters.safetensors
├── cuda_v1/                   # Linux adapter (PEFT format, ~57% accuracy)
│   ├── adapter_config.json
│   └── adapter_model.safetensors
└── registry.yaml              # Adapter metadata
```

**Verify adapters exist:**
```bash
ls -la models/adapters/mlx_v1/   # Should show adapter_config.json, adapters.safetensors
ls -la models/adapters/cuda_v1/  # Should show adapter_config.json, adapter_model.safetensors
```

**Important:** These adapters are NOT interchangeable - MLX format only works with `mlx_inference.py`, PEFT format only works with `transformers_inference.py`.

**Verify symlink:**
```bash
ls -la models/lora_adapter
# Should show: lora_adapter -> lora_adapter_v3_20251212/
```

### FAISS Embedder Configuration (REQUIRED)

The FAISS similarity search requires `models/embedder_info.json`:

```bash
cat models/embedder_info.json
```

**Expected content:**
```json
{
  "model_name": "sentence-transformers/all-MiniLM-L6-v2",
  "dimension": 384,
  "num_examples": 7681,
  "source_file": "merged_with_silver_labels"
}
```

> **Warning:** If this file is missing, PSIRT analysis API calls will fail with 500 errors.

---

## 5. Database Verification

The vulnerability database is included in the repository.

**Verify database:**
```bash
sqlite3 vulnerability_db.sqlite "
SELECT 'vulnerabilities' as tbl, COUNT(*) as cnt FROM vulnerabilities
UNION ALL SELECT 'device_inventory', COUNT(*) FROM device_inventory
UNION ALL SELECT 'version_index', COUNT(*) FROM version_index
UNION ALL SELECT 'label_index', COUNT(*) FROM label_index;
"
```

**Expected output:**
```
vulnerabilities|9705
device_inventory|10
version_index|272524
label_index|1002
```

---

## 6. Running the Application

### Start Backend

**Apple Silicon (MLX - Recommended):**
```bash
source venv/bin/activate
export PSIRT_BACKEND=mlx  # Optional, MLX is default on Apple Silicon
python -m uvicorn backend.app:app --host 0.0.0.0 --port 8000
```

**Linux/CUDA:**
```bash
source venv/bin/activate
export PSIRT_BACKEND=transformers
python -m uvicorn backend.app:app --host 0.0.0.0 --port 8000
```

### Start Frontend

In a separate terminal:
```bash
cd frontend
npm run dev
```

### Access Application

- **Frontend:** http://localhost:3000
- **API Docs:** http://localhost:8000/docs
- **Health Check:** http://localhost:8000/api/v1/health

---

## 7. Verification

### Test API Health

```bash
curl http://localhost:8000/api/v1/health
```

**Expected response:**
```json
{"status": "healthy", "database": "connected", "model": "loaded"}
```

### Test PSIRT Analysis

```bash
curl -X POST http://localhost:8000/api/v1/analyze-psirt \
  -H "Content-Type: application/json" \
  -d '{"summary": "A vulnerability in SSH could allow unauthenticated access", "platform": "IOS-XE"}'
```

### Test Database Scan

```bash
curl -X POST http://localhost:8000/api/v1/scan-device \
  -H "Content-Type: application/json" \
  -d '{"platform": "IOS-XE", "version": "17.10.1"}'
```

### Run Test Suite

```bash
source venv/bin/activate
pytest tests/ -v
# Expected: 175+ tests passing (including 16 platform detection tests)
```

**Verify test fixtures exist:**
```bash
ls tests/fixtures/psirt_corpus.json
# Should exist - required for architecture tests
```

---

## 8. Troubleshooting

### "No module named 'mlx'" on Apple Silicon

MLX only works with ARM64 Python. Check your Python architecture:
```bash
python -c "import platform; print(platform.machine())"
```

If it shows `x86_64`, you're running Python under Rosetta. Reinstall native Python:
```bash
brew install python@3.11
# Then recreate your venv with the new Python
```

### "CUDA out of memory"

Reduce batch size or use quantization:
```bash
export PSIRT_QUANTIZATION=8bit
```

### CUDA/Linux Troubleshooting

**Step 1: Verify CUDA is available**
```bash
python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}')"
python -c "import torch; print(f'CUDA device: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"N/A\"}')"
```

**Step 2: Verify platform detection**
```bash
python -c "from predict_and_verify import detect_platform; detect_platform()"
# Expected: "Platform detection: CUDA available (GPU_NAME) → using Transformers+PEFT"
```

**Step 3: Verify PEFT adapter exists**
```bash
ls -la models/adapters/cuda_v1/
# Expected: adapter_config.json, adapter_model.safetensors
```

**Step 4: Verify PEFT loads correctly**
```bash
python -c "
from peft import PeftModel
from transformers import AutoModelForCausalLM
print('PEFT import successful')
"
```

**Step 5: Test inference directly**
```bash
# Quick smoke test
python -c "
from transformers_inference import TransformersPSIRTLabeler
labeler = TransformersPSIRTLabeler()
print('Labeler initialized successfully')
"
```

**Common CUDA Errors:**

| Error | Cause | Solution |
|-------|-------|----------|
| `CUDA not available` | PyTorch installed without CUDA | `pip install torch --index-url https://download.pytorch.org/whl/cu118` |
| `No module named 'peft'` | PEFT not installed | `pip install peft` |
| `Adapter not found` | Missing cuda_v1 adapter | Verify `models/adapters/cuda_v1/` exists |
| `CUDA OOM` | Insufficient VRAM | Use `PSIRT_QUANTIZATION=8bit` |
| `cuDNN version mismatch` | Driver/toolkit mismatch | Reinstall CUDA toolkit to match driver |

**Force specific backend (override auto-detect):**
```bash
# Force MLX (Mac only)
PSIRT_BACKEND=mlx python -m uvicorn backend.app:app --port 8000

# Force Transformers+PEFT (any platform)
PSIRT_BACKEND=transformers_local python -m uvicorn backend.app:app --port 8000

# Force legacy (no adapter)
PSIRT_BACKEND=transformers python -m uvicorn backend.app:app --port 8000
```

### "Database is locked"

Only one process can write to SQLite at a time. Stop any other backend processes:
```bash
lsof vulnerability_db.sqlite
# Kill any processes using the database
```

### Model download fails

Check your internet connection and HuggingFace Hub access:
```bash
pip install --upgrade huggingface-hub
huggingface-cli login  # Optional: for gated models
```

### Frontend build fails

Clear npm cache and reinstall:
```bash
cd frontend
rm -rf node_modules package-lock.json
npm install
npm run dev
```

### Tests failing

Ensure all dependencies are installed:
```bash
pip install -r requirements-test.txt
pytest tests/test_framework_setup.py -v  # Verify framework
```

### Missing embedder_info.json (500 errors on PSIRT analysis)

This file is required for FAISS similarity search:
```bash
# Check if file exists
ls models/embedder_info.json

# If missing, the API will return 500 errors on /api/v1/analyze-psirt
# The file should contain:
# {"model_name": "sentence-transformers/all-MiniLM-L6-v2", "dimension": 384, ...}
```

### Missing psirt_corpus.json (architecture test failures)

This file is required for architecture validation tests:
```bash
# Check if file exists
ls tests/fixtures/psirt_corpus.json

# If missing, tests in tests/architecture/ will fail
```

---

## Environment Variables

Create a `.env` file in the project root (optional):

```bash
# Backend Configuration
PSIRT_BACKEND=auto             # auto (default), mlx (Mac), transformers_local (CUDA/CPU)
PSIRT_QUANTIZATION=16bit       # or "8bit" for lower memory
LOG_LEVEL=INFO                 # DEBUG, INFO, WARNING, ERROR

# Database
DATABASE_PATH=vulnerability_db.sqlite

# API Keys (for Cisco API integration)
# CISCO_CLIENT_ID=your_client_id
# CISCO_CLIENT_SECRET=your_client_secret

# Frontier LLM (for batch labeling - development only)
# GEMINI_API_KEY=your_gemini_key
# ANTHROPIC_API_KEY=your_anthropic_key
```

---

## Quick Reference

| Command | Purpose |
|---------|---------|
| `source venv/bin/activate` | Activate virtual environment |
| `pip install -r requirements.txt` | Install production dependencies |
| `pip install -r requirements-mlx.txt` | Install MLX (Apple Silicon) |
| `pip install -r requirements-test.txt` | Install test dependencies |
| `python -m uvicorn backend.app:app --reload` | Start backend (dev mode) |
| `cd frontend && npm run dev` | Start frontend |
| `pytest tests/ -v` | Run all tests |
| `pytest tests/ --cov=backend` | Run tests with coverage |

---

**Document Version:** 1.1
**Last Updated:** December 19, 2025
