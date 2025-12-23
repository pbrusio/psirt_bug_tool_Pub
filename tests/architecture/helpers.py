"""
Architecture Test Helpers

This module provides helper classes and utilities for architecture tests.
Some are also available as pytest fixtures in tests/conftest.py.

Reference: docs/ARCHITECTURE_AND_WORKFLOW.md Section 9

Classes provided:
- OutputComparator: Compare pre/post refactor outputs
- PerformanceBenchmark: Measure and assert latency (same as timing_helper fixture)
- CacheManipulator: Manipulate and verify cache state (same as cache_manipulator fixture)
- FAISSSimulator: Simulate FAISS low-similarity scenarios
- LLMSimulator: Simulate LLM timeout/error scenarios
"""

import json
import time
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
from contextlib import contextmanager
from dataclasses import dataclass, field
from unittest.mock import MagicMock, patch

# Re-export constants from conftest for direct import
from tests.conftest import (
    FAISS_SIMILARITY_THRESHOLD,
    CACHE_CONFIDENCE_THRESHOLD,
    DB_LATENCY_TARGET_MS,
    AI_LATENCY_TARGET_MS,
    FAISS_RETRIEVAL_TARGET_MS,
)


def load_psirt_corpus() -> Dict:
    """
    Load the golden-path PSIRT test corpus.

    This is a standalone function for use outside of pytest context.
    For pytest tests, use the `psirt_corpus` fixture instead.
    """
    corpus_path = Path(__file__).parent.parent / 'fixtures' / 'psirt_corpus.json'
    if corpus_path.exists():
        with open(corpus_path, 'r') as f:
            return json.load(f)
    return {"psirts": [], "bugs": []}


# =============================================================================
# CACHE MANIPULATION CLASS
# =============================================================================

class CacheManipulator:
    """
    Manipulate and verify cache state.

    Also available as `cache_manipulator` fixture in conftest.py.
    Reference: Section 6 - Caching tiers and invalidation rules.
    """
    def __init__(self, db_path: str = 'vulnerability_db.sqlite'):
        self.db_path = db_path

    def clear_psirt_cache(self, advisory_id: Optional[str] = None) -> int:
        """Clear PSIRT cache entries"""
        try:
            with sqlite3.connect(self.db_path) as db:
                cursor = db.cursor()
                if advisory_id:
                    cursor.execute(
                        "DELETE FROM vulnerabilities WHERE advisory_id = ? AND vuln_type = 'psirt'",
                        (advisory_id,)
                    )
                else:
                    cursor.execute(
                        "DELETE FROM vulnerabilities WHERE vuln_type = 'psirt' AND advisory_id LIKE 'test-%'"
                    )
                db.commit()
                return cursor.rowcount
        except Exception:
            return 0

    def verify_cached(self, advisory_id: str, platform: str) -> bool:
        """Verify an entry IS in cache"""
        try:
            with sqlite3.connect(self.db_path) as db:
                cursor = db.cursor()
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
        """Get a cache entry's details"""
        try:
            with sqlite3.connect(self.db_path) as db:
                db.row_factory = sqlite3.Row
                cursor = db.cursor()
                cursor.execute(
                    """SELECT advisory_id, platform, labels, labels_source
                       FROM vulnerabilities
                       WHERE advisory_id = ? AND platform = ? AND vuln_type = 'psirt'""",
                    (advisory_id, platform)
                )
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception:
            return None

    def get_cache_stats(self) -> Dict:
        """Get cache statistics"""
        try:
            with sqlite3.connect(self.db_path) as db:
                cursor = db.cursor()
                cursor.execute("SELECT COUNT(*) FROM vulnerabilities WHERE vuln_type = 'psirt'")
                psirt_count = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM vulnerabilities WHERE vuln_type = 'bug'")
                bug_count = cursor.fetchone()[0]
                return {
                    "psirt_cache_entries": psirt_count,
                    "bug_entries": bug_count,
                    "total": psirt_count + bug_count
                }
        except Exception:
            return {"error": "Could not retrieve cache stats"}


# =============================================================================
# PERFORMANCE BENCHMARK CLASS
# =============================================================================

@dataclass
class TimingResult:
    """Result of a timing measurement"""
    operation: str
    latency_ms: float = 0.0
    success: bool = False
    timestamp: datetime = field(default_factory=datetime.now)
    details: Dict = field(default_factory=dict)


class PerformanceBenchmark:
    """
    Measure and assert latency in benchmark tests.

    Also available as `timing_helper` fixture in conftest.py.
    Reference: Section 9 - "Performance check: DB path remains ~<10ms"
    """
    def __init__(self):
        self.results: List[TimingResult] = []

    @contextmanager
    def measure(self, operation: str):
        """Context manager to measure operation latency"""
        result = TimingResult(operation=operation)
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

    def get_summary(self) -> Dict:
        """Get summary statistics of all measurements"""
        if not self.results:
            return {"measurements": 0, "operations": {}}

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


