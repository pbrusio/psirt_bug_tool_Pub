# Architecture Test Framework

This directory contains the **Architecture Testing Framework** for CVE_EVAL_V2, implementing the testing workflow defined in [docs/ARCHITECTURE_AND_WORKFLOW.md](../../docs/ARCHITECTURE_AND_WORKFLOW.md) Section 9.

## Overview

The architecture tests verify system integrity during refactoring and ongoing development:

- **Baseline behavior** before changes
- **Correct fallback handling** during refactoring
- **Output consistency** after refactoring
- **Performance targets** are maintained
- **Observability** is functioning

## Directory Structure

```
tests/
├── conftest.py              # ALL fixtures including architecture fixtures
├── fixtures/
│   ├── psirt_corpus.json    # Golden-path PSIRT test data
│   └── baseline_results.json # Captured baseline (generated)
└── architecture/
    ├── __init__.py          # Module docstring
    ├── helpers.py           # Utility functions (OutputComparator, etc.)
    ├── test_baseline.py     # Pre-refactor baseline tests
    ├── test_refactor.py     # During-refactor verification tests
    ├── test_comparison.py   # Post-refactor comparison tests
    └── README.md            # This file
```

## Quick Start

### Run All Architecture Tests
```bash
pytest tests/architecture/ -v
```

### Run by Phase (CLI Options)

```bash
# Run ONLY baseline tests (pre-refactor verification)
pytest tests/ --baseline -v

# Run ONLY refactor tests (during-refactor verification)
pytest tests/ --refactor -v

# Run ONLY comparison tests (post-refactor verification)
pytest tests/ --comparison -v

# Run ONLY architecture tests (isolate from other tests)
pytest tests/ --architecture -v

# Run performance benchmarks
pytest tests/ --benchmark -v

# Run observability/logging tests
pytest tests/ --observability -v
```

### Combined Options
```bash
# Baseline + slow tests (includes LLM inference)
pytest tests/ --baseline --slow -v

# Architecture tests with benchmarks
pytest tests/ --architecture --benchmark -v
```

## Fixtures in `tests/conftest.py`

All architecture fixtures are defined in `tests/conftest.py` for global availability.

### Constants

```python
from tests.conftest import (
    FAISS_SIMILARITY_THRESHOLD,  # 0.70 - Section 6 fallback trigger
    CACHE_CONFIDENCE_THRESHOLD,  # 0.75 - Section 6 cache threshold
    DB_LATENCY_TARGET_MS,        # 10ms - Section 2 DB target
    AI_LATENCY_TARGET_MS,        # 3400ms - Section 2 LLM target
    FAISS_RETRIEVAL_TARGET_MS,   # 30ms - Section 2 FAISS target
)
```

### FAISS Fallback Fixtures

```python
@pytest.fixture
def faiss_low_similarity_results():
    """Mock FAISS results with similarity < 0.70"""
    # Returns 3 results at 0.45, 0.52, 0.61 similarity

@pytest.fixture
def faiss_threshold_boundary_results():
    """Mock FAISS results at exactly 0.70 boundary"""

@pytest.fixture
def mock_faiss_index_low_similarity():
    """Context manager mock for FAISS index"""
    # Usage:
    def test_fallback(mock_faiss_index_low_similarity):
        with mock_faiss_index_low_similarity(similarity=0.45):
            result = labeler.predict_labels(summary, platform)
            assert result.get('needs_review', False)
```

### LLM Timeout/Error Fixtures

```python
@pytest.fixture
def llm_timeout_response():
    """Sample response when LLM times out (needs_review=True, cached=False)"""

@pytest.fixture
def llm_error_response():
    """Sample response when LLM errors (needs_review=True, cached=False)"""

@pytest.fixture
def mock_llm_timeout():
    """Context manager to simulate LLM timeout"""
    # Usage:
    def test_timeout(mock_llm_timeout):
        with mock_llm_timeout(timeout_seconds=0.1):
            # Code should handle timeout gracefully

@pytest.fixture
def mock_llm_error():
    """Context manager to simulate LLM error"""
    # Usage:
    def test_error(mock_llm_error):
        with mock_llm_error(error_type=RuntimeError, error_msg="Failed"):
            # Code should handle error gracefully
```

