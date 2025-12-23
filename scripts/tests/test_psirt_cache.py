#!/usr/bin/env python3
"""
Test PSIRT caching functionality

This script tests:
1. Cache miss (first analysis)
2. Cache hit (second analysis)
3. Persistence across restarts
"""

from backend.core.vulnerability_scanner import VulnerabilityScanner
from datetime import datetime
import json

def test_cache():
    """Test PSIRT cache functionality"""

    # Test data - simulate SEC-8B result
    test_advisory_id = 'cisco-sa-test-cache-001'
    test_platform = 'IOS-XE'

    # Clean up any existing test data
    import sqlite3
    db = sqlite3.connect('vulnerability_db.sqlite')
    cursor = db.cursor()
    cursor.execute('DELETE FROM vulnerabilities WHERE advisory_id = ?', (test_advisory_id,))
    db.commit()
    db.close()
    print(f"🧹 Cleaned up test data for {test_advisory_id}\n")

    # Create scanner with mock SEC-8B analyzer to avoid loading model
    class MockAnalyzer:
        pass

    scanner = VulnerabilityScanner(db_path='vulnerability_db.sqlite', sec8b_analyzer=MockAnalyzer())

    mock_result = {
        'analysis_id': 'test-123',
        'advisory_id': test_advisory_id,
        'psirt_summary': 'This is a test PSIRT for cache validation',
        'platform': test_platform,
        'predicted_labels': ['MGMT_SSH_HTTP', 'SEC_CoPP'],
        'confidence': 0.85,
        'config_regex': [r'ip ssh', r'control-plane'],
        'show_commands': ['show ip ssh', 'show control-plane'],
        'timestamp': datetime.now()
    }

    print("=" * 80)
    print("TEST 1: Cache Miss (First Analysis)")
    print("=" * 80)

    # Check cache (should be empty)
    cached = scanner._check_cache(test_advisory_id, test_platform)
    if cached:
        print("❌ FAIL: Cache should be empty but found entry")
        return False
    else:
        print("✅ PASS: Cache empty as expected")

    print("\n" + "=" * 80)
    print("TEST 2: Cache Insert (Storing Result)")
    print("=" * 80)

    # Cache the result
    scanner._cache_result(mock_result)
    print("✅ PASS: Result cached")

    print("\n" + "=" * 80)
    print("TEST 3: Cache Hit (Second Analysis)")
    print("=" * 80)

    # Check cache again (should find entry)
    cached = scanner._check_cache(test_advisory_id, test_platform)
    if not cached:
        print("❌ FAIL: Cache should contain entry but found nothing")
        return False

    print("✅ PASS: Cache hit successful")
    print(f"\nCached Result:")
    print(f"  Advisory ID: {cached['advisory_id']}")
    print(f"  Platform: {cached['platform']}")
    print(f"  Labels: {cached['predicted_labels']}")
    print(f"  Confidence: {cached['confidence']}")
    print(f"  Config Regex: {len(cached['config_regex'])} patterns")
    print(f"  Show Commands: {len(cached['show_commands'])} commands")

    # Verify data integrity
    if cached['advisory_id'] != test_advisory_id:
        print("❌ FAIL: Advisory ID mismatch")
        return False

    if cached['platform'] != test_platform:
        print("❌ FAIL: Platform mismatch")
        return False

    if set(cached['predicted_labels']) != set(mock_result['predicted_labels']):
        print("❌ FAIL: Labels mismatch")
        return False

    print("\n✅ PASS: Data integrity verified")

    print("\n" + "=" * 80)
    print("TEST 4: Platform Isolation")
    print("=" * 80)

    # Check cache for different platform (should be empty)
    cached_different = scanner._check_cache(test_advisory_id, 'IOS-XR')
    if cached_different:
        print("❌ FAIL: Cache should be platform-specific")
        return False
    else:
        print("✅ PASS: Platform isolation working (IOS-XR cache is separate)")

    print("\n" + "=" * 80)
    print("TEST 5: Database Persistence")
    print("=" * 80)

    # Create new scanner instance (simulates restart)
    scanner2 = VulnerabilityScanner(db_path='vulnerability_db.sqlite', sec8b_analyzer=MockAnalyzer())
    cached_after_restart = scanner2._check_cache(test_advisory_id, test_platform)

    if not cached_after_restart:
        print("❌ FAIL: Cache should persist across restarts")
        return False
    else:
        print("✅ PASS: Cache persists across restarts (SQLite file intact)")

    print("\n" + "=" * 80)
    print("ALL TESTS PASSED! ✅")
    print("=" * 80)

    print("\n📊 Database State:")
    import sqlite3
    db = sqlite3.connect('vulnerability_db.sqlite')
    cursor = db.cursor()

    cursor.execute('SELECT vuln_type, COUNT(*) FROM vulnerabilities GROUP BY vuln_type')
    for row in cursor.fetchall():
        print(f"  {row[0]:10s}: {row[1]:,}")

    db.close()

    print("\n🎉 PSIRT caching is fully functional!")
    print("\nTo test in the UI:")
    print("1. Start the server: cd backend && ./run_server.sh")
    print("2. Go to PSIRT Analysis tab")
    print("3. Analyze a PSIRT with advisory_id (e.g., cisco-sa-iosxe-webui-priv-esc-dUpB2rZ)")
    print("4. First time: ~3.4s (SEC-8B inference)")
    print("5. Second time: <10ms (database cache hit)")
    print("6. Restart server and try again: <10ms (cache persists!)")

    return True


if __name__ == '__main__':
    success = test_cache()
    exit(0 if success else 1)
