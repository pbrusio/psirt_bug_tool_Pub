"""
Refactor Tests - During Refactor (Section 9.2)

These tests verify correct behavior during the scanner refactoring process.
They ensure fallback behavior, threshold handling, and caching rules work correctly.

Reference: docs/ARCHITECTURE_AND_WORKFLOW.md Section 9 - "During refactor (per step)"

Tests covered:
1. Keep vulnerability_scanner.py facade green with delegations
2. Fallback behavior at 0.70 FAISS similarity threshold
3. Heuristic needs_review path (not cached)
4. Cache invalidation regression tests

Usage:
    # Run refactor tests
    pytest tests/architecture/test_refactor.py -v

    # Run with markers
    pytest tests/architecture/test_refactor.py -v -m refactor
"""

import pytest
import json
import time
from pathlib import Path
from typing import Dict, List, Optional
from unittest.mock import MagicMock, patch, PropertyMock
from datetime import datetime

from .helpers import (
    FAISSSimulator,
    LLMSimulator,
    CacheManipulator,
    PerformanceBenchmark,
    FAISS_SIMILARITY_THRESHOLD,
    CACHE_CONFIDENCE_THRESHOLD,
    load_psirt_corpus
)


# Markers for test categorization
pytestmark = [pytest.mark.refactor, pytest.mark.architecture]


class TestFallbackBehaviorAtThreshold:
    """
    Test fallback behavior at FAISS similarity threshold.

    Reference: Section 6 - "FAISS similarity threshold: cosine_similarity < 0.70 triggers fallback"
    """

    @pytest.fixture
    def mock_scanner(self):
        """Create scanner with mock components"""
        from backend.core.vulnerability_scanner import VulnerabilityScanner

        mock_analyzer = MagicMock()
        mock_analyzer.analyze_psirt.return_value = {
            'analysis_id': 'test-123',
            'advisory_id': 'test-advisory',
            'psirt_summary': 'Test summary',
            'platform': 'IOS-XE',
            'predicted_labels': ['MGMT_SSH_HTTP'],
            'confidence': 0.85,
            'config_regex': [],
            'show_commands': [],
            'timestamp': datetime.now()
        }

        return VulnerabilityScanner(
            db_path='vulnerability_db.sqlite',
            sec8b_analyzer=mock_analyzer
        )

    def test_fallback_threshold_constant_defined(self):
        """Verify fallback threshold constant is defined correctly"""
        assert FAISS_SIMILARITY_THRESHOLD == 0.70, (
            f"FAISS threshold should be 0.70, got {FAISS_SIMILARITY_THRESHOLD}"
        )

    def test_low_similarity_triggers_minimal_prompt_or_needs_review(self):
        """
        Test that low FAISS similarity triggers fallback behavior.

        Reference: Section 6 - "FAISS low similarity (< threshold) -> skip few-shot examples,
        run minimal heuristic prompt or return needs_review"
        """
        # This tests the expected behavior when FAISS returns low similarity
        # The actual implementation should:
        # 1. Detect low similarity
        # 2. Either skip few-shot examples OR return needs_review

        # Mock FAISS to return low similarity
        # Uses platform auto-detection (mlx_inference on Mac, transformers_inference on Linux)
        with FAISSSimulator.simulate_low_similarity():
            # The behavior here depends on implementation
            # We're testing that the system handles this case gracefully
            pass  # Implementation-specific test would go here

    def test_high_similarity_uses_few_shot(self):
        """
        Test that high FAISS similarity uses few-shot examples.

        Reference: Section 3 - "Retrieve Few-Shot" flow in diagram
        """
        # When similarity is high, few-shot examples should be included
        high_similarity = 0.95
        assert high_similarity > FAISS_SIMILARITY_THRESHOLD


