# Scanner Architecture Deliverables - Summary

## Overview

This document summarizes the Phase 2 (Scanner Backend) design deliverables created by the SystemArchitectAgent.

## Deliverable Files

### 1. Scanner Architecture Design
**File:** `docs/scanner_architecture.md`

**Contents:**
- Dual-path architecture overview (Database vs LLM)
- Query strategy for fast scanning
- Result format and severity-based grouping
- API contract specifications
- Performance targets and monitoring

**Key Sections:**
- Path A: Database Scan (Fast) - <100ms target
- Path B: LLM Analysis (Slow) - SEC-8B fallback
- Dual-path routing logic
- Result grouping (Critical/High vs Medium/Low)
- Error handling and future enhancements

### 2. Scanner Class Interface
**File:** `backend/core/vulnerability_scanner.py`

**Contents:**
- VulnerabilityScanner class with complete interface
- Method signatures for scan_device() and analyze_psirt()
- Helper methods for version parsing, caching, and grouping
- Comprehensive docstrings explaining each method
- Singleton pattern for global access

**Key Methods:**
```python
def scan_device(platform, version, labels, severity_filter, limit, offset)
    # Fast database scan - PATH A

def analyze_psirt(summary, platform, advisory_id)
    # Check DB cache, fallback to SEC-8B - PATH B

def get_vulnerability_details(vuln_id)
    # Expand collapsed results on-demand
```

### 3. API Models
**File:** `backend/api/models.py` (updated)

**New Models Added:**
- `ScanDeviceRequest` - Device scan parameters
- `ScanResult` - Scan response with grouped results
- `VulnerabilityFull` - Full vulnerability details (Critical/High)
- `VulnerabilityCollapsed` - Minimal details (Medium/Low)
- `DeviceInfo`, `PaginationInfo` - Supporting models

**Updated Models:**
- `AnalysisResult` - Added `source` and `cached` fields

### 4. Integration Plan
**File:** `docs/scanner_integration_plan.md`

**Contents:**
- How scanner integrates with existing components
- Required changes to API routes
- Database layer interface requirements
- Batch verification enhancements
- Implementation sequence (Phase 1 → Phase 2 → Phase 3)
- Testing strategy (unit, integration, performance)
- Configuration and monitoring

**Key Integration Points:**
- SEC8BAnalyzer: No changes needed
- API Routes: Modify /analyze-psirt, add /scan-device
- Device Verifier: Optional batch enhancement
- Database Layer: Interface defined for VulnerabilityDBArchitectAgent

### 5. Design Decisions Document
**File:** `docs/scanner_design_decisions.md`

**Contents:**
- Detailed rationale for all four key design questions
- Trade-off analysis for each decision
- Implementation examples and edge cases
- Performance comparisons

**Questions Answered:**
1. **Include verification commands?** → YES (immediate actionability)
2. **Handle unlabeled bugs?** → Include with warning (security over convenience)
3. **Auto-cache LLM results?** → YES if confidence ≥0.75 (team consistency)
4. **Pagination strategy?** → Two-tier (severity + optional limit)

## Key Design Principles

### 1. Dual-Path Architecture

**Fast Path (Database):**
- Query SQLite for known vulnerabilities
- Version + label matching
- Target: <100ms response time

**Slow Path (LLM):**
- Check database cache first
- Fallback to SEC-8B inference
- Auto-cache high-confidence results

### 2. Security-First

**Design choices prioritize security:**
- Include unlabeled bugs (avoid false negatives)
- Version-only matching when no labels available
- Prominent warnings for manual verification
- All verification commands included by default

### 3. Performance Optimization

**Multi-level optimization:**
- Indexed database queries (version + label indexes)
- Severity-based result grouping (reduce payload)
- Optional pagination for large result sets
- Expand-on-demand for Medium/Low details

### 4. Analyst Workflow Alignment

**UI matches security triage process:**
- Critical/High vulnerabilities shown first (expanded)
- Medium/Low vulnerabilities collapsed by default
- Verification commands immediately available
- One-click expansion for details

## API Endpoints Summary

### POST /api/v1/scan-device (NEW)

**Purpose:** Fast vulnerability scan using database

**Request:**
```json
{
  "platform": "IOS-XE",
  "version": "17.3.5",
  "labels": ["MGMT_SSH_HTTP", "SEC_CoPP"],
  "severity_filter": [1, 2],
  "limit": 100
}
```