### Confidence Source / needs_review Fixtures

```python
@pytest.fixture
def confidence_source_model_payload():
    """High confidence payload (confidence_source='model', cacheable)"""

@pytest.fixture
def confidence_source_heuristic_payload():
    """Low confidence payload (confidence_source='heuristic', NOT cacheable)"""

@pytest.fixture
def needs_review_payload():
    """Payload with needs_review=True (NOT cacheable)"""
```

### Model Version / LoRA Update Fixtures

```python
@pytest.fixture
def model_version_toggle():
    """Simulate model/LoRA version changes"""
    # Usage:
    def test_lora_update(model_version_toggle, faiss_rebuild_spy):
        model_version_toggle.set_version("v4")
        assert model_version_toggle.version_changed

@pytest.fixture
def lora_update_flag():
    """Simple flag for LoRA update detection"""
    # Usage:
    def test_update_detection(lora_update_flag):
        lora_update_flag.trigger_update(old="v3", new="v4")
        assert lora_update_flag.updated

@pytest.fixture
def faiss_rebuild_spy():
    """Spy to track FAISS rebuild calls"""
    # Usage:
    def test_rebuild(faiss_rebuild_spy):
        faiss_rebuild_spy.record_rebuild(reason="lora_update")
        faiss_rebuild_spy.assert_rebuild_called(reason="lora_update")

@pytest.fixture
def mock_faiss_rebuild():
    """Mock FAISS rebuild with spy integration"""
    # Usage:
    def test_rebuild(mock_faiss_rebuild, faiss_rebuild_spy):
        with mock_faiss_rebuild(spy=faiss_rebuild_spy):
            build_faiss_index()
        faiss_rebuild_spy.assert_rebuild_called()
```

### Taxonomy Delta Fixture

```python
@pytest.fixture
def taxonomy_delta():
    """Track taxonomy changes"""
    # Usage:
    def test_taxonomy_change(taxonomy_delta):
        taxonomy_delta.add_label("NEW_FEATURE", "IOS-XE")
        taxonomy_delta.modify_label("MGMT_SSH_HTTP", "IOS-XE", {"description": "updated"})
        assert taxonomy_delta.has_changes()
        assert "NEW_FEATURE" in taxonomy_delta.get_affected_labels()
```

### Timing / Performance Fixtures

```python
@pytest.fixture
def timing_helper():
    """Measure and assert latency"""
    # Usage:
    def test_performance(timing_helper):
        with timing_helper.measure("db_scan") as result:
            scanner.scan_device(platform, version)

        timing_helper.assert_db_latency(result)  # <10ms with tolerance
        # or
        timing_helper.assert_latency_under(result, target_ms=50, tolerance_factor=2.0)

        summary = timing_helper.get_summary()
        print(f"Avg: {summary['operations']['db_scan']['avg_ms']:.2f}ms")
```

### Observability / Log Capture Fixtures

```python
@pytest.fixture
def log_capture():
    """Capture and assert log outputs"""
    # Usage:
    def test_logging(log_capture):
        with log_capture.capture("backend.core.vulnerability_scanner") as logs:
            scanner.scan_device(platform, version)

        log_capture.assert_logged("scan", level="INFO")
        log_capture.assert_logged_field("query_time_ms")
        log_capture.assert_not_logged("error")

@pytest.fixture
def metric_capture():
    """Capture and assert metrics"""
    # Usage:
    def test_metrics(metric_capture):
        with metric_capture.track():
            metric_capture.record("cache_hit", True)
            metric_capture.record_histogram("latency_ms", 5.2)

        metric_capture.assert_metric_recorded("cache_hit")
        metric_capture.assert_metric_value("cache_hit", True)
        stats = metric_capture.get_histogram_stats("latency_ms")
```

### Cache Manipulation Fixture

