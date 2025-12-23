# CVE_EVAL_V2: API Reference & Feature Documentation

**Version:** 3.2 | **Last Updated:** December 16, 2025

> [!IMPORTANT]
> **MAINTENANCE REQUIREMENT**
> This document describes all API endpoints and features of the system.
> **IT MUST BE UPDATED** whenever new endpoints are added or existing functionality changes.

> **Version 3.0 Release:** See **[CHANGELOG_V3.md](CHANGELOG_V3.md)** for complete release notes, breaking changes, and migration guide.

## 1. API Overview

The system exposes three API routers:
- **Core Routes** (`/api/v1/`): PSIRT analysis, device scanning, exports
- **Inventory Routes** (`/api/v1/inventory/`): Device management, ISE integration, scan tracking
- **System Routes** (`/api/v1/system/`): Offline updates, health monitoring, cache management

### Base URLs
- **Development**: `http://localhost:8000`
- **API Documentation**: `http://localhost:8000/docs` (Swagger UI)

## 2. Core API Endpoints

### 2.1 Health Check Endpoints

#### `GET /api/v1/health`
Basic health check to verify API is running.

**Response:**
```json
{
    "status": "healthy",
    "message": "PSIRT Analysis API is running"
}
```

#### `GET /api/v1/health/db`
Database health check with detailed statistics.

**Response:**
```json
{
    "status": "healthy",
    "db_path": "vulnerability_db.sqlite",
    "journal_mode": "wal",
    "busy_timeout_ms": 5000,
    "foreign_keys_enabled": true,
    "tables": ["vulnerabilities", "device_inventory", "scan_results", ...],
    "table_count": 7,
    "size_mb": 32.03,
    "latency_ms": 1.29
}
```

---

### 2.2 PSIRT Analysis

#### `POST /api/v1/analyze-psirt`
Analyze a PSIRT summary using SEC-8B AI model to predict affected features.

**Request:**
```json
{
    "summary": "A vulnerability in BGP implementation of Cisco IOS XE allows remote attacker to cause DoS",
    "platform": "IOS-XE",
    "advisory_id": "cisco-sa-20231025-bgp" // optional
}
```

**Response:**
```json
{
    "analysis_id": "uuid-string",
    "psirt_summary": "...",
    "platform": "IOS-XE",
    "advisory_id": "cisco-sa-20231025-bgp",
    "predicted_labels": ["RTE_BGP"],
    "confidence": 0.621,
    "config_regex": ["^router bgp"],
    "show_commands": ["show ip bgp summary"],
    "source": "llm",
    "cached": false,
    "needs_review": true,
    "confidence_source": "heuristic",
    "timestamp": "2025-12-14T14:00:00"
}
```

**Key Fields:**
| Field | Description |
|-------|-------------|
| `predicted_labels` | Feature labels predicted by SEC-8B |
| `confidence` | FAISS similarity score (0.0-1.0) |
| `needs_review` | `true` if confidence < 0.70 |
| `confidence_source` | `model` (high conf), `heuristic` (low conf), `cache` |
| `config_regex` | Patterns to search in device config |
| `show_commands` | CLI commands for verification |

**Three-Tier Caching:**
1. **Tier 1 (Database)**: <10ms - Previously analyzed PSIRTs
2. **Tier 2 (FAISS Exact)**: ~30ms - Advisory ID in training data
3. **Tier 3 (LLM Inference)**: ~2-3s - New PSIRTs via SEC-8B

---

### 2.3 Vulnerability Scanning

#### `POST /api/v1/scan-device`
Scan for vulnerabilities by version, hardware, and features.

**Request:**
```json
{
    "platform": "IOS-XE",
    "version": "17.10.1",
    "hardware_model": "Cat9300",      // optional - 25% reduction
    "labels": ["MGMT_SSH_HTTP", "SEC_CoPP"]  // optional - 40-80% reduction
}
```

