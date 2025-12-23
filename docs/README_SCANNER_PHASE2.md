# Scanner Backend - Phase 2 Design Documentation

**Created by:** SystemArchitectAgent
**Date:** 2025-10-10
**Status:** Design Complete - Ready for Implementation

## Quick Navigation

### Start Here

**New to the project?** Read this order:

1. **SCANNER_DELIVERABLES_SUMMARY.md** (8 min read)
   - High-level overview of entire Phase 2
   - Quick answers to all key questions
   - Implementation roadmap

2. **scanner_architecture.md** (15 min read)
   - Detailed dual-path architecture
   - Database query strategy
   - API specifications and performance targets

3. **scanner_architecture_diagram.txt** (5 min browse)
   - Visual diagrams of request flow
   - Database query execution
   - UI layout and component integration

**Ready to implement?** Continue with:

4. **scanner_integration_plan.md** (20 min read)
   - How scanner integrates with existing code
   - Required changes to API routes
   - Testing strategy and deployment sequence

5. **scanner_design_decisions.md** (25 min read)
   - Detailed rationale for all design choices
   - Trade-off analysis and edge cases
   - Examples and performance comparisons

## File Overview

### Documentation (docs/)

| File | Size | Purpose | Target Audience |
|------|------|---------|-----------------|
| **SCANNER_DELIVERABLES_SUMMARY.md** | 13 KB | Executive summary of all deliverables | Project managers, architects |
| **scanner_architecture.md** | 21 KB | Complete architectural specification | Backend developers, architects |
| **scanner_architecture_diagram.txt** | 32 KB | Visual diagrams (ASCII art) | All technical roles |
| **scanner_integration_plan.md** | 23 KB | Integration guide with existing code | Implementation team |
| **scanner_design_decisions.md** | 19 KB | Rationale for key design choices | Architects, senior developers |

**Total documentation:** 108 KB across 5 files

### Implementation Files (backend/)

| File | Size | Purpose | Status |
|------|------|---------|--------|
| **backend/core/vulnerability_scanner.py** | 18 KB | VulnerabilityScanner class with complete interface | Interface defined, TODOs for implementation |
| **backend/api/models.py** | 6.1 KB | Pydantic models for scan requests/responses | Complete - ready to use |

**Total code:** 24 KB across 2 files

## What's Been Delivered

### 1. Architecture Design

**Complete dual-path architecture** balancing fast database scans with LLM flexibility:

- **Path A (Fast):** SQLite database queries for known vulnerabilities (<100ms)
- **Path B (Slow):** SEC-8B LLM inference for new/unknown advisories (~3.4s)
- **Auto-caching:** High-confidence LLM results stored in database
- **Severity grouping:** Critical/High expanded, Medium/Low collapsed

### 2. API Specifications

**Three endpoints defined:**

1. **POST /api/v1/scan-device** (NEW)
   - Fast database scan for all known vulnerabilities
   - Returns severity-grouped results with pagination

2. **POST /api/v1/analyze-psirt** (MODIFIED)
   - Enhanced with database cache check
   - Auto-cache high-confidence results

3. **GET /api/v1/vulnerability/{vuln_id}** (NEW)
   - Expand collapsed Medium/Low results on-demand

### 3. Scanner Class Interface

**VulnerabilityScanner with complete method signatures:**

- `scan_device()` - Fast database scan (Path A)
- `analyze_psirt()` - DB cache + LLM fallback (Path B)
- `get_vulnerability_details()` - Expand individual vulnerabilities
- Helper methods for version parsing, caching, grouping

**All methods documented with:**
- Parameters and return types
- Process descriptions
- Performance targets
- Usage examples

### 4. Integration Plan

**Complete roadmap for integrating with existing system:**

- SEC8BAnalyzer integration (no changes needed)
- API routes modifications (detailed code snippets)
- Database layer interface requirements
- Testing strategy (unit, integration, performance)
- Deployment sequence (Phase 1 → Phase 2 → Phase 3)

### 5. Design Rationale

**Answers to all four key questions with detailed justification:**

1. **Should scan results include verification commands?** → YES
2. **How to handle unlabeled vulnerabilities?** → Include with warning
3. **Should we cache LLM results automatically?** → YES (confidence ≥0.75)
4. **How to paginate large result sets?** → Two-tier (severity + limit)

Each decision includes:
- Rationale and trade-offs
- Implementation examples
- Edge case handling
- Performance impact analysis

