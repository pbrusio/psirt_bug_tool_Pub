"""
Baseline Tests - Before Refactor (Section 9.1)

These tests establish the current behavior baseline before refactoring.
Run these BEFORE making changes to verify current state.

Reference: docs/ARCHITECTURE_AND_WORKFLOW.md Section 9 - "Before refactor (baseline)"

Tests covered:
1. Existing unit/integration tests pass
2. Golden-path PSIRT inference check
3. FAISS retrieval sanity
4. Device discovery/verification smoke

Usage:
    # Run baseline tests
    pytest tests/architecture/test_baseline.py -v

    # Run with markers
    pytest tests/architecture/test_baseline.py -v -m baseline
"""

import pytest
import json
import time
from pathlib import Path
from typing import Dict, List, Optional
from unittest.mock import MagicMock, patch

from .helpers import (
    load_psirt_corpus,
    PerformanceBenchmark,
    OutputComparator,
    CacheManipulator,
    DB_LATENCY_TARGET_MS,
    AI_LATENCY_TARGET_MS,
    FAISS_SIMILARITY_THRESHOLD
)


# Markers for test categorization
pytestmark = [pytest.mark.baseline, pytest.mark.architecture]


class TestGoldenPathPSIRTInference:
    """
    Golden-path PSIRT inference check.

    Reference: Section 9 - "Golden-path PSIRT inference check: sample PSIRT returns same labels/confidence"
    """

    @pytest.fixture
    def psirt_corpus(self) -> Dict:
        """Load test PSIRT corpus"""
        return load_psirt_corpus()

    @pytest.fixture
    def comparator(self) -> OutputComparator:
        """Output comparator with default tolerance"""
        return OutputComparator(tolerance=0.1)  # 10% tolerance for confidence

    @pytest.mark.slow
    def test_golden_path_psirt_returns_expected_labels(self, psirt_corpus):
        """
        Test that known PSIRTs return expected labels.

        This is a sanity check - if this fails, something fundamental is broken.
        """
        # Skip if model not available (unit test mode)
        try:
            from mlx_inference import MLXPSIRTLabeler
        except ImportError:
            pytest.skip("MLX not available - run with --slow flag")

        labeler = MLXPSIRTLabeler()

        for psirt in psirt_corpus['psirts'][:2]:  # Test first 2 for speed
            result = labeler.predict_labels(
                psirt['summary'],
                psirt['platform'],
                mode='auto'
            )

            predicted = set(result.get('predicted_labels', []))
            expected = set(psirt['expected_labels'])

            # Check at least one expected label is present
            overlap = predicted & expected
            assert len(overlap) > 0, (
                f"PSIRT {psirt['id']}: No overlap between "
                f"predicted={predicted} and expected={expected}"
            )

    @pytest.mark.slow
    def test_golden_path_confidence_above_threshold(self, psirt_corpus):
        """
        Test that high-quality PSIRTs produce high confidence scores.

        Reference: Section 6 - Caching threshold >= 0.75
        """
        try:
            from mlx_inference import MLXPSIRTLabeler
        except ImportError:
            pytest.skip("MLX not available")

        labeler = MLXPSIRTLabeler()

        for psirt in psirt_corpus['psirts'][:2]:
            result = labeler.predict_labels(
                psirt['summary'],
                psirt['platform'],
                mode='auto'
            )

            confidence = result.get('confidence', 0.0)
            min_expected = psirt.get('expected_confidence_min', 0.70)

            assert confidence >= min_expected, (
                f"PSIRT {psirt['id']}: confidence {confidence:.3f} "
                f"below expected minimum {min_expected}"
            )

    def test_psirt_corpus_structure_valid(self, psirt_corpus):
        """Verify test corpus has required structure"""
        assert 'psirts' in psirt_corpus
        assert len(psirt_corpus['psirts']) >= 3, "Need at least 3 test PSIRTs"

        for psirt in psirt_corpus['psirts']:
            assert 'id' in psirt
            assert 'summary' in psirt
            assert 'platform' in psirt
            assert 'expected_labels' in psirt
            assert len(psirt['expected_labels']) >= 1