**Response:**
```json
{
    "scan_id": "scan-15a9974b",
    "platform": "IOS-XE",
    "version": "17.10.1",
    "hardware_model": "Cat9300",
    "features": ["MGMT_SSH_HTTP", "SEC_CoPP"],
    "total_bugs_checked": 731,
    "version_matches": 16,
    "hardware_filtered": 12,
    "hardware_filtered_count": 4,
    "feature_filtered": 3,
    "critical_high": 1,
    "medium_low": 2,
    "bug_count": 3,
    "psirt_count": 0,
    "bug_critical_high": 1,
    "psirt_critical_high": 0,
    "bugs": [
        {
            "bug_id": "CSCwo92456",
            "severity": 2,
            "headline": "...",
            "summary": "...",
            "status": "Open",
            "affected_versions": "17.10.1 17.12.4",
            "labels": ["SYS_Boot_Upgrade"],
            "url": "https://bst.cisco.com/bugsearch/bug/CSCwo92456",
            "vuln_type": "bug"
        }
    ],
    "timestamp": "2025-12-14T14:00:00",
    "query_time_ms": 2.5
}
```

**New Fields (v3.1):**
| Field | Description |
|-------|-------------|
| `bug_count` | Number of bugs matching version + hardware + features |
| `psirt_count` | Number of PSIRTs matching version + hardware + features |
| `bug_critical_high` | Critical/High severity bugs |
| `psirt_critical_high` | Critical/High severity PSIRTs |
| `vuln_type` | Type identifier: "bug" or "psirt" |

**Note:** PSIRTs require `affected_versions_raw` data populated in the database for accurate version matching. PSIRTs without version data will not appear in scan results.

**False Positive Reduction:**
| Filter | Reduction | When Applied |
|--------|-----------|--------------|
| Version only | 0% (baseline) | Always |
| + Hardware model | ~25% | If `hardware_model` provided |
| + Feature labels | ~40-80% | If `labels` provided |
| Combined | ~85%+ | Both provided |

---

### 2.4 Device Verification

#### `POST /api/v1/verify-device`
Verify device vulnerability via live SSH connection.

**Request:**
```json
{
    "host": "192.168.1.1",
    "username": "admin",
    "password": "secret",
    "platform": "IOS-XE",
    "labels": ["MGMT_SSH_HTTP"],
    "config_regex": ["^ip ssh"],
    "show_commands": ["show ip ssh"]
}
```

**Response:**
```json
{
    "verification_id": "uuid",
    "device_info": {
        "hostname": "switch1",
        "platform": "IOS-XE",
        "version": "17.10.1"
    },
    "features_detected": ["MGMT_SSH_HTTP"],
    "vulnerable": true,
    "verification_details": {...},
    "timestamp": "2025-12-14T14:00:00"
}
```

#### `POST /api/v1/verify-snapshot`
Verify against pre-extracted device snapshot (air-gapped support).

**Request:**
```json
{
    "snapshot": {
        "hostname": "switch1",
        "platform": "IOS-XE",
        "version": "17.10.1",
        "features": ["MGMT_SSH_HTTP", "RTE_OSPF"]
    },
    "labels": ["MGMT_SSH_HTTP"],
    "config_regex": ["^ip ssh"]
}
```

#### `POST /api/v1/extract-features`
Extract features from a live device via SSH.

**Request:**
```json
{
    "host": "192.168.1.1",
    "username": "admin",
    "password": "secret"
}
```

**Response:**
```json
{
    "hostname": "switch1",
    "platform": "IOS-XE",
    "version": "17.10.1",
    "hardware_model": "Cat9300",
    "features": ["MGMT_SSH_HTTP", "RTE_OSPF", "SEC_ACL"],
    "extraction_time": "2025-12-14T14:00:00"
}
```

---

### 2.5 Export Endpoints

#### `POST /api/v1/export/csv`
Export scan results to CSV format.

**Request:** Full `ScanResult` object from `/scan-device`

**Response:** CSV file download with columns:
- Bug ID, Severity, Headline, Summary, Status, Affected Versions, Labels, URL

#### `POST /api/v1/export/json`
Export scan results to formatted JSON.

**Request:** Full `ScanResult` object

**Response:** Formatted JSON with metadata

#### `POST /api/v1/export/pdf`
Export scan results to PDF report.

**Request:** Full `ScanResult` object

**Response:** PDF file download

**Note:** Requires `reportlab` package: `pip install reportlab`

---

### 2.6 Results Retrieval

#### `GET /api/v1/results/{analysis_id}`
Retrieve cached PSIRT analysis result.

