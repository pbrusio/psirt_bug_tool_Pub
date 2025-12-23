# Orphaned Files Documentation

**Version:** 3.0 | **Last Updated:** December 22, 2025 | **Branch:** alpha/4.5

This document tracks files that may have no active purpose in production.

---

## v4.5 Distribution Cleanup

The following directories were removed from version control (added to `.gitignore`):

| Directory | Files Removed | Reason |
|-----------|---------------|--------|
| `.claude/` | 7 | Developer-specific Claude Code agent configs |
| `archived/` | 106 | Legacy code, prototyping artifacts - not needed for runtime |
| `future_architecture/` | 40 | Planned/roadmap features - not implemented |
| **Total** | **153 files** | Reduced distribution size |

These directories still exist locally for development but are excluded from the repository.

---

## v4.4 Cleanup Summary

The following items were addressed in v4.4:

| Category | Action Taken |
|----------|--------------|
| Root temp files (5) | Deleted |
| Temp directories (2) | Deleted |
| `Setup/` directory | Deleted |
| `12_11_Overnight/` directory | Deleted |
| `transfer_package/` directory | Deleted |
| Duplicate model files (2) | Deleted (~12MB saved) |
| Frontier batch YAMLs (8) | Archived (now gitignored) |
| Internal planning docs (2) | Moved to `docs/internal/` |
| Obsolete checklists (2) | Deleted |

---

## Classification System

| Status | Meaning |
|--------|---------|
| **ORPHAN** | No imports/references found, not used in production |
| **LEGACY** | Superseded by newer implementation |
| **INTERNAL** | Internal planning/documentation (not for production) |
| **KEEP** | Intentionally retained for future use |

---

## Remaining Items to Review

### Scripts Directory - Potentially Unused (ORPHAN)

These scripts may or may not be actively used. Verify before removal:

| File | Purpose | Notes |
|------|---------|-------|
| `scripts/close_loop.py` | Close loop training | Check if used in pipeline |
| `scripts/curate_gold_eval.py` | Gold evaluation curation | May be needed for retraining |
| `scripts/enrich_bugs.py` | Bug enrichment | Check if used |
| `scripts/prune_data_for_training.py` | Data pruning | May be needed for retraining |
| `scripts/self_train.py` | Self-training loop | Check if used |
| `scripts/taxonomy_alignment.py` | Taxonomy alignment | Check if used |
| `scripts/verify_ingestion.py` | Verify data ingestion | Utility - likely keep |

**Recommendation:** These are training/evaluation utilities. Keep for potential retraining unless confirmed unused.

---

## Properly Organized (KEEP)

### `docs/internal/` Directory

Internal planning documents moved from root:

| File | Purpose |
|------|---------|
| `docs/internal/PROJECT_AUDIT.md` | Internal project evaluation |
| `docs/internal/PSIRT_BUG_INTEGRATION_PLAN.md` | Phase 2 planning |

### `docs/archive/` Directory

Historical documentation (~40+ files) - kept for reference.

---

## Models Directory

### Active Files (KEEP)

| File | Purpose |
|------|---------|
| `models/faiss_index.bin` | FAISS similarity index (10.3MB) |
| `models/labeled_examples.parquet` | Training examples (1.1MB) |
| `models/embedder_info.json` | **REQUIRED** - Embedder config |
| `models/adapters/` | Platform-specific LoRA adapters |

---

## Summary Statistics

### v4.5 Distribution Results

| Category | Count |
|----------|-------|
| Directories gitignored | 3 |
| Files removed from tracking | 153 |
| Remaining review items | 7 scripts |

### Remaining Review Items

| Category | Count | Recommendation |
|----------|-------|----------------|
| Potentially unused scripts | 7 | Verify before removal |
| Internal docs | 2 | Keep in `docs/internal/` |

---

## Changelog

### v3.0 (December 22, 2025)
- Updated for v4.5 distribution cleanup
- Documented removal of `archived/`, `future_architecture/`, `.claude/` from version control
- Simplified document since most orphan directories are now gitignored

### v2.0 (December 21, 2025)
- Updated after v4.4 cleanup
- Marked resolved items as complete
- Reduced active orphan list from ~30 items to ~7

### v1.0 (December 16, 2025)
- Initial orphaned files audit

---

**Document Version:** 3.0
**Last Updated:** December 22, 2025
