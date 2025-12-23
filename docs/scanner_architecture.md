# Scanner Architecture Design

## Overview

The vulnerability scanner provides two distinct paths for vulnerability assessment:

1. **Path A: Database Scan (Fast)** - Query pre-populated SQLite database for known vulnerabilities
2. **Path B: LLM Analysis (Slow)** - Use SEC-8B inference when advisory not in database

Both paths integrate with the existing device verification system for live SSH testing or snapshot validation.

## Design Goals

- **Performance**: Database queries must complete in <100ms
- **Accuracy**: Database results must match LLM quality (GPT-4o labeled data)
- **Scalability**: Support scanning thousands of devices against 2,654+ vulnerabilities
- **Incremental Updates**: Database grows as new advisories are analyzed
- **Zero External Deps**: No API calls during production scanning (post-training)

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     Scan Request                             │
│  {device_version, device_platform, device_labels}            │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
                ┌────────────────────────┐
                │  VulnerabilityScanner  │
                │   (Dual-Path Router)   │
                └────────────┬───────────┘
                             │
            ┌────────────────┴────────────────┐
            ▼                                 ▼
    ┌───────────────┐                ┌──────────────────┐
    │   PATH A:     │                │    PATH B:       │
    │ Database Scan │                │  LLM Analysis    │
    │   (FAST)      │                │   (SLOW)         │
    └───────┬───────┘                └────────┬─────────┘
            │                                 │
            ▼                                 ▼
    ┌──────────────────┐            ┌──────────────────┐
    │  SQLite Query    │            │  SEC-8B Inference│
    │  - Version Index │            │  - FAISS RAG     │
    │  - Label Index   │            │  - Few-shot      │
    │  <100ms          │            │  ~3.4s (8-bit)   │
    └──────┬───────────┘            └────────┬─────────┘
           │                                 │
           │         ┌──────────────┐        │
           └────────▶│ Cache Result │◀───────┘
                     │  (Optional)  │
                     └──────┬───────┘
                            │
                            ▼
                  ┌──────────────────┐
                  │  Result Grouping  │
                  │  - By Severity    │
                  │  - With Metadata  │
                  └─────────┬─────────┘
                            │
                            ▼
                  ┌──────────────────┐
                  │  Scan Response   │
                  │  - Critical/High  │
                  │  - Medium/Low     │
                  │  - Total Count    │
                  └──────────────────┘
```

## Path A: Database Scan (Fast)

### Purpose

Fast vulnerability scanning by querying pre-populated SQLite database containing 2,654+ labeled vulnerabilities (PSIRTs and bugs).

### Query Strategy

**Step 1: Version-Based Filtering**

```sql
-- Find vulnerabilities affecting device version
SELECT DISTINCT v.vuln_id
FROM version_index vi
JOIN vulnerabilities v ON vi.vuln_id = v.vuln_id
WHERE vi.platform = ?
  AND vi.major = ?
  AND vi.minor = ?
  AND (vi.patch IS NULL OR vi.patch <= ?);
```

**Step 2: Label-Based Filtering**

```sql
-- From version matches, find those with matching labels
SELECT v.*, li.label
FROM vulnerabilities v
JOIN label_index li ON v.vuln_id = li.vuln_id
WHERE v.vuln_id IN (version_matches)
  AND li.label IN (device_labels);
```

**Step 3: Join and Enrich**

```sql
-- Get complete vulnerability details with all labels
SELECT
    v.vuln_id,
    v.advisory_id,
    v.summary,
    v.severity,
    v.cvss_score,
    v.cves,
    v.product_names,
    v.fixed_versions,
    v.config_regex,
    v.show_commands,
    GROUP_CONCAT(li.label) as matched_labels