**Response:** Same as `/analyze-psirt` response

---

## 3. Inventory API Endpoints

### 3.1 ISE Integration

#### `POST /api/v1/inventory/sync-ise`
Synchronize device inventory from Cisco ISE.

**Request:**
```json
{
    "use_mock": true  // Use mock ISE for testing
}
```

**Response:**
```json
{
    "success": true,
    "synced_devices": 10,
    "new_devices": 5,
    "updated_devices": 3,
    "errors": []
}
```

---

### 3.2 Device Discovery

#### `POST /api/v1/inventory/discover-device`
Discover device details via SSH.

**Request:**
```json
{
    "device_id": 31,
    "username": "admin",
    "password": "secret"
}
```

**Response:**
```json
{
    "success": true,
    "device_id": 31,
    "hostname": "switch1",
    "platform": "IOS-XE",
    "version": "17.10.1",
    "hardware_model": "Cat9300",
    "features": ["MGMT_SSH_HTTP", "RTE_OSPF"],
    "discovery_status": "success"
}
```

---

### 3.3 Device Listing

#### `GET /api/v1/inventory/devices`
List devices with optional filtering.

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `platform` | string | Filter by platform (IOS-XE, IOS-XR, etc.) |
| `status` | string | Filter by discovery_status (pending, success, failed) |
| `limit` | int | Max results (default: 100) |
| `offset` | int | Pagination offset |

**Response:**
```json
{
    "success": true,
    "total_devices": 10,
    "devices": [
        {
            "id": 31,
            "hostname": "C9200L",
            "ip_address": "192.168.0.33",
            "platform": "IOS-XE",
            "version": "17.9.1",
            "hardware_model": "Cat9200L",
            "features": ["MGMT_SSH_HTTP"],
            "discovery_status": "success",
            "last_scan_id": "scan-abc123",
            "last_scan_timestamp": "2025-12-14T14:00:00"
        }
    ]
}
```

#### `GET /api/v1/inventory/devices/{device_id}`
Get single device details.

#### `GET /api/v1/inventory/stats`
Get inventory statistics.

**Response:**
```json
{
    "success": true,
    "total_devices": 10,
    "by_status": {
        "pending": 9,
        "success": 1
    },
    "by_platform": {
        "IOS-XE": 1
    },
    "needs_scan": 9
}
```

---

### 3.4 Vulnerability Scanning (Inventory)

#### `POST /api/v1/inventory/scan-device/{device_id}`
Scan an inventory device and save results.

**Response:**
```json
{
    "success": true,
    "device_id": 31,
    "hostname": "C9200L",
    "scan_summary": {
        "scan_id": "scan-abc123",
        "total_bugs": 12,
        "bug_critical_high": 0,
        "total_psirts": 0,
        "psirt_critical_high": 0,
        "critical_high": 0,
        "medium_low": 12,
        "timestamp": "2025-12-14T14:00:00"
    }
}
```

**New Summary Fields (v3.1):**
| Field | Description |
|-------|-------------|
| `total_bugs` | Bugs matching device version + hardware + features |
| `bug_critical_high` | Critical/High severity bugs |
| `total_psirts` | PSIRTs matching device version + features |
| `psirt_critical_high` | Critical/High severity PSIRTs |

**Features:**
- Uses cached device metadata (platform, version, hardware, features)
- Saves full results to `scan_results` table
- Rotates previous scan for comparison
- Scans both bugs AND PSIRTs (PSIRTs require version data)

#### `GET /api/v1/inventory/scan-results/{scan_id}`
Retrieve full vulnerability details for a scan.

**Response:**
```json
{
    "success": true,
    "scan_id": "scan-abc123",
    "device_id": 31,
    "timestamp": "2025-12-14T14:00:00",
    "result": {
        "platform": "IOS-XE",
        "version": "17.9.1",
        "vulnerabilities": [...]
    }
}
```

---

### 3.5 Comparison Features

#### `POST /api/v1/inventory/compare-scans`
Compare two scan results from the same device.

**Use Cases:**
- Config change validation (did enabling CoPP introduce new vulns?)
- Patch verification (did the upgrade fix what we expected?)
- Change management audit trail