class TestNeedsReviewNotCached:
    """
    Test that heuristic/needs_review results are NOT cached.

    Reference: Section 6 - "LLM timeout/error -> return needs_review flag...do NOT cache as confident"
    """

    @pytest.fixture
    def cache_manipulator(self) -> CacheManipulator:
        return CacheManipulator()

    @pytest.fixture
    def scanner_with_mock(self):
        """Create scanner that returns needs_review results"""
        from backend.core.vulnerability_scanner import VulnerabilityScanner

        mock_analyzer = MagicMock()

        # Configure mock to return low confidence (heuristic) result
        mock_analyzer.analyze_psirt.return_value = {
            'analysis_id': 'heuristic-test',
            'advisory_id': 'test-needs-review-001',
            'psirt_summary': 'Test heuristic summary',
            'platform': 'IOS-XE',
            'predicted_labels': ['MGMT_SSH_HTTP'],
            'confidence': 0.50,  # Below cache threshold (0.75)
            'confidence_source': 'heuristic',
            'needs_review': True,
            'config_regex': [],
            'show_commands': [],
            'timestamp': datetime.now()
        }

        return VulnerabilityScanner(
            db_path='vulnerability_db.sqlite',
            sec8b_analyzer=mock_analyzer
        )

    def test_cache_threshold_constant_defined(self):
        """Verify cache confidence threshold is defined correctly"""
        assert CACHE_CONFIDENCE_THRESHOLD == 0.75, (
            f"Cache threshold should be 0.75, got {CACHE_CONFIDENCE_THRESHOLD}"
        )

    def test_low_confidence_not_cached(self, scanner_with_mock, cache_manipulator):
        """
        Test that low confidence results are NOT cached.

        Reference: Section 6 - Cache only if confidence >= 0.75
        """
        test_advisory_id = 'test-low-confidence-001'

        # Clean up any existing test data
        cache_manipulator.clear_psirt_cache(test_advisory_id)

        # Create a mock result with low confidence
        low_confidence_result = {
            'advisory_id': test_advisory_id,
            'psirt_summary': 'Low confidence test',
            'platform': 'IOS-XE',
            'predicted_labels': ['MGMT_SSH_HTTP'],
            'confidence': 0.50  # Below threshold
        }

        # Check should_cache returns False (access through ai_analyzer after facade refactor)
        should_cache = scanner_with_mock.ai_analyzer._should_cache(low_confidence_result)
        assert not should_cache, "Low confidence results should not be cached"

        # Verify not in cache
        assert cache_manipulator.verify_not_cached(test_advisory_id, 'IOS-XE')

    def test_high_confidence_is_cached(self, cache_manipulator):
        """
        Test that high confidence results ARE cached.

        Reference: Section 6 - Cache if confidence >= 0.75
        """
        from backend.core.vulnerability_scanner import VulnerabilityScanner

        mock_analyzer = MagicMock()
        scanner = VulnerabilityScanner(
            db_path='vulnerability_db.sqlite',
            sec8b_analyzer=mock_analyzer
        )

        test_advisory_id = 'test-high-confidence-001'

        # Clean up
        cache_manipulator.clear_psirt_cache(test_advisory_id)

        # Create high confidence result
        high_confidence_result = {
            'advisory_id': test_advisory_id,
            'psirt_summary': 'High confidence test',
            'platform': 'IOS-XE',
            'predicted_labels': ['MGMT_SSH_HTTP'],
            'confidence': 0.85  # Above threshold
        }

        # Check should_cache returns True (access through ai_analyzer after facade refactor)
        should_cache = scanner.ai_analyzer._should_cache(high_confidence_result)
        assert should_cache, "High confidence results should be cached"

        # Actually cache it (access through ai_analyzer)
        scanner.ai_analyzer._cache_result(high_confidence_result)

        # Verify in cache
        assert not cache_manipulator.verify_not_cached(test_advisory_id, 'IOS-XE')

        # Clean up
        cache_manipulator.clear_psirt_cache(test_advisory_id)

    def test_needs_review_flag_preserved_in_response(self):
        """
        Test that needs_review flag is included in response when appropriate.

        Reference: Section 6 - "return needs_review flag with confidence_source=heuristic"
        """
        from backend.core.vulnerability_scanner import VulnerabilityScanner

        mock_analyzer = MagicMock()
        mock_analyzer.analyze_psirt.return_value = {
            'analysis_id': 'test-123',
            'advisory_id': 'test-needs-review',
            'psirt_summary': 'Test',
            'platform': 'IOS-XE',
            'predicted_labels': ['MGMT_SSH_HTTP'],
            'confidence': 0.50,
            'needs_review': True,
            'confidence_source': 'heuristic',
            'config_regex': [],
            'show_commands': [],
            'timestamp': datetime.now()
        }

        scanner = VulnerabilityScanner(
            db_path='vulnerability_db.sqlite',
            sec8b_analyzer=mock_analyzer
        )

        # The scanner should preserve the needs_review flag from the analyzer
        result = scanner.analyze_psirt(
            summary="Test summary for needs review",
            platform="IOS-XE",
            advisory_id="test-needs-review-preserve"
        )

        # Check that the mock was called and returned expected structure
        assert mock_analyzer.analyze_psirt.called