FROM vulnerabilities v
LEFT JOIN label_index li ON v.vuln_id = li.vuln_id
WHERE v.vuln_id IN (filtered_matches)
GROUP BY v.vuln_id;
```

### Performance Optimizations

**Indexes:**
- `(platform, major, minor, patch)` composite index on version_index
- `label` index on label_index
- `vuln_id` primary keys for fast joins

**Query Plan:**
1. Version index scan (O(log N) - indexed)
2. Label index scan (O(log M) - indexed)
3. Set intersection (O(K) - small result set)
4. Join to vulnerabilities table (O(1) per match - PK lookup)

**Expected Performance:**
- Typical device: 10-50 version matches → 5-20 label matches → <100ms
- Large result set (100+ vulns): <200ms

### Handling Edge Cases

**Unlabeled Vulnerabilities:**
- If `labels = '[]'` in database, skip label filtering
- Version match alone triggers inclusion
- Flag in response: `unlabeled: true`

**Partial Version Matches:**
- `17.3.5` matches `17.3.x` (patch wildcard)
- `17.3` matches `17.3.x` (exact major.minor)
- No cross-major matches: `17.x` != `16.x`

**Platform Mismatches:**
- Strict platform filtering (no IOS-XE != IOS-XR cross-matching)
- Multi-platform vulns have separate rows per platform

## Path B: LLM Analysis (Slow)

### Purpose

Handle new/unknown advisories not yet in database. Uses existing SEC-8B inference pipeline.

### Process

**Step 1: Check Database Cache**

```python
# Check if advisory_id already analyzed
cached = db.query("SELECT * FROM vulnerabilities WHERE advisory_id = ?", advisory_id)
if cached:
    return cached  # Skip LLM, return DB result
```

**Step 2: SEC-8B Inference**

```python
# Existing pipeline - no changes needed
analyzer = SEC8BAnalyzer()
result = analyzer.analyze_psirt(summary, platform, advisory_id)
```

**Step 3: Optional Database Caching**

```python
# Store LLM result in database for future fast scans
if should_cache(result):
    db.insert_vulnerability(result)
    db.insert_labels(result.predicted_labels)
    db.insert_versions(result.product_names)
```

### Caching Policy

**Auto-cache if:**
- Confidence >= 0.75 (HIGH confidence)
- Advisory ID provided (not ad-hoc query)
- Labels validated against taxonomy

**Do NOT cache if:**
- Confidence < 0.60 (LOW confidence)
- No advisory ID (ephemeral analysis)
- Platform not supported

## Dual-Path Routing Logic

### Decision Tree

```python
def route_request(request):
    if request.mode == "scan":
        # Path A: Scan all known vulnerabilities
        return database_scan(
            platform=request.platform,
            version=request.version,
            labels=request.labels
        )

    elif request.mode == "analyze":
        # Path B: Analyze specific advisory
        if request.advisory_id:
            # Check database first
            cached = db.get_by_advisory_id(request.advisory_id)
            if cached:
                return cached  # Fast path

        # LLM inference
        result = sec8b_analyzer.analyze(request.summary, request.platform)

        # Optional: Cache for future scans
        if should_cache(result):
            db.insert_vulnerability(result)

        return result
