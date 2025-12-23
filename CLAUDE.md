# CLAUDE.md

**Project:** Cisco PSIRT Vulnerability Analysis & Device Verification System
**Version:** 4.5 | **Last Updated:** December 22, 2025

## Quick Status

**Production Ready** - Complete end-to-end vulnerability analysis pipeline

**Current State:**
- 2,654 labeled training examples (PSIRTs + bugs)
- 9,617 bugs + 88 PSIRTs across 5 platforms in SQLite database
  - IOS-XE: 730 bugs, 53 PSIRTs | IOS-XR: 3,827 bugs, 6 PSIRTs | ASA: 1,704 bugs, 3 PSIRTs | FTD: 3,326 bugs, 20 PSIRTs | NX-OS: 30 bugs, 6 PSIRTs
- Foundation-Sec-8B + LoRA adapters (MLX ~71%, CUDA ~57% accuracy)
- **Multi-platform support**: Mac (MLX/MPS) and Linux (CUDA/CPU) with platform-specific adapters
- Three-tier PSIRT caching (database <10ms, FAISS exact match, few-shot)
- FastAPI backend + React frontend + air-gapped support
- Unified Bug/PSIRT scanning with separate counts
- Hardware filtering (25% reduction) + Feature filtering (40-80% reduction)

> **PSIRT Version Data:** 62 of 88 PSIRTs (70%) now have version data populated from Cisco API. Version-based PSIRT scanning is now functional.

---

## Documentation Map

> **START HERE** - This file provides project overview and quick start. For details, see:

| Document | Purpose |
|----------|---------|
| **[docs/SETUP_GUIDE.md](docs/SETUP_GUIDE.md)** | **START HERE FOR NEW DEVS** - Hardware requirements, installation, model setup, verification |
| **[docs/VISUAL_LEAD_GUIDE.md](docs/VISUAL_LEAD_GUIDE.md)** | **USER WORKFLOWS** - Flow-based guide to using the tool (Security Analysis, Defect Scanner, AI Assistant) |
| **[docs/ADMIN_GUIDE.md](docs/ADMIN_GUIDE.md)** | **DATA PIPELINES** - How we got here, training data, loading bugs/PSIRTs, FAISS index, air-gapped updates |
| **[docs/DATA_FLOW_DOCUMENTATION.md](docs/DATA_FLOW_DOCUMENTATION.md)** | **COMPREHENSIVE DATA FLOWS** - Traces every feature from source to UI, database schemas, ISE integration, AI Assistant, intent classification |
| **[docs/UI_DATA_FLOWS.md](docs/UI_DATA_FLOWS.md)** | **UI-TO-DATABASE MAPPING** - Every UI component traced to APIs, backend handlers, and database tables |
| **[docs/FILE_STRUCTURE.md](docs/FILE_STRUCTURE.md)** | **FILE HIERARCHY** - Every file mapped to its purpose, function, and connections |
| **[docs/ORPHANED_FILES.md](docs/ORPHANED_FILES.md)** | **CLEANUP GUIDE** - Files with no active purpose, candidates for removal |
| **[docs/ARCHITECTURE_AND_WORKFLOW.md](docs/ARCHITECTURE_AND_WORKFLOW.md)** | System architecture, Mermaid diagrams, dependency map, fallback rules, caching tiers |
| **[docs/API_AND_FEATURES.md](docs/API_AND_FEATURES.md)** | Complete API reference (all endpoints), request/response schemas, UI workflows |
| **[docs/CHANGELOG_V4.2.md](docs/CHANGELOG_V4.2.md)** | v4.2 Release notes - Unified docs, platform-aware health, test improvements |
| **[docs/CHANGELOG_V3.md](docs/CHANGELOG_V3.md)** | Previous version history (v3.x), breaking changes, migration guide |
| **[docs/AIR_GAP_DEPLOYMENT.md](docs/AIR_GAP_DEPLOYMENT.md)** | **AIR-GAP DEPLOYMENT** - Portable HF_HOME, packaging, offline deployment |
| **[docs/ADDING_LABELED_DATA.md](docs/ADDING_LABELED_DATA.md)** | **DATA INGESTION** - Adding new labeled bugs/PSIRTs to knowledge base |
| **[sidecar_extractor/README.md](sidecar_extractor/README.md)** | Air-gapped feature extraction guide |
| **[backend/db/README_VULN_DB.md](backend/db/README_VULN_DB.md)** | Database schema documentation |

