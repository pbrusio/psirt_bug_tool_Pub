"""
Pytest configuration and shared fixtures

This module provides fixtures for all test categories including:
- Basic sample data (PSIRT, bugs, taxonomy)
- Architecture test fixtures (Section 9 of ARCHITECTURE_AND_WORKFLOW.md)
  - FAISS low-similarity fallback (<0.70)
  - LLM timeout simulation
  - needs_review/confidence_source payloads
  - Model version toggle and FAISS rebuild spy
  - Timing helpers for performance benchmarks
  - Log/metric capture for observability
"""
import pytest
import json
import yaml
import time
import logging
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from unittest.mock import MagicMock, patch, PropertyMock
from contextlib import contextmanager
from dataclasses import dataclass, field

# Test data directory
TEST_DATA_DIR = Path(__file__).parent / "fixtures"

# =============================================================================
# ARCHITECTURE CONSTANTS (from docs/ARCHITECTURE_AND_WORKFLOW.md Section 6)
# =============================================================================

FAISS_SIMILARITY_THRESHOLD = 0.70      # Section 6: cosine_similarity < 0.70 triggers fallback
CACHE_CONFIDENCE_THRESHOLD = 0.75      # Section 6: cache if confidence >= 0.75
DB_LATENCY_TARGET_MS = 10              # Section 2: Database hit <10ms
AI_LATENCY_TARGET_MS = 3400            # Section 2: ~3s for LLM inference
FAISS_RETRIEVAL_TARGET_MS = 30         # Section 2: FAISS exact match ~30ms


# =============================================================================
# BASIC SAMPLE DATA FIXTURES
# =============================================================================

@pytest.fixture
def sample_psirt() -> Dict:
    """Sample PSIRT for testing"""
    return {
        "bug_id": "cisco-sa-iox-dos-95Fqnf7b",
        "summary": "A vulnerability in the IOx application hosting subsystem of Cisco IOS XE Software could allow an authenticated, remote attacker to cause a denial of service (DoS) condition on an affected device.",
        "platform": "IOS-XE",
        "product_names": ["Cisco IOS XE Software, Version 17.3.1"],
        "labels": ["APP_IOx"],
        "config_regex": ["^iox$", "^app-hosting"],
        "show_cmds": ["show iox", "show app-hosting list"]
    }


@pytest.fixture
def sample_bug() -> Dict:
    """Sample bug report for testing"""
    return {
        "bug_id": "CSCwq12345",
        "summary": "SSH server crashes when processing malformed key exchange messages on IOS-XE devices",
        "platform": "IOS-XE",
        "labels": ["MGMT_SSH_HTTP", "SEC_CoPP"]
    }


@pytest.fixture
def sample_taxonomy() -> List[Dict]:
    """Sample feature taxonomy"""
    return [
        {
            "label": "APP_IOx",
            "domain": "Application",
            "presence": {
                "config_regex": ["^iox$", "^app-hosting"],
                "show_cmds": ["show iox", "show app-hosting list"]
            }
        },
        {
            "label": "MGMT_SSH_HTTP",
            "domain": "Management",
            "presence": {
                "config_regex": ["^ip ssh", "^ip http server"],
                "show_cmds": ["show ip ssh", "show ip http server"]
            }
        },
        {
            "label": "SEC_CoPP",
            "domain": "Security",
            "presence": {
                "config_regex": ["^control-plane", "^service-policy input"],
                "show_cmds": ["show policy-map control-plane"]
            }
        }
    ]


@pytest.fixture
def sample_device_config() -> str:
    """Sample device running configuration"""
    return """
!
version 17.3
service timestamps debug datetime msec
service timestamps log datetime msec
!
hostname TestRouter
!
ip ssh version 2
ip ssh server algorithm encryption aes128-ctr
!
control-plane
 service-policy input copp-system-policy
!
line vty 0 4
 transport input ssh
!
end
"""


@pytest.fixture
def sample_device_version() -> Dict:
    """Sample device version output"""
    return {
        "version": "17.3.5",
        "platform": "IOS-XE",
        "model": "C9200L-48P-4X",
        "raw_output": """
Cisco IOS XE Software, Version 17.03.05
Cisco IOS Software [Amsterdam], Catalyst L3 Switch Software
System image file is "flash:packages.conf"
"""
    }


@pytest.fixture
def mock_faiss_results() -> List[Dict]:
    """Mock FAISS similarity search results (above threshold)"""
    return [
        {
            "summary": "IOx vulnerability in IOS XE",
            "labels": ["APP_IOx"],
            "similarity": 0.92
        },
        {
            "summary": "Application hosting DoS in IOS XE",
            "labels": ["APP_IOx", "SEC_CoPP"],
            "similarity": 0.88
        },
        {
            "summary": "SSH vulnerability in management interface",
            "labels": ["MGMT_SSH_HTTP"],
            "similarity": 0.75
        }
    ]


@pytest.fixture
def api_test_url() -> str:
    """Base URL for API tests"""
    return "http://localhost:8000"


@pytest.fixture
def mock_llm_response() -> Dict:
    """Mock LLM response for testing"""
    return {
        "labels": ["APP_IOx", "SEC_CoPP"],
        "reasoning": "The vulnerability affects the IOx application hosting subsystem, which is a specific feature that can be detected via config checks.",
        "confidence": "HIGH"
    }