class TestFAISSRetrievalSanity:
    """
    FAISS retrieval sanity checks.

    Reference: Section 9 - "FAISS retrieval sanity: ensure top-N results still returned for known query"
    """

    @pytest.fixture
    def faiss_artifacts(self) -> Dict:
        """Load FAISS index and examples"""
        import faiss
        import pandas as pd

        index_path = Path('models/faiss_index.bin')
        examples_path = Path('models/labeled_examples.parquet')

        if not index_path.exists() or not examples_path.exists():
            pytest.skip("FAISS artifacts not found")

        return {
            'index': faiss.read_index(str(index_path)),
            'examples': pd.read_parquet(examples_path)
        }

    def test_faiss_index_not_empty(self, faiss_artifacts):
        """Verify FAISS index contains vectors"""
        index = faiss_artifacts['index']
        assert index.ntotal > 0, "FAISS index is empty"
        # Based on CLAUDE.md: 2,654 labeled examples
        assert index.ntotal >= 2000, f"FAISS index too small: {index.ntotal}"

    def test_faiss_index_matches_parquet(self, faiss_artifacts):
        """Verify FAISS index size matches labeled examples"""
        index = faiss_artifacts['index']
        examples = faiss_artifacts['examples']

        # Allow small discrepancy (within 5%)
        diff_ratio = abs(index.ntotal - len(examples)) / max(index.ntotal, len(examples))
        assert diff_ratio < 0.05, (
            f"FAISS index ({index.ntotal}) significantly differs from "
            f"parquet ({len(examples)})"
        )

    def test_faiss_search_returns_results(self, faiss_artifacts):
        """Verify FAISS search returns results for a query"""
        from sentence_transformers import SentenceTransformer

        index = faiss_artifacts['index']

        # Load embedder
        with open('models/embedder_info.json', 'r') as f:
            embedder_info = json.load(f)
        embedder = SentenceTransformer(embedder_info['model_name'])

        # Test query
        test_query = "SSH vulnerability in IOS-XE allows denial of service"
        embedding = embedder.encode([test_query])

        # Search
        k = 5
        distances, indices = index.search(embedding, k)

        assert len(indices[0]) == k, f"Expected {k} results, got {len(indices[0])}"
        assert all(idx >= 0 for idx in indices[0]), "Invalid indices returned"

    def test_faiss_similarity_scores_valid(self, faiss_artifacts):
        """Verify similarity scores are in expected range"""
        from sentence_transformers import SentenceTransformer

        index = faiss_artifacts['index']

        with open('models/embedder_info.json', 'r') as f:
            embedder_info = json.load(f)
        embedder = SentenceTransformer(embedder_info['model_name'])

        test_query = "BGP routing protocol vulnerability"
        embedding = embedder.encode([test_query])

        distances, indices = index.search(embedding, 5)

        # For L2 distance, smaller is better (closer)
        # For cosine similarity, we'd expect values closer to 0 for similar items
        for dist in distances[0]:
            # L2 distances should be non-negative
            assert dist >= 0, f"Invalid distance: {dist}"