### Interactive Documentation (via API)

When the backend is running, access styled interactive docs at:

| URL | Description |
|-----|-------------|
| `http://localhost:8000/api/v1/docs-hub` | Central documentation hub with navigation |
| `http://localhost:8000/api/v1/tutorial` | Getting Started tutorial |
| `http://localhost:8000/api/v1/admin-guide` | Admin Guide (styled HTML) |
| `http://localhost:8000/api/v1/setup-guide` | Setup Guide for Mac/Linux |
| `http://localhost:8000/api/v1/api-reference` | Swagger UI with navigation |
| `http://localhost:8000/api/v1/redoc` | ReDoc with navigation |

---

## Document & File Versioning Conventions

> **IMPORTANT:** Follow these conventions when creating or updating documents and files.

### Documentation Files

**Naming Format:** `{NAME}_{YYYY-MM-DD}.md` or include version in header

**Rules:**
1. **Check for existing docs first** - Before creating a new doc, search for similar files
2. **Update existing docs** - Prefer updating over creating duplicates
3. **Add version header** - Include `Version: X.Y | Last Updated: YYYY-MM-DD` at top
4. **Archive old versions** - Move superseded docs to `docs/archive/`

**Examples:**
- `WORK_LOG_2025-12-15.md` - Daily work log
- `CHANGELOG_V3.md` - Version-specific changelog
- Update `ARCHITECTURE_AND_WORKFLOW.md` header when making changes

### Model Artifacts & Data Files

**Naming Format:** `{name}_v{version}_{YYYYMMDD}.{ext}`

**Examples:**
- `faiss_index_v2_20251212.bin`
- `labeled_examples_v2_20251212.parquet`
- `lora_adapter_v3_20251212/`

**Symlinks for Stable References:**
```
models/faiss_index.bin        → faiss_index_v2_20251212.bin
models/labeled_examples.parquet → labeled_examples_v2_20251212.parquet
models/lora_adapter/          → lora_adapter_v3_20251212/
```

**When Creating New Versions:**
1. Create new versioned file: `{name}_v{N+1}_{YYYYMMDD}.{ext}`
2. Update symlink: `ln -sf {new_versioned_file} {symlink_name}`
3. Move old version to `models/archive/` if no longer needed

---

## Terminology

> **IMPORTANT:** This project distinguishes between bugs and vulnerabilities:

| Term | Definition | Source | User Relationship |
|------|------------|--------|-------------------|
| **Bug** | Software defect (CSCxxxx IDs) | Cisco Bug Search Tool | "Susceptible to" |
| **PSIRT/Advisory** | Security advisory (cisco-sa-xxxx) | Cisco Security Advisories | "Vulnerable to" |
| **Vulnerability** | Reserved for PSIRT/security context | General term | Use sparingly |

See `docs/CHANGELOG_TERMINOLOGY_MIGRATION.md` for migration details.

---

## Architecture Overview

```
┌─────────────────┐      ┌──────────────────┐      ┌──────────────────┐
│  PSIRT/Bug      │─────▶│  SEC-8B Model    │─────▶│  Feature Labels  │
│  Summary        │      │  (Foundation-    │      │  + Commands      │
└─────────────────┘      │   Sec-8B 8-bit)  │      └──────────────────┘
                         └──────────────────┘               │
                                  │                          ▼
                         ┌──────────────────┐      ┌──────────────────┐
                         │  FAISS Index     │      │  Device Verify   │
                         │  (2,654 examples)│      │  - Live SSH      │
                         └──────────────────┘      │  - Snapshot      │
                                                    └──────────────────┘
                                  │                          │
                         ┌──────────────────┐      ┌──────────────────┐
                         │  Vuln Database   │      │  Scan Results    │
                         │  (9,586 bugs)    │◀─────│  - Version match │
                         │  5 platforms     │      │  - Hardware filter│
                         │  20 hw models    │      │  - Feature filter│
                         └──────────────────┘      └──────────────────┘
```