**Response:**
```json
{
  "scan_id": "scan-abc123",
  "total_vulnerabilities": 12,
  "critical_high": [...],  // Full details
  "medium_low": [...],     // Collapsed
  "source": "database",
  "query_time_ms": 87
}
```

### POST /api/v1/analyze-psirt (MODIFIED)

**Purpose:** Analyze specific advisory (DB cache → LLM fallback)

**Changes:**
- Check database cache if advisory_id provided
- Auto-cache high-confidence results
- Return `source` and `cached` fields

**New Response Fields:**
```json
{
  "analysis_id": "...",
  "source": "database",  // NEW: "database" or "llm"
  "cached": true,        // NEW: True if LLM result cached
  ...
}
```

### GET /api/v1/vulnerability/{vuln_id} (NEW)

**Purpose:** Get full details for specific vulnerability

**Use Case:** Expand collapsed Medium/Low results

**Response:** Full vulnerability details (VulnerabilityFull model)

## Result Grouping Strategy

### Critical/High (Severity 1-2)

**Full Details Included:**
- Summary, CVSS score, CVEs
- Matched labels
- Product names and fixed versions
- Config regex patterns
- Show commands
- Unlabeled flag and confidence score

**Typical Count:** 5-20 vulnerabilities
**Payload:** ~400 bytes per vulnerability

### Medium/Low (Severity 3-6)

**Minimal Details:**
- vuln_id, advisory_id
- Severity and CVSS score
- Summary only

**Typical Count:** 30-100 vulnerabilities
**Payload:** ~200 bytes per vulnerability

**Expand on-demand:** GET /api/v1/vulnerability/{vuln_id}

## Performance Targets

| Operation | Target | Stretch Goal | Notes |
|-----------|--------|--------------|-------|
| Database scan | <100ms | <50ms | 10-50 vulnerabilities |
| Large scan | <200ms | <100ms | 100+ vulnerabilities |
| Cache hit | <10ms | <5ms | DB lookup only |
| LLM inference | ~3400ms | N/A | SEC-8B (8-bit) |
| Batch verify | <30s | <20s | 10 vulnerabilities |

## Implementation Sequence

### Phase 1: Database Layer (VulnerabilityDBArchitectAgent)

**Status:** In progress

**Deliverables:**
- SQLite schema creation
- CSV data loader (2,654 labeled examples)
- VulnerabilityDatabase class
- Version and label indexes

**Blocks:** Phase 2

### Phase 2: Scanner Implementation (Next)

**Prerequisites:** Phase 1 complete

**Tasks:**
1. Complete VulnerabilityScanner implementation
2. Add API endpoints (/scan-device, /vulnerability/{id})
3. Modify /analyze-psirt for dual-path routing
4. Update app.py for initialization
5. Write unit and integration tests

**Estimated Effort:** 2-3 days

### Phase 3: Frontend Integration (Future)

**Prerequisites:** Phase 2 complete

**New UI Features:**
1. Device scan form
2. Scan results view (severity-grouped)
3. Batch verification interface
4. Expand-on-demand for Medium/Low

**Estimated Effort:** 3-4 days

## Database Interface Requirements

**For VulnerabilityDBArchitectAgent to implement:**

```python
class VulnerabilityDatabase:
    def query_version_index(platform, major, minor, patch) -> List[str]
        # Return vuln_ids matching version

    def query_label_index(vuln_ids, labels) -> List[str]
        # Filter vuln_ids by label matches

    def get_vulnerabilities(vuln_ids) -> List[Dict]
        # Get full vulnerability records

    def get_by_advisory_id(advisory_id, platform) -> Optional[Dict]
        # Check cache by advisory_id

    def insert_vulnerability(vuln) -> str
        # Cache LLM result

    def insert_label(vuln_id, label)
        # Insert into label_index

    def insert_version(vuln_id, platform, major, minor, patch)
        # Insert into version_index
```

**These methods are called by VulnerabilityScanner** - implementation details left to database architect.

## Testing Requirements

### Unit Tests

**backend/tests/test_scanner.py:**
- Version parsing (leading zeros, letter suffixes, partial versions)
- Cache decision logic (confidence thresholds)
- Severity grouping and sorting
- Pagination logic