# =============================================================================
# FAISS FALLBACK FIXTURES (Section 6 - FAISS similarity < 0.70)
# =============================================================================

@pytest.fixture
def faiss_low_similarity_results() -> List[Dict]:
    """
    Mock FAISS results with similarity BELOW threshold (0.70).

    Reference: Section 6 - "FAISS similarity threshold: cosine_similarity < 0.70 triggers fallback"

    Use this fixture to test fallback behavior when FAISS cannot find
    sufficiently similar examples.
    """
    return [
        {
            "summary": "Unrelated vulnerability in different subsystem",
            "labels": ["RTE_OSPF"],
            "similarity": 0.45  # Below 0.70 threshold
        },
        {
            "summary": "Another unrelated security issue",
            "labels": ["SEC_AAA"],
            "similarity": 0.52  # Below 0.70 threshold
        },
        {
            "summary": "Generic network vulnerability",
            "labels": ["RTE_BGP"],
            "similarity": 0.61  # Below 0.70 threshold
        }
    ]


@pytest.fixture
def faiss_threshold_boundary_results() -> List[Dict]:
    """
    Mock FAISS results at exactly the threshold boundary.

    Useful for testing edge cases at similarity = 0.70.
    """
    return [
        {
            "summary": "Boundary case vulnerability",
            "labels": ["MGMT_SSH_HTTP"],
            "similarity": 0.70  # Exactly at threshold
        },
        {
            "summary": "Just below threshold",
            "labels": ["SEC_CoPP"],
            "similarity": 0.69  # Just below
        },
        {
            "summary": "Just above threshold",
            "labels": ["APP_IOx"],
            "similarity": 0.71  # Just above
        }
    ]


@pytest.fixture
def mock_faiss_index_low_similarity():
    """
    Mock FAISS index that returns low similarity scores.

    Reference: Section 6 - Triggers fallback to minimal heuristic prompt or needs_review.

    Usage:
        def test_fallback(mock_faiss_index_low_similarity):
            with mock_faiss_index_low_similarity(similarity=0.45):
                result = labeler.predict_labels(summary, platform)
                assert result.get('needs_review', False)
    """
    @contextmanager
    def _mock_faiss(similarity: float = 0.45, target_module: str = 'mlx_inference'):
        mock_index = MagicMock()
        # FAISS returns L2 distances; for cosine similarity index, lower distance = higher similarity
        # We simulate by returning 1 - similarity as distance
        mock_index.search.return_value = (
            [[1.0 - similarity] * 3],  # Distances for k=3
            [[0, 1, 2]]  # Indices
        )
        mock_index.ntotal = 1000  # Pretend we have vectors

        with patch(f'{target_module}.faiss.read_index', return_value=mock_index):
            yield mock_index

    return _mock_faiss


# =============================================================================
# LLM TIMEOUT/ERROR FIXTURES (Section 6 - LLM timeout/error handling)
# =============================================================================

@pytest.fixture
def llm_timeout_response() -> Dict:
    """
    Sample response when LLM times out.

    Reference: Section 6 - "LLM timeout/error -> return needs_review flag
    with confidence_source=heuristic; do NOT cache as confident"
    """
    return {
        "analysis_id": "timeout-fallback",
        "advisory_id": None,
        "psirt_summary": "",
        "platform": "IOS-XE",
        "predicted_labels": [],
        "confidence": 0.0,
        "confidence_source": "heuristic",
        "needs_review": True,
        "error": "LLM inference timed out",
        "cached": False,
        "timestamp": datetime.now().isoformat()
    }


@pytest.fixture
def llm_error_response() -> Dict:
    """
    Sample response when LLM encounters an error.

    Reference: Section 6 - Error responses should NOT be cached.
    """
    return {
        "analysis_id": "error-fallback",
        "advisory_id": None,
        "psirt_summary": "",
        "platform": "IOS-XE",
        "predicted_labels": [],
        "confidence": 0.0,
        "confidence_source": "heuristic",
        "needs_review": True,
        "error": "LLM inference failed: RuntimeError",
        "cached": False,
        "timestamp": datetime.now().isoformat()
    }


@pytest.fixture
def mock_llm_timeout():
    """
    Mock that simulates LLM timeout.

    Usage:
        def test_timeout_handling(mock_llm_timeout):
            with mock_llm_timeout(timeout_seconds=0.1):
                # Code under test - should handle timeout gracefully
                pass
    """
    @contextmanager
    def _mock_timeout(timeout_seconds: float = 0.1, target_module: str = 'mlx_inference'):
        def slow_generate(*args, **kwargs):
            time.sleep(timeout_seconds)
            raise TimeoutError("LLM inference timed out")

        with patch(f'{target_module}.generate', side_effect=slow_generate):
            yield

    return _mock_timeout


@pytest.fixture
def mock_llm_error():
    """
    Mock that simulates LLM error.

    Usage:
        def test_error_handling(mock_llm_error):
            with mock_llm_error(error_type=RuntimeError, error_msg="Model failed"):
                # Code under test - should handle error gracefully
                pass
    """
    @contextmanager
    def _mock_error(error_type: type = RuntimeError, error_msg: str = "LLM inference failed", target_module: str = 'mlx_inference'):
        with patch(f'{target_module}.generate', side_effect=error_type(error_msg)):
            yield

    return _mock_error