**Query Parameters:**
```
?current_scan_id=scan-abc123&previous_scan_id=scan-xyz789
```

**Response:**
```json
{
    "success": true,
    "comparison_id": "comp-abc123-xyz789",
    "current_scan": {
        "scan_id": "scan-abc123",
        "timestamp": "2025-12-14T14:00:00",
        "platform": "IOS-XE",
        "version": "17.10.1",
        "total_vulnerabilities": 12
    },
    "previous_scan": {
        "scan_id": "scan-xyz789",
        "timestamp": "2025-12-13T10:00:00",
        "platform": "IOS-XE",
        "version": "17.9.1",
        "total_vulnerabilities": 17
    },
    "fixed_bugs": [...],      // Bugs no longer present
    "new_bugs": [...],        // Bugs newly introduced
    "unchanged_bugs": [...],  // Bugs present in both
    "summary": {
        "total_fixed": 8,
        "total_new": 3,
        "total_unchanged": 9,
        "net_change": -5,
        "fixed_by_severity": {"Critical": 1, "High": 2, ...},
        "new_by_severity": {"Critical": 0, "High": 1, ...}
    }
}
```

#### `POST /api/v1/inventory/compare-versions`
Compare vulnerabilities between two software versions for upgrade planning.

**Use Cases:**
- Upgrade planning (what bugs will be fixed by upgrading?)
- Downgrade risk assessment (what new bugs would I get?)
- Version selection (compare multiple target versions)

**Request:**
```json
{
    "platform": "IOS-XE",
    "current_version": "17.9.1",
    "target_version": "17.12.1",
    "hardware_model": "Cat9300",           // optional
    "features": ["MGMT_SSH_HTTP", "SEC_CoPP"]  // optional
}
```

**Response (v3.0 schema):**
```json
{
    "success": true,
    "comparison_type": "version",
    "platform": "IOS-XE",
    "hardware_model": "Cat9300",
    "features_filtered": ["MGMT_SSH_HTTP", "SEC_CoPP"],
    "current_version_scan": {
        "version": "17.9.1",
        "total_bugs": 17,
        "critical_high": 2,
        "medium_low": 15
    },
    "target_version_scan": {
        "version": "17.12.1",
        "total_bugs": 15,
        "critical_high": 1,
        "medium_low": 14
    },
    "fixed_in_upgrade": [...],    // Bugs fixed by upgrading
    "new_in_upgrade": [...],      // Bugs introduced by upgrading
    "still_present": [...],       // Bugs present in both versions
    "summary": {
        "total_fixed": 13,
        "total_new": 11,
        "total_unchanged": 4,
        "net_change": -2,
        "fixed_by_severity": {"Critical": 1, "High": 3, ...},
        "new_by_severity": {"Critical": 0, "High": 2, ...}
    },
    "upgrade_recommendation": {
        "risk_level": "LOW",
        "risk_score": 25,
        "recommendation": "Upgrade recommended. Fixes 13 bugs with minimal new exposure."
    }
}
```

**Recommendation Logic:**
| Condition | Recommendation |
|-----------|----------------|
| New Critical bugs | `⚠️ CAUTION: Upgrade introduces X Critical vulnerabilities` |
| Fixes only, no new | `✅ RECOMMENDED: Upgrade fixes X vulnerabilities with no new bugs` |
| More fixed than new | `✅ FAVORABLE: Upgrade fixes X, introduces Y (net improvement)` |
| No changes | `ℹ️ NEUTRAL: No vulnerability changes between versions` |
| More new than fixed | `⚠️ REVIEW: Upgrade introduces more bugs than it fixes` |

---

### 3.6 Bulk Operations

#### `POST /api/v1/inventory/scan-all`
Scan multiple devices asynchronously.

**Request:**
```json
{
    "platforms": ["IOS-XE"],
    "device_ids": null  // null = scan all matching devices
}
```

**Response:**
```json
{
    "success": true,
    "job_id": "bulk-abc12345",
    "status": "running",
    "total_devices": 10,
    "message": "Scan started. Poll /scan-status/bulk-abc12345 for progress."
}
```

#### `GET /api/v1/inventory/scan-status/{job_id}`
Check bulk scan progress.

