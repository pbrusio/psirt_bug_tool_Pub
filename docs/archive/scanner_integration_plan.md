# Scanner Integration Plan

## Overview

This document outlines how the new VulnerabilityScanner integrates with existing components and the implementation sequence after Phase 1 (database) is complete.

## Integration Points

### 1. SEC8BAnalyzer (backend/core/sec8b.py)

**Status:** No changes required - already compatible

**Integration:**

```python
# VulnerabilityScanner constructor
def __init__(self, db_path: str, sec8b_analyzer=None):
    if sec8b_analyzer is None:
        from .sec8b import get_analyzer
        self.sec8b = get_analyzer()  # Use existing singleton
    else:
        self.sec8b = sec8b_analyzer
```

**Why this works:**
- SEC8BAnalyzer.analyze_psirt() already returns all needed fields
- Return format matches exactly what scanner expects
- No modifications needed to existing LLM pipeline

### 2. API Routes (backend/api/routes.py)

**Required Changes:**

#### A. Modify /analyze-psirt endpoint

**Current behavior:**
- Directly calls SEC8BAnalyzer
- Caches result in in-memory cache

**New behavior:**
- Route through VulnerabilityScanner
- Check database cache first
- Fallback to SEC-8B if not found
- Cache high-confidence results in database

**Code changes:**

```python
from ..core.vulnerability_scanner import get_scanner

@router.post("/analyze-psirt", response_model=AnalysisResult)
async def analyze_psirt(request: AnalyzePSIRTRequest):
    try:
        # Validate platform (existing)
        valid_platforms = ["IOS-XE", "IOS-XR", "ASA", "FTD", "NX-OS"]
        if request.platform not in valid_platforms:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid platform. Must be one of: {', '.join(valid_platforms)}"
            )

        # NEW: Use scanner instead of direct SEC8B call
        scanner = get_scanner()

        # Dual-path routing (DB cache -> LLM fallback)
        result = scanner.analyze_psirt(
            summary=request.summary,
            platform=request.platform,
            advisory_id=request.advisory_id
        )

        # Cache result (existing - keep for in-memory cache)
        await save_analysis(result)

        logger.info(
            f"Analysis complete: {result['analysis_id']}, "
            f"source={result['source']}, cached={result['cached']}"
        )

        return AnalysisResult(**result)

    except Exception as e:
        logger.error(f"Analysis failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analysis failed: {str(e)}"
        )
```

**Migration strategy:**
- Keep existing in-memory cache (db/cache.py) for backward compatibility
- Database cache is additional layer (persistent, shared across API instances)
- Both caches checked: in-memory (fastest) -> DB (fast) -> LLM (slow)

#### B. Add /scan-device endpoint

**New endpoint:**

```python
from ..core.vulnerability_scanner import get_scanner
from .models import ScanDeviceRequest, ScanResult

@router.post("/scan-device", response_model=ScanResult)
async def scan_device(request: ScanDeviceRequest):
    """
    Fast vulnerability scan using database

    Process:
    1. Parse device version
    2. Query version_index for potential matches
    3. Filter by label_index for configured features
    4. Group by severity (Critical/High vs Medium/Low)
    5. Return sorted results

    Performance target: <100ms
    """
    try:
        # Validate platform
        valid_platforms = ["IOS-XE", "IOS-XR", "ASA", "FTD", "NX-OS"]
        if request.platform not in valid_platforms:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid platform. Must be one of: {', '.join(valid_platforms)}"
            )

        # Validate version format
        if not request.version:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Version required (e.g., '17.3.5')"
            )

        # Get scanner
        scanner = get_scanner()

        # Run database scan
        logger.info(
            f"Scanning device: platform={request.platform}, "
            f"version={request.version}, labels={len(request.labels)}"
        )

        result = scanner.scan_device(
            platform=request.platform,
            version=request.version,
            labels=request.labels,
            severity_filter=request.severity_filter,
            limit=request.limit,
            offset=request.offset
        )

        logger.info(
            f"Scan complete: scan_id={result['scan_id']}, "
            f"total={result['total_vulnerabilities']}, "
            f"time={result['query_time_ms']:.1f}ms"
        )

        return ScanResult(**result)

    except ValueError as e:
        # Version parsing error
        logger.error(f"Invalid version format: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid version format: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Scan failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Scan failed: {str(e)}"
        )
```

