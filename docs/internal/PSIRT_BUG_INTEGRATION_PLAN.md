# PSIRT + Bug Integration Plan

**Date:** December 07, 2025 (Updated)
**Purpose:** Unify PSIRT and Bug data sources into a single vulnerability assessment workflow

---

## Executive Summary

Currently, the system has two separate paths:
- **Path A (PSIRT Analysis):** LLM-based label prediction → device verification
- **Path B (Bug Database Scan):** Fast version + hardware + feature matching

**Goal:** Integrate both paths so all features (version comparison, device scanning, ISE integration, detection rules) leverage **both PSIRTs and bugs simultaneously** in a unified output.

**Key Insight:** PSIRTs and Bugs are both vulnerabilities - they should be treated uniformly throughout the system with a common data model.

---

## Current Architecture (Separated)

```
┌─────────────────┐                    ┌─────────────────┐
│  PSIRT Summary  │                    │  Device IP      │
│  (SEC-8B)       │                    │  + Version      │
└────────┬────────┘                    └────────┬────────┘
         │                                      │
         ▼                                      ▼
┌─────────────────┐                    ┌─────────────────┐
│ Label Prediction│                    │ Bug Database    │
│ (LLM Inference) │                    │ Query (SQL)     │
└────────┬────────┘                    └────────┬────────┘
         │                                      │
         ▼                                      ▼
┌─────────────────┐                    ┌─────────────────┐
│ PSIRT Results   │                    │ Bug Results     │
│ - Labels        │                    │ - Bug IDs       │
│ - Commands      │                    │ - Confidence    │
│ - Confidence    │                    │ - Severity      │
└─────────────────┘                    └─────────────────┘

         ❌ SEPARATE OUTPUTS ❌
```

## Target Architecture (Unified)

```
┌─────────────────┐       ┌─────────────────┐
│  PSIRT Summary  │       │  Device IP      │
│  (SEC-8B)       │       │  + Version      │
└────────┬────────┘       └────────┬────────┘
         │                         │
         │                         │
         └────────┬────────────────┘
                  │
                  ▼
         ┌─────────────────┐
         │ Unified Vuln    │
         │ Assessment      │
         │ Engine          │
         └────────┬────────┘
                  │
         ┌────────┴────────┐
         │                 │
         ▼                 ▼
┌─────────────────┐ ┌─────────────────┐
│ PSIRT Source    │ │ Bug Source      │
│ - LLM inference │ │ - Database scan │
│ - Cache lookup  │ │ - Version filter│
└────────┬────────┘ └────────┬────────┘
         │                   │
         └─────────┬─────────┘
                   │
                   ▼
         ┌─────────────────┐
         │ Unified Results │
         │ - All vulns     │
         │ - Source tagged │
         │ - Deduplicated  │
         │ - Prioritized   │
         └─────────────────┘

         ✅ SINGLE UNIFIED OUTPUT ✅
```

---

## Integration Details

The technical details of the integration have been modularized for better maintainability. Please refer to the specific documents below:

### 1. [Data Model & Schema](./docs/integration/data_model.md)
   - Unified Vulnerability Object
   - Bug/PSIRT Mappings
   - Database Schema Updates (`psirt_cache`)

### 2. [Device Scanning & Deduplication](./docs/integration/scanning.md)
   - Unified Scanning Logic
   - Deduplication Strategy (handling duplicates by CVE ID)

### 3. [Version Comparison](./docs/integration/version_comparison.md)
   - Combined PSIRT + Bug analysis for upgrade planning
   - UI Mockups

### 4. [ISE Workflows](./docs/integration/ise_workflows.md)
   - Inventory-wide unified assessment
   - Integration with Cisco ISE

### 5. [Detection Rules](./docs/integration/detection_rules.md)
   - Unified IOC generation
   - Firepower, Stealthwatch, and Snort rule formats

### 6. [API Specifications](./docs/integration/api_specs.md)
   - New unified endpoints (`compare-versions`, `scan-device-unified`, etc.)

### 7. [Frontend UI](./docs/integration/frontend_ui.md)
   - Scanner form updates
   - Results display components

---

## Migration Path

### Phase 1: Create Unified Data Model (1 week)
- Define `UnifiedVulnerability` class
- Implement `bug_to_unified_vuln()` and `psirt_to_unified_vuln()` converters
- Create `psirt_cache` database table
- Populate `psirt_cache` with existing PSIRT analysis results

### Phase 2: Unified Query Engine (1 week)
- Implement `query_vulnerabilities_unified()` function
- Update scanner to query both sources
- Implement deduplication logic
- Add frontend toggles (scan bugs, scan PSIRTs, scan both)

### Phase 3: Version Comparison Integration (1 week)
- Implement `compare_versions_unified()` function
- Create new `/api/v1/compare-versions` endpoint
- Build frontend UI for version comparison
- Add breakdown of bugs vs PSIRTs fixed/introduced

### Phase 4: ISE + Detection Rules Integration (2 weeks)
- ✅ Integrate unified scanning into ISE inventory workflow (Inventory Sync & Discovery Verified)
- 🚧 Unified Scanning for ISE devices (In Progress)
- Extend detection rule generation to work with unified vulnerabilities
- Add PSIRT-specific IOC mapping (threat intelligence)
