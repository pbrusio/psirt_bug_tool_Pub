# Data Flow Documentation

**Version:** 1.2 | **Last Updated:** December 19, 2025

This document provides comprehensive data flow documentation for every major feature in the PSIRT Analysis system. It traces data from source to UI, documenting which APIs, functions, and database tables are involved.

---

## Table of Contents

1. [Database Architecture](#1-database-architecture)
2. [AI Assistant Dashboard](#2-ai-assistant-dashboard)
3. [ISE Integration & Device Inventory](#3-ise-integration--device-inventory)
4. [Vulnerability Scanner](#4-vulnerability-scanner)
5. [PSIRT Analysis (LLM Path)](#5-psirt-analysis-llm-path)
6. [AI Assistant Intent Classification](#6-ai-assistant-intent-classification)
7. [System Administration](#7-system-administration)
8. [Verified API Response Structures](#8-verified-api-response-structures)

---

## 1. Database Architecture

### Single Database: `vulnerability_db.sqlite`

All data is stored in a single SQLite database located at the project root.

> ⚠️ **CRITICAL ASSET - MUST BE VERSION CONTROLLED**
>
> This database is the "secret sauce" of the system. It contains:
> - **9,705+ labeled vulnerabilities** (bugs + PSIRTs with curated feature labels)
> - **272,524 version index entries** for sub-millisecond version matching
> - **1,002 label index mappings** for feature-based vulnerability filtering
>
> This data represents significant curation effort: Cisco API fetching, LLM labeling pipeline,
> and human validation. The ML model, FAISS index, and this database are the three pillars.
> Without any one of them, the system cannot function.

### Tables Overview

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `vulnerabilities` | Bugs and PSIRTs | bug_id, vuln_type, platform, severity, labels, affected_versions_raw |
| `version_index` | Fast version lookups | vulnerability_id, version_normalized |
| `label_index` | Fast label lookups | vulnerability_id, label |
| `db_metadata` | Schema version, timestamps | key, value |
| `device_inventory` | Network devices from ISE/SSH | hostname, ip_address, platform, version, last_scan_result |
| `scan_results` | Full scan result storage | scan_id, device_id, full_result (JSON) |

### Schema Details

#### `vulnerabilities` Table
```sql
CREATE TABLE vulnerabilities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bug_id TEXT NOT NULL UNIQUE,        -- CSCxxxx for bugs, cisco-sa-xxx for PSIRTs
    advisory_id TEXT,                   -- PSIRT advisory ID
    vuln_type TEXT NOT NULL,            -- 'bug' or 'psirt'
    severity INTEGER,                   -- 1-6 (1=Critical, 6=Low)
    headline TEXT,
    summary TEXT,
    url TEXT,
    status TEXT,
    platform TEXT NOT NULL,             -- IOS-XE, IOS-XR, ASA, FTD, NX-OS
    product_series TEXT,
    affected_versions_raw TEXT NOT NULL, -- "17.10.1 17.12.4 17.13.1"
    version_pattern TEXT NOT NULL,      -- EXPLICIT, WILDCARD, OPEN_LATER, etc.
    version_min TEXT,
    version_max TEXT,
    fixed_version TEXT,
    labels TEXT,                        -- JSON: ["MGMT_SSH_HTTP", "SEC_CoPP"]
    labels_source TEXT,
    hardware_model TEXT,                -- For hardware-specific bugs
    last_modified TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

#### `device_inventory` Table
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
    serial_number TEXT,
    uptime TEXT,
    features TEXT,                      -- JSON: ["MGMT_SSH_HTTP", "RTE_BGP"]

    -- Current Scan Results
    last_scan_result TEXT,              -- JSON summary
    last_scan_id TEXT,
    last_scan_timestamp TEXT,

    -- Previous Scan Results (for comparison)
    previous_scan_result TEXT,
    previous_scan_id TEXT,
    previous_scan_timestamp TEXT,

    -- Metadata
    last_scanned TIMESTAMP,
    ise_sync_time TIMESTAMP,
    ssh_discovery_time TIMESTAMP,
    discovery_status TEXT,              -- 'success', 'failed', 'pending', 'manual'
    discovery_error TEXT,
    source TEXT,                        -- 'ise', 'manual'
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

### Data Relationships

```
┌─────────────────────┐         ┌─────────────────────┐
│   vulnerabilities   │         │   device_inventory  │
├─────────────────────┤         ├─────────────────────┤
│ id                  │◄────────┤ last_scan_result    │
│ bug_id              │         │ (JSON with bugs)    │
│ platform            │         │ platform            │
│ version_pattern     │         │ version             │
│ labels (JSON)       │         │ features (JSON)     │
└─────────────────────┘         └─────────────────────┘
         │                               │
         │                               │
         ▼                               ▼
┌─────────────────────┐         ┌─────────────────────┐
│   version_index     │         │   scan_results      │
├─────────────────────┤         ├─────────────────────┤
│ vulnerability_id  ──┤         │ device_id  ─────────┤
│ version_normalized  │         │ scan_id             │
└─────────────────────┘         │ full_result (JSON)  │
                                └─────────────────────┘
```

---

## 2. AI Assistant Dashboard

The AI Assistant Dashboard shows security posture metrics derived from **your inventory**, not the entire database.

### Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                           FRONTEND                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐ │
│  │ AIAssistant.tsx                                                      │ │
│  │                                                                      │ │
│  │ useQuery(['reasoning-summary']) ────┐                                │ │
│  │   └─► reasoningApi.getSummary()     │                                │ │
│  │                                      ▼                               │ │
│  │ ┌──────────────────────────────────────────────────────────────────┐│ │
│  │ │ Security Posture Summary                                          ││ │
│  │ │ ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐      ││ │
│  │ │ │ Risk Level │ │ Bugs       │ │ Critical   │ │ Period     │      ││ │
│  │ │ │ ELEVATED   │ │ Affecting  │ │ + High     │ │ Past 7 days│      ││ │
│  │ │ │            │ │ Inventory  │ │            │ │            │      ││ │
│  │ │ └────────────┘ └────────────┘ └────────────┘ └────────────┘      ││ │
│  │ │                                                                   ││ │
│  │ │ Database Totals (Reference)                                       ││ │
│  │ │ [Bugs] [PSIRTs] - toggle shows DB totals vs inventory impact     ││ │
│  │ └──────────────────────────────────────────────────────────────────┘│ │
│  └─────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ GET /api/v1/reasoning/summary
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                             BACKEND                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐ │
│  │ backend/api/reasoning_routes.py                                      │ │
│  │                                                                      │ │
│  │ @router.get("/summary")                                              │ │
│  │ async def get_summary(period, scope, format):                        │ │
│  │     engine = get_reasoning_engine()                                  │ │
│  │     result = await engine.summary(period, scope, format)             │ │
│  │     return SummaryResponse(...)                                      │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
│                                    │                                      │
│                                    ▼                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐ │
│  │ backend/core/reasoning_engine.py                                     │ │
│  │                                                                      │ │
│  │ async def summary(self, period, scope, format):                      │ │
│  │     # 1. Query device_inventory for stats                            │ │
│  │     cursor.execute("SELECT discovery_status, COUNT(*) ...")          │ │
│  │                                                                      │ │
│  │     # 2. Aggregate from last_scan_result JSON                        │ │
│  │     cursor.execute("""                                               │ │
│  │         SELECT last_scan_result FROM device_inventory                │ │
│  │         WHERE discovery_status = 'success'                           │ │
│  │           AND last_scan_result IS NOT NULL                           │ │
│  │     """)                                                             │ │
│  │                                                                      │ │
│  │     # 3. Parse each device's scan_summary JSON                       │ │
│  │     for row in last_scans:                                           │ │
│  │         scan_summary = json.loads(row['last_scan_result'])           │ │
│  │         total_bugs += scan_summary.get('total_bugs', 0)              │ │
│  │         bug_critical_high += scan_summary.get('bug_critical_high')   │ │
│  │         total_psirts += scan_summary.get('total_psirts', 0)          │ │
│  │                                                                      │ │
│  │     # 4. Query DB totals for reference                               │ │
│  │     cursor.execute("SELECT COUNT(*) FROM vulnerabilities ...")       │ │
│  │                                                                      │ │
│  │     return {                                                         │ │
│  │         'total_advisories': total_affecting_bugs,  # YOUR inventory  │ │
│  │         'total_bugs_in_db': total_db_bugs,         # Reference       │ │
│  │         'inventory_critical_high': ...,                              │ │
│  │         'bugs': {...by_platform...},                                 │ │
│  │         'psirts': {...affecting_inventory...},                       │ │
│  │     }                                                                │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                            DATABASE                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐ │
│  │ device_inventory                                                     │ │
│  │ ┌─────────────┬──────────────┬────────────────────────────────────┐ │ │
│  │ │ hostname    │ platform     │ last_scan_result (JSON)            │ │ │
│  │ ├─────────────┼──────────────┼────────────────────────────────────┤ │ │
│  │ │ C9200L      │ IOS-XE       │ {"total_bugs": 15,                 │ │ │
│  │ │             │              │  "bug_critical_high": 3,           │ │ │
│  │ │             │              │  "total_psirts": 2,                │ │ │
│  │ │             │              │  "psirt_critical_high": 1}         │ │ │
│  │ ├─────────────┼──────────────┼────────────────────────────────────┤ │ │
│  │ │ FPR1010     │ FTD          │ {"total_bugs": 8, ...}             │ │ │
│  │ └─────────────┴──────────────┴────────────────────────────────────┘ │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────────┐ │
│  │ vulnerabilities (for DB totals reference)                            │ │
│  │ ┌───────────┬──────────┬──────────┬────────────┐                    │ │
│  │ │ bug_id    │ vuln_type│ severity │ platform   │                    │ │
│  │ ├───────────┼──────────┼──────────┼────────────┤                    │ │
│  │ │ CSCxx123  │ bug      │ 1        │ IOS-XE     │ (9,617 total bugs) │ │
│  │ │ cisco-sa..│ psirt    │ 2        │ IOS-XE     │ (88 total PSIRTs)  │ │
│  │ └───────────┴──────────┴──────────┴────────────┘                    │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────┘
```

### Key Response Fields

| Field | Source | Meaning |
|-------|--------|---------|
| `total_advisories` | Aggregated from `last_scan_result` JSON | Bugs affecting YOUR inventory |
| `total_bugs_in_db` | `SELECT COUNT(*) FROM vulnerabilities` | Total bugs in database (reference) |
| `inventory_devices_scanned` | Count of devices with `last_scan_result IS NOT NULL` | Devices with scan data |
| `inventory_critical_high` | Aggregated from `last_scan_result.bug_critical_high` | Critical+High bugs affecting your devices |
| `bugs.total` | `SELECT COUNT(*) WHERE vuln_type='bug'` | DB reference count |
| `bugs.by_platform` | `GROUP BY platform WHERE vuln_type='bug'` | DB reference by platform |
| `psirts.affecting_inventory` | Aggregated from `last_scan_result.total_psirts` | PSIRTs affecting your versions |

### Key Files

| File | Purpose |
|------|---------|
| `frontend/src/components/AIAssistant.tsx:31-34` | React Query hook for summary |
| `frontend/src/api/client.ts:250-259` | `reasoningApi.getSummary()` |
| `backend/api/reasoning_routes.py:369-430` | `GET /summary` endpoint |
| `backend/core/reasoning_engine.py:1935-2200` | `summary()` method |

---

## 3. ISE Integration & Device Inventory

The ISE integration provides network device discovery and enrichment.

### Device Lifecycle

```
┌────────────────────────────────────────────────────────────────────────────┐
│                     DEVICE LIFECYCLE                                        │
│                                                                             │
│   ┌────────────┐      ┌────────────┐      ┌────────────┐                   │
│   │  PHASE 1   │      │  PHASE 2   │      │  PHASE 3   │                   │
│   │  ISE Sync  │ ───► │  SSH       │ ───► │  Vuln Scan │                   │
│   │            │      │  Discovery │      │            │                   │
│   └────────────┘      └────────────┘      └────────────┘                   │
│        │                    │                   │                           │
│        ▼                    ▼                   ▼                           │
│   ┌────────────┐      ┌────────────┐      ┌────────────┐                   │
│   │ hostname   │      │ + platform │      │ + scan     │                   │
│   │ ip_address │      │ + version  │      │   results  │                   │
│   │ location   │      │ + hardware │      │ + vulns    │                   │
│   │ (pending)  │      │ + features │      │ + severity │                   │
│   └────────────┘      └────────────┘      └────────────┘                   │
│                                                                             │
│   discovery_status:   discovery_status:   last_scan_result:                │
│   'pending'           'success'           {total_bugs: N, ...}             │
└────────────────────────────────────────────────────────────────────────────┘
```

### Phase 1: ISE Sync

```
┌──────────────────────────────────────────────────────────────────────────┐
│                      ISE SYNC FLOW                                        │
│                                                                           │
│   Frontend (DeviceInventory.tsx)                                          │
│   ┌─────────────────────────────────────────────────────────────────┐    │
│   │ [Sync from ISE] button                                           │    │
│   │     │                                                            │    │
│   │     ▼                                                            │    │
│   │ POST /api/v1/inventory/sync-ise                                  │    │
│   │ { use_mock: true }   // or real ISE credentials                  │    │
│   └─────────────────────────────────────────────────────────────────┘    │
│                              │                                            │
│                              ▼                                            │
│   Backend (inventory_routes.py:266-340)                                   │
│   ┌─────────────────────────────────────────────────────────────────┐    │
│   │ async def sync_from_ise(request):                                │    │
│   │     if request.use_mock:                                         │    │
│   │         ise_client = MockISEClient(...)                          │    │
│   │     else:                                                        │    │
│   │         ise_client = ISEClient(host, user, password)             │    │
│   │                                                                  │    │
│   │     ise_result = ise_client.sync_devices(max_devices=N)          │    │
│   │     db_result = inventory.sync_from_ise(ise_result['devices'])   │    │
│   └─────────────────────────────────────────────────────────────────┘    │
│                              │                                            │
│                              ▼                                            │
│   MockISEClient (ise_client_mock.py) or ISEClient (ise_client.py)         │
│   ┌─────────────────────────────────────────────────────────────────┐    │
│   │ def sync_devices(max_devices):                                   │    │
│   │     return {                                                     │    │
│   │         'success': True,                                         │    │
│   │         'devices': [                                             │    │
│   │             {                                                    │    │
│   │                 'ise_id': 'lab-uuid-001',                        │    │
│   │                 'hostname': 'C9200L',                            │    │
│   │                 'ip_addresses': ['192.168.0.33'],                │    │
│   │                 'location': 'Lab',                               │    │
│   │                 'device_type': 'Cisco Catalyst 9200L'            │    │
│   │             }, ...                                               │    │
│   │         ]                                                        │    │
│   │     }                                                            │    │
│   └─────────────────────────────────────────────────────────────────┘    │
│                              │                                            │
│                              ▼                                            │
│   DeviceInventoryManager (device_inventory.py:38-172)                     │
│   ┌─────────────────────────────────────────────────────────────────┐    │
│   │ def sync_from_ise(ise_devices):                                  │    │
│   │     for device in ise_devices:                                   │    │
│   │         # Check if exists (by hostname+IP or ise_id)             │    │
│   │         cursor.execute("SELECT id FROM device_inventory WHERE...") │   │
│   │                                                                  │    │
│   │         if existing:                                             │    │
│   │             # UPDATE                                             │    │
│   │         else:                                                    │    │
│   │             # INSERT with discovery_status='pending'             │    │
│   │                                                                  │    │
│   │     return {'devices_added': N, 'devices_updated': M}            │    │
│   └─────────────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────────┘
```

### Phase 2: SSH Discovery

```
┌──────────────────────────────────────────────────────────────────────────┐
│                    SSH DISCOVERY FLOW                                     │
│                                                                           │
│   Frontend (DeviceInventory.tsx)                                          │
│   ┌─────────────────────────────────────────────────────────────────┐    │
│   │ SSH Credentials Modal                                            │    │
│   │ [Username] [Password] [Discover]                                 │    │
│   │     │                                                            │    │
│   │     ▼                                                            │    │
│   │ POST /api/v1/inventory/discover-device                           │    │
│   │ { device_id: 1, username: "admin", password: "xxx" }             │    │
│   └─────────────────────────────────────────────────────────────────┘    │
│                              │                                            │
│                              ▼                                            │
│   Backend (inventory_routes.py:347-396)                                   │
│   ┌─────────────────────────────────────────────────────────────────┐    │
│   │ async def discover_device(request):                              │    │
│   │     result = inventory.discover_device_via_ssh(                  │    │
│   │         device_id=request.device_id,                             │    │
│   │         ssh_credentials={...}                                    │    │
│   │     )                                                            │    │
│   └─────────────────────────────────────────────────────────────────┘    │
│                              │                                            │
│                              ▼                                            │
│   DeviceInventoryManager (device_inventory.py:174-292)                    │
│   ┌─────────────────────────────────────────────────────────────────┐    │
│   │ def discover_device_via_ssh(device_id, ssh_credentials):         │    │
│   │     # Connect via Netmiko                                        │    │
│   │     snapshot = extract_from_live_device(                         │    │
│   │         host=ip_address,                                         │    │
│   │         username=..., password=...                               │    │
│   │     )                                                            │    │
│   │                                                                  │    │
│   │     # Extract from snapshot                                      │    │
│   │     platform = snapshot.get('platform')      # IOS-XE            │    │
│   │     version = snapshot.get('version')        # 17.10.1           │    │
│   │     hardware_model = snapshot.get('hardware_model')  # Cat9200L  │    │
│   │     features = snapshot.get('features_present')  # [MGMT_SSH...] │    │
│   │                                                                  │    │
│   │     # Update device_inventory                                    │    │
│   │     cursor.execute("UPDATE device_inventory SET                  │    │
│   │         platform=?, version=?, hardware_model=?, features=?,     │    │
│   │         discovery_status='success' WHERE id=?")                  │    │
│   └─────────────────────────────────────────────────────────────────┘    │
│                              │                                            │
│                              ▼                                            │
│   extract_device_features.py (SSH + show commands)                        │
│   ┌─────────────────────────────────────────────────────────────────┐    │
│   │ def extract_from_live_device(host, username, password):          │    │
│   │     # SSH via Netmiko                                            │    │
│   │     # Run: show version, show running-config                     │    │
│   │     # Parse config for feature labels (regex matching)           │    │
│   │     return {                                                     │    │
│   │         'platform': 'IOS-XE',                                    │    │
│   │         'version': '17.10.1',                                    │    │
│   │         'hardware_model': 'C9200L-24P-4X',                       │    │
│   │         'features_present': ['MGMT_SSH_HTTP', 'RTE_OSPF', ...]   │    │
│   │     }                                                            │    │
│   └─────────────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────────┘
```

### Phase 3: Vulnerability Scan

```
┌──────────────────────────────────────────────────────────────────────────┐
│                    VULNERABILITY SCAN FLOW                                │
│                                                                           │
│   POST /api/v1/inventory/scan-device/{device_id}                          │
│   ┌─────────────────────────────────────────────────────────────────┐    │
│   │ inventory_routes.py:968-1061                                     │    │
│   │                                                                  │    │
│   │ 1. Get device from inventory (platform, version, features)       │    │
│   │ 2. Run VulnerabilityScanner.scan_device()                        │    │
│   │ 3. Save to device_inventory.last_scan_result (with rotation)     │    │
│   │ 4. Save full results to scan_results table                       │    │
│   └─────────────────────────────────────────────────────────────────┘    │
│                              │                                            │
│                              ▼                                            │
│   Result stored in device_inventory.last_scan_result:                     │
│   {                                                                       │
│       "scan_id": "scan-abc123",                                           │
│       "total_bugs": 15,                                                   │
│       "bug_critical_high": 3,                                             │
│       "total_psirts": 2,                                                  │
│       "psirt_critical_high": 1,                                           │
│       "critical_high": 4,                                                 │
│       "medium_low": 11,                                                   │
│       "hardware_filtered": 12,                                            │
│       "feature_filtered": 8                                               │
│   }                                                                       │
└──────────────────────────────────────────────────────────────────────────┘
```

### Key Files

| File | Purpose |
|------|---------|
| `backend/api/inventory_routes.py` | All inventory API endpoints |
| `backend/core/device_inventory.py` | DeviceInventoryManager class |
| `backend/core/ise_client_mock.py` | Mock ISE client for development |
| `backend/core/ise_client.py` | Real ISE ERS API client (when available) |
| `extract_device_features.py` | SSH feature extraction |

---

## 4. Vulnerability Scanner

The scanner uses a facade pattern with two paths: fast database path and LLM path.

### Architecture

```
┌────────────────────────────────────────────────────────────────────────────┐
│                    VULNERABILITY SCANNER ARCHITECTURE                       │
│                                                                             │
│   ┌──────────────────────────────────────────────────────────────────────┐ │
│   │ VulnerabilityScanner (vulnerability_scanner.py)                       │ │
│   │ ────────────────────────────────────────────────────────────────────  │ │
│   │ Facade - maintains backwards compatible public interface              │ │
│   │                                                                       │ │
│   │ - scan_device(platform, version, labels, hardware_model)              │ │
│   │ - analyze_psirt(summary, platform, advisory_id)                       │ │
│   │ - get_vulnerability_details(vuln_id)                                  │ │
│   └────────────────────────────────────┬─────────────────────────────────┘ │
│                                        │                                    │
│                                        ▼                                    │
│   ┌──────────────────────────────────────────────────────────────────────┐ │
│   │ ScanRouter (scan_router.py)                                           │ │
│   │ ────────────────────────────────────────────────────────────────────  │ │
│   │ Routes requests to appropriate handler                                 │ │
│   └───────────────────┬──────────────────────────────┬───────────────────┘ │
│                       │                              │                      │
│                       ▼                              ▼                      │
│   ┌──────────────────────────────────┐ ┌──────────────────────────────────┐│
│   │ PATH A: DatabaseScanner          │ │ PATH B: AIAnalyzer               ││
│   │ (db_scanner.py)                  │ │ (ai_analyzer.py)                 ││
│   │ ─────────────────────────────────│ │ ─────────────────────────────────││
│   │ Fast: <10ms                      │ │ Slow: ~2s                        ││
│   │                                  │ │                                  ││
│   │ 1. Query all bugs for platform   │ │ 1. Check DB cache (advisory_id)  ││
│   │ 2. Filter by version             │ │ 2. Check FAISS exact match       ││
│   │ 3. Filter by hardware model      │ │ 3. Run SEC-8B inference          ││
│   │ 4. Filter by features/labels     │ │ 4. Cache high-confidence results ││
│   │ 5. Group by severity             │ │                                  ││
│   └──────────────────────────────────┘ └──────────────────────────────────┘│
│                       │                              │                      │
│                       ▼                              ▼                      │
│   ┌──────────────────────────────────────────────────────────────────────┐ │
│   │                        vulnerability_db.sqlite                        │ │
│   │                        (vulnerabilities table)                        │ │
│   └──────────────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────────────┘
```

### Path A: Database Scan (Fast)

```python
# db_scanner.py:48-219
def scan_device(platform, version, labels, hardware_model):
    # 1. Get all bugs for platform
    cursor.execute("""
        SELECT bug_id, headline, severity, affected_versions_raw,
               labels, hardware_model, vuln_type
        FROM vulnerabilities
        WHERE platform = ?
    """, (platform,))

    # 2. Version matching
    normalized = self._normalize_version(version)  # 17.03.05 → 17.3.5
    version_matches = [b for b in all_bugs
                       if normalized in b['affected_versions_raw']]

    # 3. Hardware filtering (40-60% reduction)
    if hardware_model:
        hardware_matches = [b for b in version_matches
                           if b['hardware_model'] is None  # Generic bugs
                           or b['hardware_model'] == hardware_model]

    # 4. Feature filtering (additional reduction)
    if labels:
        for bug in hardware_matches:
            bug_labels = json.loads(bug['labels'] or '[]')
            if bug_labels:  # Has labels
                if any(label in labels for label in bug_labels):
                    feature_matches.append(bug)
            else:  # No labels = keep (conservative)
                feature_matches.append(bug)

    return {
        'scan_id': 'scan-xxx',
        'bugs': [...],
        'bug_count': N,
        'psirt_count': M,
        'critical_high': X,
        'medium_low': Y,
        'query_time_ms': 5.2
    }
```

### Path B: LLM Analysis

```python
# ai_analyzer.py
def analyze_psirt(summary, platform, advisory_id):
    # Tier 1: Database cache (<10ms)
    if advisory_id:
        cached = self._check_db_cache(advisory_id)
        if cached:
            return {'source': 'database', 'labels': cached['labels']}

    # Tier 2: FAISS exact match (~30ms)
    faiss_result = self._check_faiss_cache(summary)
    if faiss_result:
        return {'source': 'faiss', 'labels': faiss_result['labels']}

    # Tier 3: SEC-8B inference (~2s)
    labels = self.sec8b.predict_labels(summary, platform)

    # Cache if high confidence
    if labels['confidence'] >= 0.75:
        self._cache_result(advisory_id, labels)

    return {'source': 'mlx', 'labels': labels}
```

### Key Files

| File | Purpose |
|------|---------|
| `backend/core/vulnerability_scanner.py` | Facade (public interface) |
| `backend/core/scan_router.py` | Request routing |
| `backend/core/db_scanner.py` | Fast database path |
| `backend/core/ai_analyzer.py` | LLM analysis path |
| `backend/core/sec8b.py` | SEC-8B model wrapper |

---

## 5. PSIRT Analysis (LLM Path)

For new/unknown PSIRTs, the system uses SEC-8B for label prediction.

### Three-Tier Caching

```
┌──────────────────────────────────────────────────────────────────────────┐
│                    PSIRT ANALYSIS CACHING TIERS                           │
│                                                                           │
│   Request: "Analyze cisco-sa-iosxe-ssh-dos"                               │
│                                                                           │
│   ┌────────────────────────────────────────────────────────────────────┐ │
│   │ TIER 1: Database Cache                                              │ │
│   │ ─────────────────────────────────────────────────────────────────── │ │
│   │ Speed: <10ms                                                        │ │
│   │ Check: vulnerabilities table WHERE advisory_id = ?                  │ │
│   │ Hit:   Return cached labels, confidence, source='database'          │ │
│   │ Miss:  → Tier 2                                                     │ │
│   └────────────────────────────────────────────────────────────────────┘ │
│                              │                                            │
│                              ▼ (miss)                                     │
│   ┌────────────────────────────────────────────────────────────────────┐ │
│   │ TIER 2: FAISS Exact Match                                           │ │
│   │ ─────────────────────────────────────────────────────────────────── │ │
│   │ Speed: ~30ms                                                        │ │
│   │ Check: FAISS index with advisory_id as key                          │ │
│   │ Hit:   Return training example labels, source='faiss'               │ │
│   │ Miss:  → Tier 3                                                     │ │
│   └────────────────────────────────────────────────────────────────────┘ │
│                              │                                            │
│                              ▼ (miss)                                     │
│   ┌────────────────────────────────────────────────────────────────────┐ │
│   │ TIER 3: MLX Inference (SEC-8B + LoRA v3)                            │ │
│   │ ─────────────────────────────────────────────────────────────────── │ │
│   │ Speed: ~2s                                                          │ │
│   │ Process:                                                            │ │
│   │   1. Build prompt with taxonomy context                             │ │
│   │   2. Run SEC-8B inference                                           │ │
│   │   3. Parse labels from response                                     │ │
│   │   4. If confidence >= 75%, cache to database                        │ │
│   │ Return: labels, confidence, source='mlx'                            │ │
│   └────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────┘
```

### FAISS Similarity Search Configuration

The FAISS index requires `models/embedder_info.json` to configure the sentence transformer embedder:

```json
{
  "model_name": "sentence-transformers/all-MiniLM-L6-v2",
  "dimension": 384,
  "num_examples": 7681,
  "source_file": "merged_with_silver_labels"
}
```

**Data Flow:**
```
┌──────────────────────┐     ┌───────────────────────┐     ┌──────────────────┐
│  embedder_info.json  │────▶│  SentenceTransformer  │────▶│  FAISS Search    │
│  (config)            │     │  (embedding model)    │     │  (similarity)    │
└──────────────────────┘     └───────────────────────┘     └──────────────────┘
```

**Files that reference embedder_info.json:**
- `fewshot_inference.py:24-31` - Loads embedder config for similarity search
- `build_faiss_index.py:52-60` - Reads config when building index
- `query_fewshot_faiss.py:38-45` - Uses config for query embedding

### Key Files

| File | Purpose |
|------|---------|
| `backend/core/sec8b.py` | SEC-8B model wrapper |
| `mlx_inference.py` | MLX-based inference engine |
| `backend/core/ai_analyzer.py` | Caching and orchestration |
| `models/faiss_index.bin` | FAISS index for training examples |
| `models/embedder_info.json` | **REQUIRED** - Embedder config for FAISS |

---

## 6. AI Assistant Intent Classification

The `/ask` endpoint uses a 3-tier hybrid intent classification system.

### Intent Classification Flow

```
┌──────────────────────────────────────────────────────────────────────────┐
│                    INTENT CLASSIFICATION                                  │
│                                                                           │
│   User Question: "Which devices have critical bugs?"                      │
│                                                                           │
│   ┌────────────────────────────────────────────────────────────────────┐ │
│   │ TIER 1: Quick Override (~0ms)                                       │ │
│   │ ─────────────────────────────────────────────────────────────────── │ │
│   │ Check: Keyword combinations that clearly indicate intent            │ │
│   │                                                                     │ │
│   │ if 'device' in q and ('critical' or 'high' in q):                  │ │
│   │     return DEVICES_BY_RISK (confidence=0.95)                        │ │
│   │                                                                     │ │
│   │ if 'recommend' or 'prioriti' in q:                                  │ │
│   │     return PRIORITIZE (confidence=0.95)                             │ │
│   │                                                                     │ │
│   │ Match? → Return immediately                                         │ │
│   │ No match? → Tier 2                                                  │ │
│   └────────────────────────────────────────────────────────────────────┘ │
│                              │                                            │
│                              ▼ (no override)                              │
│   ┌────────────────────────────────────────────────────────────────────┐ │
│   │ TIER 2: Keyword Scoring (~1ms)                                      │ │
│   │ ─────────────────────────────────────────────────────────────────── │ │
│   │ Score ALL intents based on:                                         │ │
│   │   - Keyword matches (weight × count)                                │ │
│   │   - Required keywords (must have one)                               │ │
│   │   - Excluded keywords (penalty)                                     │ │
│   │   - Special patterns (device names, labels, advisories)             │ │
│   │   - Regex pattern bonus                                             │ │
│   │                                                                     │ │
│   │ scores = {                                                          │ │
│   │   DEVICES_BY_RISK: 25,    ← Best match                              │ │
│   │   LIST_VULNERABILITIES: 8,                                          │ │
│   │   PRIORITIZE: 3,                                                    │ │
│   │   ...                                                               │ │
│   │ }                                                                   │ │
│   │                                                                     │ │
│   │ if best_score >= 15 or margin >= 5:                                 │ │
│   │     return best_intent (confidence based on margin)                 │ │
│   │ elif best_score >= 5:                                               │ │
│   │     return best_intent (medium confidence)                          │ │
│   │ else:                                                               │ │
│   │     → Tier 3 (if enabled)                                           │ │
│   └────────────────────────────────────────────────────────────────────┘ │
│                              │                                            │
│                              ▼ (ambiguous)                                │
│   ┌────────────────────────────────────────────────────────────────────┐ │
│   │ TIER 3: LLM Fallback (~1-2s)                                        │ │
│   │ ─────────────────────────────────────────────────────────────────── │ │
│   │ Use SEC-8B to classify ambiguous queries                            │ │
│   │ Only used when: margin < 3 AND use_llm_fallback=True                │ │
│   │                                                                     │ │
│   │ Returns: intent with 0.85 confidence                                │ │
│   └────────────────────────────────────────────────────────────────────┘ │
│                                                                           │
│   ┌────────────────────────────────────────────────────────────────────┐ │
│   │ INTENT HANDLERS                                                     │ │
│   │ ─────────────────────────────────────────────────────────────────── │ │
│   │ DEVICES_BY_RISK     → _handle_devices_by_risk()                     │ │
│   │ DEVICE_VULNERABILITIES → _handle_device_vulnerabilities()           │ │
│   │ PRIORITIZE          → _handle_prioritize()                          │ │
│   │ LIST_VULNERABILITIES → _handle_list_vulnerabilities()               │ │
│   │ SUMMARY             → self.summary()                                │ │
│   │ EXPLAIN_LABEL       → _handle_explain_label()                       │ │
│   │ COUNT               → _handle_count()                               │ │
│   │ ...                                                                 │ │
│   └────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────┘
```

### Supported Intents

| Intent | Example Question | Handler |
|--------|-----------------|---------|
| `LIST_VULNERABILITIES` | "What bugs affect IOS-XE?" | Query vulnerabilities table |
| `LIST_DEVICES` | "Show me all devices" | Query device_inventory |
| `DEVICE_VULNERABILITIES` | "What bugs affect C9200L?" | Query device's scan results |
| `DEVICES_BY_RISK` | "Which devices have critical bugs?" | Aggregate from scan results |
| `PRIORITIZE` | "What should I focus on?" | Rank bugs by severity + device count |
| `EXPLAIN_VULNERABILITY` | "Explain cisco-sa-xxx" | Fetch PSIRT + taxonomy context |
| `EXPLAIN_LABEL` | "What is SEC_CoPP?" | Load from taxonomy YAML |
| `REMEDIATION` | "How do I fix the WebUI bug?" | Generate remediation guidance |
| `SUMMARY` | "Give me a security summary" | Run `summary()` method |
| `COUNT` | "How many critical bugs?" | COUNT query |
| `COMPARE_VERSIONS` | "Compare 17.9.1 to 17.12.1" | Run two scans, compare |

### Key Files

| File | Lines | Purpose |
|------|-------|---------|
| `backend/core/reasoning_engine.py` | 33-115 | Intent patterns & keywords |
| `backend/core/reasoning_engine.py` | 178-201 | `_quick_intent_override()` |
| `backend/core/reasoning_engine.py` | 203-265 | `_score_intent()` |
| `backend/core/reasoning_engine.py` | 268-343 | `classify_intent()` |
| `backend/core/reasoning_engine.py` | 800-1800 | Intent handlers |

---

## 7. System Administration

The System Admin tab provides database management, health monitoring, and cache control.

### Data Sources

```
┌──────────────────────────────────────────────────────────────────────────┐
│                    SYSTEM ADMIN DATA FLOWS                                │
│                                                                           │
│   ┌─────────────────────────────────────────────────────────────────────┐│
│   │ Database Stats (GET /api/v1/system/stats/database)                   ││
│   │                                                                      ││
│   │ Source: vulnerability_db.sqlite                                      ││
│   │ Queries:                                                             ││
│   │   SELECT COUNT(*) FROM vulnerabilities                               ││
│   │   SELECT vuln_type, COUNT(*) FROM vulnerabilities GROUP BY vuln_type ││
│   │   SELECT platform, COUNT(*) FROM vulnerabilities GROUP BY platform   ││
│   │   SELECT value FROM db_metadata WHERE key='last_update'              ││
│   └─────────────────────────────────────────────────────────────────────┘│
│                                                                           │
│   ┌─────────────────────────────────────────────────────────────────────┐│
│   │ System Health (GET /api/v1/system/health)                            ││
│   │                                                                      ││
│   │ Sources:                                                             ││
│   │   - Database file existence and size                                 ││
│   │   - MLX model status (loaded/available)                              ││
│   │   - FAISS index status                                               ││
│   │   - Memory usage                                                     ││
│   │   - API response time                                                ││
│   └─────────────────────────────────────────────────────────────────────┘│
│                                                                           │
│   ┌─────────────────────────────────────────────────────────────────────┐│
│   │ Cache Stats (GET /api/v1/system/cache/stats)                         ││
│   │                                                                      ││
│   │ Sources:                                                             ││
│   │   - FAISS index entry count                                          ││
│   │   - Database cache hit rate                                          ││
│   │   - LRU cache statistics                                             ││
│   └─────────────────────────────────────────────────────────────────────┘│
│                                                                           │
│   ┌─────────────────────────────────────────────────────────────────────┐│
│   │ Offline Updates (POST /api/v1/system/update/offline)                 ││
│   │                                                                      ││
│   │ Process:                                                             ││
│   │   1. Upload ZIP package                                              ││
│   │   2. Validate structure and checksums                                ││
│   │   3. Backup existing database                                        ││
│   │   4. Apply updates (bugs, PSIRTs, taxonomies)                        ││
│   │   5. Rebuild indexes                                                 ││
│   └─────────────────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────────────┘
```

### Key Files

| File | Purpose |
|------|---------|
| `backend/api/routes.py` | System API endpoints |
| `frontend/src/components/SystemAdmin.tsx` | Admin UI |
| `frontend/src/api/client.ts` | `systemApi` object |

---

## Quick Reference: Data Source by UI Element

| UI Element | Data Source | API Endpoint |
|------------|-------------|--------------|
| AI Assistant → Risk Level | Aggregated from `last_scan_result` | `/reasoning/summary` |
| AI Assistant → Bugs Affecting Inventory | Sum of `last_scan_result.total_bugs` | `/reasoning/summary` |
| AI Assistant → Critical + High | Sum of `last_scan_result.bug_critical_high` | `/reasoning/summary` |
| AI Assistant → Database Totals (Bugs) | `vulnerabilities WHERE vuln_type='bug'` | `/reasoning/summary` |
| AI Assistant → Database Totals (PSIRTs) | `vulnerabilities WHERE vuln_type='psirt'` | `/reasoning/summary` |
| Device Inventory → Device List | `device_inventory` table | `/inventory/devices` |
| Device Inventory → Stats | `device_inventory` GROUP BY | `/inventory/stats` |
| Vulnerability Scanner → Scan Results | `vulnerabilities` + filtering | `/scan-device` |
| PSIRT Analysis → Labels | SEC-8B or cache | `/analyze-psirt` |
| System Admin → DB Stats | `vulnerabilities` + `db_metadata` | `/system/stats/database` |

---

## 8. Verified API Response Structures

This section documents the actual tested API responses (verified December 16, 2025).

### `/api/v1/scan-device` Response

```json
{
  "scan_id": "scan-1bde2b31",
  "platform": "IOS-XE",
  "version": "17.10.1",
  "hardware_model": null,
  "features": null,
  "total_bugs_checked": 783,
  "version_matches": 16,
  "hardware_filtered": null,
  "hardware_filtered_count": 0,
  "feature_filtered": null,
  "critical_high": 1,
  "medium_low": 15,
  "bug_count": 16,           // NEW in v3.1+
  "psirt_count": 0,          // NEW in v3.1+
  "bug_critical_high": 1,    // NEW in v3.1+
  "psirt_critical_high": 0,  // NEW in v3.1+
  "bugs": [...],
  "timestamp": "...",
  "query_time_ms": 2.9
}
```

### `/api/v1/reasoning/summary` Response

```json
{
  "request_id": "sum-xxx",
  "period": "Past 7 days",
  "total_advisories": 12,           // Bugs affecting YOUR inventory
  "total_bugs_in_db": 9705,         // Reference: total in database
  "inventory_devices_scanned": 1,   // Devices with scan data
  "inventory_critical_high": 0,     // From aggregated last_scan_result
  "inventory_medium_low": 12,
  "inventory_platforms": ["IOS-XE"],
  "affecting_environment": 0,
  "summary_text": "...",
  "risk_assessment": "low",
  "critical_actions": [...],
  "bugs": {
    "total": 9617,
    "critical_high": 3069,
    "by_platform": {...}
  },
  "psirts": {
    "total": 88,
    "critical_high": 0,
    "by_platform": {...},
    "affecting_inventory": 0,
    "inventory_critical_high": 0
  }
}
```

### `/api/v1/reasoning/ask` Response (DEVICES_BY_RISK intent)

```json
{
  "request_id": "ask-xxx",
  "question": "Which devices have critical bugs?",
  "answer": "Good news! None of your 1 scanned devices have critical or high severity bugs...",
  "sources": [{"type": "inventory", "scanned_devices": 1}],
  "suggested_actions": ["View device details", "Get remediation for specific bug"],
  "confidence": 0.95,
  "reasoning_time_ms": 1.185
}
```

### `last_scan_result` JSON (stored in device_inventory)

```json
{
  "scan_id": "scan-53b43406",
  "timestamp": "2025-12-16T15:12:14.665751",
  "platform": "IOS-XE",
  "version": "17.03.05",
  "hardware_model": "Cat9200",
  "total_bugs_checked": 783,
  "version_matches": 33,
  "hardware_filtered": 25,
  "feature_filtered": 12,
  "total_bugs": 12,           // Used by reasoning/summary
  "bug_critical_high": 0,     // Used by reasoning/summary
  "total_psirts": 0,          // Used by reasoning/summary
  "psirt_critical_high": 0,   // Used by reasoning/summary
  "critical_high": 0,
  "medium_low": 12,
  "query_time_ms": 1.74
}
```

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.2 | 2025-12-19 | Added FAISS embedder_info.json documentation, data flow diagram |
| 1.1 | 2025-12-16 | Added verified API response structures, documented `bug_count`/`psirt_count` fields |
| 1.0 | 2025-12-16 | Initial comprehensive documentation |