#### C. Add /vulnerability/{vuln_id} endpoint

**New endpoint for expanding collapsed results:**

```python
from .models import VulnerabilityFull

@router.get("/vulnerability/{vuln_id}", response_model=VulnerabilityFull)
async def get_vulnerability(vuln_id: str):
    """
    Get full details for a specific vulnerability

    Used to expand collapsed Medium/Low results from scan
    """
    try:
        scanner = get_scanner()
        result = scanner.get_vulnerability_details(vuln_id)

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Vulnerability not found: {vuln_id}"
            )

        return VulnerabilityFull(**result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get vulnerability: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get vulnerability: {str(e)}"
        )
```

### 3. Device Verifier (backend/core/verifier.py)

**Enhancement: Batch Verification**

**Current behavior:**
- Verify one vulnerability per device connection
- Connect -> Get version -> Get config -> Check features -> Disconnect

**New behavior (optional enhancement):**
- Verify multiple vulnerabilities in one connection
- Connect once -> Get version/config once -> Check all features -> Disconnect

**Code changes (optional):**

```python
class DeviceVerifier:
    def verify_vulnerabilities(
        self,
        device_config: Dict,
        vulnerabilities: List[Dict]
    ) -> List[Dict]:
        """
        Verify multiple vulnerabilities against one device

        More efficient than N individual verifications

        Args:
            device_config: Device credentials and connection info
            vulnerabilities: List of vulnerabilities from scan

        Returns:
            List of VerificationResult dicts
        """
        results = []

        # Connect once
        self.connect(device_config)

        # Get version and config once
        version = self.get_version()
        config = self.get_running_config()

        # Verify each vulnerability
        for vuln in vulnerabilities:
            try:
                result = self._verify_single_vulnerability(
                    vuln=vuln,
                    device_version=version,
                    device_config=config
                )
                results.append(result)
            except Exception as e:
                logger.error(
                    f"Failed to verify {vuln['vuln_id']}: {str(e)}"
                )
                results.append({
                    'vuln_id': vuln['vuln_id'],
                    'overall_status': 'ERROR',
                    'error': str(e)
                })

        self.disconnect()
        return results

    def _verify_single_vulnerability(
        self,
        vuln: Dict,
        device_version: str,
        device_config: str
    ) -> Dict:
        """
        Verify single vulnerability using pre-fetched device data

        Args:
            vuln: Vulnerability dict with config_regex patterns
            device_version: Device software version
            device_config: Device running-config output

        Returns:
            VerificationResult dict
        """
        # Version check
        version_affected = self._check_version(
            device_version,
            vuln['product_names']
        )

        # Feature check
        features_present = []
        features_absent = []

        for pattern in vuln['config_regex']:
            if re.search(pattern, device_config, re.MULTILINE):
                features_present.append(pattern)
            else:
                features_absent.append(pattern)

        # Determine status
        if version_affected and features_present:
            status = "VULNERABLE"
        elif not version_affected:
            status = "NOT VULNERABLE"
        elif not features_present:
            status = "NOT VULNERABLE"
        else:
            status = "UNKNOWN"

        return {
            'vuln_id': vuln['vuln_id'],
            'version_affected': version_affected,
            'features_present': features_present,
            'features_absent': features_absent,
            'overall_status': status
        }
```

**New API endpoint:**

```python
@router.post("/verify-batch", response_model=List[VerificationResult])
async def verify_batch(
    scan_id: str,
    device: DeviceCredentials
):
    """
    Verify all vulnerabilities from a scan against one device

    More efficient than individual verification calls

    Args:
        scan_id: Scan ID from /scan-device response
        device: Device SSH credentials

    Returns:
        List of verification results (one per vulnerability)
    """
    # Get scan results
    scan = await get_scan_results(scan_id)
    if not scan:
        raise HTTPException(404, "Scan not found")

    # Extract all vulnerabilities
    all_vulns = scan['critical_high'] + scan['medium_low']

    # Batch verify
    verifier = get_verifier()
    results = verifier.verify_vulnerabilities(
        device_config={
            'host': device.host,
            'username': device.username,
            'password': device.password,
            'device_type': device.device_type
        },
        vulnerabilities=all_vulns
    )

    return results
```

