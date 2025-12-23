# UI Data Flows Documentation

**Version:** 1.1 | **Last Updated:** December 18, 2025

This document maps every UI component to its API endpoints, backend handlers, database tables, and data flow patterns.

---

## Table of Contents

1. [Application Structure](#1-application-structure)
2. [Tab 1: Security Analysis (PSIRT)](#2-tab-1-security-analysis-psirt)
3. [Tab 2: Defect Scanner](#3-tab-2-defect-scanner)
4. [Tab 3: Device Inventory](#4-tab-3-device-inventory)
5. [Tab 4: AI Assistant](#5-tab-4-ai-assistant)
6. [Tab 5: System Administration](#6-tab-5-system-administration)
7. [Database Schema Summary](#7-database-schema-summary)
8. [API Client Architecture](#8-api-client-architecture)

---

## 1. Application Structure

### Component Hierarchy

```
App.tsx
├── ThemeProvider (context)
├── QueryClientProvider (React Query)
└── AppContent
    ├── Header
    ├── Tab Navigation (5 tabs)
    └── Tab Content
        ├── [psirt] AnalyzeForm → ResultsDisplay → DeviceForm/SnapshotForm → VerificationReport
        ├── [scanner] ScannerForm → ScanResults
        ├── [inventory] InventoryManager
        ├── [assistant] AIAssistant
        └── [system] SystemAdmin
```

### Global State Management

| State Type | Location | Purpose |
|------------|----------|---------|
| Theme | `ThemeContext` | Dark/light mode |
| API Cache | `QueryClient` | React Query cache |
| Tab State | `App.tsx` useState | Active tab |
| Form State | Individual components | Form inputs |

---

## 2. Tab 1: Security Analysis (PSIRT)

### Overview
Analyzes PSIRT/bug summaries using the SEC-8B model to predict feature labels, then optionally verifies against a live device or snapshot.

### Data Flow Diagram

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                           SECURITY ANALYSIS TAB                               │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────┐                                                         │
│  │  AnalyzeForm.tsx│                                                         │
│  │  - summary      │                                                         │
│  │  - platform     │                                                         │
│  │  - advisory_id  │                                                         │
│  └────────┬────────┘                                                         │
│           │ onAnalyze()                                                      │
│           ▼                                                                  │
│  ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────────────┐│
│  │   App.tsx       │────►│ api.analyzePSIRT│────►│ POST /api/v1/analyze-   ││
│  │ analyzeMutation │     │   (client.ts)   │     │      psirt              ││
│  └─────────────────┘     └─────────────────┘     └───────────┬─────────────┘│
│                                                              │              │
│           ┌──────────────────────────────────────────────────┘              │
│           ▼                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                         BACKEND (routes.py)                              ││
│  │  analyze_psirt() → get_analyzer() → sec8b.analyze_psirt()               ││
│  │                                                                          ││
│  │  Three-Tier Caching:                                                     ││
│  │  ├── Tier 1: Database cache (labeled_psirts in vulnerabilities)         ││
│  │  ├── Tier 2: FAISS exact match (models/faiss_index.bin)                 ││
│  │  └── Tier 3: MLX inference (Foundation-Sec-8B + LoRA)                   ││
│  │                                                                          ││
│  │  Output: { analysis_id, predicted_labels, config_regex, show_commands } ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│           │                                                                  │
│           ▼                                                                  │
│  ┌─────────────────┐                                                         │
│  │ResultsDisplay.tsx│◄─── Displays labels, commands, confidence             │
│  └────────┬────────┘                                                         │
│           │ Choose verification                                              │
│           ▼                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │  DeviceForm.tsx (SSH)           │  SnapshotForm.tsx (Air-gapped)        ││
│  │  - host, username, password     │  - JSON snapshot paste                 ││
│  │  - device_type                  │  - features_present array              ││
│  └───────────┬─────────────────────┴───────────┬───────────────────────────┘│
│              │                                  │                            │
│              ▼                                  ▼                            │
│  ┌─────────────────────┐           ┌─────────────────────┐                   │
│  │POST /verify-device  │           │POST /verify-snapshot│                   │
│  └──────────┬──────────┘           └──────────┬──────────┘                   │
│             │                                  │                             │
│             └──────────────┬───────────────────┘                             │
│                            ▼                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                       BACKEND (verifier.py)                              ││
│  │  1. Get cached analysis by analysis_id (in-memory cache)                ││
│  │  2. Stage 1: Version matching (device version vs affected_versions)     ││
│  │  3. Stage 2: Feature detection (device features vs predicted_labels)    ││
│  │  4. Determine: VULNERABLE | NOT_VULNERABLE | POTENTIALLY_VULNERABLE     ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                            │                                                 │
│                            ▼                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │  VerificationReport.tsx                                                  ││
│  │  - overall_status (VULNERABLE/NOT_VULNERABLE)                            ││
│  │  - version_check { affected, reason }                                    ││
│  │  - feature_check { present, absent }                                     ││
│  │  - Export to JSON                                                        ││
│  └─────────────────────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────────────────┘
```

### API Endpoints Used

| Component | Action | API Endpoint | Backend Handler | Database/Storage |
|-----------|--------|--------------|-----------------|------------------|
| AnalyzeForm | Submit | `POST /api/v1/analyze-psirt` | `routes.analyze_psirt()` | In-memory cache, FAISS index, ML model |
| DeviceForm | Verify | `POST /api/v1/verify-device` | `routes.verify_device()` | SSH connection to device |
| SnapshotForm | Verify | `POST /api/v1/verify-snapshot` | `routes.verify_snapshot()` | In-memory cache lookup |

### Files Involved

| Layer | Files |
|-------|-------|
| **Frontend** | `AnalyzeForm.tsx`, `ResultsDisplay.tsx`, `DeviceForm.tsx`, `SnapshotForm.tsx`, `VerificationReport.tsx` |
| **API Client** | `client.ts` → `api.analyzePSIRT()`, `api.verifyDevice()`, `api.verifySnapshot()` |
| **Backend Routes** | `backend/api/routes.py` |
| **Core Logic** | `backend/core/sec8b.py`, `backend/core/verifier.py` |
| **Storage** | `backend/db/cache.py` (in-memory), `models/faiss_index.bin`, `models/lora_adapter/` |

---

## 3. Tab 2: Defect Scanner

### Overview
Fast database-based scanning to find bugs affecting a specific platform/version/hardware combination.

### Data Flow Diagram

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                           DEFECT SCANNER TAB                                  │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │  ScannerForm.tsx                                                         ││
│  │  ├── Platform dropdown (IOS-XE, IOS-XR, ASA, FTD, NX-OS)                ││
│  │  ├── Version input (e.g., "17.10.1")                                     ││
│  │  ├── Hardware Model dropdown (platform-specific)                         ││
│  │  ├── Feature Mode (none | device | snapshot)                             ││
│  │  │   ├── [device] SSH credentials → extract features                     ││
│  │  │   └── [snapshot] JSON paste                                           ││
│  │  └── Severity Filter (Critical/High/Medium/Low)                          ││
│  └────────┬────────────────────────────────────────────────────────────────┘│
│           │ onScan() / onExtractFeatures()                                   │
│           ▼                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │  App.tsx                                                                 ││
│  │  ├── scanMutation → api.scanDevice()                                     ││
│  │  └── extractFeaturesMutation → api.extractFeatures()                     ││
│  └────────┬────────────────────────────────────────────────────────────────┘│
│           │                                                                  │
│           ▼                                                                  │
│  ┌─────────────────┐     ┌─────────────────────────────────────────────────┐│
│  │ POST /scan-device│────►│ BACKEND (routes.py + db_scanner.py)            ││
│  └─────────────────┘     │                                                  ││
│                          │ VulnerabilityScanner.scan() →                    ││
│                          │ DatabaseScanner.scan_device()                    ││
│                          │                                                  ││
│                          │ Query Flow:                                      ││
│                          │ 1. SELECT from vulnerabilities WHERE platform=X  ││
│                          │ 2. JOIN version_index for version matching       ││
│                          │ 3. Filter by hardware_model (product_names JSON) ││
│                          │ 4. Filter by features (labels JSON)              ││
│                          │ 5. Apply severity_filter if specified            ││
│                          │                                                  ││
│                          │ Returns:                                         ││
│                          │ - scan_id, version_matches, bugs[]               ││
│                          │ - bug_count, psirt_count (v3.1+)                 ││
│                          │ - critical_high, medium_low                      ││
│                          └─────────────────────────────────────────────────┘│
│           │                                                                  │
│           ▼                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │  ScanResults.tsx                                                         ││
│  │  - Summary stats (total, critical/high, filtered counts)                 ││
│  │  - Bug list with severity badges                                         ││
│  │  - Expand for details (headline, summary, labels)                        ││
│  │  - Links to Cisco Bug Search Tool                                        ││
│  └─────────────────────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────────────────┘
```

### Database Queries

```sql
-- Main scan query (simplified)
SELECT v.*, vi.version_normalized
FROM vulnerabilities v
JOIN version_index vi ON v.id = vi.vulnerability_id
WHERE v.platform = :platform
  AND vi.version_normalized = :version
  AND (v.hardware_models IS NULL OR v.hardware_models LIKE :hardware_pattern)
ORDER BY v.severity ASC;
```

### API Endpoints Used

| Component | Action | API Endpoint | Backend Handler | Database Table |
|-----------|--------|--------------|-----------------|----------------|
| ScannerForm | Scan | `POST /api/v1/scan-device` | `routes.scan_device()` | `vulnerabilities`, `version_index`, `label_index` |
| ScannerForm | Extract | `POST /api/v1/extract-features` | `routes.extract_features()` | SSH connection |

### Files Involved

| Layer | Files |
|-------|-------|
| **Frontend** | `ScannerForm.tsx`, `ScanResults.tsx` |
| **API Client** | `client.ts` → `api.scanDevice()`, `api.extractFeatures()` |
| **Backend Routes** | `backend/api/routes.py` |
| **Core Logic** | `backend/core/vulnerability_scanner.py`, `backend/core/db_scanner.py` |
| **Database** | `vulnerability_db.sqlite` → `vulnerabilities`, `version_index`, `label_index` |

---

## 4. Tab 3: Device Inventory

### Overview
Manages device inventory with ISE synchronization, SSH discovery, bulk scanning, and scan comparison features.

### Data Flow Diagram

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                          DEVICE INVENTORY TAB                                 │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │  InventoryManager.tsx                                                    ││
│  │                                                                          ││
│  │  State:                                                                  ││
│  │  - devices: Device[]                                                     ││
│  │  - stats: InventoryStats                                                 ││
│  │  - filters: { status, platform }                                         ││
│  │  - modals: { details, compare, versionCompare, addDevice, import }       ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                            ACTIONS                                       ││
│  ├──────────────────────┬──────────────────────────────────────────────────┤│
│  │                      │                                                   ││
│  │  ┌────────────────┐  │  ┌────────────────────────────────────────────┐  ││
│  │  │ Load Devices   │  │  │ API: GET /api/v1/inventory/devices         │  ││
│  │  │ loadDevices()  │──┼─►│ Query: device_inventory table              │  ││
│  │  └────────────────┘  │  │ Returns: devices[] with last_scan_result   │  ││
│  │                      │  └────────────────────────────────────────────┘  ││
│  │  ┌────────────────┐  │  ┌────────────────────────────────────────────┐  ││
│  │  │ Sync from ISE  │  │  │ API: POST /api/v1/inventory/sync-ise       │  ││
│  │  │ handleSync()   │──┼─►│ ISE API → INSERT/UPDATE device_inventory   │  ││
│  │  └────────────────┘  │  │ Sets: hostname, ip_address, ise_id, etc.   │  ││
│  │                      │  └────────────────────────────────────────────┘  ││
│  │  ┌────────────────┐  │  ┌────────────────────────────────────────────┐  ││
│  │  │ SSH Discovery  │  │  │ API: POST /api/v1/inventory/discover-device│  ││
│  │  │ performDiscov. │──┼─►│ SSH → UPDATE device_inventory SET          │  ││
│  │  │ (via modal)    │  │  │   platform, version, hardware_model,       │  ││
│  │  └────────────────┘  │  │   features, discovery_status='success'     │  ││
│  │                      │  └────────────────────────────────────────────┘  ││
│  │  ┌────────────────┐  │  ┌────────────────────────────────────────────┐  ││
│  │  │ Scan Device    │  │  │ API: POST /api/v1/inventory/scan-device/:id│  ││
│  │  │ (row action)   │──┼─►│ db_scanner.scan() → UPDATE device_inventory│  ││
│  │  └────────────────┘  │  │   SET last_scan_result, last_scan_id,      │  ││
│  │                      │  │       last_scan_timestamp                   │  ││
│  │                      │  │   (moves current to previous_scan_*)        │  ││
│  │                      │  └────────────────────────────────────────────┘  ││
│  │  ┌────────────────┐  │  ┌────────────────────────────────────────────┐  ││
│  │  │ Bulk Scan All  │  │  │ API: POST /api/v1/inventory/scan-all       │  ││
│  │  │ handleBulkScan │──┼─►│ Background job scans all discovered devices│  ││
│  │  └────────────────┘  │  │ Updates: _bulk_scan_jobs (in-memory)       │  ││
│  │                      │  │ Poll: GET /api/v1/inventory/scan-status/:id│  ││
│  │                      │  └────────────────────────────────────────────┘  ││
│  │  ┌────────────────┐  │  ┌────────────────────────────────────────────┐  ││
│  │  │ Compare Scans  │  │  │ API: GET /inventory/devices/:id/compare    │  ││
│  │  │ (modal)        │──┼─►│ Compares: last_scan_result vs              │  ││
│  │  └────────────────┘  │  │           previous_scan_result             │  ││
│  │                      │  │ Returns: fixed_bugs[], new_bugs[]          │  ││
│  │                      │  └────────────────────────────────────────────┘  ││
│  │  ┌────────────────┐  │  ┌────────────────────────────────────────────┐  ││
│  │  │ Version Compare│  │  │ API: POST /inventory/devices/:id/          │  ││
│  │  │ (modal)        │──┼─►│      compare-version                       │  ││
│  │  └────────────────┘  │  │ Scans target version, compares bugs        │  ││
│  │                      │  │ Returns: upgrade_recommendation            │  ││
│  │                      │  └────────────────────────────────────────────┘  ││
│  │  ┌────────────────┐  │  ┌────────────────────────────────────────────┐  ││
│  │  │ Add Device     │  │  │ API: POST /api/v1/inventory/devices        │  ││
│  │  │ handleAddDevice│──┼─►│ INSERT INTO device_inventory               │  ││
│  │  └────────────────┘  │  └────────────────────────────────────────────┘  ││
│  │  ┌────────────────┐  │  ┌────────────────────────────────────────────┐  ││
│  │  │ Import CSV     │  │  │ API: POST /api/v1/inventory/devices/import │  ││
│  │  │ handleImportCSV│──┼─►│ Parse CSV → bulk INSERT device_inventory   │  ││
│  │  └────────────────┘  │  └────────────────────────────────────────────┘  ││
│  │  ┌────────────────┐  │  ┌────────────────────────────────────────────┐  ││
│  │  │ Delete Device  │  │  │ API: DELETE /api/v1/inventory/devices/:id  │  ││
│  │  │ handleDelete   │──┼─►│ DELETE FROM device_inventory WHERE id=X    │  ││
│  │  └────────────────┘  │  └────────────────────────────────────────────┘  ││
│  └──────────────────────┴──────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────────────────┘
```

### Database Table: device_inventory

```sql
CREATE TABLE device_inventory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- ISE Information
    ise_id TEXT UNIQUE,
    hostname TEXT NOT NULL,
    ip_address TEXT NOT NULL,
    location TEXT,
    device_type TEXT,

    -- Device Information (from SSH discovery)
    platform TEXT,                      -- IOS-XE, IOS-XR, ASA, FTD, NX-OS
    version TEXT,                       -- "17.10.1"
    hardware_model TEXT,                -- "Cat9300"
    features TEXT,                      -- JSON: ["MGMT_SSH_HTTP", "RTE_BGP"]

    -- Current Scan Results
    last_scan_result TEXT,              -- JSON: full scan result
    last_scan_id TEXT,
    last_scan_timestamp TEXT,

    -- Previous Scan Results (for comparison)
    previous_scan_result TEXT,
    previous_scan_id TEXT,
    previous_scan_timestamp TEXT,

    -- Status tracking
    discovery_status TEXT,              -- 'pending', 'success', 'failed'
    discovery_error TEXT,
    ise_sync_time TIMESTAMP,
    ssh_discovery_time TIMESTAMP
);
```

### API Endpoints Used

| Action | API Endpoint | Database Operation |
|--------|--------------|-------------------|
| List | `GET /inventory/devices` | SELECT * FROM device_inventory |
| Stats | `GET /inventory/stats` | COUNT/GROUP BY queries |
| Add | `POST /inventory/devices` | INSERT INTO device_inventory |
| Delete | `DELETE /inventory/devices/:id` | DELETE FROM device_inventory |
| ISE Sync | `POST /inventory/sync-ise` | INSERT/UPDATE device_inventory |
| Discover | `POST /inventory/discover-device` | UPDATE device_inventory (SSH) |
| Scan One | `POST /inventory/scan-device/:id` | UPDATE last_scan_* columns |
| Scan All | `POST /inventory/scan-all` | Background job updates all |
| Compare | `GET /inventory/devices/:id/compare` | Read last_scan_result, previous_scan_result |
| Import | `POST /inventory/devices/import` | Bulk INSERT from CSV |

### Files Involved

| Layer | Files |
|-------|-------|
| **Frontend** | `InventoryManager.tsx`, `SSHCredentialsModal.tsx` |
| **API Config** | `api/config.ts` → `buildInventoryUrl()` |
| **Backend Routes** | `backend/api/inventory_routes.py` |
| **Core Logic** | `backend/core/device_inventory.py`, `backend/core/ise_client_mock.py` |
| **Database** | `vulnerability_db.sqlite` → `device_inventory` |

---

## 5. Tab 4: AI Assistant

### Overview
Provides a chat interface with AI-powered security analysis, including a summary dashboard and natural language queries.

### Data Flow Diagram

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                            AI ASSISTANT TAB                                   │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │  AIAssistant.tsx                                                         ││
│  │                                                                          ││
│  │  ┌───────────────────────────────────────────────────────────────────┐  ││
│  │  │  Security Posture Summary Dashboard (auto-loaded on mount)        │  ││
│  │  │  useQuery(['reasoning-summary']) → reasoningApi.getSummary()      │  ││
│  │  │                                                                    │  ││
│  │  │  Displays:                                                         │  ││
│  │  │  - Risk Level (critical/elevated/moderate/low)                     │  ││
│  │  │  - Bugs/PSIRTs Affecting Inventory (from device scans)            │  ││
│  │  │  - Critical + High count                                           │  ││
│  │  │  - Database breakdown by platform                                  │  ││
│  │  │  - Recommended Actions                                             │  ││
│  │  └───────────────────────────────────────────────────────────────────┘  ││
│  │                                                                          ││
│  │  ┌───────────────────────────────────────────────────────────────────┐  ││
│  │  │  Chat Interface                                                    │  ││
│  │  │  - Messages state: Message[]                                       │  ││
│  │  │  - Input field → askMutation → reasoningApi.ask()                 │  ││
│  │  │  - Suggested questions chips                                       │  ││
│  │  │  - Follow-up action buttons (from suggested_actions)              │  ││
│  │  └───────────────────────────────────────────────────────────────────┘  ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
│  API FLOW:                                                                   │
│                                                                              │
│  ┌─────────────────┐     ┌─────────────────────────────────────────────────┐│
│  │GET /reasoning/  │────►│ BACKEND (reasoning_routes.py)                   ││
│  │    summary      │     │                                                  ││
│  └─────────────────┘     │ reasoning_engine.summary():                      ││
│                          │                                                  ││
│                          │ 1. Query device_inventory:                       ││
│                          │    - Count devices with scans                    ││
│                          │    - Sum critical_high from last_scan_result    ││
│                          │    - Get unique platforms                        ││
│                          │                                                  ││
│                          │ 2. Query vulnerabilities table:                  ││
│                          │    - COUNT bugs by platform/severity             ││
│                          │    - COUNT psirts by platform/severity           ││
│                          │                                                  ││
│                          │ 3. Calculate risk_assessment based on:           ││
│                          │    - inventory_critical_high count               ││
│                          │    - devices affected ratio                      ││
│                          │                                                  ││
│                          │ Returns: SummaryResponse                         ││
│                          └─────────────────────────────────────────────────┘│
│                                                                              │
│  ┌─────────────────┐     ┌─────────────────────────────────────────────────┐│
│  │POST /reasoning/ │────►│ BACKEND (reasoning_routes.py)                   ││
│  │     ask         │     │                                                  ││
│  └─────────────────┘     │ reasoning_engine.ask():                          ││
│                          │                                                  ││
│                          │ 1. Intent Classification (3-tier):               ││
│                          │    - Tier 1: Quick override (keyword combos)    ││
│                          │    - Tier 2: Keyword scoring                     ││
│                          │    - Tier 3: LLM fallback                        ││
│                          │                                                  ││
│                          │ 2. Intent Handlers:                              ││
│                          │    - DEVICES_BY_RISK → query device_inventory   ││
│                          │    - PRIORITIZE → aggregate from scans          ││
│                          │    - EXPLAIN_LABEL → lookup taxonomies          ││
│                          │    - BUGS_BY_PLATFORM → query vulnerabilities   ││
│                          │    - DEVICE_VULNERABILITIES → specific device   ││
│                          │    - GENERAL → LLM reasoning                     ││
│                          │                                                  ││
│                          │ Returns: AskResponse with answer, sources,       ││
│                          │          suggested_actions                       ││
│                          └─────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────────────────┘
```

### Data Aggregation Flow

The summary endpoint aggregates data from two sources:

```
┌─────────────────────────┐     ┌─────────────────────────────────────────────┐
│   device_inventory      │     │          vulnerabilities                     │
│   (last_scan_result)    │     │          (database totals)                   │
├─────────────────────────┤     ├─────────────────────────────────────────────┤
│ JSON stored per device: │     │ Direct query:                                │
│ {                       │     │ SELECT COUNT(*), platform, severity,         │
│   "critical_high": 12,  │     │        vuln_type FROM vulnerabilities        │
│   "bug_count": 10,      │     │ GROUP BY platform, vuln_type                 │
│   "psirt_count": 2      │     │                                              │
│ }                       │     │ Returns: 9,617 bugs, 88 PSIRTs by platform   │
├─────────────────────────┤     └─────────────────────────────────────────────┘
│ Aggregated as:          │
│ - inventory_critical_   │
│   high (sum across      │
│   scanned devices)      │
│ - total_advisories      │
│   (sum of bug counts)   │
└─────────────────────────┘
```

### API Endpoints Used

| Component | Action | API Endpoint | Data Source |
|-----------|--------|--------------|-------------|
| Dashboard | Load summary | `GET /reasoning/summary` | `device_inventory.last_scan_result`, `vulnerabilities` |
| Chat | Ask question | `POST /reasoning/ask` | Intent-dependent queries |

### Files Involved

| Layer | Files |
|-------|-------|
| **Frontend** | `AIAssistant.tsx` |
| **API Client** | `client.ts` → `reasoningApi.getSummary()`, `reasoningApi.ask()` |
| **Backend Routes** | `backend/api/reasoning_routes.py` |
| **Core Logic** | `backend/core/reasoning_engine.py` |
| **Database** | `vulnerability_db.sqlite` → `device_inventory`, `vulnerabilities` |

---

## 6. Tab 5: System Administration

### Overview
Provides system management capabilities including offline updates, health monitoring, and cache management.

### Data Flow Diagram

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                         SYSTEM ADMINISTRATION TAB                             │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │  SystemAdmin.tsx                                                         ││
│  │                                                                          ││
│  │  Uses React Query for auto-refresh (30s interval):                       ││
│  │  - useQuery(['dbStats']) → systemApi.getDatabaseStats()                 ││
│  │  - useQuery(['systemHealth']) → systemApi.getSystemHealth()             ││
│  │  - useQuery(['cacheStats']) → systemApi.getCacheStats()                 ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                            PANELS                                        ││
│  ├──────────────────────┬──────────────────────────────────────────────────┤│
│  │                      │                                                   ││
│  │  ┌────────────────┐  │  ┌────────────────────────────────────────────┐  ││
│  │  │ Database Stats │  │  │ API: GET /api/v1/system/stats/database     │  ││
│  │  │ Panel          │──┼─►│                                             │  ││
│  │  └────────────────┘  │  │ Queries:                                    │  ││
│  │                      │  │ - SELECT COUNT(*) FROM vulnerabilities     │  ││
│  │                      │  │   WHERE vuln_type='bug'                     │  ││
│  │                      │  │ - SELECT COUNT(*) FROM vulnerabilities     │  ││
│  │                      │  │   WHERE vuln_type='psirt'                   │  ││
│  │                      │  │ - GROUP BY platform, severity               │  ││
│  │                      │  │ - SELECT COUNT(*) FROM device_inventory     │  ││
│  │                      │  │                                             │  ││
│  │                      │  │ Returns: { bugs: {total, by_platform},     │  ││
│  │                      │  │           psirts: {total, by_platform} }    │  ││
│  │                      │  └────────────────────────────────────────────┘  ││
│  │  ┌────────────────┐  │  ┌────────────────────────────────────────────┐  ││
│  │  │ System Health  │  │  │ API: GET /api/v1/system/health             │  ││
│  │  │ Panel          │──┼─►│                                             │  ││
│  │  └────────────────┘  │  │ Checks:                                     │  ││
│  │                      │  │ - Database file exists and readable         │  ││
│  │                      │  │ - ML model loaded                           │  ││
│  │                      │  │ - FAISS index loaded                        │  ││
│  │                      │  │ - Taxonomies loaded                         │  ││
│  │                      │  │                                             │  ││
│  │                      │  │ Returns: { status: 'healthy'|'degraded',   │  ││
│  │                      │  │           components: {...} }               │  ││
│  │                      │  └────────────────────────────────────────────┘  ││
│  │  ┌────────────────┐  │  ┌────────────────────────────────────────────┐  ││
│  │  │ Cache Stats    │  │  │ API: GET /api/v1/system/cache/stats        │  ││
│  │  │ Panel          │──┼─►│                                             │  ││
│  │  └────────────────┘  │  │ Returns: { analysis_cache: entries,        │  ││
│  │                      │  │           faiss_cache: size }               │  ││
│  │                      │  └────────────────────────────────────────────┘  ││
│  │  ┌────────────────┐  │  ┌────────────────────────────────────────────┐  ││
│  │  │ Clear Cache    │  │  │ API: POST /api/v1/system/cache/clear       │  ││
│  │  │ Button         │──┼─►│       ?cache_type=all|analysis|faiss       │  ││
│  │  └────────────────┘  │  │                                             │  ││
│  │                      │  │ Clears in-memory caches                     │  ││
│  │                      │  └────────────────────────────────────────────┘  ││
│  │  ┌────────────────┐  │  ┌────────────────────────────────────────────┐  ││
│  │  │ Offline Update │  │  │ API: POST /api/v1/system/update/offline    │  ││
│  │  │ Upload Zone    │──┼─►│                                             │  ││
│  │  └────────────────┘  │  │ 1. Receive .zip package (multipart)        │  ││
│  │                      │  │ 2. Validate SHA256 hash (from manifest)    │  ││
│  │                      │  │ 3. Extract to temp directory                │  ││
│  │                      │  │ 4. Load labeled_update.jsonl:               │  ││
│  │                      │  │    - Detect version patterns (EXPLICIT,    │  ││
│  │                      │  │      OPEN_LATER, WILDCARD, etc.)           │  ││
│  │                      │  │    - Extract hardware model from text      │  ││
│  │                      │  │    - Populate version_index table          │  ││
│  │                      │  │    - Populate label_index table            │  ││
│  │                      │  │                                             │  ││
│  │                      │  │ Returns: { inserted, updated, skipped }     │  ││
│  │                      │  └────────────────────────────────────────────┘  ││
│  └──────────────────────┴──────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────────────────┘
```

### API Endpoints Used

| Panel | API Endpoint | Database/Storage |
|-------|--------------|------------------|
| DB Stats | `GET /system/stats/database` | `vulnerabilities`, `device_inventory` |
| Health | `GET /system/health` | File system checks, model state |
| Cache Stats | `GET /system/cache/stats` | In-memory cache inspection |
| Clear Cache | `POST /system/cache/clear` | In-memory cache operations |
| Offline Update | `POST /system/update/offline` | `vulnerabilities` table, taxonomy files |

### Files Involved

| Layer | Files |
|-------|-------|
| **Frontend** | `SystemAdmin.tsx` |
| **API Client** | `client.ts` → `systemApi.*` |
| **Backend Routes** | `backend/api/system_routes.py` |
| **Core Logic** | `backend/core/updater.py` (OfflineUpdater with VersionPatternDetector) |
| **Database** | `vulnerability_db.sqlite` → `vulnerabilities`, `version_index`, `label_index` |

---

## 7. Database Schema Summary

### Tables and Their UI Connections

| Table | Primary UI Tab | Purpose |
|-------|---------------|---------|
| `vulnerabilities` | Scanner, AI Assistant, System | Bug/PSIRT records |
| `version_index` | Scanner | Fast version lookups |
| `label_index` | Scanner | Fast label filtering |
| `device_inventory` | Inventory, AI Assistant | Device records and scan results |
| `db_metadata` | System | Update tracking |

### Key JSON Columns

| Table | Column | UI Usage |
|-------|--------|----------|
| `device_inventory` | `last_scan_result` | Inventory table, AI summary aggregation |
| `device_inventory` | `features` | Feature filtering in scans |
| `vulnerabilities` | `labels` | Label-based filtering |
| `vulnerabilities` | `product_names` | Hardware filtering |

---

## 8. API Client Architecture

### Client Structure (`frontend/src/api/client.ts`)

```typescript
// Base configuration
const apiClient = axios.create({
  baseURL: API_BASE_URL,  // Default: 'http://localhost:8000/api/v1'
  timeout: 300000,        // 5 minutes
});

// API namespaces
export const api = {
  analyzePSIRT(),      // → POST /analyze-psirt
  verifyDevice(),      // → POST /verify-device
  verifySnapshot(),    // → POST /verify-snapshot
  scanDevice(),        // → POST /scan-device
  extractFeatures(),   // → POST /extract-features
  healthCheck(),       // → GET /health
};

export const systemApi = {
  getDatabaseStats(),      // → GET /system/stats/database
  getSystemHealth(),       // → GET /system/health
  getCacheStats(),         // → GET /system/cache/stats
  clearCache(),            // → POST /system/cache/clear
  uploadOfflinePackage(),  // → POST /system/update/offline
};

export const reasoningApi = {
  explain(),         // → POST /reasoning/explain
  remediate(),       // → POST /reasoning/remediate
  ask(),             // → POST /reasoning/ask
  getSummary(),      // → GET /reasoning/summary
};
```

### Inventory API (Direct Fetch)

The InventoryManager uses direct fetch calls with `buildInventoryUrl()`:

```typescript
// frontend/src/api/config.ts
export const buildInventoryUrl = (path: string) =>
  `${API_BASE_URL}/inventory/${path}`;

// Usage in InventoryManager.tsx
fetch(buildInventoryUrl('devices'))    // → GET /api/v1/inventory/devices
fetch(buildInventoryUrl('sync-ise'))   // → POST /api/v1/inventory/sync-ise
```

---

## Quick Reference: UI Component → API → Database

| UI Component | API Endpoint | Database Table |
|--------------|--------------|----------------|
| `AnalyzeForm` | `/analyze-psirt` | In-memory cache, FAISS |
| `DeviceForm` | `/verify-device` | In-memory cache (analysis lookup) |
| `SnapshotForm` | `/verify-snapshot` | In-memory cache (analysis lookup) |
| `ScannerForm` | `/scan-device` | `vulnerabilities`, `version_index` |
| `InventoryManager` | `/inventory/*` | `device_inventory` |
| `AIAssistant` | `/reasoning/summary`, `/reasoning/ask` | `device_inventory`, `vulnerabilities` |
| `SystemAdmin` | `/system/*` | `vulnerabilities`, `device_inventory`, `db_metadata` |

---

**Document Version:** 1.0
**Generated:** December 16, 2025