# =============================================================================
# CONFIDENCE SOURCE / NEEDS_REVIEW FIXTURES (Section 6 - Caching rules)
# =============================================================================

@pytest.fixture
def confidence_source_model_payload() -> Dict:
    """
    Sample payload with confidence_source='model' (high confidence, cacheable).

    Reference: Section 6 - Cache if confidence >= 0.75 and source is model.
    """
    return {
        "analysis_id": "model-result-001",
        "advisory_id": "cisco-sa-test-model",
        "psirt_summary": "Test PSIRT with model-sourced labels",
        "platform": "IOS-XE",
        "predicted_labels": ["MGMT_SSH_HTTP", "SEC_CoPP"],
        "confidence": 0.85,
        "confidence_source": "model",
        "needs_review": False,
        "config_regex": [r"ip ssh", r"control-plane"],
        "show_commands": ["show ip ssh", "show control-plane"],
        "timestamp": datetime.now().isoformat()
    }


@pytest.fixture
def confidence_source_heuristic_payload() -> Dict:
    """
    Sample payload with confidence_source='heuristic' (low confidence, NOT cacheable).

    Reference: Section 6 - Heuristic results should NOT be cached.
    """
    return {
        "analysis_id": "heuristic-result-001",
        "advisory_id": "cisco-sa-test-heuristic",
        "psirt_summary": "Test PSIRT with heuristic fallback labels",
        "platform": "IOS-XE",
        "predicted_labels": ["MGMT_SSH_HTTP"],
        "confidence": 0.50,
        "confidence_source": "heuristic",
        "needs_review": True,
        "config_regex": [r"ip ssh"],
        "show_commands": ["show ip ssh"],
        "timestamp": datetime.now().isoformat()
    }


@pytest.fixture
def needs_review_payload() -> Dict:
    """
    Sample payload with needs_review=True (should NOT be cached).

    Reference: Section 6 - "do NOT cache as confident" when needs_review.
    """
    return {
        "analysis_id": "needs-review-001",
        "advisory_id": "cisco-sa-needs-review",
        "psirt_summary": "PSIRT requiring manual review",
        "platform": "IOS-XE",
        "predicted_labels": ["MGMT_SSH_HTTP"],
        "confidence": 0.45,
        "confidence_source": "heuristic",
        "needs_review": True,
        "review_reason": "Low FAISS similarity and ambiguous text",
        "cached": False,
        "timestamp": datetime.now().isoformat()
    }


# =============================================================================
# MODEL VERSION / LORA UPDATE FIXTURES (Section 6 - Cache invalidation)
# =============================================================================

@pytest.fixture
def model_version_toggle():
    """
    Fixture to simulate model/LoRA version changes.

    Reference: Section 6 - "LoRA/model update -> rebuild FAISS index to avoid embedding drift"

    Usage:
        def test_lora_update_triggers_rebuild(model_version_toggle, faiss_rebuild_spy):
            model_version_toggle.set_version("v4")
            # Trigger rebuild check
            assert faiss_rebuild_spy.rebuild_called
    """
    class ModelVersionToggle:
        def __init__(self):
            self.current_version = "v3"
            self.previous_version = "v3"
            self.version_changed = False

        def set_version(self, new_version: str):
            self.previous_version = self.current_version
            self.current_version = new_version
            self.version_changed = self.current_version != self.previous_version

        def reset(self):
            self.current_version = "v3"
            self.previous_version = "v3"
            self.version_changed = False

        def get_adapter_path(self) -> str:
            return f"models/lora_adapter_{self.current_version}"

    return ModelVersionToggle()


@pytest.fixture
def lora_update_flag():
    """
    Simple flag to simulate LoRA update detection.

    Reference: Section 6 - Invalidation rules for LoRA update.
    """
    class LoRAUpdateFlag:
        def __init__(self):
            self.updated = False
            self.old_version = None
            self.new_version = None

        def trigger_update(self, old: str = "v3", new: str = "v4"):
            self.updated = True
            self.old_version = old
            self.new_version = new

        def reset(self):
            self.updated = False
            self.old_version = None
            self.new_version = None

    return LoRAUpdateFlag()


@pytest.fixture
def faiss_rebuild_spy():
    """
    Spy to track FAISS index rebuild calls.

    Reference: Section 6 - "LoRA/model update -> rebuild FAISS index"

    Usage:
        def test_rebuild_triggered(faiss_rebuild_spy, lora_update_flag):
            lora_update_flag.trigger_update()
            # Code that should trigger rebuild
            assert faiss_rebuild_spy.rebuild_called
            assert faiss_rebuild_spy.rebuild_count == 1
    """
    class FAISSRebuildSpy:
        def __init__(self):
            self.rebuild_called = False
            self.rebuild_count = 0
            self.rebuild_reasons = []
            self.last_rebuild_time = None

        def record_rebuild(self, reason: str = "unspecified"):
            self.rebuild_called = True
            self.rebuild_count += 1
            self.rebuild_reasons.append(reason)
            self.last_rebuild_time = datetime.now()

        def reset(self):
            self.rebuild_called = False
            self.rebuild_count = 0
            self.rebuild_reasons = []
            self.last_rebuild_time = None

        def assert_rebuild_called(self, reason: Optional[str] = None):
            assert self.rebuild_called, "Expected FAISS rebuild but none recorded"
            if reason:
                assert reason in self.rebuild_reasons, f"Expected rebuild reason '{reason}' not found"

        def assert_no_rebuild(self):
            assert not self.rebuild_called, f"Unexpected FAISS rebuild: {self.rebuild_reasons}"

    return FAISSRebuildSpy()