**Response:**
```json
{
    "success": true,
    "job_id": "bulk-abc12345",
    "status": "running",  // running, completed, failed
    "progress": {
        "total": 10,
        "completed": 6,
        "failed": 0,
        "percent": 60
    },
    "results": [...]  // Completed scan summaries
}
```

---

## 4. System Administration API Endpoints

### 4.1 Offline Updates

#### `POST /api/v1/system/update/offline`
Upload and apply an offline vulnerability database update package.

**Request:** `multipart/form-data`
| Field | Type | Description |
|-------|------|-------------|
| `file` | File | ZIP package containing manifest.json and data file |

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `skip_hash` | bool | false | Skip SHA256 verification (not recommended) |

**Response:**
```json
{
    "success": true,
    "message": "Update applied successfully",
    "inserted": 0,
    "updated": 106,
    "skipped": 0,
    "errors": [],
    "hash_verified": true,
    "hash_message": "SHA256 verified: b421a1e762ddb917..."
}
```

**Error Response:**
```json
{
    "success": false,
    "message": "Hash mismatch! Expected: b421a1e762..., Got: c532b2f873...",
    "inserted": 0,
    "updated": 0,
    "skipped": 0,
    "errors": ["Hash verification failed"]
}
```

#### `POST /api/v1/system/update/validate`
Validate an update package without applying it.

**Request:** `multipart/form-data` (same as `/update/offline`)

**Response:**
```json
{
    "valid": true,
    "message": "Package is valid and ready to apply",
    "record_count": 106,
    "platforms": ["IOS-XE", "IOS-XR"],
    "hash_verified": true,
    "hash_message": "SHA256 verified: b421a1e762ddb917..."
}
```

---

### 4.2 Database Statistics

#### `GET /api/v1/system/stats/database`
Get comprehensive database statistics.

**Response:**
```json
{
    "success": true,
    "total_vulnerabilities": 9725,
    "labeled_vulnerabilities": 1260,
    "unlabeled_vulnerabilities": 8465,
    "by_platform": {
        "IOS-XE": 835,
        "IOS-XR": 3827,
        "ASA": 1704,
        "FTD": 3326,
        "NX-OS": 33
    },
    "by_severity": {
        "1": 450,
        "2": 3200,
        "3": 4500,
        "4": 1575
    },
    "database_size_mb": 32.5,
    "last_update": "2025-12-14T19:07:51"
}
```

---

### 4.3 System Health

#### `GET /api/v1/system/health`
Get system health status with component checks.

**Response:**
```json
{
    "status": "healthy",
    "components": {
        "database": {
            "status": "healthy",
            "latency_ms": 1.2,
            "message": "Database responsive"
        },
        "cache": {
            "status": "healthy",
            "entries": 150,
            "message": "Cache operational"
        }
    },
    "uptime_seconds": 3600,
    "version": "2.1.0"
}
```

**Status Values:**
| Status | Meaning |
|--------|---------|
| `healthy` | All components operational |
| `degraded` | Some components have issues |
| `error` | Critical component failure |

---

### 4.4 Cache Management

#### `POST /api/v1/system/cache/clear`
Clear specified cache(s).

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `cache_type` | string | "all" | Which cache to clear: `psirt`, `scan`, or `all` |

**Response:**
```json
{
    "success": true,
    "message": "Cleared all caches",
    "cleared": ["psirt", "scan"]
}
```

#### `GET /api/v1/system/cache/stats`
Get cache statistics.

**Response:**
```json
{
    "success": true,
    "caches": {
        "psirt": {
            "entries": 50,
            "hit_rate": 0.85,
            "size_kb": 128
        },
        "scan": {
            "entries": 100,
            "hit_rate": 0.92,
            "size_kb": 256
        }
    },
    "total_entries": 150,
    "total_size_kb": 384
}
```

---

## 5. Feature Matrix

### 5.1 Scanning Modes

| Mode | Speed | False Positives | Use Case |
|------|-------|-----------------|----------|
| **Version-Only** | 1-2ms | High | Quick triage |
| **+ Hardware** | 1-3ms | Medium (~25% lower) | Known hardware |
| **+ Features** | 2-4ms | Low (~80% lower) | Feature-aware scan |
| **Live Device** | 5-10s | Lowest | Full verification |
| **JSON Snapshot** | <100ms | Low | Air-gapped |