## Key Design Principles

### 1. Security First

- Include all version-matched vulnerabilities (avoid false negatives)
- Unlabeled bugs flagged for manual review
- Verification commands always included
- Conservative caching (only high-confidence results)

### 2. Performance Optimized

- Database queries target <100ms (indexed)
- Severity-based result grouping reduces payload
- Optional pagination for large result sets
- Expand-on-demand for Medium/Low details

### 3. Analyst Workflow Alignment

- Critical/High vulnerabilities shown first (expanded)
- Medium/Low vulnerabilities collapsed by default
- Immediate access to verification commands
- One-click expansion for additional details

### 4. Backward Compatible

- No breaking changes to existing APIs
- Existing frontend continues to work
- SEC-8B pipeline unchanged
- Enhancement-only approach (additive)

## Performance Targets

| Operation | Target | Stretch Goal | Notes |
|-----------|--------|--------------|-------|
| Database scan (typical) | <100ms | <50ms | 10-50 vulnerabilities |
| Database scan (large) | <200ms | <100ms | 100+ vulnerabilities |
| Cache hit | <10ms | <5ms | Database lookup only |
| LLM inference | ~3400ms | N/A | SEC-8B (8-bit) |
| Batch verify (10 vulns) | <30s | <20s | SSH connection |

## Implementation Roadmap

### Phase 1: Database Layer (Prerequisites)

**Owner:** VulnerabilityDBArchitectAgent
**Status:** In progress

**Deliverables:**
- SQLite schema creation
- CSV data loader (2,654 labeled examples)
- VulnerabilityDatabase class
- Version and label indexes

**Blocks:** Phase 2 implementation

### Phase 2: Scanner Backend (This Design)

**Owner:** Backend implementation team
**Status:** Design complete, awaiting Phase 1

**Tasks:**

1. **Complete VulnerabilityScanner** (2 days)
   - Implement TODOs in vulnerability_scanner.py
   - Add version parsing logic
   - Integrate with VulnerabilityDatabase
   - Add error handling

2. **Add API endpoints** (1 day)
   - Modify /analyze-psirt (add DB cache check)
   - Add /scan-device endpoint
   - Add /vulnerability/{vuln_id} endpoint

3. **Update app.py** (0.5 days)
   - Initialize scanner on startup
   - Configure database path

4. **Testing** (1.5 days)
   - Unit tests (version parsing, caching, grouping)
   - Integration tests (dual-path routing, end-to-end)
   - Performance tests (query latency, concurrent scans)

**Total effort:** ~5 days

### Phase 3: Frontend Integration (Future)

**Owner:** Frontend team
**Status:** Not started, awaiting Phase 2

**Tasks:**

1. **Device scan form** (1 day)
   - Platform, version, labels inputs
   - Feature selection from snapshot

2. **Scan results view** (2 days)
   - Severity-grouped display
   - Expand-on-demand for Medium/Low
   - Verification button integration

3. **Batch verification** (1 day)
   - "Verify All" button
   - Progress indicator
   - Results summary

**Total effort:** ~4 days

## Database Interface Requirements

**For VulnerabilityDBArchitectAgent to implement:**

```python
class VulnerabilityDatabase:
    # Query methods (for Path A)
    def query_version_index(platform, major, minor, patch) -> List[str]
    def query_label_index(vuln_ids, labels) -> List[str]
    def get_vulnerabilities(vuln_ids) -> List[Dict]

    # Cache methods (for Path B)
    def get_by_advisory_id(advisory_id, platform) -> Optional[Dict]

    # Insert methods (for auto-caching)
    def insert_vulnerability(vuln) -> str
    def insert_label(vuln_id, label)
    def insert_version(vuln_id, platform, major, minor, patch)
```

**Performance requirements:**
- `query_version_index()` + `query_label_index()` + `get_vulnerabilities()` combined: <100ms
- `get_by_advisory_id()`: <10ms
- Indexes on: (platform, major, minor, patch), label

## Testing Requirements

### Unit Tests (backend/tests/test_scanner.py)

**Coverage:**
- Version parsing (valid, invalid, edge cases)
- Cache decision logic (confidence thresholds)
- Severity grouping and sorting
- Pagination logic

**Target:** 90%+ code coverage

### Integration Tests (backend/tests/test_scanner_integration.py)

**Scenarios:**
- Dual-path routing (DB hit/miss)
- End-to-end scan flow
- LLM result caching
- Concurrent scans