```

### Use Cases

| Scenario | Path | Rationale |
|----------|------|-----------|
| Network admin scans 100 devices | A | Fast batch scanning |
| New PSIRT published today | B | Not in DB yet |
| Ad-hoc "what if" analysis | B | No advisory ID |
| Compliance audit (known CVEs) | A | All CVEs in DB |
| Re-analyzing cisco-sa-xyz | A | Check DB cache first |

## Result Format and Ranking

### Response Structure

```json
{
  "scan_id": "scan-abc123",
  "device": {
    "platform": "IOS-XE",
    "version": "17.3.5",
    "labels": ["MGMT_SSH_HTTP", "SEC_CoPP", "RTE_OSPF"]
  },
  "scan_timestamp": "2025-10-10T14:30:00Z",
  "total_vulnerabilities": 12,
  "critical_high": [
    {
      "vuln_id": "vuln-001",
      "advisory_id": "cisco-sa-iosxe-ssh-dos",
      "severity": 1,
      "cvss_score": 8.6,
      "cves": ["CVE-2023-12345"],
      "summary": "Denial of Service in SSH...",
      "matched_labels": ["MGMT_SSH_HTTP"],
      "product_names": ["Cisco IOS XE 17.3.1"],
      "fixed_versions": ["17.3.6"],
      "config_regex": ["^ip ssh"],
      "show_commands": ["show ip ssh"],
      "unlabeled": false,
      "confidence": 0.87
    }
  ],
  "medium_low": [
    {
      "vuln_id": "vuln-015",
      "advisory_id": "cisco-sa-iosxe-ospf-info",
      "severity": 4,
      "summary": "Information Disclosure in OSPF..."
    }
  ],
  "source": "database",  // or "llm"
  "query_time_ms": 87
}
```

### Grouping Rules

**Critical/High (Severity 1-2):**
- Full details included
- Summary, labels, fix versions, verification commands
- Sorted by CVSS score (descending)

**Medium/Low (Severity 3-6):**
- Collapsed to save bandwidth
- Only: vuln_id, advisory_id, severity, summary
- Sorted by severity then CVSS

**Rationale:**
- Security teams triage high-severity first
- Medium/Low can be expanded on-demand via `/api/v1/vulnerability/{vuln_id}`
- Reduces response size for large result sets (100+ vulns)

## API Contracts

### POST /api/v1/scan-device

**Purpose:** Fast vulnerability scan using database

**Request:**

```json
{
  "platform": "IOS-XE",
  "version": "17.3.5",
  "labels": ["MGMT_SSH_HTTP", "SEC_CoPP", "RTE_OSPF"],
  "severity_filter": [1, 2],  // Optional: only Critical/High
  "limit": 100  // Optional: pagination
}
```

**Response:**

```json
{
  "scan_id": "scan-abc123",
  "total_vulnerabilities": 12,
  "critical_high": [...],
  "medium_low": [...],
  "source": "database",
  "query_time_ms": 87
}
```

**Performance:**
- Target: <100ms for typical scan (10-50 results)
- Timeout: 500ms (fallback to error if DB query slow)

### POST /api/v1/analyze-psirt (Modified)

**Purpose:** Analyze specific advisory (check DB first, fallback to LLM)

**Request:**

```json
{
  "summary": "A vulnerability in SSH...",
  "platform": "IOS-XE",
  "advisory_id": "cisco-sa-iosxe-ssh-dos"  // Optional
}
```

**Response:**

```json
{
  "analysis_id": "analysis-xyz789",
  "advisory_id": "cisco-sa-iosxe-ssh-dos",
  "predicted_labels": ["MGMT_SSH_HTTP"],
  "confidence": 0.87,
  "config_regex": ["^ip ssh"],
  "show_commands": ["show ip ssh"],
  "source": "database",  // or "llm"
  "cached": true,  // If result saved to DB
  "timestamp": "2025-10-10T14:30:00Z"
}
```

**Behavior Change:**
1. If `advisory_id` provided, check DB first
2. If not in DB, run SEC-8B (existing behavior)
3. If confidence >= 0.75, cache result in DB
4. Return `source` field to indicate path taken

### GET /api/v1/vulnerability/{vuln_id}

**Purpose:** Get full details for a specific vulnerability

**Response:**

```json
{
  "vuln_id": "vuln-015",
  "advisory_id": "cisco-sa-iosxe-ospf-info",
  "severity": 4,
  "cvss_score": 5.3,
  "summary": "Information Disclosure in OSPF...",
  "labels": ["RTE_OSPF"],
  "config_regex": ["^router ospf"],
  "show_commands": ["show ip ospf", "show ip protocols"],
  "product_names": ["Cisco IOS XE 17.3.1"],
  "fixed_versions": ["17.3.7"],
  "cves": ["CVE-2023-67890"]
}
```

## Integration with Existing Components

### SEC8BAnalyzer (backend/core/sec8b.py)

**No changes required** - existing interface works as-is.

**Integration point:**

```python
class VulnerabilityScanner:
    def __init__(self, db_path, sec8b_analyzer=None):
        self.db = Database(db_path)
        self.sec8b = sec8b_analyzer or get_analyzer()  # Existing singleton
```

### API Routes (backend/api/routes.py)

**Modify `/analyze-psirt` endpoint:**

```python
@router.post("/analyze-psirt")
async def analyze_psirt(request: AnalyzePSIRTRequest):
    scanner = get_scanner()

    # Use dual-path routing
    result = scanner.analyze_psirt(
        summary=request.summary,
        platform=request.platform,
        advisory_id=request.advisory_id
    )

    # Cache analysis (existing behavior)
    await save_analysis(result)

    return AnalysisResult(**result)