**Two Analysis Paths:**
1. **Path A: PSIRT Analysis** - LLM predicts labels → device verification
2. **Path B: Database Scan** - Fast version + feature matching (1-2ms)

> For detailed Mermaid diagrams, dependency maps, and fallback rules, see **[docs/ARCHITECTURE_AND_WORKFLOW.md](docs/ARCHITECTURE_AND_WORKFLOW.md)**.

---

## Quick Start

### Mac (Apple Silicon - 32GB+ RAM)

```bash
# One-time setup (~5 min)
./setup_mac_env.sh

# Start backend (background)
source venv_mac/bin/activate
nohup ./backend/run_server.sh > backend.log 2>&1 &

# Start frontend
cd frontend && npm install && npm run dev
```

### Mac (Apple Silicon - 16GB RAM)

```bash
# One-time setup (~15 min, quantizes model to 4-bit)
./setup_mac_lowram.sh

# Start backend (background)
source venv_mac/bin/activate
nohup ./backend/run_server.sh > backend.log 2>&1 &

# Start frontend
cd frontend && npm install && npm run dev
```

> **16GB Note:** Uses 4-bit quantized model. ~65% accuracy (vs ~71%). Memory: ~8-10GB (vs ~32GB).

### Linux (NVIDIA GPU / CPU)

```bash
# One-time setup (~5 min)
./setup_linux_env.sh

# Start backend (background)
source venv/bin/activate
nohup ./backend/run_server.sh > backend.log 2>&1 &

# Start frontend
cd frontend && npm install && npm run dev
```

> **Tips:** Backend logs in `backend.log`. Stop backend: `pkill -f uvicorn`. Stop frontend: `Ctrl+C`.

**Access:**
- Frontend: http://localhost:3000
- API Docs: http://localhost:8000/docs

### Quick API Test

```bash
# PSIRT analysis
curl -X POST http://localhost:8000/api/v1/analyze-psirt \
  -H "Content-Type: application/json" \
  -d '{"summary": "SSH DoS vulnerability", "platform": "IOS-XE"}'

# Database scan (hardware + feature-aware)
curl -X POST http://localhost:8000/api/v1/scan-device \
  -H "Content-Type: application/json" \
  -d '{"platform": "IOS-XE", "version": "17.10.1", "hardware_model": "Cat9300"}'
```

> For complete API reference with all endpoints, see **[docs/API_AND_FEATURES.md](docs/API_AND_FEATURES.md)**.

---

## Key Components

### 1. ML Model (Foundation-Sec-8B + Platform-Specific LoRA Adapters)
- **Files:** `mlx_inference.py` (Mac), `transformers_inference.py` (Linux), `backend/core/sec8b.py`
- **Adapters:** `models/adapters/mlx_v1/` (~71% accuracy), `models/adapters/cuda_v1/` (~57% accuracy)
- **Platform Detection:** Auto-selects MLX on Mac (MPS), PEFT/Transformers on Linux (CUDA/CPU)
- **Three-Tier Caching:**
  - Tier 1 (Database): <10ms - Previously analyzed PSIRTs
  - Tier 2 (FAISS Exact): ~30ms - Advisory IDs in training data
  - Tier 3 (LLM Inference): ~2s - New PSIRTs
- **Memory:** ~18 GB observed (Mac/MLX full, 32GB recommended), ~6 GB (Mac/MLX 4-bit), 13 GB VRAM (Linux/CUDA)