### 4. Database Layer (backend/db/)

**New module: backend/db/vulnerability_db.py**

**Required by VulnerabilityScanner - implemented by VulnerabilityDBArchitectAgent**

**Interface:**

```python
class VulnerabilityDatabase:
    def __init__(self, db_path: str):
        """Connect to SQLite database"""

    def query_version_index(
        self,
        platform: str,
        major: int,
        minor: int,
        patch: Optional[int]
    ) -> List[str]:
        """
        Query version_index for matching vulnerability IDs

        Returns: List of vuln_id strings
        """

    def query_label_index(
        self,
        vuln_ids: List[str],
        labels: List[str]
    ) -> List[str]:
        """
        Filter vuln_ids by label matches

        Returns: List of vuln_id strings
        """

    def get_vulnerabilities(
        self,
        vuln_ids: List[str]
    ) -> List[Dict]:
        """
        Get full vulnerability records

        Returns: List of vulnerability dicts
        """

    def get_by_advisory_id(
        self,
        advisory_id: str,
        platform: str
    ) -> Optional[Dict]:
        """
        Get vulnerability by advisory ID (for cache check)

        Returns: Vulnerability dict or None
        """

    def insert_vulnerability(self, vuln: Dict) -> str:
        """
        Insert vulnerability from LLM result

        Returns: Generated vuln_id
        """

    def insert_label(self, vuln_id: str, label: str):
        """Insert label into label_index"""

    def insert_version(
        self,
        vuln_id: str,
        platform: str,
        major: int,
        minor: int,
        patch: Optional[int]
    ):
        """Insert version into version_index"""
```

**Implementation:** VulnerabilityDBArchitectAgent will implement based on schema.

### 5. Application Startup (backend/app.py)

**Required Changes:**

Initialize scanner singleton on app startup:

```python
from fastapi import FastAPI
from .core.vulnerability_scanner import get_scanner
from pathlib import Path

app = FastAPI()

@app.on_event("startup")
async def startup_event():
    """Initialize global components on app startup"""

    # Initialize database path
    db_path = Path(__file__).parent.parent / "vulnerability_db.sqlite"

    # Initialize scanner (creates singleton)
    scanner = get_scanner(db_path=str(db_path))

    logger.info(f"VulnerabilityScanner initialized with DB: {db_path}")

    # Existing startup logic...
```

## Implementation Sequence

### Phase 1: Database Layer (VulnerabilityDBArchitectAgent)

**Status:** In progress

**Deliverables:**
1. SQLite schema creation
2. CSV data loader
3. VulnerabilityDatabase class implementation
4. Indexes for fast querying

**Blocks:** Phase 2 (scanner implementation)

### Phase 2: Scanner Implementation (This Document)

**Prerequisites:** Phase 1 complete

**Tasks:**

1. **Complete VulnerabilityScanner implementation**
   - Implement _parse_version() method
   - Implement _check_cache() method using VulnerabilityDatabase
   - Implement _cache_result() method
   - Implement scan_device() database query logic
   - Add error handling

2. **Add API endpoints**
   - Modify /analyze-psirt to use scanner
   - Add /scan-device endpoint
   - Add /vulnerability/{vuln_id} endpoint

3. **Update app.py**
   - Initialize scanner on startup
   - Configure database path

4. **Testing**
   - Unit tests for version parsing
   - Integration tests for dual-path routing
   - Performance tests for scan speed

### Phase 3: Frontend Integration (Future)

**New UI features:**

1. **Device Scan Form**
   - Input: platform, version, labels
   - Output: List of vulnerabilities grouped by severity

2. **Scan Results View**
   - Critical/High: Expanded cards with full details
   - Medium/Low: Collapsed list, click to expand

3. **Batch Verification**
   - "Verify All on Device" button
   - Shows verification status for each vulnerability

## Backward Compatibility

**No breaking changes:**

1. Existing /analyze-psirt API unchanged (only enhanced with caching)
2. Existing /verify-device API unchanged
3. Existing frontend still works (new features are additive)
4. SEC-8B pipeline unchanged (still used for new advisories)

**Migration path:**