```

**Add new `/scan-device` endpoint:**

```python
@router.post("/scan-device")
async def scan_device(request: ScanDeviceRequest):
    scanner = get_scanner()

    # Fast database scan
    result = scanner.scan_device(
        platform=request.platform,
        version=request.version,
        labels=request.labels
    )

    return ScanResult(**result)
```

### Device Verifier (backend/core/verifier.py)

**Enhance with batch verification:**

```python
class DeviceVerifier:
    def verify_vulnerabilities(self, device, vulnerabilities):
        """
        Verify multiple vulnerabilities against one device

        More efficient than N individual verifications:
        - Connect to device once
        - Get running-config once
        - Get version once
        - Check all regex patterns in one pass
        """
        results = []

        # Connect once
        self.connect(device)
        version = self.get_version()
        config = self.get_running_config()

        # Verify each vulnerability
        for vuln in vulnerabilities:
            result = self._verify_single(vuln, version, config)
            results.append(result)

        self.disconnect()
        return results
```

## Key Design Decisions

### 1. Should scan results include verification commands?

**YES - Always include config_regex and show_commands**

**Rationale:**
- Enables immediate device verification
- Analyst can copy/paste commands to SSH session
- Frontend can auto-populate verification form
- No additional API call needed

**Trade-off:**
- Larger response size (acceptable - lists are small)
- Benefit outweighs cost

### 2. How to handle vulnerabilities with no labels?

**Include in results with `unlabeled: true` flag**

**Matching strategy:**
- Version match only (ignore label filtering)
- Flag prominently in UI: "⚠️ No feature detection available"
- Recommend manual verification

**Rationale:**
- ~40% of bugs have no labels (SEC-8B couldn't determine)
- Still valuable to know version is affected
- Better false positive than false negative

**Example:**

```json
{
  "vuln_id": "vuln-042",
  "advisory_id": "CSCabc12345",
  "unlabeled": true,
  "labels": [],
  "config_regex": [],
  "show_commands": [],
  "warning": "No feature labels available - manual verification required"
}
```

### 3. Should we cache LLM results in database automatically?

**YES - Auto-cache if confidence >= 0.75**

**Cache decision matrix:**

| Condition | Cache? | Rationale |
|-----------|--------|-----------|
| Confidence >= 0.75 + advisory_id | YES | High quality, identifiable |
| Confidence 0.60-0.74 + advisory_id | NO | Medium - may improve later |
| Confidence < 0.60 | NO | Low quality - likely wrong |
| No advisory_id | NO | Ephemeral query - no ID |

**Benefits:**
- Database grows automatically as analysts use system
- Second analyst scanning same device sees instant results
- Reduces LLM inference load over time

**Safeguards:**
- Only cache HIGH confidence (minimize bad data)
- Include confidence score in DB for future filtering
- Admin can purge low-confidence entries

### 4. How to paginate if device has 100+ vulnerabilities?

**Two-tier pagination strategy:**

**Tier 1: Severity-based grouping (built-in)**
- Critical/High (full details) - typically <20 results
- Medium/Low (collapsed) - could be 80+ results

**Tier 2: Optional limit parameter**

```json
{
  "severity_filter": [1, 2],  // Only Critical/High
  "limit": 50,                 // First 50 results
  "offset": 0
}
```

**Response includes pagination metadata:**

```json
{
  "total_vulnerabilities": 156,
  "returned": 50,
  "has_more": true,
  "next_offset": 50
}
```

**Rationale:**
- Most devices have <50 high-severity vulns
- Medium/Low can be retrieved separately if needed
- Prevents UI from hanging on massive result sets

**Frontend UX:**
- Show Critical/High immediately
- "Show 80 Medium/Low vulnerabilities" (collapsed)
- Click to expand with second API call

## Performance Targets

| Operation | Target | Stretch Goal |
|-----------|--------|--------------|
| Database scan (10-50 vulns) | <100ms | <50ms |
| Database scan (100+ vulns) | <200ms | <100ms |
| LLM analysis (cache hit) | <10ms | <5ms |
| LLM analysis (cache miss) | ~3400ms | N/A (SEC-8B) |
| Batch verification (10 vulns) | <30s | <20s |

## Error Handling

### Database Unavailable

```json
{
  "error": "database_unavailable",
  "message": "Vulnerability database unavailable - falling back to LLM",
  "fallback": true
}
```

**Behavior:**
- Auto-fallback to LLM analysis
- Return LLM result with warning
- Don't fail completely

### Version Parse Error

```json
{
  "error": "invalid_version",
  "message": "Could not parse version '17.3.abc' - expected format: X.Y.Z",
  "hint": "Example: 17.3.5"
}
```

### No Results Found

```json
{
  "scan_id": "scan-abc123",
  "total_vulnerabilities": 0,
  "critical_high": [],
  "medium_low": [],
  "message": "No known vulnerabilities for IOS-XE 17.3.5 with configured features"
}
```

**Not an error** - valid result.

## Future Enhancements

### 1. Incremental Database Updates

**Problem:** Database becomes stale as new PSIRTs published

**Solution:**
- Periodic job fetches new PSIRTs from Cisco API
- Auto-analyzes with SEC-8B
- Inserts into database
- Track in `db_metadata` table: `last_update_timestamp`

### 2. Confidence-based Filtering

**Allow filtering by confidence threshold:**

```json
{
  "platform": "IOS-XE",
  "version": "17.3.5",
  "labels": [...],
  "min_confidence": 0.80  // Only show high-confidence vulns
}
```

### 3. Multi-device Batch Scanning

**Scan multiple devices in one request:**

```json
{
  "devices": [
    {"hostname": "router1", "platform": "IOS-XE", "version": "17.3.5", ...},
    {"hostname": "router2", "platform": "IOS-XR", "version": "7.4.1", ...}
  ]
}
```

**Response:**
- Results grouped by device
- Parallel scanning (async)

### 4. Vulnerability Trending

**Track vulnerability counts over time:**
- Store scan history in `scan_history` table
- API endpoint: `GET /api/v1/trends?device_id=xyz`
- Show if vulnerability count increasing/decreasing

## Testing Strategy

### Unit Tests

**Database Scanner:**
- Test version matching logic
- Test label filtering
- Test severity grouping
- Test pagination

**LLM Analyzer:**
- Test cache hit/miss
- Test confidence thresholds
- Test caching policy

### Integration Tests

**End-to-end flow:**
1. Populate database with 100 known vulns
2. Scan device with known vulnerable version
3. Verify results match expected vulns
4. Verify query time <100ms

**Dual-path routing:**
1. Analyze known advisory (should hit DB cache)
2. Analyze unknown advisory (should hit LLM)
3. Re-analyze same advisory (should hit DB)

### Performance Tests

**Load test:**
- Scan 1000 devices against 2,654 vulns
- Measure p50, p95, p99 latency
- Ensure <100ms p95

**Stress test:**
- Concurrent scans (10 simultaneous)
- Database lock contention
- Memory usage

## Monitoring and Observability

**Key Metrics:**

- `scan_latency_ms` (histogram)
- `scan_result_count` (histogram)
- `cache_hit_rate` (%)
- `llm_fallback_rate` (%)
- `db_size_mb` (gauge)
- `queries_per_second` (rate)

**Logging:**

```python
logger.info(
    "Database scan completed",
    extra={
        "scan_id": scan_id,
        "platform": platform,
        "version": version,
        "result_count": len(results),
        "query_time_ms": elapsed_ms,
        "cache_hit": cache_hit
    }
)
```

**Alerts:**

- Query time >200ms (p95)
- Cache hit rate <80%
- Database size >500MB (needs cleanup)

## Summary

This dual-path architecture provides:

1. **Fast scanning** for known vulnerabilities (<100ms)
2. **LLM flexibility** for new/unknown advisories (3.4s)
3. **Automatic caching** for incremental database growth
4. **Backward compatibility** with existing SEC-8B pipeline
5. **Severity-based result grouping** for analyst triage
6. **Batch verification** for efficient device testing

The system balances performance (database) with flexibility (LLM) while maintaining the existing high-quality SEC-8B analysis when needed.