# Alias for backwards compatibility
PerformanceBaseline = PerformanceBenchmark


# =============================================================================
# FAISS SIMULATOR CLASS
# =============================================================================

def get_inference_module() -> str:
    """
    Get the appropriate inference module based on platform.

    Returns 'mlx_inference' on Mac/MPS, 'fewshot_inference' on Linux/CUDA/CPU.

    Note: On Linux, faiss is imported in fewshot_inference.py (base class),
    not in transformers_inference.py.
    """
    import sys
    try:
        import torch
        if sys.platform == 'darwin' and hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            return 'mlx_inference'
    except ImportError:
        pass
    # faiss is imported in fewshot_inference.py which is the base class
    return 'fewshot_inference'


class FAISSSimulator:
    """
    Simulate FAISS low-similarity scenarios for fallback testing.

    Reference: Section 6 - "FAISS similarity threshold: cosine_similarity < 0.70 triggers fallback"
    """

    @staticmethod
    @contextmanager
    def simulate_low_similarity(target_module: str = None, similarity: float = 0.45):
        """
        Context manager to simulate low FAISS similarity scores.

        Usage:
            with FAISSSimulator.simulate_low_similarity():
                result = labeler.predict_labels(summary, platform)
                assert result.get('needs_review', False)

        Args:
            target_module: Module to patch. If None, auto-detects based on platform
                          (mlx_inference on Mac, transformers_inference on Linux)
            similarity: Simulated similarity score (default 0.45, below 0.70 threshold)
        """
        if target_module is None:
            target_module = get_inference_module()

        mock_index = MagicMock()
        # FAISS returns L2 distances; for cosine similarity index, lower distance = higher similarity
        mock_index.search.return_value = (
            [[1.0 - similarity] * 3],  # Distances for k=3
            [[0, 1, 2]]  # Indices
        )
        mock_index.ntotal = 1000

        with patch(f'{target_module}.faiss.read_index', return_value=mock_index):
            yield mock_index

    @staticmethod
    def get_low_similarity_results() -> List[Dict]:
        """Get mock FAISS results with similarity below threshold"""
        return [
            {"summary": "Unrelated vulnerability", "labels": ["RTE_OSPF"], "similarity": 0.45},
            {"summary": "Another unrelated issue", "labels": ["SEC_AAA"], "similarity": 0.52},
            {"summary": "Generic network vuln", "labels": ["RTE_BGP"], "similarity": 0.61}
        ]


# =============================================================================
# LLM SIMULATOR CLASS
# =============================================================================

class LLMSimulator:
    """
    Simulate LLM timeout and error scenarios.

    Reference: Section 6 - "LLM timeout/error -> return needs_review flag"
    """

    @staticmethod
    @contextmanager
    def simulate_timeout(target_module: str = None, timeout_seconds: float = 0.1):
        """
        Context manager to simulate LLM timeout.

        Usage:
            with LLMSimulator.simulate_timeout():
                # Code should handle timeout gracefully
                pass

        Args:
            target_module: Module to patch. If None, auto-detects based on platform
            timeout_seconds: How long to wait before raising timeout
        """
        if target_module is None:
            target_module = get_inference_module()

        def slow_generate(*args, **kwargs):
            time.sleep(timeout_seconds)
            raise TimeoutError("LLM inference timed out")

        with patch(f'{target_module}.generate', side_effect=slow_generate):
            yield

    @staticmethod
    @contextmanager
    def simulate_error(target_module: str = None, error_type: type = RuntimeError, error_msg: str = "LLM inference failed"):
        """
        Context manager to simulate LLM error.

        Usage:
            with LLMSimulator.simulate_error():
                # Code should handle error gracefully
                pass

        Args:
            target_module: Module to patch. If None, auto-detects based on platform
            error_type: Type of exception to raise
            error_msg: Error message
        """
        if target_module is None:
            target_module = get_inference_module()

        with patch(f'{target_module}.generate', side_effect=error_type(error_msg)):
            yield

    @staticmethod
    def get_timeout_response() -> Dict:
        """Get expected response structure when LLM times out"""
        return {
            "analysis_id": "timeout-fallback",
            "predicted_labels": [],
            "confidence": 0.0,
            "confidence_source": "heuristic",
            "needs_review": True,
            "error": "LLM inference timed out",
            "cached": False
        }

    @staticmethod
    def get_error_response() -> Dict:
        """Get expected response structure when LLM errors"""
        return {
            "analysis_id": "error-fallback",
            "predicted_labels": [],
            "confidence": 0.0,
            "confidence_source": "heuristic",
            "needs_review": True,
            "error": "LLM inference failed",
            "cached": False
        }