### 5.2 Comparison Types

| Comparison | Use Case | Data Source |
|------------|----------|-------------|
| **compare-scans** | Before/after same device | Stored scan results |
| **compare-versions** | Upgrade planning | Live database queries |

### 5.3 Export Formats

| Format | Use Case | Dependencies |
|--------|----------|--------------|
| CSV | Spreadsheet analysis | None |
| JSON | Automation/integration | None |
| PDF | Executive reports | `reportlab` |

---

## 6. Error Handling

### Standard Error Response
```json
{
    "detail": "Error message describing the issue"
}
```

### HTTP Status Codes
| Code | Meaning | Common Causes |
|------|---------|---------------|
| 200 | Success | - |
| 400 | Bad Request | Missing/invalid parameters |
| 404 | Not Found | Device/scan ID not found |
| 500 | Server Error | Database/model errors |
| 503 | Service Unavailable | Database locked/busy |

### Database Errors
The API handles SQLite locking gracefully:
- Returns 503 with "Database is busy, please retry"
- WAL mode enabled for concurrent reads
- 5000ms busy timeout configured

---

## 7. Authentication

### Development Mode
- No authentication required when `DEV_MODE=true` or no API key configured
- CORS allows `http://localhost:3000`

### Production Mode
- Set `API_KEY` environment variable
- Pass key via `X-API-Key` header
- Configure `ALLOWED_ORIGINS` for CORS

---

## 8. Rate Limiting

| Endpoint Type | Rate Limit |
|---------------|------------|
| Default | 100 requests/minute |
| Analyze PSIRT | 30 requests/minute |
| Scan Device | 60 requests/minute |

---

## 9. Testing Endpoints

Quick test commands:

```bash
# Health check
curl http://localhost:8000/api/v1/health

# Scan device
curl -X POST http://localhost:8000/api/v1/scan-device \
  -H "Content-Type: application/json" \
  -d '{"platform": "IOS-XE", "version": "17.10.1"}'

# PSIRT analysis
curl -X POST http://localhost:8000/api/v1/analyze-psirt \
  -H "Content-Type: application/json" \
  -d '{"summary": "SSH DoS vulnerability", "platform": "IOS-XE"}'

# Compare versions
curl -X POST http://localhost:8000/api/v1/inventory/compare-versions \
  -H "Content-Type: application/json" \
  -d '{"platform": "IOS-XE", "current_version": "17.9.1", "target_version": "17.12.1"}'

# Inventory stats
curl http://localhost:8000/api/v1/inventory/stats

# System health
curl http://localhost:8000/api/v1/system/health

# Database stats
curl http://localhost:8000/api/v1/system/stats/database

# Cache stats
curl http://localhost:8000/api/v1/system/cache/stats

# Upload offline update package
curl -X POST http://localhost:8000/api/v1/system/update/offline \
  -F "file=@/path/to/update_package.zip"
```

---

## 9.5 Documentation Endpoints

Interactive HTML documentation accessible via API.

### GET `/api/v1/tutorial`

Returns an interactive HTML tutorial for using the PSIRT Analyzer.

**Response:** HTML page with styled tutorial content covering:
- Dual-path architecture (Database vs AI engine)
- How to use each UI tab effectively
- Best practices for filtering and scanning
- Air-gapped environment support

### GET `/api/v1/tutorial/json`

Returns tutorial content as structured JSON for programmatic access.

### GET `/api/v1/admin-guide`

Returns an interactive HTML admin guide for data pipelines and system maintenance.

**Response:** HTML page with styled guide content covering:
- Data stack architecture
- Loading bugs and PSIRTs
- FAISS index management
- Feature taxonomy configuration
- Air-gapped deployment procedures

### GET `/api/v1/admin-guide/json`

Returns admin guide content as structured JSON for programmatic access.

---

## 10. AI Reasoning Layer Endpoints

The Reasoning Layer provides AI-powered analysis capabilities that leverage the fine-tuned Foundation-Sec-8B model to provide contextual understanding beyond simple label assignment.

### Overview