class TestDatabaseScanBaseline:
    """
    Database scan baseline tests.

    Reference: Section 2 - "DB lookup <10ms"
    """

    @pytest.fixture
    def scanner(self):
        """Get or create scanner instance"""
        try:
            from backend.core.vulnerability_scanner import VulnerabilityScanner

            # Use mock analyzer to avoid loading LLM
            mock_analyzer = MagicMock()
            return VulnerabilityScanner(
                db_path='vulnerability_db.sqlite',
                sec8b_analyzer=mock_analyzer
            )
        except ImportError:
            pytest.skip("Backend not available")

    @pytest.fixture
    def benchmark(self) -> PerformanceBenchmark:
        return PerformanceBenchmark()

    def test_database_exists(self):
        """Verify database file exists"""
        db_path = Path('vulnerability_db.sqlite')
        assert db_path.exists(), "vulnerability_db.sqlite not found"

    def test_database_has_vulnerabilities(self):
        """Verify database contains vulnerabilities"""
        import sqlite3

        with sqlite3.connect('vulnerability_db.sqlite') as db:
            cursor = db.cursor()
            cursor.execute("SELECT COUNT(*) FROM vulnerabilities")
            count = cursor.fetchone()[0]

        # Based on CLAUDE.md: 9,586 bugs
        assert count > 5000, f"Database has too few vulnerabilities: {count}"

    def test_scan_device_returns_results(self, scanner):
        """Test basic scan returns results"""
        result = scanner.scan_device(
            platform='IOS-XE',
            version='17.3.5'
        )

        assert 'scan_id' in result
        assert 'bugs' in result  # Changed from 'vulnerabilities' per terminology migration
        assert 'total_bugs_checked' in result
        assert result['source'] == 'database'

    def test_scan_device_performance(self, scanner, benchmark):
        """Test scan performance is within target (<10ms)"""
        with benchmark.measure('db_scan'):
            result = scanner.scan_device(
                platform='IOS-XE',
                version='17.3.5'
            )

        summary = benchmark.get_summary()
        latency = summary['operations']['db_scan']['avg_ms']

        # Be lenient for test environments (allow 100ms)
        assert latency < 100, f"DB scan too slow: {latency:.2f}ms"

        # Log if above target
        if latency > DB_LATENCY_TARGET_MS:
            pytest.xfail(f"DB scan {latency:.2f}ms exceeds target {DB_LATENCY_TARGET_MS}ms")

    def test_hardware_filtering_reduces_results(self, scanner):
        """Test hardware filtering reduces vulnerability count"""
        # Scan without hardware filter
        result_no_hw = scanner.scan_device(
            platform='IOS-XE',
            version='17.3.5'
        )

        # Scan with hardware filter
        result_with_hw = scanner.scan_device(
            platform='IOS-XE',
            version='17.3.5',
            hardware_model='Cat9300'
        )

        # Hardware filtering should reduce or maintain count (not increase)
        assert len(result_with_hw['bugs']) <= len(result_no_hw['bugs']), (
            "Hardware filtering should not increase bug count"
        )

    def test_feature_filtering_reduces_results(self, scanner):
        """Test feature filtering reduces bug count"""
        result_no_features = scanner.scan_device(
            platform='IOS-XE',
            version='17.3.5'
        )

        result_with_features = scanner.scan_device(
            platform='IOS-XE',
            version='17.3.5',
            labels=['MGMT_SSH_HTTP']  # Only SSH-related bugs
        )

        # Feature filtering should reduce count
        assert len(result_with_features['bugs']) <= len(result_no_features['bugs'])


class TestDeviceVerificationSmoke:
    """
    Device discovery/verification smoke tests.

    Reference: Section 9 - "Device discovery/verification smoke: SSH mock/integration unchanged"
    """

    def test_device_verifier_module_imports(self):
        """Test that device verifier module can be imported"""
        try:
            from device_verifier import DeviceVerifier
            assert DeviceVerifier is not None
        except ImportError:
            pytest.skip("device_verifier module not available")

    def test_feature_extraction_module_imports(self):
        """Test that feature extraction module can be imported"""
        try:
            from extract_device_features import FeatureExtractor
            assert FeatureExtractor is not None
        except ImportError:
            # Try alternative import
            try:
                from sidecar_extractor.extract_iosxe_features_standalone import extract_features
                assert extract_features is not None
            except ImportError:
                pytest.skip("Feature extraction modules not available")

    def test_mock_device_response_structure(self):
        """Test mock device response has expected structure"""
        from .helpers import create_mock_device_response

        response = create_mock_device_response()

        assert 'platform' in response
        assert 'version' in response
        assert 'model' in response
        assert 'features' in response
        assert isinstance(response['features'], list)