```python
@pytest.fixture
def cache_manipulator():
    """Manipulate and verify cache state"""
    # Usage:
    def test_cache(cache_manipulator):
        cache_manipulator.clear_psirt_cache("test-advisory")
        assert cache_manipulator.verify_not_cached("test-advisory", "IOS-XE")

        # After caching...
        assert cache_manipulator.verify_cached("test-advisory", "IOS-XE")
        entry = cache_manipulator.get_cache_entry("test-advisory", "IOS-XE")
```

### Golden Path Corpus Fixture

```python
@pytest.fixture
def psirt_corpus():
    """Load golden-path PSIRT test corpus"""
    # Returns {"psirts": [...], "bugs": [...]} from tests/fixtures/psirt_corpus.json
```

## Test Categories

### 1. Baseline Tests (`test_baseline.py`)

**Purpose:** Establish current behavior before refactoring.

| Test Class | Description |
|------------|-------------|
| `TestGoldenPathPSIRTInference` | Verify known PSIRTs return expected labels |
| `TestFAISSRetrievalSanity` | Verify FAISS index returns valid results |
| `TestDatabaseScanBaseline` | Verify database scan performance (<10ms) |
| `TestDeviceVerificationSmoke` | Verify SSH/verification modules import |
| `TestCacheBaseline` | Verify cache isolation and persistence |
| `TestTaxonomyBaseline` | Verify taxonomy files are valid |

**When to run:** Before making any changes to core modules.

### 2. Refactor Tests (`test_refactor.py`)

**Purpose:** Verify correct behavior during refactoring.

| Test Class | Description |
|------------|-------------|
| `TestFallbackBehaviorAtThreshold` | Verify FAISS <0.70 triggers fallback |
| `TestNeedsReviewNotCached` | Verify low-confidence results NOT cached |
| `TestCacheInvalidation` | Verify cache entries can be evicted |
| `TestVulnerabilityScannerFacade` | Verify public interface is stable |
| `TestLLMTimeoutFallback` | Verify timeout returns needs_review |
| `TestSSHDiscoveryFallback` | Verify SSH failure marks device stale |

**When to run:** After each refactoring step.

### 3. Comparison Tests (`test_comparison.py`)

**Purpose:** Compare outputs before/after refactoring.

| Test Class | Description |
|------------|-------------|
| `TestOutputDiff` | Compare labels and confidence within tolerance |
| `TestPerformanceTargets` | Verify DB <10ms, AI within budget |
| `TestObservabilitySmoke` | Verify logging and metrics |
| `TestMigrationCompatibility` | Verify database schema |

**When to run:** After refactoring is complete.

## Capturing Baseline

Before refactoring, capture current outputs as baseline:

```bash
# From project root
python -c "from tests.architecture.helpers import capture_baseline_results; capture_baseline_results()"
```

This creates `tests/fixtures/baseline_results.json` for comparison tests.

## Results Storage

Test results are stored in `tests/architecture/results/` with date/version naming for tracking changes over time.

### Directory Structure

```
tests/architecture/results/
├── baseline/           # Pre-refactor baseline results
├── refactor/           # During-refactor verification results
├── comparison/         # Post-refactor comparison results
├── benchmark/          # Performance benchmark results
├── observability/      # Observability test results
└── latest/             # Symlinks to most recent results per phase
```

### Naming Convention

Files follow the pattern: `{phase}_{YYYYMMDD}_{version}.json`

Examples:
- `baseline_20251214_v1.json`
- `refactor_20251214_pre-refactor.json`
- `comparison_20251215_post-cleanup.json`

### Saving Results

```bash
# Save results with default version tag (v1)
pytest tests/architecture/ --save-results -v

# Save with custom version tag
pytest tests/architecture/ --save-results --results-version=pre-refactor -v

# Save only baseline tests with version tag
pytest tests/ --baseline --save-results --results-version=v2 -v
```

### Viewing and Comparing Results