| Endpoint | Method | Purpose | Typical Latency |
|----------|--------|---------|-----------------|
| `/api/v1/reasoning/explain` | POST | Explain why labels apply | 2-4s |
| `/api/v1/reasoning/remediate` | POST | Generate remediation guidance | 3-5s |
| `/api/v1/reasoning/ask` | POST | Natural language queries | 3-6s |
| `/api/v1/reasoning/summary` | GET | Executive posture summary | 5-10s |

### 9.1 POST `/api/v1/reasoning/explain`

Explain why specific labels apply to a PSIRT advisory, optionally in the context of a specific device.

**Use Cases:**
- "Why is this PSIRT tagged with SEC_CoPP?"
- "Is my device affected by this vulnerability?"
- "What's the technical impact of this advisory?"

**Request:**
```json
{
  "psirt_id": "cisco-sa-20231018-iosxe-webui",
  "platform": "IOS-XE",
  "device_id": 1,
  "question_type": "why"
}
```

**Response:**
```json
{
  "request_id": "expl-abc123",
  "psirt_id": "cisco-sa-20231018-iosxe-webui",
  "platform": "IOS-XE",
  "labels_explained": ["MGMT_SSH_HTTP", "SEC_CoPP"],
  "explanation": "This advisory is labeled MGMT_SSH_HTTP because...",
  "device_context": "Device: switch-core-01, Version: 17.9.4",
  "affected": true,
  "confidence": 0.92,
  "reasoning_time_ms": 2847.3,
  "timestamp": "2024-12-15T14:30:00Z"
}
```

**Question Types:**
- `why` - Explain why each label applies (default)
- `impact` - Business and operational impact analysis
- `technical` - Deep technical analysis with attack vectors

### 9.2 POST `/api/v1/reasoning/remediate`

Generate remediation guidance with specific CLI commands for a vulnerability.

**Request:**
```json
{
  "psirt_id": "cisco-sa-20231018-iosxe-webui",
  "platform": "IOS-XE",
  "device_version": "17.9.4"
}
```

**Response:**
```json
{
  "request_id": "rem-xyz789",
  "psirt_id": "cisco-sa-20231018-iosxe-webui",
  "platform": "IOS-XE",
  "severity": "critical",
  "options": [
    {
      "action": "disable_feature",
      "title": "Disable HTTP/HTTPS Server",
      "description": "Completely disables the vulnerable web UI",
      "commands": ["no ip http server", "no ip http secure-server"],
      "impact": "Web UI will be unavailable",
      "effectiveness": "full"
    },
    {
      "action": "upgrade",
      "title": "Upgrade to Fixed Version",
      "description": "Upgrade to 17.12.2 or later",
      "commands": null,
      "impact": "Requires maintenance window",
      "effectiveness": "full"
    }
  ],
  "recommended_option": 0,
  "upgrade_path": {
    "current": "17.9.4",
    "target": "17.12.2",
    "direct_upgrade": true
  },
  "confidence": 0.88,
  "reasoning_time_ms": 3124.5,
  "timestamp": "2024-12-15T14:35:00Z"
}
```

### 9.3 POST `/api/v1/reasoning/ask`

Natural language interface to query vulnerability and device data using 3-tier hybrid classification.

**Request:**
```json
{
  "question": "Which devices have critical bugs?"
}
```

**Response:**
```json
{
  "request_id": "ask-def456",
  "question": "Which devices have critical bugs?",
  "answer": "✅ **Good news!** None of your 1 scanned devices have critical or high severity bugs...",
  "sources": [
    {"type": "inventory", "scanned_devices": 1}
  ],
  "suggested_actions": ["View device details", "Get remediation for specific bug"],
  "follow_up_questions": null,
  "confidence": 0.95,
  "reasoning_time_ms": 1.2,
  "timestamp": "2025-12-16T08:18:22Z"
}
```

**3-Tier Intent Classification:**

The endpoint uses a hybrid approach for robust query routing:

| Tier | Method | Latency | Description |
|------|--------|---------|-------------|
| 1 | Quick Override | ~0ms | Keyword combinations clearly indicate intent |
| 2 | Keyword Scoring | ~1ms | Scores all intents, picks highest |
| 3 | LLM Fallback | ~1-2s | SEC-8B classifies ambiguous queries |

**Supported Intents:**