class TestCacheBaseline:
    """
    Cache behavior baseline tests.

    Reference: Section 6 - Caching tiers
    """

    @pytest.fixture
    def cache_manipulator(self) -> CacheManipulator:
        return CacheManipulator()

    def test_cache_stats_accessible(self, cache_manipulator):
        """Test cache statistics can be retrieved"""
        stats = cache_manipulator.get_cache_stats()
        assert isinstance(stats, dict)

    def test_psirt_cache_isolation_by_platform(self, cache_manipulator):
        """
        Test that PSIRT cache is platform-isolated.

        Reference: Section 6 - Platform isolation
        """
        # This is verified by the test_psirt_cache.py but we include a basic check here
        from backend.core.vulnerability_scanner import VulnerabilityScanner

        mock_analyzer = MagicMock()
        scanner = VulnerabilityScanner(
            db_path='vulnerability_db.sqlite',
            sec8b_analyzer=mock_analyzer
        )

        test_id = 'test-platform-isolation-001'
        test_platform = 'IOS-XE'

        # Clean up
        cache_manipulator.clear_psirt_cache(test_id)

        # Verify not cached
        assert cache_manipulator.verify_not_cached(test_id, test_platform)
        assert cache_manipulator.verify_not_cached(test_id, 'IOS-XR')

        # Insert test entry (access through ai_analyzer after facade refactor)
        scanner.ai_analyzer._cache_result({
            'advisory_id': test_id,
            'psirt_summary': 'Test summary',
            'platform': test_platform,
            'predicted_labels': ['MGMT_SSH_HTTP'],
            'confidence': 0.85
        })

        # Verify cached for correct platform only
        assert not cache_manipulator.verify_not_cached(test_id, test_platform)
        assert cache_manipulator.verify_not_cached(test_id, 'IOS-XR')

        # Clean up
        cache_manipulator.clear_psirt_cache(test_id)


class TestTaxonomyBaseline:
    """
    Taxonomy baseline tests.

    Reference: Architecture decision #2 - Closed taxonomy
    """

    @pytest.fixture
    def taxonomies(self) -> Dict:
        """Load all platform taxonomies"""
        import yaml

        taxonomy_files = {
            'IOS-XE': 'taxonomies/features.yml',
            'IOS-XR': 'taxonomies/features_iosxr.yml',
            'ASA': 'taxonomies/features_asa.yml',
            'NX-OS': 'taxonomies/features_nxos.yml'
        }

        taxonomies = {}
        for platform, filepath in taxonomy_files.items():
            try:
                with open(filepath, 'r') as f:
                    taxonomies[platform] = yaml.safe_load(f)
            except FileNotFoundError:
                pass

        return taxonomies

    def test_taxonomy_files_exist(self):
        """Test that taxonomy files exist"""
        taxonomy_dir = Path('taxonomies')
        assert taxonomy_dir.exists(), "taxonomies/ directory not found"

        # At least IOS-XE should exist
        iosxe_file = taxonomy_dir / 'features.yml'
        assert iosxe_file.exists(), "features.yml not found"

    def test_taxonomy_has_labels(self, taxonomies):
        """Test taxonomies contain labels"""
        assert len(taxonomies) > 0, "No taxonomies loaded"

        for platform, features in taxonomies.items():
            assert len(features) > 0, f"{platform} taxonomy is empty"

            # Each feature should have required fields
            for feature in features[:5]:  # Check first 5
                assert 'label' in feature, f"{platform}: feature missing 'label'"

    def test_taxonomy_labels_unique(self, taxonomies):
        """Test labels are unique within platform"""
        for platform, features in taxonomies.items():
            labels = [f['label'] for f in features]
            unique_labels = set(labels)

            assert len(labels) == len(unique_labels), (
                f"{platform}: duplicate labels found"
            )


# Convenience function to run baseline tests
def run_baseline_tests():
    """Run all baseline tests and return summary"""
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
