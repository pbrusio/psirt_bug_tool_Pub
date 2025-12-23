# Foundation-Sec-8B Setup & Usage Guide

Complete guide for deploying the Cisco Foundation-Sec-8B few-shot learning pipeline for PSIRT labeling and device verification.

## Table of Contents
- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [Performance](#performance)
- [Troubleshooting](#troubleshooting)

---

## Overview

**Foundation-Sec-8B** is Cisco's 8B parameter cybersecurity-specialized LLM based on Llama 3.1. This implementation uses **few-shot learning with retrieval-augmented generation (RAG)** to achieve:

- **80% exact match accuracy** on PSIRT labeling
- **0.93 F1 score** (8-bit quantization)
- **Zero marginal cost** after initial setup
- **Fully offline deployment** (no API calls)

### What It Does
```
PSIRT Summary → SEC-8B → Feature Labels → Config Verification Commands
```

Example:
```
Input:  "SSH vulnerability in Cisco IOS XE Software allows remote DoS"
Labels: ['SEC_CoPP', 'MGMT_SSH_HTTP']
Commands: ['show policy-map control-plane', 'show run ssh', 'show ssh']
```

---

## Prerequisites

### Hardware Requirements

**Minimum (4-bit quantization):**
- GPU: 8GB VRAM (RTX 3070 or better)
- RAM: 16GB
- Storage: 25GB

**Recommended (8-bit quantization):**
- GPU: 16GB VRAM (RTX 4080, RTX 5080, A4000, or better)
- RAM: 32GB
- Storage: 30GB

**Current Setup (Tested):**
- GPU: NVIDIA RTX 5080 (16GB VRAM)
- CUDA: 12.9
- Driver: 575.57.08

### Software Requirements
- Python 3.10+
- CUDA 11.8+ (for GPU acceleration)
- Git LFS (for HuggingFace model downloads)

---

## Installation

### 1. Clone Repository
```bash
git clone git@github.com:pbrusio/cve_EVAL_V2.git
cd cve_EVAL_V2
```

### 2. Setup Python Environment
```bash
./setup_venv.sh
source venv/bin/activate
```

### 3. Install ML Dependencies
```bash
pip install transformers torch accelerate bitsandbytes sentence-transformers faiss-cpu pyarrow
```

Expected install time: ~5 minutes (downloads ~3GB)

### 4. Login to HuggingFace
```bash
python -c "from huggingface_hub import login; login(token='YOUR_HF_TOKEN')"
```

Get your token from: https://huggingface.co/settings/tokens

### 5. Build FAISS Index (One-time)
```bash
python build_faiss_index.py
```

Output:
- `models/faiss_index.bin` - 165 example embeddings
- `models/labeled_examples.parquet` - Training data for retrieval
- `models/embedder_info.json` - Embedder configuration

---

## Quick Start

### Basic Usage

```python
from predict_and_verify import PSIRTVerificationPipeline

# Initialize (loads SEC-8B model - takes ~10 seconds)
pipeline = PSIRTVerificationPipeline()

# Process a PSIRT
result = pipeline.process_psirt(
    psirt_summary="SSH authentication bypass in ASA allows unauthorized access",
    platform="ASA"
)

# Access results
print("Predicted Labels:", result['predicted_labels'])
print("Config Patterns:", result['config_checks'])
print("Show Commands:", result['show_commands'])
print("Domains:", result['domains'])
```

### Command Line Usage

```bash
# Run demo with 3 test cases
python predict_and_verify.py

# Results saved to: verification_output.json
```

### Batch Processing

```python
import pandas as pd
from predict_and_verify import PSIRTVerificationPipeline

pipeline = PSIRTVerificationPipeline()

# Load PSIRTs
df = pd.read_csv('your_psirts.csv')

results = []
for _, row in df.iterrows():
    result = pipeline.process_psirt(
        row['summary'],
        row['platform']
    )
    results.append(result)

# Save
import json
with open('batch_results.json', 'w') as f:
    json.dump(results, f, indent=2)
```

---

## Architecture

### Pipeline Flow

```
┌─────────────────────────────────────────────────────────┐
│  1. PSIRT Input                                         │
│     - Summary text                                      │
│     - Platform (IOS-XE, ASA, FTD, IOS-XR, NX-OS)       │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│  2. Retrieval (FAISS Semantic Search)                   │
│     - Embed query with sentence-transformers           │
│     - Find 5 most similar labeled examples             │
│     - Filter by platform                                │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│  3. Prompt Construction                                 │
│     - Platform-specific taxonomy (70 IOS-XE labels)    │
│     - Retrieved examples (summary → labels)            │
│     - Current PSIRT to label                           │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│  4. SEC-8B Inference                                    │
│     - Foundation-Sec-8B (4-bit or 8-bit quantized)     │
│     - Temperature: 0.2                                  │
│     - Max tokens: 150                                   │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│  5. Post-Processing                                     │
│     - Validate labels against taxonomy                  │
│     - Map to config_regex patterns                      │
│     - Map to show commands                              │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│  6. Output                                              │
│     - predicted_labels: ['SEC_CoPP', 'MGMT_SSH_HTTP']  │
│     - config_checks: regex patterns                     │
│     - show_commands: device verification cmds           │
│     - domains: ['Security', 'Management']              │
└─────────────────────────────────────────────────────────┘
```

### Key Components

**1. Foundation-Sec-8B**
- Base: Llama 3.1 8B
- Specialization: Cybersecurity domain (CTI-MCQA, CTI-RCM benchmarks)
- Context window: 4096 tokens
- Training: Continued pre-training on security data

**2. FAISS Index**
- Embedder: sentence-transformers/all-MiniLM-L6-v2
- Dimension: 384
- Metric: L2 (Euclidean distance)
- Size: 165 labeled examples

**3. Taxonomy Files**
- `features.yml` - IOS-XE (70 labels)
- `features_iosxr.yml` - IOS-XR (22 labels)
- `features_asa.yml` - ASA/FTD (46 labels)
- `features_nxos.yml` - NX-OS (25 labels)

Each label contains:
- `config_regex`: Patterns to detect feature in config
- `show_cmds`: Commands to verify feature on device
- `domain`: Category (Security, Management, VPN, etc.)

---

## Performance

### Accuracy Comparison

| Model | Exact Match | F1 Score | Inference Speed |
|-------|-------------|----------|-----------------|
| **SEC-8B (4-bit)** | 80% | 0.87 | 0.84s/PSIRT |
| **SEC-8B (8-bit)** | 80% | **0.93** | 3.42s/PSIRT |
| Gemini API | 95%+ | 0.99 | Variable |
| XGBoost Flat | 14.5% | 0.19 | 0.01s |
| XGBoost Hierarchical | 22.8% | 0.26 | 0.02s |

### Quantization Trade-offs

**4-bit Quantization:**
- ✅ Faster inference (4x speedup)
- ✅ Lower VRAM (6GB vs 13GB)
- ✅ Good for development/testing
- ⚠️ Slightly lower accuracy (F1: 0.87)

**8-bit Quantization:**
- ✅ Better accuracy (F1: 0.93)
- ✅ More consistent predictions
- ✅ Fewer catastrophic failures
- ⚠️ Slower (3.4s vs 0.8s)
- ⚠️ More VRAM (13GB)

**Recommendation:** Use 8-bit for production, 4-bit for development

### Switching Quantization

Edit `fewshot_inference.py` line 22:

**For 8-bit:**
```python
quantization_config = BitsAndBytesConfig(
    load_in_8bit=True
)
```

**For 4-bit (current):**
```python
quantization_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_compute_dtype=torch.float16
)
```

### Performance Testing

```bash
# Run quantization comparison (takes ~15 minutes)
python compare_quantization.py

# Results saved to: quantization_comparison_results.json
```

---

## Output Format

### Example Output

```json
{
  "psirt_summary": "SSH vulnerability in IOS XE allows DoS",
  "platform": "IOS-XE",
  "predicted_labels": ["SEC_CoPP", "MGMT_SSH_HTTP"],
  "domains": ["Security", "Management"],
  "config_checks": [
    {
      "label": "SEC_CoPP",
      "pattern": "^control-plane\\b",
      "description": "Check if SEC_CoPP is configured"
    },
    {
      "label": "MGMT_SSH_HTTP",
      "pattern": "^ip\\s+ssh\\b",
      "description": "Check if MGMT_SSH_HTTP is configured"
    }
  ],
  "show_commands": [
    {
      "label": "SEC_CoPP",
      "command": "show policy-map control-plane",
      "description": "Verify SEC_CoPP on device"
    },
    {
      "label": "MGMT_SSH_HTTP",
      "command": "show run ssh",
      "description": "Verify MGMT_SSH_HTTP on device"
    }
  ]
}
```

---

## Troubleshooting

### GPU Issues

**Error: CUDA out of memory**
- Switch to 4-bit quantization
- Reduce batch size
- Close other GPU applications

**Error: CUDA not available**
```bash
python -c "import torch; print(torch.cuda.is_available())"
```
If False:
- Check NVIDIA driver: `nvidia-smi`
- Reinstall PyTorch with CUDA: `pip install torch --index-url https://download.pytorch.org/whl/cu118`

### Model Download Issues

**Error: Repository not found**
- Ensure HuggingFace token has access to `fdtn-ai/Foundation-Sec-8B`
- Check token: https://huggingface.co/settings/tokens

**Slow downloads:**
- Model is ~16GB, expect 10-30 minutes on first run
- Subsequent runs use cached model

### FAISS Index Issues

**Error: Index not found**
```bash
python build_faiss_index.py
```

**Error: Dimension mismatch**
- Rebuild index: `rm models/faiss_index.bin && python build_faiss_index.py`

### Inference Issues

**JSON parsing errors:**
- Model sometimes outputs malformed JSON
- Pipeline has fallback regex parsing
- If persistent, try 8-bit quantization (more reliable)

**Low accuracy:**
- Ensure FAISS index is built
- Check platform matches taxonomy (IOS-XE, ASA, FTD, IOS-XR, NX-OS)
- Verify labeled examples exist for platform

---

## Advanced Usage

### Custom Temperature

```python
result = labeler.predict_labels(
    psirt_summary="...",
    platform="IOS-XE",
    k=5,                    # Number of retrieval examples
    max_new_tokens=150      # Max response length
)
```

Edit temperature in `fewshot_inference.py` line 148:
```python
temperature=0.2,  # Lower = more deterministic (0.0-1.0)
```

### Adding New Examples

1. Label new PSIRTs with Gemini:
```bash
python psirt_labeling_pipeline.py new_psirts.csv
python merge_to_csv.py
```

2. Rebuild FAISS index:
```bash
python build_faiss_index.py
```

3. New examples automatically used for retrieval

---

## File Reference

**Production Files:**
- `fewshot_inference.py` - Main inference class
- `predict_and_verify.py` - Complete pipeline with command generation
- `build_faiss_index.py` - FAISS index builder
- `compare_quantization.py` - Performance benchmarking

**Data Files:**
- `output/enriched_gemini_with_labels.csv` - Training data (165 labeled)
- `models/faiss_index.bin` - Embedding index
- `models/labeled_examples.parquet` - Retrieval examples

**Config Files:**
- `features.yml`, `features_*.yml` - Platform taxonomies
- `Prompt.txt` - (Legacy) Gemini prompt template

---

## Support

**Issues & Questions:**
- GitHub Issues: https://github.com/pbrusio/cve_EVAL_V2/issues
- See `CLAUDE.md` for technical details
- See `RECOMMENDATIONS.md` for deployment guidance

**Model Information:**
- HuggingFace: https://huggingface.co/fdtn-ai/Foundation-Sec-8B
- Cisco Foundation AI: Technical report available on model page