1. Deploy Phase 1 (database layer) - no user impact
2. Deploy Phase 2 (scanner) - existing APIs gain caching
3. Deploy Phase 3 (frontend) - new scan UI available

## Configuration

**Environment variables:**

```bash
# Database path
VULNERABILITY_DB_PATH=/path/to/vulnerability_db.sqlite

# Cache policy
MIN_CONFIDENCE_TO_CACHE=0.75

# Performance tuning
SCAN_QUERY_TIMEOUT_MS=500
MAX_SCAN_RESULTS=1000
```

**Example .env file:**

```
VULNERABILITY_DB_PATH=/app/data/vulnerability_db.sqlite
MIN_CONFIDENCE_TO_CACHE=0.75
SCAN_QUERY_TIMEOUT_MS=500
MAX_SCAN_RESULTS=1000
```

## Error Handling

### Database Unavailable

**Scenario:** SQLite file missing or corrupted

**Behavior:**
- Log error
- Fallback to LLM-only mode (no caching)
- Return results with warning flag

**Code:**

```python
try:
    scanner = VulnerabilityScanner(db_path)
except Exception as e:
    logger.error(f"Database unavailable: {e} - falling back to LLM-only")
    scanner = VulnerabilityScanner(db_path, fallback_mode=True)
```

### Version Parse Error

**Scenario:** Invalid version format (e.g., "abc.def")

**Behavior:**
- Raise HTTPException with helpful error message
- Return 400 Bad Request
- Suggest correct format

**Code:**

```python
try:
    major, minor, patch = self._parse_version(version)
except ValueError as e:
    raise HTTPException(
        status_code=400,
        detail=f"Invalid version '{version}'. Expected format: X.Y.Z (e.g., 17.3.5)"
    )
```

### Large Result Set

**Scenario:** Device has 500+ vulnerabilities

**Behavior:**
- Enforce pagination (max 100 per page)
- Return has_more flag
- Log warning for analyst

**Code:**

```python
if total_vulnerabilities > 1000:
    logger.warning(
        f"Large result set: {total_vulnerabilities} vulnerabilities found. "
        f"Consider applying severity filter."
    )

    # Enforce pagination
    if limit is None or limit > 100:
        limit = 100
```

## Performance Monitoring

**Key metrics to track:**

```python
# Scan latency
histogram("scan.latency_ms", elapsed_ms, tags=["platform", "result_count"])

# Cache hit rate
counter("cache.hit", tags=["source:database"])
counter("cache.miss", tags=["source:llm"])

# Result counts
histogram("scan.result_count", total_vulnerabilities)

# Database size
gauge("database.size_mb", db_size_mb)
gauge("database.vulnerability_count", total_vulns)
```

**Alerts:**

```yaml
# Scan too slow
- alert: SlowScanQueries
  expr: scan_latency_ms{quantile="0.95"} > 200
  for: 5m
  severity: warning

# Low cache hit rate
- alert: LowCacheHitRate
  expr: cache_hit_rate < 0.80
  for: 10m
  severity: warning

# Database too large
- alert: LargeDatabaseSize
  expr: database_size_mb > 500
  severity: warning
```

## Testing Strategy

### Unit Tests

**backend/tests/test_scanner.py:**