**Target:** All critical paths tested

### Performance Tests (backend/tests/test_scanner_performance.py)

**Benchmarks:**
- Scan latency (<100ms for typical)
- Large result sets (100+ vulns)
- Concurrent scans (10 simultaneous)
- Cache hit rate (>80%)

**Target:** All performance targets met

## Configuration

**Environment variables needed:**

```bash
# Database path
VULNERABILITY_DB_PATH=/path/to/vulnerability_db.sqlite

# Cache policy
MIN_CONFIDENCE_TO_CACHE=0.75

# Performance tuning
SCAN_QUERY_TIMEOUT_MS=500
MAX_SCAN_RESULTS=1000
```

## Monitoring

**Key metrics to track:**

```python
# Latency
histogram("scan.latency_ms")
histogram("cache.lookup_time_ms")

# Cache performance
counter("cache.hit", tags=["source:database|llm"])
counter("cache.miss")

# Result counts
histogram("scan.result_count")
histogram("scan.critical_high_count")
histogram("scan.medium_low_count")

# Database health
gauge("database.size_mb")
gauge("database.vulnerability_count")
```

**Alerts:**
- Scan latency p95 >200ms
- Cache hit rate <80%
- Database size >500MB

## FAQ

### Q: Why dual-path instead of database-only?

**A:** New PSIRTs published daily. Database only contains known vulnerabilities (2,654 initially). Need LLM fallback for new/unknown advisories. Dual-path provides:
- Fast scanning for known vulns (99% of queries)
- LLM flexibility for new vulns (1% of queries)
- Auto-caching grows database organically

### Q: Why include unlabeled bugs?

**A:** ~55% of bugs have no labels (SEC-8B couldn't determine features). Still valuable to know version is affected. Security principle: Better false positive than false negative.

### Q: Why auto-cache LLM results?

**A:** Team efficiency. First analyst waits 3.4s (LLM), subsequent analysts get <10ms (DB). Also ensures consistency across team (same labels for same PSIRT).

### Q: Why severity-based grouping?

**A:** Matches analyst workflow (triage by severity). Critical/High reviewed first (expanded), Medium/Low rarely reviewed (collapsed). Reduces payload size for large result sets.

### Q: How does this integrate with existing SEC-8B pipeline?

**A:** Zero changes to SEC-8B. Scanner wraps existing SEC8BAnalyzer, calls it only when needed (cache miss). Existing /analyze-psirt API enhanced with caching but interface unchanged.

### Q: What if database is unavailable?

**A:** Graceful degradation. Scanner falls back to LLM-only mode (no caching). System continues to work, just slower. Error logged, monitoring alerted.

### Q: How to update database as new PSIRTs are published?

**A:** Two approaches:
1. **Auto-caching:** Analysts analyze new PSIRTs via /analyze-psirt, high-confidence results auto-cached
2. **Batch import:** Periodic job fetches new PSIRTs from Cisco API, runs SEC-8B, imports to DB

Recommend hybrid: Auto-caching for ad-hoc queries, batch import for systematic updates.

## Next Steps

### For VulnerabilityDBArchitectAgent (Phase 1)

1. ✅ Review scanner architecture design
2. ⏳ Implement VulnerabilityDatabase class
3. ⏳ Ensure indexes support <100ms queries
4. ⏳ Populate database with 2,654 labeled examples
5. ⏳ Signal Phase 2 handoff

### For Implementation Team (Phase 2)

1. ⏳ Wait for Phase 1 completion
2. ⏳ Implement VulnerabilityScanner (fill TODOs)
3. ⏳ Add API endpoints to routes.py
4. ⏳ Write tests (unit, integration, performance)
5. ⏳ Deploy and monitor

### For Frontend Team (Phase 3)

1. ⏳ Wait for Phase 2 completion
2. ⏳ Design scan form UI
3. ⏳ Implement results view (severity-grouped)
4. ⏳ Add batch verification flow

## Document Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-10-10 | SystemArchitectAgent | Initial design complete |

## Contact

**Questions about this design?** Consult:

- **Architecture:** scanner_architecture.md
- **Integration:** scanner_integration_plan.md
- **Design rationale:** scanner_design_decisions.md
- **Visual diagrams:** scanner_architecture_diagram.txt

**Ready to implement?** Start with vulnerability_scanner.py TODOs after Phase 1 complete.