### Integration Tests

**backend/tests/test_scanner_integration.py:**
- Dual-path routing (DB cache hit/miss)
- End-to-end scan flow
- LLM result caching
- Batch verification

### Performance Tests

**backend/tests/test_scanner_performance.py:**
- Scan latency (<100ms target)
- Large result sets (100+ vulnerabilities)
- Concurrent scans (SQLite locking)
- Cache hit rate monitoring

## Configuration

**Environment Variables:**

```bash
VULNERABILITY_DB_PATH=/path/to/vulnerability_db.sqlite
MIN_CONFIDENCE_TO_CACHE=0.75
SCAN_QUERY_TIMEOUT_MS=500
MAX_SCAN_RESULTS=1000
```

## Monitoring

**Key Metrics:**

```python
# Latency
histogram("scan.latency_ms", elapsed_ms)

# Cache performance
counter("cache.hit", tags=["source:database"])
counter("cache.miss", tags=["source:llm"])

# Result counts
histogram("scan.result_count", total_vulnerabilities)

# Database health
gauge("database.size_mb", db_size_mb)
gauge("database.vulnerability_count", total_vulns)
```

**Alerts:**

- Scan latency p95 >200ms
- Cache hit rate <80%
- Database size >500MB

## Backward Compatibility

**No Breaking Changes:**

1. Existing /analyze-psirt API unchanged (only enhanced)
2. Existing /verify-device API unchanged
3. Existing frontend still works
4. SEC-8B pipeline unchanged

**Migration Path:**

- Deploy Phase 1 → No user impact (DB layer only)
- Deploy Phase 2 → Existing APIs gain caching
- Deploy Phase 3 → New scan UI available

## Questions Answered

### 1. Should scan results include verification commands?

**Answer: YES**

**Rationale:**
- Enables immediate device verification
- Frontend can auto-populate forms
- Minimal cost (~200 bytes per vulnerability)
- Consistent with existing /analyze-psirt API

### 2. How to handle unlabeled vulnerabilities?

**Answer: Include with `unlabeled: true` flag**

**Rationale:**
- 55% of bugs have no labels (can't ignore)
- Version match alone is valuable information
- Better false positive than false negative
- Prominent warning in UI for manual verification

### 3. Should we cache LLM results automatically?

**Answer: YES, if confidence ≥0.75 and advisory_id present**

**Rationale:**
- Faster for subsequent users (3400ms → <10ms)
- Consistent results across team
- Database grows organically
- Offline capability when SEC-8B unavailable

### 4. How to paginate large result sets?

**Answer: Two-tier pagination (severity grouping + optional limit)**

**Rationale:**
- Matches analyst triage workflow
- Critical/High expanded, Medium/Low collapsed
- Handles edge cases (100+ vulnerabilities)
- Expand-on-demand for details

## Next Steps

### For VulnerabilityDBArchitectAgent (Phase 1)

1. Review this scanner architecture
2. Implement VulnerabilityDatabase class matching interface
3. Ensure indexes support fast queries (<100ms)
4. Populate database with 2,654 labeled examples
5. Signal completion for Phase 2 handoff

### For Implementation Team (Phase 2)

1. Wait for Phase 1 completion
2. Implement VulnerabilityScanner (fill TODOs in vulnerability_scanner.py)
3. Add new API endpoints to backend/api/routes.py
4. Write tests (unit, integration, performance)
5. Update app.py for initialization
6. Deploy and monitor performance

### For Frontend Team (Phase 3)

1. Wait for Phase 2 completion
2. Design device scan form
3. Implement scan results view with severity grouping
4. Add expand-on-demand for Medium/Low vulnerabilities
5. Integrate batch verification flow

## Summary

The scanner architecture provides:

1. **Fast scanning** via database (10-50ms typical)
2. **LLM flexibility** for new advisories (SEC-8B fallback)
3. **Automatic caching** for team efficiency
4. **Severity-based grouping** for analyst workflow
5. **Backward compatibility** with existing system

All design decisions prioritize:
- **Security** (don't miss vulnerabilities)
- **Performance** (fast scans, small payloads)
- **Usability** (match analyst workflow)
- **Scalability** (handle edge cases gracefully)

**Ready for implementation after Phase 1 (database layer) is complete.**