```python
def test_parse_version():
    scanner = VulnerabilityScanner(":memory:")

    # Valid versions
    assert scanner._parse_version("17.3.5") == (17, 3, 5)
    assert scanner._parse_version("17.3") == (17, 3, None)
    assert scanner._parse_version("7.4.1") == (7, 4, 1)

    # Leading zeros
    assert scanner._parse_version("17.03.05") == (17, 3, 5)

    # Letter suffixes
    assert scanner._parse_version("17.3.1a") == (17, 3, 1)

    # Invalid
    with pytest.raises(ValueError):
        scanner._parse_version("abc.def")


def test_should_cache():
    scanner = VulnerabilityScanner(":memory:")

    # Should cache
    assert scanner._should_cache({
        'advisory_id': 'cisco-sa-123',
        'confidence': 0.85,
        'predicted_labels': ['MGMT_SSH_HTTP']
    }) == True

    # Should NOT cache (low confidence)
    assert scanner._should_cache({
        'advisory_id': 'cisco-sa-123',
        'confidence': 0.55,
        'predicted_labels': ['MGMT_SSH_HTTP']
    }) == False

    # Should NOT cache (no advisory_id)
    assert scanner._should_cache({
        'advisory_id': None,
        'confidence': 0.85,
        'predicted_labels': ['MGMT_SSH_HTTP']
    }) == False


def test_group_by_severity():
    scanner = VulnerabilityScanner(":memory:")

    vulns = [
        {'severity': 1, 'cvss_score': 9.8, 'vuln_id': 'v1'},
        {'severity': 2, 'cvss_score': 7.5, 'vuln_id': 'v2'},
        {'severity': 3, 'cvss_score': 5.3, 'vuln_id': 'v3'},
        {'severity': 4, 'cvss_score': 4.2, 'vuln_id': 'v4'},
    ]

    critical_high, medium_low = scanner._group_by_severity(vulns)

    assert len(critical_high) == 2
    assert len(medium_low) == 2

    # Check sorting (CVSS descending for critical_high)
    assert critical_high[0]['vuln_id'] == 'v1'  # 9.8
    assert critical_high[1]['vuln_id'] == 'v2'  # 7.5
```

### Integration Tests

**backend/tests/test_scanner_integration.py:**

```python
def test_dual_path_routing(test_db):
    scanner = VulnerabilityScanner(test_db)

    # First call - should hit LLM
    result1 = scanner.analyze_psirt(
        summary="SSH vulnerability in IOS XE",
        platform="IOS-XE",
        advisory_id="cisco-sa-test-001"
    )
    assert result1['source'] == 'llm'
    assert result1['cached'] == True  # Should cache

    # Second call - should hit DB cache
    result2 = scanner.analyze_psirt(
        summary="Different summary",  # Doesn't matter
        platform="IOS-XE",
        advisory_id="cisco-sa-test-001"  # Same advisory_id
    )
    assert result2['source'] == 'database'
    assert result2['predicted_labels'] == result1['predicted_labels']


def test_scan_device(test_db):
    # Populate test DB with known vulnerabilities
    populate_test_vulnerabilities(test_db)

    scanner = VulnerabilityScanner(test_db)

    # Scan device
    result = scanner.scan_device(
        platform="IOS-XE",
        version="17.3.5",
        labels=["MGMT_SSH_HTTP", "SEC_CoPP"]
    )

    assert result['source'] == 'database'
    assert result['query_time_ms'] < 100  # Performance target
    assert result['total_vulnerabilities'] > 0
    assert len(result['critical_high']) >= 0
    assert len(result['medium_low']) >= 0
```

### Performance Tests

**backend/tests/test_scanner_performance.py:**

```python
def test_scan_performance(test_db):
    # Populate DB with 2,654 vulnerabilities
    populate_full_database(test_db)

    scanner = VulnerabilityScanner(test_db)

    # Measure scan time
    import time
    start = time.time()

    result = scanner.scan_device(
        platform="IOS-XE",
        version="17.3.5",
        labels=["MGMT_SSH_HTTP", "SEC_CoPP", "RTE_OSPF"]
    )

    elapsed_ms = (time.time() - start) * 1000

    # Assert performance target
    assert elapsed_ms < 100, f"Scan took {elapsed_ms}ms (target: <100ms)"

    # Assert correct results
    assert result['total_vulnerabilities'] > 0


def test_concurrent_scans(test_db):
    # Test concurrent access (SQLite locking)
    import concurrent.futures

    scanner = VulnerabilityScanner(test_db)

    def scan():
        return scanner.scan_device("IOS-XE", "17.3.5", ["MGMT_SSH_HTTP"])

    # 10 concurrent scans
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(scan) for _ in range(10)]
        results = [f.result() for f in futures]

    # All should succeed
    assert len(results) == 10
    assert all(r['total_vulnerabilities'] >= 0 for r in results)
```

## Summary

This integration plan provides:

1. **Clear interfaces** between scanner and existing components
2. **Backward compatibility** - no breaking changes
3. **Incremental deployment** - can deploy in phases
4. **Comprehensive testing** - unit, integration, performance
5. **Error handling** - graceful degradation if DB unavailable
6. **Performance targets** - <100ms scan, <10ms cache hit

The scanner is ready for implementation once Phase 1 (database layer) is complete.
