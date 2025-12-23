"""
Application configuration
"""
import os
from pathlib import Path

# Base paths
BASE_DIR = Path(__file__).parent.parent.parent
MODELS_DIR = BASE_DIR / "models"
OUTPUT_DIR = BASE_DIR / "output"
FEATURES_DIR = BASE_DIR

# Model configuration
FAISS_INDEX_PATH = MODELS_DIR / "faiss_index.bin"
LABELED_EXAMPLES_PATH = MODELS_DIR / "labeled_examples.parquet"
EMBEDDER_INFO_PATH = MODELS_DIR / "embedder_info.json"

# SEC-8B model
MODEL_NAME = "fdtn-ai/Foundation-Sec-8B"
# Use float16 on Mac (MPS), 8-bit on Linux/CUDA with bitsandbytes
import platform
QUANTIZATION_BITS = 16 if platform.system() == "Darwin" else 8

# Feature taxonomy files
FEATURE_FILES = {
    "IOS-XE": FEATURES_DIR / "taxonomies/features.yml",
    "IOS-XR": FEATURES_DIR / "taxonomies/features_iosxr.yml",
    "ASA": FEATURES_DIR / "taxonomies/features_asa.yml",
    "FTD": FEATURES_DIR / "taxonomies/features_asa.yml",  # FTD uses same as ASA
    "NX-OS": FEATURES_DIR / "taxonomies/features_nxos.yml"
}

# API settings
API_TITLE = "PSIRT Vulnerability Analysis API"
API_VERSION = "3.2.0"
API_DESCRIPTION = """
# Cisco PSIRT Vulnerability Analysis & Device Verification System

**9,600+ bugs/PSIRTs | 5 Platforms | Feature-Aware Scanning**

---

## The "Dual-Path" Concept

This tool has **two distinct engines**. Knowing which one to use is the key to leveraging it effectively:

### Path A: Database Engine (Speed)
- **Response Time:** <10ms
- **What:** Fast lookup against 9,600+ known Cisco bugs/PSIRTs
- **When to use:** Known versions, upgrade planning, bulk scanning

### Path B: AI Engine (Adaptability)
- **Response Time:** ~3s (cached: <10ms)
- **What:** LLM analysis that reads unstructured text
- **When to use:** New advisory emails, zero-day alerts, text snippets

---

## Quick Reference: Which Tab to Use?

| Scenario | Use This Tab | Engine |
|----------|-------------|--------|
| Got a new advisory email? | **Security Analysis** | AI |
| Planning an upgrade? | **Defect Scanner** | Database |
| Daily fleet posture check? | **Device Inventory** | Database |
| Need to explain to management? | **AI Assistant** | AI |
| System maintenance? | **System Admin** | - |

---

## Best Practices

### 1. Filter Aggressively
Always provide **Hardware Model** and **Feature Configs**:
- Raw Database: 9,600+ bugs
- + Hardware Filter: ~7,200 bugs (~25% reduction)
- + Feature Filter: ~50-500 bugs (40-80% reduction)

### 2. Sync Often
- Keep Inventory synced with ISE
- Re-run SSH discovery after config changes
- Keeps "Feature Profile" accurate

### 3. Air-Gapped Support
- Use **Snapshot Form** in Scanner/Analysis tabs
- Use **Offline Updates** in Admin tab

---

## API Sections

- **Core Analysis:** `/api/v1/analyze-psirt`, `/api/v1/scan-device`
- **Device Inventory:** `/api/v1/inventory/*`
- **AI Reasoning:** `/api/v1/reasoning/*`
- **System:** `/api/v1/health`, `/api/v1/system/*`

For the full interactive tutorial, visit: [/api/v1/tutorial](/api/v1/tutorial)
"""

# Rate limiting (requests per minute)
# Configurable via env vars: RATE_LIMIT_DEFAULT, RATE_LIMIT_ANALYZE, RATE_LIMIT_VERIFY
RATE_LIMIT_DEFAULT = int(os.getenv("RATE_LIMIT_DEFAULT", "100"))  # Default per-IP limit
RATE_LIMIT_ANALYZE = int(os.getenv("RATE_LIMIT_ANALYZE", "30"))   # /analyze-psirt limit
RATE_LIMIT_VERIFY = int(os.getenv("RATE_LIMIT_VERIFY", "20"))     # /verify-* limit
RATE_LIMIT_SCAN = int(os.getenv("RATE_LIMIT_SCAN", "60"))         # /scan-device limit
RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW", "60"))  # Sliding window

# SSH timeout (seconds)
SSH_TIMEOUT = 30

# Cache settings
CACHE_DB = OUTPUT_DIR / "api_cache.db"
CACHE_EXPIRY_HOURS = 24

# Security settings
# CORS - comma-separated list of allowed origins
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
# Strip whitespace from origins
ALLOWED_ORIGINS = [origin.strip() for origin in ALLOWED_ORIGINS if origin.strip()]

# API Key for write operations (POST/DELETE)
# Leave empty to disable API key authentication
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "")

# Development mode - disables API key requirement
# WARNING: Set to "true" only in development. Production should use DEV_MODE=false
DEV_MODE = os.getenv("DEV_MODE", "false").lower() == "true"