### 2. Vulnerability Database
- **File:** `vulnerability_db.sqlite`
- **Contents:** 9,617 bugs + 88 PSIRTs across 5 platforms
- **Query Speed:** 1-6ms with hardware + feature filtering

### 3. Feature Taxonomies
- **Files:** `taxonomies/features*.yml` (141 labels across 5 platforms)
- **Each Label:** `config_regex`, `show_cmds`, `domains`

### 4. Web Application
- **Frontend:** React + TypeScript + Tailwind
- **Backend:** FastAPI + async
- **Tabs:** PSIRT Analysis, Vulnerability Scanner, Device Inventory, System Admin

### 5. AI Reasoning Layer
- **Endpoints:** `/reasoning/explain`, `/remediate`, `/ask`, `/summary`
- **Files:** `backend/api/reasoning_routes.py`, `backend/core/reasoning_engine.py`

> For detailed component descriptions, see **[docs/ARCHITECTURE_AND_WORKFLOW.md](docs/ARCHITECTURE_AND_WORKFLOW.md)**.

---

## Project Structure

```
├── backend/              # FastAPI application
│   ├── api/             # Routes (routes.py, reasoning_routes.py, inventory_routes.py)
│   ├── core/            # Business logic (sec8b.py, reasoning_engine.py, device_inventory.py)
│   └── db/              # Database schema & loaders
├── frontend/            # React + TypeScript UI
├── models/              # ML artifacts and adapters
│   ├── adapters/        # Platform-specific LoRA adapters
│   │   ├── mlx_v1/      # Mac adapter (MLX format, ~71% accuracy)
│   │   ├── cuda_v1/     # Linux adapter (PEFT format, ~57% accuracy)
│   │   └── registry.yaml # Adapter metadata and defaults
│   ├── faiss_index.bin  # Similarity search index
│   ├── labeled_examples.parquet  # Few-shot training examples
│   ├── embedder_info.json  # FAISS embedder config (REQUIRED)
│   └── archive/         # Legacy versions
├── taxonomies/          # Platform feature definitions (features*.yml)
├── sidecar_extractor/   # Air-gapped feature extraction
├── scripts/             # Utility scripts (demos, migrations, tests)
├── tests/               # Pytest suite
│   ├── unit/            # Unit tests
│   ├── integration/     # Integration tests
│   ├── architecture/    # Architecture validation tests
│   └── fixtures/        # Test data files (psirt_corpus.json)
├── docs/                # Documentation
│   ├── ARCHITECTURE_AND_WORKFLOW.md  # System architecture
│   ├── API_AND_FEATURES.md           # API reference
│   ├── CHANGELOG_V3.md               # Version history
│   └── archive/                       # Historical docs
├── vulnerability_db.sqlite  # SQLite database
├── mlx_inference.py     # MLX inference (primary)
└── version_matcher.py   # Version comparison logic
```

---

## Common Tasks

**Load bugs from CSV:**
```bash
python backend/db/load_bugs.py bugs/Cat9Kbugs_IOSXE_17.csv --platform IOS-XE
```

**Rebuild FAISS index:**
```bash
python build_faiss_index.py
```

**Air-gapped extraction:**
```bash
# On air-gapped network
python sidecar_extractor/extract_iosxe_features_standalone.py \
  --config device-config.txt --output snapshot.json
```

**Add new feature label:**
1. Edit `taxonomies/features*.yml`
2. Add `config_regex` and `show_cmds`
3. Rebuild FAISS index if retraining

---

## Troubleshooting

**Backend won't start:**
```bash
tail -f backend/logs/server.log
ls -lh vulnerability_db.sqlite
```

**Frontend build errors:**
```bash
rm -rf frontend/node_modules/.vite
cd frontend && npm install && npm run dev
```

**FAISS index errors:**
```bash
python build_faiss_index.py
ls -lh models/faiss_index.bin
```

**Low model accuracy:**
- Check FAISS index is current
- Verify platform matches taxonomy
- Review confidence score (≥75% = high)