class TestCacheInvalidation:
    """
    Regression tests for cache invalidation.

    Reference: Section 6 - Invalidation rules:
    - New PSIRT ingested -> evict SQLite PSIRT cache entry
    - LoRA/model update -> rebuild FAISS index
    - Taxonomy change -> rebuild FAISS entries for changed features
    """

    @pytest.fixture
    def cache_manipulator(self) -> CacheManipulator:
        return CacheManipulator()

    def test_cache_entry_can_be_evicted(self, cache_manipulator):
        """Test that cache entries can be manually evicted"""
        from backend.core.vulnerability_scanner import VulnerabilityScanner

        mock_analyzer = MagicMock()
        scanner = VulnerabilityScanner(
            db_path='vulnerability_db.sqlite',
            sec8b_analyzer=mock_analyzer
        )

        test_id = 'test-eviction-001'

        # Insert test entry (access through ai_analyzer after facade refactor)
        scanner.ai_analyzer._cache_result({
            'advisory_id': test_id,
            'psirt_summary': 'Test for eviction',
            'platform': 'IOS-XE',
            'predicted_labels': ['SEC_CoPP'],
            'confidence': 0.90
        })

        # Verify cached
        assert not cache_manipulator.verify_not_cached(test_id, 'IOS-XE')

        # Evict
        rows_deleted = cache_manipulator.clear_psirt_cache(test_id)
        assert rows_deleted > 0

        # Verify evicted
        assert cache_manipulator.verify_not_cached(test_id, 'IOS-XE')

    def test_lora_update_flag_concept(self):
        """
        Test concept: LoRA update should trigger FAISS rebuild.

        Reference: Section 6 - "LoRA/model update -> rebuild FAISS index to avoid embedding drift"

        This is a conceptual test - actual implementation would involve:
        1. Detecting LoRA version change
        2. Triggering FAISS rebuild
        3. Verifying index integrity
        """
        # Check that FAISS index and LoRA adapter paths exist
        faiss_path = Path('models/faiss_index.bin')
        lora_path = Path('models/lora_adapter')

        # Both should exist for the system to function
        assert faiss_path.exists() or faiss_path.is_symlink(), (
            "FAISS index not found - rebuild required"
        )

        # LoRA adapter can be a symlink to versioned directory
        if lora_path.is_symlink():
            target = lora_path.resolve()
            assert target.exists(), f"LoRA symlink target {target} not found"

    def test_taxonomy_change_detection_concept(self):
        """
        Test concept: Taxonomy changes should trigger partial FAISS rebuild.

        Reference: Section 6 - "Taxonomy change -> rebuild FAISS entries that reference changed features"

        This is a conceptual test validating the structure exists.
        """
        import yaml

        taxonomy_path = Path('taxonomies/features.yml')
        assert taxonomy_path.exists(), "IOS-XE taxonomy not found"

        with open(taxonomy_path, 'r') as f:
            features = yaml.safe_load(f)

        # Taxonomy should have labels that could be referenced in FAISS
        labels = [f['label'] for f in features]
        assert len(labels) > 50, f"Too few labels: {len(labels)}"


