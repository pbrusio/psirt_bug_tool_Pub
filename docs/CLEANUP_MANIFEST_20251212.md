# Cleanup Manifest - December 12, 2025

This document records all files removed during the alpha/pre-launch branch cleanup.
All removals were verified to not break functionality before deletion.

## Pre-Cleanup Verification

All systems verified working before cleanup:
- [x] Backend imports (app, models, routes, core modules)
- [x] Rate limiting middleware present
- [x] Host validation working (accepts valid IPs/FQDNs, rejects invalid)
- [x] Frontend builds successfully (141 modules, 701ms)
- [x] MLX inference module loads
- [x] Model artifacts (FAISS, parquet, LoRA) aligned (7065 vectors)
- [x] Database integrity (9619 vulnerabilities, 10 devices)
- [x] Moved scripts importable

## Files Removed

### 1. output/*.json (178 files)
**Reason:** Cached inference outputs
**Status:** Already in `.gitignore`
**Impact:** None - regenerated on demand

### 2. tools/ directory (3 files)
**Reason:** Moved to `scripts/` directory
**Files:**
- `tools/__init__.py`
- `tools/apply_offline_update.py` → `scripts/apply_offline_update.py`
- `tools/offline_update_packager.py` → `scripts/offline_update_packager.py`

### 3. logs/ directory (3 files)
**Reason:** Log files - transient
**Status:** Already in `.gitignore`

### 4. llama_training_data/ (3 files)
**Reason:** Training data - managed separately
**Status:** Already in `.gitignore`

### 5. llama_lora_final/ (2 files)
**Reason:** Legacy LoRA adapter, superseded by `models/lora_adapter_v3`

### 6. tmp/ directory (2 files)
**Reason:** Temporary test files

### 7. Root-level files removed

| File | Reason | New Location |
|------|--------|--------------|
| `DATA_INGESTION_GUIDE.md` | Moved | `archived/analysis_reports/` |
| `OFFLINE_UPDATES_PLAN.md` | Moved | `archived/analysis_reports/` |
| `evaluate_v2_adapter.py` | Moved | `scripts/` |
| `analyze_labels.py` | Deprecated | `scripts/analyze_label_performance.py` replacement |
| `dashboard.py` | Legacy Streamlit UI | Reference in `archived/README.md` |
| `Prompt.txt` | Legacy prompt template | Referenced in docs only |
| `label_pack.json` | Legacy label pack | Referenced in archived docs |
| `gemini_enriched_PSIRTS_mrk1.csv` | Training data artifact | Not needed in repo |
| `Expected_Output.json` | Test artifact | Referenced in archived validator |
| `FRONTEND_DESIGN.md` | Historical | `docs/archive/` has reference |
| `FRONTEND_IMPLEMENTATION.md` | Historical | `docs/archive/` has reference |
| `IMPLEMENTATION_PLAN.md` | Completed | Not needed |
| `LABELING_PIPELINE_PLAN.md` | Completed | Not needed |
| `SELF_TRAINING_PLAN.md` | Completed | Not needed |
| `SESSION_SUMMARY_2025_12_12.md` | Session artifact | Not needed |

## Modified Files (to be reviewed)

The following files have uncommitted modifications:
- `frontend/` - UI updates (6 files)
- `scripts/` - Migration and cleanup scripts (4 files)
- `archived/README.md` - Updated during cleanup
- `transformers_inference.py` - Minor updates
- `vulnerability_db.sqlite` - Database with current data

## Post-Cleanup State

After this cleanup:
- Root directory contains only production code
- All scripts consolidated in `scripts/`
- Historical docs in `docs/archive/`
- Training data managed via `.gitignore`
- Model artifacts use symlink versioning