**Missing embedder_info.json (500 errors on PSIRT analysis):**
- This file is REQUIRED for FAISS similarity search
- Verify it exists at `models/embedder_info.json`
- Contains embedder model config: `{"model_name": "sentence-transformers/all-MiniLM-L6-v2", "dimension": 384, ...}`
- Referenced by `fewshot_inference.py`, `build_faiss_index.py`, `query_fewshot_faiss.py`

**Missing psirt_corpus.json (test failures):**
- Required for architecture tests in `tests/architecture/`
- Verify it exists at `tests/fixtures/psirt_corpus.json`
- Contains golden-path PSIRT test corpus for validation

**Platform adapter issues:**
- Mac: Verify MLX adapter exists at `models/adapters/mlx_v1/`
- Linux: Verify CUDA adapter exists at `models/adapters/cuda_v1/`
- Check `models/adapters/registry.yaml` for adapter metadata
- Install PEFT on Linux: `pip install peft`
- **See [docs/SETUP_GUIDE.md#cudaLinux-troubleshooting](docs/SETUP_GUIDE.md#cudalinux-troubleshooting)** for step-by-step CUDA verification

**ISE/Device connection credentials:**
- Copy `.env.example` to `.env` and fill in your credentials
- ISE client (`backend/core/ise_client.py`) requires: `ISE_HOST`, `ISE_USERNAME`, `ISE_PASSWORD`
- Device verifier (`device_verifier.py`) requires: `DEVICE_HOST`, `DEVICE_USERNAME`, `DEVICE_PASSWORD`
- Scripts will exit with instructions if required password env vars are missing

---

## What's New (v4.5)

- **Low-RAM Mac Support** - New Option C for 16GB Macs
  - `setup_mac_lowram.sh` - Downloads and quantizes model to 4-bit
  - ~65% accuracy (vs ~71% full precision), ~8-10GB RAM (vs ~32GB)
  - Auto-detects mode via `models/lowram_config.json` or `LOWRAM_MODE` env var
- **Distribution Ready** - Cleaned up repository for sharing
  - Removed `.claude/`, `archived/`, `future_architecture/` from version control
  - Redacted exposed Google API key from `docs/archive/SETUP_COMPLETE.md`
  - Reduced repo size by ~150 files (dev-only artifacts)
- **Security Hardening** - Production-safe defaults
  - `DEV_MODE` now defaults to `false` (was `true`) - requires explicit opt-in for dev mode
- **Documentation Updates** - Synchronized all version references
  - Updated README.md to v4.5 with accurate performance metrics
  - Corrected database record counts (9,705 total: 9,617 bugs + 88 PSIRTs)

### Previous (v4.4)

- **Repository Cleanup** - Removed duplicate files and reorganized legacy content
  - Deleted duplicate model files (~12MB saved)
  - Archived 8 frontier batch YAMLs to `archived/frontier_batches/`
  - Updated `docs/ORPHANED_FILES.md` v2.0 with cleanup summary
- **Leaner Codebase** - Reduced orphaned items from ~30 to 7
  - Temp files, obsolete directories removed
  - Internal docs properly organized

### Previous (v4.3)

- **Security Hardening** - Removed hardcoded credentials from source code
  - ISE client and device verifier now use environment variables
  - Added `.env.example` template with all required credentials
  - Scripts exit with helpful instructions if passwords not set
- **Air-Gap Deployment Guide** - Complete offline deployment workflow
  - `docs/AIR_GAP_DEPLOYMENT.md` - Portable `HF_HOME` configuration
  - ~18GB package with pre-cached models for USB transfer
  - Step-by-step instructions for internet-connected and air-gapped machines
- **Data Ingestion Guide** - Adding new labeled vulnerabilities
  - `docs/ADDING_LABELED_DATA.md` - Three methods: API fetch, manual, direct insert
  - Workflow diagrams and taxonomy reference
  - Troubleshooting for common ingestion issues

### Previous (v4.2)

- **Unified Interactive Documentation System** - Consistent styled docs accessible via API
  - `/api/v1/docs-hub` - Central navigation hub with quick links and stats
  - `/api/v1/tutorial`, `/api/v1/admin-guide`, `/api/v1/setup-guide` - Styled HTML docs
  - `/api/v1/api-reference`, `/api/v1/redoc` - Swagger/ReDoc with navigation bar
  - Consistent navigation across all documentation pages
- **Platform-Aware System Health** - Health tray now correctly detects platform-specific adapters
  - Detects Mac (MLX/MPS) vs Linux (CUDA) vs CPU environments
  - Shows correct adapter path and status for current platform
  - Frontend displays platform, backend, and device info
- **Improved Test Infrastructure** - Cross-platform test utilities
  - `tests/unit/test_platform_detection.py` - 16 new platform detection tests
  - `tests/fixtures/psirt_corpus.json` - Golden-path test corpus
  - Updated architecture tests for cross-platform compatibility

### Previous (v4.0)

- **Multi-Platform Adapter Architecture** - Fresh clone works on Mac (MLX) and Linux (CUDA)
  - `models/adapters/mlx_v1/` - Mac adapter (~71% accuracy, MLX format)
  - `models/adapters/cuda_v1/` - Linux adapter (~57% accuracy, PEFT format)
  - `models/adapters/registry.yaml` - Adapter metadata and platform defaults
- **Shared Data Files** - Cross-platform data used by both adapters
- **PEFT Integration** - `transformers_inference.py` now loads CUDA adapter via HuggingFace PEFT
- **Required Data Files** - `models/embedder_info.json` and `tests/fixtures/psirt_corpus.json` now tracked in git

### Previous (v3.2)

- **3-Tier Hybrid Intent Classification** - Robust query routing for AI Assistant
  - Tier 1: Quick override (~0ms) - keyword combinations
  - Tier 2: Keyword scoring (~1ms) - scores all intents, picks best
  - Tier 3: LLM fallback (~1-2s) - handles ambiguous queries
- **New AI Assistant Intents** - PRIORITIZE, DEVICES_BY_RISK, DEVICE_VULNERABILITIES

### Previous (v3.1)

- **Unified Bug/PSIRT Scanning** - Separate counts for bugs and PSIRTs
- **AI Assistant Dashboard** - Clear inventory vs database metrics
- **PSIRT Platform Cleanup** - 88 PSIRTs with proper platform assignments

> **Full Changelog:** See **[docs/CHANGELOG_V4.2.md](docs/CHANGELOG_V4.2.md)** for v4.2 release notes, or **[docs/CHANGELOG_V3.md](docs/CHANGELOG_V3.md)** for previous versions.

---

## Next Steps / Future Work

**In Progress:**
- Version comparison for upgrade planning

**Planned:**
- Batch PSIRT analysis
- CSV upload for bulk scanning
- Better version range parsing (SMUs, interim builds)
- Sidecar extractors for IOS-XR, ASA, FTD, NX-OS

---

## Additional Documentation

| Category | Documents |
|----------|-----------|
| **Architecture** | `docs/ARCHITECTURE_AND_WORKFLOW.md` |
| **API Reference** | `docs/API_AND_FEATURES.md` |
| **Database** | `backend/db/README_VULN_DB.md`, `VULNERABILITY_DB_PROJECT_PLAN.md` |
| **Features** | `FEATURE_AWARE_SCANNING.md`, `HARDWARE_FILTERING_PLAN.md` |
| **Air-Gapped** | `sidecar_extractor/README.md` |
| **Scripts** | `scripts/README.md` |
| **Legacy** | `docs/archive/` |

---

**TL;DR:** Full-stack Cisco PSIRT/bug analysis system. 9,617 bugs + 88 PSIRTs across 5 platforms. Three-tier caching (<10ms to 2s). Hardware + feature filtering = 85%+ false positive reduction. ISE integration with device inventory. Production ready.

> Use MCP context7 to review documentation for new tools as needed.