| Intent | Example Questions | Source |
|--------|-------------------|--------|
| PRIORITIZE | "What should I focus on?", "Any recommendations?" | Inventory |
| DEVICES_BY_RISK | "Which devices have critical bugs?" | Inventory |
| DEVICE_VULNERABILITIES | "What bugs affect C9200L?" | Inventory + Scan Results |
| LIST_VULNERABILITIES | "Show me critical IOS-XE bugs" | Database |
| EXPLAIN_LABEL | "What does SEC_CoPP mean?" | Taxonomy |
| REMEDIATION | "How do I fix cisco-sa-xxx?" | LLM |
| COUNT | "How many bugs in IOS-XE?" | Database |
| SUMMARY | "Give me a security summary" | Inventory + Database |

**Example Questions:**
- "Which devices have critical bugs?" (routes to inventory)
- "What bugs affect C9200L?" (shows actual bugs from scan results)
- "What should I prioritize?" (recommendations based on scan data)
- "Show me critical IOS-XE bugs" (queries vulnerabilities database)
- "What does SEC_CoPP mean?" (taxonomy lookup)

### 9.4 GET `/api/v1/reasoning/summary`

Generate an executive summary of vulnerability posture.

**Query Parameters:**
- `period` - Time period: "week", "month", or "YYYY-MM-DD:YYYY-MM-DD"
- `scope` - What to summarize: "all", "critical", or "device:{id}"
- `format` - Output format: "brief", "detailed", or "executive"

**Example Request:**
```bash
curl "http://localhost:8000/api/v1/reasoning/summary?period=week&format=executive"
```

**Response:**
```json
{
  "request_id": "sum-ghi012",
  "period": "Past 7 days",
  "total_advisories": 9586,
  "affecting_environment": 60,
  "summary_text": "**Executive Summary: Security Posture**...",
  "risk_assessment": "elevated",
  "critical_actions": [
    {
      "priority": 1,
      "action": "Address 10 critical vulnerabilities",
      "affected_devices": 20
    }
  ],
  "trends": {
    "by_severity": {"1": 10, "2": 50, "3": 100, "4": 200},
    "by_platform": {"IOS-XE": 729, "IOS-XR": 3827}
  },
  "timestamp": "2024-12-15T14:45:00Z"
}
```

### 9.5 Rate Limiting

Reasoning endpoints are computationally intensive and have specific rate limits:

| Endpoint | Limit |
|----------|-------|
| /explain | 30 requests/minute |
| /remediate | 20 requests/minute |
| /ask | 20 requests/minute |
| /summary | 10 requests/minute |

---

## 10. Changelog

| Date | Change | Endpoints Affected |
|------|--------|-------------------|
| 2025-12-16 | **v3.2** - 3-tier hybrid intent classification for `/ask`. New intents: PRIORITIZE, DEVICES_BY_RISK, DEVICE_VULNERABILITIES. Keyword scoring + LLM fallback. Suggested question chips in UI. | `/reasoning/ask` |
| 2025-12-15 | **v3.1** - Unified Bug/PSIRT scanning. Scanner returns separate bug and PSIRT counts. Scan summaries store PSIRT data. Reasoning engine uses scan-based PSIRT counts. | `/scan-device`, `/inventory/scan-device`, `/reasoning/summary` |
| 2025-12-15 | **v3.0 Release** - Fixed compare-versions response schema, Bug interface alignment | `/inventory/compare-versions` |
| 2025-12-15 | Added AI Reasoning Layer (explain, remediate, ask, summary) | `/reasoning/*` |
| 2025-12-14 | Added System Administration API (offline updates, health, cache) | `/system/*` |
| 2025-12-14 | Added `compare-versions` endpoint | `/inventory/compare-versions` |
| 2025-12-14 | Added `needs_review`, `confidence_source` fields | `/analyze-psirt` |
| 2025-12-12 | Added scan result storage and comparison | `/inventory/scan-results`, `/inventory/compare-scans` |
| 2025-12-08 | Added ISE sync and device inventory | `/inventory/*` |
| 2025-12-07 | Added hardware filtering | `/scan-device` |
| 2025-12-05 | Initial release | All core endpoints |

> **Full Changelog:** See **[CHANGELOG_V3.md](CHANGELOG_V3.md)** for complete v3.0 release notes.