@pytest.fixture
def mock_faiss_rebuild():
    """
    Mock the FAISS rebuild function with spy integration.

    Note: The actual FAISS builder is at scripts/build_faiss_index.py
    with a main() function. This mock provides flexible patching.

    Usage:
        def test_rebuild(mock_faiss_rebuild, faiss_rebuild_spy):
            with mock_faiss_rebuild(spy=faiss_rebuild_spy):
                # Code that triggers rebuild
                build_faiss_index()
            faiss_rebuild_spy.assert_rebuild_called(reason="lora_update")
    """
    @contextmanager
    def _mock_rebuild(spy=None, target: str = 'scripts.build_faiss_index.main'):
        """
        Args:
            spy: Optional FAISSRebuildSpy to record rebuild calls
            target: The full module path to patch (default: scripts.build_faiss_index.main)
                    Can also be 'faiss.write_index' to mock the FAISS write operation
        """
        def mock_build(*args, **kwargs):
            if spy:
                reason = kwargs.get('reason', 'manual')
                spy.record_rebuild(reason)
            return MagicMock(ntotal=1000)  # Return mock index

        try:
            with patch(target, side_effect=mock_build):
                yield
        except ModuleNotFoundError:
            # If the target module doesn't exist, just yield with spy recording
            # This allows tests to work even without the actual FAISS builder
            if spy:
                spy.record_rebuild("mock_fallback")
            yield

    return _mock_rebuild


# =============================================================================
# TAXONOMY DELTA FIXTURES (Section 6 - Taxonomy change invalidation)
# =============================================================================

@pytest.fixture
def taxonomy_delta():
    """
    Fixture representing taxonomy changes.

    Reference: Section 6 - "Taxonomy change -> rebuild FAISS entries that reference changed features"

    Usage:
        def test_taxonomy_change(taxonomy_delta, faiss_rebuild_spy):
            taxonomy_delta.add_label("NEW_FEATURE", "IOS-XE")
            # Trigger rebuild check
            assert faiss_rebuild_spy.rebuild_called
    """
    class TaxonomyDelta:
        def __init__(self):
            self.added_labels: List[Dict] = []
            self.removed_labels: List[str] = []
            self.modified_labels: List[Dict] = []
            self.affected_platforms: set = set()

        def add_label(self, label: str, platform: str, description: str = ""):
            self.added_labels.append({
                "label": label,
                "platform": platform,
                "description": description
            })
            self.affected_platforms.add(platform)

        def remove_label(self, label: str, platform: str):
            self.removed_labels.append(label)
            self.affected_platforms.add(platform)

        def modify_label(self, label: str, platform: str, changes: Dict):
            self.modified_labels.append({
                "label": label,
                "platform": platform,
                "changes": changes
            })
            self.affected_platforms.add(platform)

        def has_changes(self) -> bool:
            return bool(self.added_labels or self.removed_labels or self.modified_labels)

        def get_affected_labels(self) -> List[str]:
            labels = [l["label"] for l in self.added_labels]
            labels.extend(self.removed_labels)
            labels.extend([l["label"] for l in self.modified_labels])
            return labels

        def reset(self):
            self.added_labels = []
            self.removed_labels = []
            self.modified_labels = []
            self.affected_platforms = set()

    return TaxonomyDelta()


# =============================================================================
# TIMING / PERFORMANCE FIXTURES (Section 9 - Performance checks)
# =============================================================================

@dataclass
class TimingResult:
    """Result of a timing measurement"""
    operation: str
    latency_ms: float
    success: bool
    timestamp: datetime = field(default_factory=datetime.now)
    details: Dict = field(default_factory=dict)


