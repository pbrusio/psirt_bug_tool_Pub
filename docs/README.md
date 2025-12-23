# Documentation

This directory contains all project documentation.

## Active Documentation (Root Directory)

### Essential Docs
- **`CLAUDE.md`** - Complete project overview and technical guide (START HERE)
- **`README.md`** - Quick start and project summary

### Operations Guides
- **`AIR_GAP_DEPLOYMENT.md`** - Deploying to air-gapped networks (HF_HOME portability, ~18GB package)
- **`ADDING_LABELED_DATA.md`** - Adding new labeled bugs/PSIRTs (API fetch, manual, direct insert)

### Architecture & API Docs (docs/)
- **`ARCHITECTURE_AND_WORKFLOW.md`** - System architecture, workflow diagrams (Mermaid), dependency map, offline update workflow
- **`API_AND_FEATURES.md`** - Complete API reference, all endpoints, feature documentation, system administration API

### Planning & Implementation Docs
- **`PSIRT_BUG_INTEGRATION_PLAN.md`** - Phase 2 roadmap (ISE integration, unified scanning)
- **`HARDWARE_FILTERING_PLAN.md`** - Hardware filtering implementation plan
- **`HARDWARE_FILTERING_TEST_REPORT.md`** - Production readiness test report
- **`VULNERABILITY_DB_PROJECT_PLAN.md`** - Database architecture and design
- **`FEATURE_AWARE_SCANNING.md`** - Database scanning technical deep-dive

## Archived Documentation

Historical documentation is in `docs/archive/`:

### Legacy Pipelines
- `PHASE1_COMPLETE.md` - Original pipeline completion report
- `PROJECT_COMPLETE.md` - Phase 1 project summary
- `PROJECT_SUMMARY.md` - High-level project overview
- `PIPELINE_README.md` - Legacy data processing pipeline

### ML Model History
- `RESULTS.md` - Model performance comparisons
- `RECOMMENDATIONS.md` - Production deployment recommendations
- `QUANTIZATION_RESULTS.md` - 4-bit vs 8-bit quantization analysis
- `baseline_results_summary.md` - Initial ML baseline results
- `expanded_training_results.md` - Extended training experiments

### Data Quality
- `GPT4O_RELABELING_SUMMARY.md` - GPT-4o label verification results
- `OPENAI_VERIFICATION_README.md` - Label verification process
- `VALIDATION_WORKFLOW.md` - Data validation workflow
- `QUICK_START_VALIDATION.md` - Validation quick start

### Feature Enhancements
- `MPLS_ENHANCEMENT_SUMMARY.md` - MPLS bug integration
- `mpls_enhancement_results.md` - MPLS-specific analysis
- `CSV_ENRICHMENT_COMPLETE.md` - CSV enrichment process

### UI Development
- `UI_PREVIEW.md` - Early UI screenshots
- `UI_SCANNER_INTEGRATION.md` - Scanner integration guide
- `FRONTEND_DESIGN.md` - Frontend architecture
- `FRONTEND_IMPLEMENTATION.md` - Implementation details

### Quick Fixes & Troubleshooting
- `QUICK_FIX.md` - Quick bug fixes
- `TAXONOMY_FIX_SNMP_TRAPS.md` - SNMP taxonomy fixes
- `SNAPSHOT_TROUBLESHOOTING.md` - Snapshot workflow debugging
- `TESTING.md` - Testing strategy

### Setup & Configuration
- `SETUP_COMPLETE.md` - Initial setup completion
- `QUICKSTART.md` - Legacy quick start (superseded by CLAUDE.md)
- `QUICKSTART_WEB.md` - Web interface quick start
- `SEC8B_SETUP_GUIDE.md` - SEC-8B model setup
- `VULN_DB_QUICK_START.md` - Database quick start
- `BUG_LABELING_INSTRUCTIONS.md` - Gemini labeling instructions
- `FEATURE_EXTRACTOR_README.md` - Feature extractor guide
- `FEATURE_SNAPSHOT_IMPLEMENTATION.md` - Snapshot implementation
- `SNAPSHOT_QUICK_START.md` - Air-gapped workflow guide

## Reference Documentation

### `Command_Config_Ref_Docs/`
Cisco command and configuration reference materials for feature extraction and verification command generation.

## Documentation Updates

When updating documentation:
1. **Active features:** Update main docs in root directory
2. **Historical records:** Keep in `docs/archive/` for reference
3. **CLAUDE.md:** Keep as canonical source of truth
4. **README.md:** Keep synced with CLAUDE.md (user-facing)

## Quick Links

- **Start Here:** `../CLAUDE.md`
- **Architecture:** `ARCHITECTURE_AND_WORKFLOW.md`
- **API Reference:** `API_AND_FEATURES.md` or http://localhost:8000/docs (when backend running)
- **System Admin:** `ARCHITECTURE_AND_WORKFLOW.md#10-system-administration--offline-updates`
- **Database Schema:** `../backend/db/README_VULN_DB.md`
- **Sidecar Extractor:** `../sidecar_extractor/README.md`