```python
# List available results
from tests.architecture.results_manager import list_available_results
print(list_available_results())

# Compare two versions
from tests.architecture.results_manager import compare_results, print_comparison_report
comparison = compare_results("baseline", "v1", "v2")
print_comparison_report(comparison)
```

### Result File Contents

Each result file contains:
- **Summary**: Total tests, passed, failed, skipped, errors, total duration
- **Environment**: Python version, platform, working directory
- **Test Results**: List of all test results with:
  - Test name, class, and file
  - Status (passed/failed/skipped)
  - Duration in milliseconds
  - Error message (if failed)
  - Additional details (skip reason, custom metrics)

### Comparison Report

When comparing results, the report shows:
- **Regressions**: Tests that passed before but fail now
- **Improvements**: Tests that failed before but pass now
- **New Tests**: Tests only in the newer version
- **Removed Tests**: Tests only in the older version
- **Performance Changes**: Tests with >50% duration change

## CI/CD Integration

```yaml
# GitHub Actions example
jobs:
  test:
    steps:
      # Fast tests (no LLM) - baseline verification with results saved
      - name: Run Baseline Tests
        run: pytest tests/ --baseline --save-results --results-version=${{ github.sha }} -v

      # Refactor tests
      - name: Run Refactor Tests
        run: pytest tests/ --refactor --save-results --results-version=${{ github.sha }} -v

      # Performance benchmarks (optional)
      - name: Run Benchmarks
        run: pytest tests/ --benchmark --slow -v

      # Upload results as artifact
      - name: Upload Test Results
        uses: actions/upload-artifact@v3
        with:
          name: test-results
          path: tests/architecture/results/
```

### Comparing Results Across Commits

```bash
# After running tests on two different commits, compare:
python -c "
from tests.architecture.results_manager import compare_results, print_comparison_report
comparison = compare_results('baseline', 'abc1234', 'def5678')
print_comparison_report(comparison)
"
```

## Adding New Tests

1. **Determine category:** baseline, refactor, or comparison
2. **Add to appropriate file** in `tests/architecture/`
3. **Use markers:** `@pytest.mark.baseline`, `@pytest.mark.refactor`, etc.
4. **Use fixtures from conftest.py** - import is automatic
5. **Reference architecture doc:** Add docstring referencing Section 6-9

Example:

```python
import pytest

@pytest.mark.refactor
def test_new_fallback_behavior(
    faiss_low_similarity_results,
    needs_review_payload,
    cache_manipulator
):
    """
    Test new fallback when FAISS similarity < 0.70.

    Reference: Section 6 - "FAISS low similarity -> skip few-shot or return needs_review"
    """
    # Use fixtures directly - they're from conftest.py
    assert faiss_low_similarity_results[0]['similarity'] < 0.70
    assert needs_review_payload['needs_review'] is True
    assert cache_manipulator.verify_not_cached(
        needs_review_payload['advisory_id'],
        needs_review_payload['platform']
    )
```

## Related Documentation

- **[docs/ARCHITECTURE_AND_WORKFLOW.md](../../docs/ARCHITECTURE_AND_WORKFLOW.md)** - Source of truth for architecture
- **[CLAUDE.md](../../CLAUDE.md)** - Project overview and quick start
- **[tests/conftest.py](../conftest.py)** - All fixture definitions

## Troubleshooting

### Tests fail with "MLX not available"
The slow tests require the MLX model. Run without `--slow`:
```bash
pytest tests/architecture/ -v -m "not slow"
```

### CLI options not recognized
Ensure you're running from project root with pytest properly installed:
```bash
pip install pytest
pytest --help | grep baseline  # Should show --baseline option
```

### Fixtures not found
Fixtures are in `tests/conftest.py`. Ensure the file exists and has no syntax errors:
```bash
python -m py_compile tests/conftest.py
```

### Database not found
Ensure `vulnerability_db.sqlite` exists:
```bash
ls -la vulnerability_db.sqlite
```

### Performance tests fail
Performance targets have tolerance factors for CI. Check:
- Database connection issues
- Large test data causing slow queries
- CI environment resource constraints