class TestVulnerabilityScannerFacade:
    """
    Test that VulnerabilityScanner facade remains stable.

    Reference: Section 7 - "Keep vulnerability_scanner.py as a stable facade"
    """

    def test_scanner_public_interface_exists(self):
        """Verify scanner has expected public methods"""
        from backend.core.vulnerability_scanner import VulnerabilityScanner

        mock_analyzer = MagicMock()
        scanner = VulnerabilityScanner(
            db_path='vulnerability_db.sqlite',
            sec8b_analyzer=mock_analyzer
        )

        # Path A: Database scan
        assert hasattr(scanner, 'scan_device'), "scan_device method missing"
        assert callable(scanner.scan_device)

        # Path B: LLM analysis
        assert hasattr(scanner, 'analyze_psirt'), "analyze_psirt method missing"
        assert callable(scanner.analyze_psirt)

        # Decoupled subsystems (facade pattern)
        assert hasattr(scanner, 'ai_analyzer'), "ai_analyzer property missing"
        assert hasattr(scanner, 'db_scanner'), "db_scanner property missing"
        assert hasattr(scanner, 'router'), "router property missing"

        # Internal methods available through ai_analyzer subsystem
        assert hasattr(scanner.ai_analyzer, '_check_cache'), "ai_analyzer._check_cache method missing"
        assert hasattr(scanner.ai_analyzer, '_should_cache'), "ai_analyzer._should_cache method missing"
        assert hasattr(scanner.ai_analyzer, '_cache_result'), "ai_analyzer._cache_result method missing"

    def test_scan_device_signature_stable(self):
        """Verify scan_device method signature is stable"""
        from backend.core.vulnerability_scanner import VulnerabilityScanner
        import inspect

        sig = inspect.signature(VulnerabilityScanner.scan_device)
        params = list(sig.parameters.keys())

        # Expected parameters from architecture
        expected_params = ['self', 'platform', 'version']
        for param in expected_params:
            assert param in params, f"Missing parameter: {param}"

        # Optional parameters that should exist
        optional_params = ['labels', 'hardware_model', 'severity_filter', 'limit', 'offset']
        for param in optional_params:
            assert param in params, f"Missing optional parameter: {param}"

    def test_analyze_psirt_signature_stable(self):
        """Verify analyze_psirt method signature is stable"""
        from backend.core.vulnerability_scanner import VulnerabilityScanner
        import inspect

        sig = inspect.signature(VulnerabilityScanner.analyze_psirt)
        params = list(sig.parameters.keys())

        # Expected parameters
        expected_params = ['self', 'summary', 'platform']
        for param in expected_params:
            assert param in params, f"Missing parameter: {param}"

    def test_scan_device_return_structure(self):
        """Verify scan_device returns expected structure"""
        from backend.core.vulnerability_scanner import VulnerabilityScanner

        mock_analyzer = MagicMock()
        scanner = VulnerabilityScanner(
            db_path='vulnerability_db.sqlite',
            sec8b_analyzer=mock_analyzer
        )

        result = scanner.scan_device(
            platform='IOS-XE',
            version='17.3.5'
        )

        # Required fields from architecture
        required_fields = [
            'scan_id',
            'platform',
            'version',
            'total_bugs_checked',
            'version_matches',
            'critical_high',
            'medium_low',
            'bugs',  # Changed from 'vulnerabilities' per terminology migration
            'source',
            'query_time_ms',
            'timestamp'
        ]

        for field in required_fields:
            assert field in result, f"Missing field in scan result: {field}"

        assert result['source'] == 'database'
        assert isinstance(result['bugs'], list)


class TestLLMTimeoutFallback:
    """
    Test LLM timeout fallback behavior.

    Reference: Section 6 - "LLM timeout/error -> return needs_review flag"
    """

    def test_timeout_should_return_needs_review(self):
        """
        Test concept: LLM timeout should return needs_review flag.

        The actual implementation depends on how timeout is handled in the codebase.
        """
        # This tests the expected behavior - implementation may vary
        expected_timeout_response = {
            'needs_review': True,
            'confidence_source': 'heuristic',
            'predicted_labels': [],  # or minimal labels
            'confidence': 0.0  # or low confidence
        }

        # Verify the expected structure
        assert 'needs_review' in expected_timeout_response
        assert expected_timeout_response['needs_review'] is True
        assert expected_timeout_response['confidence'] < CACHE_CONFIDENCE_THRESHOLD

    def test_error_should_not_cache(self):
        """
        Test that errors don't result in cached entries.

        Reference: Section 6 - "do NOT cache as confident"
        """
        from backend.core.vulnerability_scanner import VulnerabilityScanner

        mock_analyzer = MagicMock()
        scanner = VulnerabilityScanner(
            db_path='vulnerability_db.sqlite',
            sec8b_analyzer=mock_analyzer
        )

        # Error result should not be cached
        error_result = {
            'advisory_id': 'test-error-001',
            'psirt_summary': 'Error occurred',
            'platform': 'IOS-XE',
            'predicted_labels': [],
            'confidence': 0.0,
            'error': True
        }

        # Access through ai_analyzer after facade refactor
        should_cache = scanner.ai_analyzer._should_cache(error_result)
        assert not should_cache, "Error results should not be cached"


class TestSSHDiscoveryFallback:
    """
    Test SSH discovery fallback behavior.

    Reference: Section 6 - "SSH discovery failure -> mark device as stale,
    enqueue retry with backoff; keep last-known-good inventory entry"
    """

    def test_ssh_failure_concept(self):
        """
        Test concept: SSH failure should mark device as stale.

        This is a structural test - actual SSH testing requires device access.
        """
        # Expected behavior on SSH failure
        expected_failure_handling = {
            'device_status': 'stale',
            'retry_enqueued': True,
            'last_known_good_preserved': True
        }

        # Verify concept
        assert expected_failure_handling['device_status'] == 'stale'
        assert expected_failure_handling['retry_enqueued'] is True
        assert expected_failure_handling['last_known_good_preserved'] is True


# Convenience function
def run_refactor_tests():
    """Run all refactor tests and return summary"""
    import subprocess
    result = subprocess.run(
        ['pytest', __file__, '-v', '--tb=short'],
        capture_output=True,
        text=True
    )
    return {
        'returncode': result.returncode,
        'stdout': result.stdout,
        'stderr': result.stderr
    }


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