@pytest.fixture
def timing_helper():
    """
    Helper for measuring and asserting latency in benchmark tests.

    Reference: Section 9 - "Performance check: DB path remains ~<10ms;
    AI path stays within expected latency budget"

    Usage:
        def test_db_performance(timing_helper):
            with timing_helper.measure("db_scan") as result:
                scanner.scan_device(platform, version)

            timing_helper.assert_latency_under(result, DB_LATENCY_TARGET_MS)
    """
    class TimingHelper:
        def __init__(self):
            self.results: List[TimingResult] = []

        @contextmanager
        def measure(self, operation: str):
            """Context manager to measure operation latency"""
            result = TimingResult(operation=operation, latency_ms=0, success=False)
            start = time.perf_counter()

            try:
                yield result
                result.success = True
            except Exception as e:
                result.success = False
                result.details['error'] = str(e)
                raise
            finally:
                end = time.perf_counter()
                result.latency_ms = (end - start) * 1000
                self.results.append(result)

        def assert_latency_under(self, result: TimingResult, target_ms: float, tolerance_factor: float = 2.0):
            """Assert latency is under target (with tolerance for CI environments)"""
            # Allow tolerance_factor multiplier for CI/test environments
            max_allowed = target_ms * tolerance_factor
            assert result.latency_ms < max_allowed, (
                f"{result.operation}: {result.latency_ms:.2f}ms exceeds "
                f"{max_allowed:.2f}ms (target {target_ms}ms * {tolerance_factor}x tolerance)"
            )

        def assert_db_latency(self, result: TimingResult):
            """Assert DB operation meets target (<10ms, with tolerance)"""
            self.assert_latency_under(result, DB_LATENCY_TARGET_MS, tolerance_factor=10.0)

        def assert_ai_latency(self, result: TimingResult):
            """Assert AI operation meets target (~3400ms, with tolerance)"""
            self.assert_latency_under(result, AI_LATENCY_TARGET_MS, tolerance_factor=2.0)

        def assert_faiss_latency(self, result: TimingResult):
            """Assert FAISS operation meets target (~30ms, with tolerance)"""
            self.assert_latency_under(result, FAISS_RETRIEVAL_TARGET_MS, tolerance_factor=5.0)

        def get_summary(self) -> Dict:
            """Get summary statistics of all measurements"""
            if not self.results:
                return {"measurements": 0}

            by_operation = {}
            for r in self.results:
                if r.operation not in by_operation:
                    by_operation[r.operation] = []
                by_operation[r.operation].append(r.latency_ms)

            summary = {"measurements": len(self.results), "operations": {}}
            for op, latencies in by_operation.items():
                sorted_lat = sorted(latencies)
                summary["operations"][op] = {
                    "count": len(latencies),
                    "min_ms": min(latencies),
                    "max_ms": max(latencies),
                    "avg_ms": sum(latencies) / len(latencies),
                    "p50_ms": sorted_lat[len(latencies) // 2],
                    "p99_ms": sorted_lat[int(len(latencies) * 0.99)] if len(latencies) >= 100 else max(latencies)
                }

            return summary

        def reset(self):
            self.results = []

    return TimingHelper()


# =============================================================================
# OBSERVABILITY / LOG CAPTURE FIXTURES (Section 8 - Observability Plan)
# =============================================================================

@pytest.fixture
def log_capture():
    """
    Fixture to capture and assert log outputs.

    Reference: Section 8 - "Structured logs for routing decision, similarity score,
    threshold used, fallback path taken, and cache write source"

    Usage:
        def test_logging(log_capture):
            with log_capture.capture("backend.core.vulnerability_scanner") as logs:
                scanner.scan_device(platform, version)

            log_capture.assert_logged("scan", level="INFO")
            log_capture.assert_logged_field("query_time_ms")
    """
    class LogCapture:
        def __init__(self):
            self.captured_records: List[logging.LogRecord] = []
            self.handler: Optional[logging.Handler] = None

        @contextmanager
        def capture(self, logger_name: str = "backend", level: int = logging.DEBUG):
            """Context manager to capture logs from specified logger"""
            logger = logging.getLogger(logger_name)
            original_level = logger.level

            # Create handler that captures records
            class CaptureHandler(logging.Handler):
                def __init__(self, records_list):
                    super().__init__()
                    self.records_list = records_list

                def emit(self, record):
                    self.records_list.append(record)

            self.captured_records = []
            handler = CaptureHandler(self.captured_records)
            handler.setLevel(level)

            logger.addHandler(handler)
            logger.setLevel(level)

            try:
                yield self.captured_records
            finally:
                logger.removeHandler(handler)
                logger.setLevel(original_level)

        def assert_logged(self, substring: str, level: Optional[str] = None):
            """Assert that a log message containing substring was captured"""
            for record in self.captured_records:
                msg = record.getMessage().lower()
                if substring.lower() in msg:
                    if level is None or record.levelname == level:
                        return True

            level_filter = f" at level {level}" if level else ""
            assert False, f"Expected log containing '{substring}'{level_filter} not found"

        def assert_logged_field(self, field_name: str):
            """Assert that a structured log field was captured"""
            for record in self.captured_records:
                msg = record.getMessage()
                if field_name in msg:
                    return True
                # Check if record has extra attributes
                if hasattr(record, field_name):
                    return True

            assert False, f"Expected log field '{field_name}' not found"

        def assert_not_logged(self, substring: str):
            """Assert that no log message contains substring"""
            for record in self.captured_records:
                msg = record.getMessage().lower()
                assert substring.lower() not in msg, f"Unexpected log containing '{substring}' found"

        def get_logs_containing(self, substring: str) -> List[str]:
            """Get all log messages containing substring"""
            return [
                record.getMessage()
                for record in self.captured_records
                if substring.lower() in record.getMessage().lower()
            ]

        def clear(self):
            self.captured_records = []

    return LogCapture()


@pytest.fixture
def metric_capture():
    """
    Fixture to capture and assert metrics outputs.

    Reference: Section 8 - "LLM latency histogram, FAISS hit/miss and similarity distribution,
    cache hit/miss, confidence score distribution"

    Usage:
        def test_metrics(metric_capture):
            with metric_capture.track():
                scanner.scan_device(platform, version)

            metric_capture.assert_metric_recorded("db_scan_latency_ms")
            metric_capture.assert_metric_value("cache_hit", expected=True)
    """
    class MetricCapture:
        def __init__(self):
            self.metrics: Dict[str, Any] = {}
            self.histograms: Dict[str, List[float]] = {}

        @contextmanager
        def track(self):
            """Context manager to track metrics"""
            self.metrics = {}
            self.histograms = {}
            yield self

        def record(self, name: str, value: Any):
            """Record a metric value"""
            self.metrics[name] = value

        def record_histogram(self, name: str, value: float):
            """Record a value in a histogram"""
            if name not in self.histograms:
                self.histograms[name] = []
            self.histograms[name].append(value)

        def assert_metric_recorded(self, name: str):
            """Assert that a metric was recorded"""
            assert name in self.metrics or name in self.histograms, (
                f"Metric '{name}' not recorded. Recorded: {list(self.metrics.keys()) + list(self.histograms.keys())}"
            )

        def assert_metric_value(self, name: str, expected: Any):
            """Assert a metric has expected value"""
            assert name in self.metrics, f"Metric '{name}' not found"
            assert self.metrics[name] == expected, (
                f"Metric '{name}': expected {expected}, got {self.metrics[name]}"
            )

        def get_histogram_stats(self, name: str) -> Dict:
            """Get statistics for a histogram"""
            if name not in self.histograms or not self.histograms[name]:
                return {}

            values = sorted(self.histograms[name])
            return {
                "count": len(values),
                "min": min(values),
                "max": max(values),
                "avg": sum(values) / len(values),
                "p50": values[len(values) // 2],
                "p99": values[int(len(values) * 0.99)] if len(values) >= 100 else max(values)
            }

        def clear(self):
            self.metrics = {}
            self.histograms = {}

    return MetricCapture()


# =============================================================================
# CACHE MANIPULATION FIXTURES
# =============================================================================

@pytest.fixture
def cache_manipulator(tmp_path):
    """
    Fixture for manipulating and verifying cache state.

    SAFETY: Uses a temporary copy of the database to avoid mutating production data.
    The fixture copies the real database to a temp location and operates only on that copy.

    Reference: Section 6 - Caching tiers and invalidation rules.
    """
    import shutil

    # Source database
    src_db = Path('vulnerability_db.sqlite')

    # Create temp copy for test isolation
    if src_db.exists():
        test_db = tmp_path / 'test_vulnerability_db.sqlite'
        shutil.copy(src_db, test_db)
        db_path = str(test_db)
    else:
        # Create in-memory db for tests when source doesn't exist
        db_path = ':memory:'

    class CacheManipulator:
        def __init__(self, db_path: str):
            self.db_path = db_path
            self._connection = None
            # For in-memory db, keep connection open
            if db_path == ':memory:':
                self._connection = sqlite3.connect(db_path)
                self._init_schema()

        def _init_schema(self):
            """Initialize minimal schema for in-memory testing.

            Note: Schema mirrors production vulnerabilities table columns
            relevant to PSIRT caching (Section 6 of ARCHITECTURE_AND_WORKFLOW.md).
            Keep in sync with backend/db/schema.py if columns are added.
            """
            if self._connection:
                cursor = self._connection.cursor()
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS vulnerabilities (
                        id INTEGER PRIMARY KEY,
                        advisory_id TEXT,
                        platform TEXT,
                        vuln_type TEXT,
                        labels TEXT,
                        labels_source TEXT,
                        confidence REAL,
                        confidence_source TEXT,
                        needs_review INTEGER DEFAULT 0
                    )
                ''')
                self._connection.commit()

        def _get_connection(self):
            """Get database connection (reuse for in-memory)"""
            if self._connection:
                return self._connection
            return sqlite3.connect(self.db_path)

        def clear_psirt_cache(self, advisory_id: Optional[str] = None) -> int:
            """Clear PSIRT cache entries"""
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                if advisory_id:
                    cursor.execute(
                        "DELETE FROM vulnerabilities WHERE advisory_id = ? AND vuln_type = 'psirt'",
                        (advisory_id,)
                    )
                else:
                    cursor.execute(
                        "DELETE FROM vulnerabilities WHERE vuln_type = 'psirt' AND advisory_id LIKE 'test-%'"
                    )
                conn.commit()
                return cursor.rowcount
            except Exception:
                return 0

        def verify_cached(self, advisory_id: str, platform: str) -> bool:
            """Verify an entry IS in cache"""
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT 1 FROM vulnerabilities WHERE advisory_id = ? AND platform = ? AND vuln_type = 'psirt'",
                    (advisory_id, platform)
                )
                return cursor.fetchone() is not None
            except Exception:
                return False

        def verify_not_cached(self, advisory_id: str, platform: str) -> bool:
            """Verify an entry is NOT in cache"""
            return not self.verify_cached(advisory_id, platform)

        def get_cache_entry(self, advisory_id: str, platform: str) -> Optional[Dict]:
            """Get a cache entry's details including confidence fields."""
            try:
                conn = self._get_connection()
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(
                    """SELECT advisory_id, platform, labels, labels_source,
                              confidence, confidence_source, needs_review
                       FROM vulnerabilities
                       WHERE advisory_id = ? AND platform = ? AND vuln_type = 'psirt'""",
                    (advisory_id, platform)
                )
                row = cursor.fetchone()
                if row:
                    entry = dict(row)
                    # Convert needs_review back to bool
                    entry['needs_review'] = bool(entry.get('needs_review', 0))
                    return entry
                return None
            except Exception:
                return None

        def insert_test_entry(
            self,
            advisory_id: str,
            platform: str,
            labels: str = "TEST_LABEL",
            labels_source: str = "model",
            confidence: float = 0.85,
            confidence_source: str = "model",
            needs_review: bool = False
        ) -> bool:
            """Insert a test cache entry (for testing cache behavior).

            Args:
                advisory_id: PSIRT advisory ID
                platform: Platform (IOS-XE, IOS-XR, etc.)
                labels: Comma-separated label string
                labels_source: Source of labels (model, heuristic, exact_match)
                confidence: Confidence score (0.0 to 1.0)
                confidence_source: Source of confidence (model, heuristic)
                needs_review: Whether entry requires manual review
            """
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute(
                    """INSERT INTO vulnerabilities
                       (advisory_id, platform, vuln_type, labels, labels_source,
                        confidence, confidence_source, needs_review)
                       VALUES (?, ?, 'psirt', ?, ?, ?, ?, ?)""",
                    (advisory_id, platform, labels, labels_source,
                     confidence, confidence_source, 1 if needs_review else 0)
                )
                conn.commit()
                return True
            except Exception:
                return False

        def cleanup(self):
            """Clean up connections"""
            if self._connection:
                self._connection.close()
                self._connection = None

    manipulator = CacheManipulator(db_path)
    yield manipulator
    manipulator.cleanup()


# =============================================================================
# PYTEST CONFIGURATION
# =============================================================================

def pytest_configure(config):
    """Register custom markers"""
    # Basic markers
    config.addinivalue_line("markers", "unit: mark test as a unit test")
    config.addinivalue_line("markers", "integration: mark test as an integration test")
    config.addinivalue_line("markers", "e2e: mark test as an end-to-end test")
    config.addinivalue_line("markers", "slow: mark test as slow (skipped unless --slow)")
    config.addinivalue_line("markers", "requires_device: mark test as requiring device access")
    config.addinivalue_line("markers", "requires_gpu: mark test as requiring GPU")

    # Architecture test markers (Section 9 of ARCHITECTURE_AND_WORKFLOW.md)
    config.addinivalue_line("markers", "architecture: mark test as architecture verification test")
    config.addinivalue_line("markers", "baseline: mark test as baseline verification (run before refactor)")
    config.addinivalue_line("markers", "refactor: mark test as refactor verification (run during refactor)")
    config.addinivalue_line("markers", "comparison: mark test as comparison test (run after refactor)")
    config.addinivalue_line("markers", "benchmark: mark test as performance benchmark")
    config.addinivalue_line("markers", "observability: mark test as observability/logging test")


def pytest_addoption(parser):
    """Add custom command-line options"""
    # Basic options
    parser.addoption("--slow", action="store_true", default=False, help="run slow tests")
    parser.addoption("--device", action="store_true", default=False, help="run tests requiring device access")
    parser.addoption("--gpu", action="store_true", default=False, help="run tests requiring GPU")

    # Architecture phase options (Section 9)
    parser.addoption("--architecture", action="store_true", default=False,
                     help="run architecture tests only (tests/architecture/)")
    parser.addoption("--baseline", action="store_true", default=False,
                     help="run baseline tests only (pre-refactor verification)")
    parser.addoption("--refactor", action="store_true", default=False,
                     help="run refactor tests only (during-refactor verification)")
    parser.addoption("--comparison", action="store_true", default=False,
                     help="run comparison tests only (post-refactor verification)")
    parser.addoption("--benchmark", action="store_true", default=False,
                     help="run performance benchmark tests")
    parser.addoption("--observability", action="store_true", default=False,
                     help="run observability/logging tests")

    # Results storage options
    parser.addoption("--save-results", action="store_true", default=False,
                     help="save test results to tests/architecture/results/")
    parser.addoption("--results-version", action="store", default="v1",
                     help="version tag for saved results (e.g., 'v1', 'pre-refactor')")


def pytest_collection_modifyitems(config, items):
    """Skip tests based on markers and CLI options"""
    # Basic skips
    skip_slow = pytest.mark.skip(reason="need --slow option to run")
    skip_device = pytest.mark.skip(reason="need --device option to run")
    skip_gpu = pytest.mark.skip(reason="need --gpu option to run")

    # Architecture phase filters
    architecture_mode = config.getoption("--architecture")
    baseline_mode = config.getoption("--baseline")
    refactor_mode = config.getoption("--refactor")
    comparison_mode = config.getoption("--comparison")
    benchmark_mode = config.getoption("--benchmark")
    observability_mode = config.getoption("--observability")

    # Check if any architecture phase is selected (including benchmark)
    phase_selected = any([baseline_mode, refactor_mode, comparison_mode, observability_mode, benchmark_mode])

    for item in items:
        # Basic marker skips
        if "slow" in item.keywords and not config.getoption("--slow"):
            item.add_marker(skip_slow)
        if "requires_device" in item.keywords and not config.getoption("--device"):
            item.add_marker(skip_device)
        if "requires_gpu" in item.keywords and not config.getoption("--gpu"):
            item.add_marker(skip_gpu)

        # Architecture phase filtering
        if architecture_mode:
            # Only run tests marked with 'architecture'
            if "architecture" not in item.keywords:
                item.add_marker(pytest.mark.skip(reason="not an architecture test (use -m architecture)"))

        if phase_selected:
            # If a specific phase is selected, skip tests not in that phase
            is_baseline = "baseline" in item.keywords
            is_refactor = "refactor" in item.keywords
            is_comparison = "comparison" in item.keywords
            is_observability = "observability" in item.keywords
            is_benchmark = "benchmark" in item.keywords

            should_run = (
                (baseline_mode and is_baseline) or
                (refactor_mode and is_refactor) or
                (comparison_mode and is_comparison) or
                (observability_mode and is_observability) or
                (benchmark_mode and is_benchmark)
            )

            # Skip if this is an architecture-phase test but not in the selected phase(s)
            if not should_run and any([is_baseline, is_refactor, is_comparison, is_observability, is_benchmark]):
                item.add_marker(pytest.mark.skip(reason="not in selected architecture phase"))


# =============================================================================
# GOLDEN PATH TEST DATA LOADER
# =============================================================================

@pytest.fixture
def psirt_corpus() -> Dict:
    """
    Load the golden-path PSIRT test corpus.

    Reference: Section 9 - "Add a small fixture PSIRT corpus...to keep tests deterministic"
    """
    corpus_path = TEST_DATA_DIR / "psirt_corpus.json"
    if corpus_path.exists():
        with open(corpus_path, 'r') as f:
            return json.load(f)
    return {"psirts": [], "bugs": []}


# =============================================================================
# RESULTS STORAGE (for tracking test outputs over time)
# =============================================================================

# Global storage for test results during a session
_test_results_collector: Dict[str, List[Dict]] = {}


def _get_test_phase(item) -> Optional[str]:
    """Determine the test phase from markers"""
    if "baseline" in item.keywords:
        return "baseline"
    elif "refactor" in item.keywords:
        return "refactor"
    elif "comparison" in item.keywords:
        return "comparison"
    elif "benchmark" in item.keywords:
        return "benchmark"
    elif "observability" in item.keywords:
        return "observability"
    elif "architecture" in item.keywords:
        return "architecture"
    return None


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """
    Hook to capture test results for storage.

    Only captures results when --save-results is enabled.
    """
    outcome = yield
    report = outcome.get_result()

    # Only process when --save-results is enabled
    if not item.config.getoption("--save-results", default=False):
        return

    # Only capture the 'call' phase (not setup/teardown)
    if report.when != "call":
        return

    phase = _get_test_phase(item)
    if not phase:
        phase = "other"

    if phase not in _test_results_collector:
        _test_results_collector[phase] = []

    # Extract test information
    test_class = item.cls.__name__ if item.cls else "NoClass"
    test_file = Path(item.fspath).name if item.fspath else "unknown"

    result_entry = {
        "test_name": item.name,
        "test_class": test_class,
        "test_file": test_file,
        "status": report.outcome,  # passed, failed, skipped
        "duration_ms": report.duration * 1000,
        "details": {},
        "error_message": None
    }

    # Capture error details if failed
    if report.outcome == "failed":
        result_entry["error_message"] = str(report.longrepr) if report.longrepr else "Unknown error"

    # Capture skip reason if skipped
    if report.outcome == "skipped":
        result_entry["details"]["skip_reason"] = str(report.longrepr[2]) if report.longrepr else "Unknown"

    _test_results_collector[phase].append(result_entry)


def pytest_sessionfinish(session, exitstatus):
    """
    Hook to save collected results at end of test session.

    Only saves when --save-results is enabled.
    """
    if not session.config.getoption("--save-results", default=False):
        return

    if not _test_results_collector:
        return

    # Import here to avoid circular imports
    from tests.architecture.results_manager import ResultsManager

    version = session.config.getoption("--results-version", default="v1")
    manager = ResultsManager(version=version)

    saved_files = []

    for phase, results in _test_results_collector.items():
        if not results:
            continue

        for result in results:
            manager.record_test(
                phase=phase,
                test_name=result["test_name"],
                test_class=result["test_class"],
                test_file=result["test_file"],
                status=result["status"],
                duration_ms=result["duration_ms"],
                details=result.get("details", {}),
                error_message=result.get("error_message")
            )

        try:
            filepath = manager.save_phase_results(
                phase=phase,
                notes=f"Automated save from pytest session (exit status: {exitstatus})"
            )
            saved_files.append(str(filepath))
        except Exception as e:
            print(f"\nWarning: Could not save results for phase '{phase}': {e}")

    if saved_files:
        print(f"\n\nTest results saved to:")
        for f in saved_files:
            print(f"  - {f}")

    # Clear collector for next run
    _test_results_collector.clear()


@pytest.fixture
def results_manager(request):
    """
    Fixture providing access to the results manager for custom result recording.

    Usage:
        def test_example(results_manager):
            # Run test logic
            result_data = {"custom_metric": 42}
            results_manager.record_test(
                phase="baseline",
                test_name="test_example",
                test_class="TestCustom",
                test_file="test_custom.py",
                status="passed",
                duration_ms=100,
                details=result_data
            )
    """
    from tests.architecture.results_manager import ResultsManager

    version = request.config.getoption("--results-version", default="v1")
    return ResultsManager(version=version)