def create_mock_device_response(
    platform: str = 'IOS-XE',
    version: str = '17.3.5',
    model: str = 'C9300-48P',
    features: Optional[List[str]] = None
) -> Dict:
    """
    Create a mock device response for SSH discovery tests.

    Args:
        platform: Device platform
        version: Software version
        model: Hardware model
        features: List of detected features

    Returns:
        Mock device discovery response
    """
    if features is None:
        features = ['MGMT_SSH_HTTP', 'SEC_CoPP', 'RTE_OSPF']

    return {
        'platform': platform,
        'version': version,
        'model': model,
        'features': features,
        'raw_output': f"""
Cisco IOS XE Software, Version {version}
Cisco IOS Software [Amsterdam], Catalyst L3 Switch Software
System image file is "flash:packages.conf"
"""
    }


class OutputComparator:
    """
    Compare outputs before/after refactoring.

    Reference: Section 9 - "Diff outputs on a PSIRT sample set:
    pre/post labels and confidence match within tolerance"

    This class provides detailed comparison beyond what fixtures offer.
    """

    def __init__(self, tolerance: float = 0.05):
        """
        Initialize comparator.

        Args:
            tolerance: Acceptable difference in confidence scores
        """
        self.tolerance = tolerance

    def compare_labels(self, expected: List[str], actual: List[str]) -> Dict:
        """
        Compare label sets.

        Returns:
            {
                'match': bool,
                'exact_match': bool,
                'missing': List[str],
                'extra': List[str],
                'jaccard': float
            }
        """
        expected_set = set(expected)
        actual_set = set(actual)

        intersection = expected_set & actual_set
        union = expected_set | actual_set

        return {
            'match': expected_set == actual_set,
            'exact_match': expected_set == actual_set,
            'missing': list(expected_set - actual_set),
            'extra': list(actual_set - expected_set),
            'jaccard': len(intersection) / len(union) if union else 1.0
        }

    def compare_confidence(self, expected: float, actual: float) -> Dict:
        """
        Compare confidence scores within tolerance.

        Returns:
            {
                'match': bool,
                'expected': float,
                'actual': float,
                'diff': float,
                'within_tolerance': bool
            }
        """
        diff = abs(expected - actual)
        return {
            'match': diff <= self.tolerance,
            'expected': expected,
            'actual': actual,
            'diff': diff,
            'within_tolerance': diff <= self.tolerance
        }

    def compare_results(self, baseline: Dict, current: Dict) -> Dict:
        """
        Full comparison of analysis results.

        Args:
            baseline: Expected/baseline result
            current: Current result to compare

        Returns:
            Detailed comparison report
        """
        label_comparison = self.compare_labels(
            baseline.get('predicted_labels', []),
            current.get('predicted_labels', [])
        )

        confidence_comparison = self.compare_confidence(
            baseline.get('confidence', 0.0),
            current.get('confidence', 0.0)
        )

        return {
            'labels': label_comparison,
            'confidence': confidence_comparison,
            'overall_match': label_comparison['match'] and confidence_comparison['match'],
            'baseline_source': baseline.get('source', 'unknown'),
            'current_source': current.get('source', 'unknown')
        }


# Utility to capture baseline results
def capture_baseline_results(
    output_file: str = 'tests/fixtures/baseline_results.json',
    corpus: Optional[Dict] = None
) -> Dict:
    """
    Capture current model outputs as baseline for comparison tests.

    Run this BEFORE refactoring:
        python -c "from tests.architecture.helpers import capture_baseline_results; capture_baseline_results()"

    Args:
        output_file: Where to save baseline results
        corpus: Optional PSIRT corpus (loads default if not provided)

    Returns:
        Dictionary of baseline results
    """
    from datetime import datetime

    try:
        from mlx_inference import MLXPSIRTLabeler
    except ImportError:
        print("ERROR: MLX not available - cannot capture baseline")
        return {}

    if corpus is None:
        corpus = load_psirt_corpus()

    labeler = MLXPSIRTLabeler()
    baseline = {}

    print(f"Capturing baseline for {len(corpus.get('psirts', []))} PSIRTs...")

    for psirt in corpus.get('psirts', []):
        print(f"  Processing {psirt['id']}...")
        result = labeler.predict_labels(
            psirt['summary'],
            psirt['platform'],
            mode='auto'
        )

        baseline[psirt['id']] = {
            'predicted_labels': result.get('predicted_labels', []),
            'confidence': result.get('confidence', 0.0),
            'source': 'llm',
            'captured_at': datetime.now().isoformat()
        }

    # Save
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        json.dump(baseline, f, indent=2)

    print(f"Baseline saved to {output_file}")
    return baseline
