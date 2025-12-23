# File Structure Documentation

**Version:** 1.1 | **Last Updated:** December 19, 2025

This document maps every file and directory in the project to its purpose, function, and connections to other components.

---

## Table of Contents

1. [Root Directory](#1-root-directory)
2. [Backend (`backend/`)](#2-backend)
3. [Frontend (`frontend/`)](#3-frontend)
4. [Scripts (`scripts/`)](#4-scripts)
5. [Models (`models/`)](#5-models)
6. [Taxonomies (`taxonomies/`)](#6-taxonomies)
7. [Tests (`tests/`)](#7-tests)
8. [Documentation (`docs/`)](#8-documentation)
9. [Data Directories](#9-data-directories)
10. [Development/Legacy Directories](#10-developmentlegacy-directories)

---

## 1. Root Directory

### Core Application Files (ACTIVE)

| File | Purpose | Used By |
|------|---------|---------|
| `mlx_inference.py` | **PRIMARY** - MLX-based PSIRT labeler with LoRA adapter | `backend/core/sec8b.py`, `tests/architecture/` |
| `fewshot_inference.py` | Few-shot PSIRT labeler with FAISS similarity search | `predict_and_verify.py`, `scripts/verify_ingestion.py`, `transformers_inference.py` |
| `version_matcher.py` | Version comparison logic (root-level module) | `device_verifier.py`, `tests/unit/test_version_matcher.py` |
| `device_verifier.py` | Device SSH connector and PSIRT verifier | `backend/core/verifier.py`, `scripts/tests/test_device_verification.py` |
| `extract_device_features.py` | Feature extraction from live devices via SSH | `backend/api/routes.py`, `backend/core/device_inventory.py` |
| `predict_and_verify.py` | PSIRT verification pipeline (MLX or Transformers) | `backend/core/sec8b.py` |
| `transformers_inference.py` | Alternative transformers-based labeler (non-MLX) | `predict_and_verify.py`, `scripts/offline_update_packager.py` |

### Configuration & Setup

| File | Purpose |
|------|---------|
| `CLAUDE.md` | Main project documentation and quick start |
| `README.md` | Public-facing project overview |
| `.env` | Environment variables (API keys, database paths) |
| `.gitignore` | Git ignore patterns |
| `requirements.txt` | Python production dependencies |
| `requirements-test.txt` | Python test dependencies |
| `pytest.ini` | Pytest configuration |
| `setup_env.sh` | Linux environment setup script |
| `setup_mac_env.sh` | macOS/Apple Silicon setup script |
| `run_tests.sh` | Test runner script |

### Database - CRITICAL ASSET

| File | Purpose |
|------|---------|
| `vulnerability_db.sqlite` | **CORE DATA ASSET** - The "secret sauce" of the system |

> ⚠️ **MUST BE VERSION CONTROLLED** - This database contains all curated, labeled vulnerability data:
> - **9,705 vulnerabilities** (bugs + PSIRTs) with feature labels
> - **272,524 version index entries** for fast version matching
> - **1,002 label index mappings** for feature-based filtering
> - **Device inventory** with scan results
>
> This data represents significant effort: Cisco API fetching, LLM labeling, and human curation.
> Without this database, the application is an empty shell. The ML model, FAISS index, and this
> database are the three pillars of the system.

---

## 2. Backend (`backend/`)

### Entry Point

| File | Purpose | Connections |
|------|---------|-------------|
| `app.py` | FastAPI application entry point | Imports all routers, configures CORS, rate limiting |
| `run_server.sh` | Server startup script | Runs uvicorn with app.py |

### API Layer (`backend/api/`)

| File | Purpose | Database Tables |
|------|---------|-----------------|
| `routes.py` | Core API routes (`/analyze-psirt`, `/scan-device`, `/verify-*`) | `vulnerabilities`, in-memory cache |
| `inventory_routes.py` | Device inventory routes (`/inventory/*`) | `device_inventory` |
| `reasoning_routes.py` | AI reasoning routes (`/reasoning/*`) | `device_inventory`, `vulnerabilities` |
| `system_routes.py` | System admin routes (`/system/*`) | `vulnerabilities`, `db_metadata` |
| `review_routes.py` | Review queue routes (low-confidence analyses) | In-memory cache |
| `models.py` | Pydantic request/response models | N/A (type definitions) |
| `export.py` | Export functionality | N/A |

### Core Logic (`backend/core/`)

| File | Purpose | Dependencies |
|------|---------|--------------|
| `sec8b.py` | SEC-8B analyzer wrapper with 3-tier caching | `mlx_inference.py`, `predict_and_verify.py`, FAISS index |
| `db_scanner.py` | Database bug/PSIRT scanner | `vulnerability_db.sqlite` |
| `vulnerability_scanner.py` | Scanner facade (routes to db_scanner) | `db_scanner.py` |
| `scan_router.py` | Scan routing logic | `db_scanner.py`, `ai_analyzer.py` |
| `ai_analyzer.py` | AI-based bug analysis | `mlx_inference.py` |
| `verifier.py` | Device verification orchestrator | `device_verifier.py` (root) |
| `device_inventory.py` | Device inventory manager | `device_inventory` table, `extract_device_features.py` |
| `ise_client.py` | Cisco ISE API client | External ISE API |
| `ise_client_mock.py` | Mock ISE client for development | N/A |
| `reasoning_engine.py` | AI reasoning/natural language interface | `device_inventory`, `vulnerabilities`, intent classification |
| `version_matcher.py` | Version comparison logic (backend copy) | N/A |
| `version_patterns.py` | Version pattern detection | N/A |
| `updater.py` | Offline update processor | `vulnerability_db.sqlite` |
| `config.py` | Backend configuration | Environment variables |

### Database Layer (`backend/db/`)

| File | Purpose |
|------|---------|
| `vuln_schema.sql` | SQLite schema definition |
| `cache.py` | In-memory analysis cache |
| `load_bugs.py` | Bug CSV loader |
| `load_psirts.py` | PSIRT loader |
| `load_labeled_bugs_json.py` | Labeled bugs JSON loader |
| `incremental_update.py` | Incremental database updates |
| `hardware_extractor.py` | Hardware model extraction from product names |
| `get_last_update.py` | Get last update timestamp |
| `test_vuln_db.py` | Database unit tests |
| `utils.py` | Database utilities |
| `README_VULN_DB.md` | Database documentation |

---

## 3. Frontend (`frontend/`)

### Configuration

| File | Purpose |
|------|---------|
| `package.json` | NPM dependencies and scripts |
| `vite.config.ts` | Vite bundler configuration |
| `tsconfig.json` | TypeScript configuration |

### Source (`frontend/src/`)

#### Entry Points

| File | Purpose |
|------|---------|
| `main.tsx` | React application entry point |
| `App.tsx` | Main application component with tab navigation |

#### API Layer (`frontend/src/api/`)

| File | Purpose | Backend Routes |
|------|---------|----------------|
| `client.ts` | Axios API client with namespaced methods | All `/api/v1/*` routes |
| `config.ts` | API configuration (base URL, headers) | N/A |

#### Components (`frontend/src/components/`)

| Component | Purpose | API Endpoints Used |
|-----------|---------|-------------------|
| `AIAssistant.tsx` | AI chat interface + security dashboard | `/reasoning/summary`, `/reasoning/ask` |
| `InventoryManager.tsx` | Device inventory management | `/inventory/*` |
| `ScannerForm.tsx` | Bug scanner input form | `/scan-device`, `/extract-features` |
| `ScanResults.tsx` | Bug scan results display | N/A (receives props) |
| `AnalyzeForm.tsx` | PSIRT analysis input form | `/analyze-psirt` |
| `ResultsDisplay.tsx` | PSIRT analysis results | N/A (receives props) |
| `DeviceForm.tsx` | SSH device verification form | `/verify-device` |
| `SnapshotForm.tsx` | Snapshot verification form | `/verify-snapshot` |
| `VerificationReport.tsx` | Verification results display | N/A (receives props) |
| `SystemAdmin.tsx` | System administration panel | `/system/*` |
| `ReviewQueue.tsx` | Low-confidence analysis review | `/review/*` |
| `SSHCredentialsModal.tsx` | Secure SSH credential input | N/A (modal) |
| `ThemeToggle.tsx` | Dark/light mode toggle | N/A |

#### Types (`frontend/src/types/`)

| File | Purpose |
|------|---------|
| `index.ts` | Core type definitions (Bug, ScanResult, etc.) |
| `reasoning.ts` | Reasoning API types |
| `system.ts` | System admin types |

#### Context (`frontend/src/context/`)

| File | Purpose |
|------|---------|
| `ThemeContext.tsx` | Theme provider (dark/light mode) |

---

## 4. Scripts (`scripts/`)

### Data Pipeline (ACTIVE)

| Script | Purpose | Outputs |
|--------|---------|---------|
| `build_faiss_index.py` | Build FAISS similarity index | `models/faiss_index.bin` |
| `cisco_vuln_fetcher.py` | Fetch bugs/PSIRTs from Cisco APIs | JSON data files |
| `fetch_psirt_versions.py` | Fetch PSIRT version data | Updates `vulnerability_db.sqlite` |
| `ingest_parquet.py` | Ingest labeled examples to DB | Updates `vulnerability_db.sqlite` |
| `ingest_frontier_labels.py` | Ingest frontier taxonomy batches | Updates `vulnerability_db.sqlite` |
| `offline_update_packager.py` | Create offline update packages | ZIP packages |
| `apply_offline_update.py` | Apply offline update packages | Updates database |

### Training & Evaluation

| Script | Purpose |
|--------|---------|
| `train_lora_cuda.py` | Train LoRA adapter (CUDA) |
| `synthesize_reasoning_*.py` | Generate CoT training data |
| `evaluate_lora_comprehensive.py` | Evaluate LoRA adapter |
| `benchmark_*.py` | Various benchmarking scripts |
| `prepare_training_data.py` | Prepare training datasets |
| `cleanup_training_data.py` | Clean contaminated training data |

### Utilities

| Script | Purpose |
|--------|---------|
| `enrich_taxonomy_definitions.py` | Enrich taxonomy with definitions |
| `standardize_labels.py` | Normalize label formats |
| `cleanup_duplicate_devices.py` | Remove duplicate device entries |

### Migrations (`scripts/migrations/`)

| Script | Purpose |
|--------|---------|
| `migration_device_inventory.py` | Create device_inventory table |
| `migration_add_hardware_model.py` | Add hardware_model column |
| `migration_add_device_unique_constraint.py` | Add unique constraint |
| `migration_scan_results_table.py` | Create scan_results table |
| `backfill_hardware_models.py` | Backfill hardware model data |

### Tests (`scripts/tests/`)

| Script | Purpose |
|--------|---------|
| `test_comprehensive_system.py` | Full system integration test |
| `test_device_verification.py` | Device verification tests |
| `test_hardware_filtering.py` | Hardware filtering tests |
| `test_faiss_improvement.py` | FAISS performance tests |
| `test_psirt_cache.py` | PSIRT caching tests |

### Demos (`scripts/demos/`)

| Script | Purpose |
|--------|---------|
| `demo_scan_simple.py` | Simple scanning demo |
| `demo_scan_feature_aware.py` | Feature-aware scanning demo |

---

## 5. Models (`models/`)

### Active Model Artifacts

| File | Purpose | Used By |
|------|---------|---------|
| `faiss_index.bin` | FAISS similarity index (symlink → v2) | `mlx_inference.py`, `fewshot_inference.py` |
| `labeled_examples.parquet` | Training examples (symlink → v2) | FAISS index building |
| `lora_adapter/` | LoRA adapter directory (symlink → v3) | `mlx_inference.py` |
| `embedder_info.json` | **REQUIRED** - Embedder config for FAISS | `fewshot_inference.py`, `build_faiss_index.py`, `query_fewshot_faiss.py` |

> ⚠️ **embedder_info.json is REQUIRED** - If missing, PSIRT analysis API calls will fail with 500 errors.
> Contains: `{"model_name": "sentence-transformers/all-MiniLM-L6-v2", "dimension": 384, ...}`

### Platform-Specific Adapters (`models/adapters/`)

| Directory | Platform | Format | Accuracy |
|-----------|----------|--------|----------|
| `mlx_v1/` | Mac (Apple Silicon) | MLX format | ~71% |
| `cuda_v1/` | Linux (NVIDIA GPU) | PEFT format | ~57% |
| `registry.yaml` | N/A | Adapter metadata | N/A |

### Evaluation Artifacts

| File | Purpose |
|------|---------|
| `evaluation_test_set.json` | Test set for model evaluation |
| `evaluation_test_set_cleaned.json` | Cleaned test set |
| `eval_results_v*.json` | Evaluation results by version |
| `benchmark_results.json` | Benchmark results |

### Configuration

| File | Purpose |
|------|---------|
| `lora_config.yaml` | LoRA training configuration |
| `lora_training_config.json` | Additional training config |
| `label_canonical_map.json` | Label normalization mapping |
| `fail_label_confusion_map.json` | Fail label analysis |

### Archive (`models/archive/`)

| Directory | Purpose |
|-----------|---------|
| `eval_history/` | Historical evaluation results |
| `faiss_index_*.bin` | Previous FAISS index versions |
| `labeled_examples_*.parquet` | Previous training data versions |
| `lora_adapter_v*/` | Previous LoRA adapter versions |

---

## 6. Taxonomies (`taxonomies/`)

### Feature Definitions

| File | Platform | Label Count |
|------|----------|-------------|
| `features.yml` | IOS-XE (default) | ~70 labels |
| `features_iosxr.yml` | IOS-XR | ~22 labels |
| `features_asa.yml` | ASA | ~46 labels |
| `features_nxos.yml` | NX-OS | ~25 labels |

### Supporting Files

| File | Purpose |
|------|---------|
| `Label_keywords.py` | Keyword-to-label mapping |
| `labels_*_v1.json` | Platform-specific label packs |

---

## 7. Tests (`tests/`)

### Test Structure

| Directory | Purpose |
|-----------|---------|
| `unit/` | Unit tests for individual components |
| `integration/` | Integration tests for API endpoints |
| `e2e/` | End-to-end workflow tests |
| `architecture/` | Architecture validation tests |
| `manual/` | Manual test scripts |
| `fixtures/` | Test data fixtures (REQUIRED) |

### Required Test Fixtures

| File | Purpose | Used By |
|------|---------|---------|
| `fixtures/psirt_corpus.json` | **REQUIRED** - Golden-path PSIRT test corpus | `tests/architecture/test_refactor.py` |

> ⚠️ **psirt_corpus.json is REQUIRED** - If missing, architecture tests will fail.
> Contains PSIRTs and bugs for testing the refactored inference pipeline.

### Key Test Files

| File | Purpose |
|------|---------|
| `conftest.py` | Pytest fixtures and configuration |
| `test_framework_setup.py` | Framework validation |
| `unit/test_version_matcher.py` | Version matching tests |
| `unit/test_taxonomy_loader.py` | Taxonomy loading tests |
| `unit/test_reasoning_engine.py` | Reasoning engine tests |
| `unit/test_platform_detection.py` | MLX/CUDA platform detection tests (16 tests) |
| `integration/test_api_endpoints.py` | API endpoint tests |
| `integration/test_reasoning_api.py` | Reasoning API tests |
| `architecture/helpers.py` | Cross-platform test helpers with `get_inference_module()` |
| `architecture/test_refactor.py` | Architecture validation tests |

---

## 8. Documentation (`docs/`)

### Active Documentation

| Document | Purpose |
|----------|---------|
| `DATA_FLOW_DOCUMENTATION.md` | Comprehensive data flow documentation |
| `UI_DATA_FLOWS.md` | UI-to-database mapping |
| `ARCHITECTURE_AND_WORKFLOW.md` | System architecture |
| `API_AND_FEATURES.md` | API reference |
| `CHANGELOG_V3.md` | Version history |
| `README.md` | Documentation index |

### Integration Guides (`docs/integration/`)

| Document | Purpose |
|----------|---------|
| `api_specs.md` | API specifications |
| `data_model.md` | Data model documentation |
| `ise_workflows.md` | ISE integration workflows |
| `scanning.md` | Scanning documentation |
| `version_comparison.md` | Version comparison guide |

### Archive (`docs/archive/`)

Historical documentation from previous development phases.

---

## 9. Data Directories

### `data/`

| Directory/File | Purpose |
|----------------|---------|
| `Labeled_Bugs/` | Labeled bug datasets (JSON) |
| `synthetic_*.json` | Synthetic training data |

### `output/`

| Directory/File | Purpose |
|----------------|---------|
| `bugs.json` | Fetched bug data |
| `psirts.json` | Fetched PSIRT data |
| `enrichment_logs/` | Enrichment process logs |

### `logs/`

Training and evaluation logs.

---

## 10. Development/Legacy Directories

### `archived/`

Legacy code organized by category:
- `legacy_ml/` - Old ML training code
- `legacy_ui/` - Old UI code
- `llama_finetuning/` - LLaMA fine-tuning experiments
- `openai_verification/` - OpenAI verification scripts
- `prototyping_phase/` - Early prototyping code
- `training_data/` - Old training data scripts

### `future_architecture/`

Planned features and architecture:
- `ai/prompts/` - AI prompt templates
- `backend/worker/` - Worker architecture (planned)
- `docs/` - Future architecture documentation
- `scripts/` - Future pipeline scripts
- `pending_updates/` - Updates awaiting application

### `transfer_package/`

Files for transferring to Linux training machine.

### `sidecar_extractor/`

Air-gapped feature extraction tools:
- `extract_iosxe_features_standalone.py` - Standalone IOS-XE extractor
- `README.md` - Usage documentation

---

## Quick Reference: File → Function Map

### Core Inference Chain

```
User Request
    ↓
backend/app.py
    ↓
backend/api/routes.py (analyze_psirt)
    ↓
backend/core/sec8b.py (PSIRTAnalyzer)
    ↓
mlx_inference.py (MLXPSIRTLabeler)
    ↓
models/lora_adapter/ (LoRA weights)
    ↓
models/faiss_index.bin (similarity search)
    ↓
taxonomies/features.yml (label definitions)
```

### Database Scanning Chain

```
User Request
    ↓
backend/app.py
    ↓
backend/api/routes.py (scan_device)
    ↓
backend/core/vulnerability_scanner.py (facade)
    ↓
backend/core/db_scanner.py (DatabaseScanner)
    ↓
vulnerability_db.sqlite
    ├── vulnerabilities table
    ├── version_index table
    └── label_index table
```

### Device Inventory Chain

```
User Request
    ↓
backend/api/inventory_routes.py
    ↓
backend/core/device_inventory.py
    ↓
vulnerability_db.sqlite
    └── device_inventory table
```

---

**Document Version:** 1.1
**Last Updated:** December 19, 2025
