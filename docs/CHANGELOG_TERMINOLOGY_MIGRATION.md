# Terminology Migration Changelog

**Date:** 2025-12-15
**Version:** Alpha v2.4
**Migration:** `vulnerabilities` → `bugs` terminology standardization

## Summary

This migration standardizes terminology across the codebase to properly distinguish between:

| Term | Definition | Source | User Relationship |
|------|------------|--------|-------------------|
| **Bug** | Software defect (CSCxxxx IDs) | Cisco Bug Search Tool | "Susceptible to" |
| **PSIRT/Advisory** | Security advisory (cisco-sa-xxxx) | Cisco Security Advisories | "Vulnerable to" |
| **Vulnerability** | Reserved for PSIRT/security context | General term | Use sparingly |

## Scope of Changes

### API Contract Changes (Breaking)

These changes affect the API response schema. Frontend must be updated simultaneously.

| Location | Old Property | New Property |
|----------|-------------|--------------|
| Scan results | `vulnerabilities` | `bugs` |
| Scan results | `total_vulnerabilities` | `total_bugs` |
| System stats | `total_vulnerabilities` | `total_bugs` |
| Inventory scan | `total_vulnerabilities` | `total_bugs` |

### Files Changed

#### Backend - API Layer

| File | Changes |
|------|---------|
| `backend/api/models.py` | Rename `Vulnerability` → `Bug`, `vulnerabilities` → `bugs` |
| `backend/api/routes.py` | Update response property names |
| `backend/api/inventory_routes.py` | Update all `vulnerabilities` → `bugs` references |
| `backend/api/system_routes.py` | Update `total_vulnerabilities` → `total_bugs` |
| `backend/api/export.py` | Update export field names |
| `backend/api/reasoning_routes.py` | Update response text |

#### Backend - Core Layer

| File | Changes |
|------|---------|
| `backend/core/vulnerability_scanner.py` | Keep class name, update return dict keys |
| `backend/core/db_scanner.py` | Update return dict keys |
| `backend/core/reasoning_engine.py` | Update user-facing text, remove anti-definitions |
| `backend/core/device_inventory.py` | Update property names |
| `backend/core/scan_router.py` | Update property names |

#### Backend - Database Layer

| File | Changes |
|------|---------|
| `backend/db/*.py` | Keep table name `vulnerabilities`, update comments only |

> **Note:** Database table `vulnerabilities` is NOT renamed. It's an internal implementation detail.

#### Frontend - Types

| File | Changes |
|------|---------|
| `frontend/src/types/index.ts` | `vulnerabilities` → `bugs`, `Vulnerability` → `Bug` |
| `frontend/src/types/system.ts` | `total_vulnerabilities` → `total_bugs` |

#### Frontend - Components

| File | Changes |
|------|---------|
| `frontend/src/components/ScanResults.tsx` | Update property references |
| `frontend/src/components/InventoryManager.tsx` | Update property references, user-facing text |
| `frontend/src/components/AIAssistant.tsx` | Update suggested questions, labels |
| `frontend/src/components/SystemAdmin.tsx` | Update property references |
| `frontend/src/components/DeviceForm.tsx` | Update user-facing text |
| `frontend/src/components/AnalyzeForm.tsx` | Update placeholder, button text |
| `frontend/src/App.tsx` | Update header, subtitle, tab, step header, footer |

#### Tests

| File | Changes |
|------|---------|
| `tests/unit/test_reasoning_engine.py` | Update assertions |
| `tests/integration/test_reasoning_api.py` | Update assertions |
| `tests/integration/test_api_endpoints.py` | Update property names |
| `scripts/tests/*.py` | Update property names |

#### Documentation

| File | Changes |
|------|---------|
| `CLAUDE.md` | Update terminology throughout |
| `docs/API_AND_FEATURES.md` | Update API documentation |

### NOT Changed (Intentionally)

| Item | Reason |
|------|--------|
| Database table `vulnerabilities` | Internal implementation, no user impact |
| Class `VulnerabilityScanner` | Internal class name, would require extensive refactor |
| File `vulnerability_scanner.py` | File rename is high-risk, low-value |
| Archived code (`archived/*`) | Legacy code, not in active use |
| Future architecture (`future_architecture/*`) | Not yet implemented |

## Additional Changes in This Migration

### 1. Remove Anti-Definitions from AI Responses
- File: `backend/core/reasoning_engine.py`
- Change: Remove anti-definition text from LABEL intent responses
- Reason: Internal labeling guidance, not end-user value

### 2. Refactor Posture Summary for Inventory-Filtered Counts
- File: `backend/core/reasoning_engine.py`
- Change: Summary shows bugs affecting YOUR inventory, not entire database
- Reason: Showing 9,725 total bugs is misleading for security posture

### 3. Fix AnalysisResult Type Mismatch
- File: `frontend/src/types/index.ts`, `frontend/src/components/ResultsDisplay.tsx`
- Change: `summary` → `psirt_summary` to match backend model
- Bug Fixed: "Explain Labels" button was failing with "Either psirt_id or psirt_summary required"
- Root Cause: Frontend had `summary` but backend sends `psirt_summary`, so the field was undefined

### 4. Rename Application to "Security Analyzer"
- Files: `frontend/src/App.tsx`, `frontend/src/components/AnalyzeForm.tsx`
- Changes:
  - Main header: "PSIRT Analyzer" → "Security Analyzer"
  - Subtitle: "Cisco Security Advisory Analysis & Defect Scanning" → "Cisco PSIRT & Bug Analysis • Feature-Aware Scanning"
  - Tab: "PSIRT Analysis" → "Security Analysis"
  - Step header: "Step 1: Analyze PSIRT" → "Step 1: Analyze PSIRT or Bug"
  - Placeholder: Added "or CSCwe12345" example for bug IDs
  - Button: "Analyze PSIRT" → "Analyze"
  - Footer: Updated to match
- Reason: System handles both PSIRTs (cisco-sa-xxx) and bugs (CSCxxxx) via intelligent routing

## Verification Checklist

After migration, verify:

- [x] `npm run build` passes (frontend)
- [ ] `pytest tests/` passes (backend)
- [ ] API endpoints return `bugs` instead of `vulnerabilities`
- [ ] UI displays "bugs" terminology
- [ ] Security Posture Summary shows inventory-filtered counts
- [ ] AI responses don't include anti-definitions
- [x] UI header says "Security Analyzer" (not "PSIRT Analyzer")
- [x] First tab says "Security Analysis"
- [x] Form accepts both PSIRT (cisco-sa-xxx) and bug (CSCxxx) IDs

## Rollback Plan

If issues arise:
1. Git revert to commit before this migration
2. Restart services

## Related Issues

- Terminology confusion between bugs/vulnerabilities/PSIRTs
- Misleading security posture numbers (showed entire DB, not inventory)
- Anti-definitions exposed to end users (internal labeling guidance)
