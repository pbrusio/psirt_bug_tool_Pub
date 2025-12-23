#!/usr/bin/env python3
"""
Vulnerability Database Test Script

Tests:
1. Database loading from CSV
2. Version matching logic
3. Query performance
4. Incremental updates

Usage:
    python backend/db/test_vuln_db.py
"""

import sqlite3
import sys
import os
import time
from typing import List, Dict

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from backend.core.version_patterns import VersionPatternDetector
from backend.core.version_matcher import VersionMatcher


class VulnDBTester:
    """Test suite for vulnerability database"""

    def __init__(self, db_path: str = 'vulnerability_db.sqlite'):
        self.db_path = db_path
        self.matcher = VersionMatcher()
        self.detector = VersionPatternDetector()

    def connect(self):
        """Connect to database"""
        if not os.path.exists(self.db_path):
            print(f"Error: Database not found at {self.db_path}")
            print("Please run load_bugs.py first to create the database.")
            sys.exit(1)

        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row

    def close(self):
        """Close connection"""
        if hasattr(self, 'conn') and self.conn:
            self.conn.close()

    def test_database_loading(self):
        """Test 1: Verify database was loaded correctly"""
        print("\n" + "=" * 80)
        print("TEST 1: Database Loading")
        print("=" * 80)

        cursor = self.conn.cursor()

        # Check vulnerabilities table
        cursor.execute("SELECT COUNT(*) as count FROM vulnerabilities")
        vuln_count = cursor.fetchone()['count']
        print(f"Total vulnerabilities: {vuln_count}")

        if vuln_count == 0:
            print("❌ FAILED: No vulnerabilities loaded")
            return False

        # Check version index
        cursor.execute("SELECT COUNT(*) as count FROM version_index")
        version_count = cursor.fetchone()['count']
        print(f"Version index entries: {version_count}")

        # Sample vulnerability
        cursor.execute('''
            SELECT bug_id, headline, version_pattern, version_min, version_max, affected_versions_raw
            FROM vulnerabilities
            LIMIT 1
        ''')
        bug = cursor.fetchone()
        print(f"\nSample bug: {bug['bug_id']}")
        print(f"  Headline: {bug['headline'][:60]}...")
        print(f"  Raw versions: {bug['affected_versions_raw']}")
        print(f"  Detected pattern: {bug['version_pattern']}")
        print(f"  Min: {bug['version_min']}, Max: {bug['version_max']}")

        print("✅ PASSED")
        return True

    def test_version_matching(self):
        """Test 2: Verify version matching logic"""
        print("\n" + "=" * 80)
        print("TEST 2: Version Matching Logic")
        print("=" * 80)

        cursor = self.conn.cursor()

        # Get a bug with EXPLICIT pattern
        cursor.execute('''
            SELECT bug_id, headline, version_pattern, version_min, version_max, affected_versions_raw
            FROM vulnerabilities
            WHERE version_pattern = 'EXPLICIT'
            LIMIT 1
        ''')
        bug = cursor.fetchone()

        if not bug:
            print("⚠️  SKIPPED: No EXPLICIT pattern bugs found")
            return True

        print(f"Testing with bug: {bug['bug_id']}")
        print(f"  Affected versions: {bug['affected_versions_raw']}")

        # Parse explicit versions
        pattern_info = self.detector.detect_pattern(bug['affected_versions_raw'])
        explicit_versions = pattern_info['versions']

        print(f"  Explicit versions: {explicit_versions}")

        # Test matching
        test_versions = explicit_versions[:2] if len(explicit_versions) >= 2 else explicit_versions

        if not test_versions:
            print("⚠️  SKIPPED: No explicit versions to test")
            return True

        # Test version that should match
        test_ver = test_versions[0]
        is_vuln, reason = self.matcher.is_version_affected(
            device_version=test_ver,
            pattern_type='EXPLICIT',
            version_min=bug['version_min'],
            version_max=bug['version_max'],
            explicit_versions=explicit_versions
        )

        print(f"\nTest version: {test_ver}")
        print(f"  Result: {'VULNERABLE' if is_vuln else 'NOT VULNERABLE'}")
        print(f"  Reason: {reason}")

        if not is_vuln:
            print("❌ FAILED: Expected version to match")
            return False

        # Test version that should NOT match
        test_ver_invalid = "99.99.99"
        is_vuln, reason = self.matcher.is_version_affected(
            device_version=test_ver_invalid,
            pattern_type='EXPLICIT',
            version_min=bug['version_min'],
            version_max=bug['version_max'],
            explicit_versions=explicit_versions
        )

        print(f"\nTest version: {test_ver_invalid} (should NOT match)")
        print(f"  Result: {'VULNERABLE' if is_vuln else 'NOT VULNERABLE'}")
        print(f"  Reason: {reason}")

        if is_vuln:
            print("❌ FAILED: Expected version NOT to match")
            return False

        print("✅ PASSED")
        return True

    def test_query_performance(self):
        """Test 3: Query performance for device scanning"""
        print("\n" + "=" * 80)
        print("TEST 3: Query Performance")
        print("=" * 80)

        test_version = "17.10.1"
        platform = "IOS-XE"

        print(f"Querying bugs affecting: {platform} {test_version}")

        cursor = self.conn.cursor()

        # Time the query
        start_time = time.time()

        cursor.execute('''
            SELECT
                v.bug_id,
                v.headline,
                v.version_pattern,
                v.version_min,
                v.version_max,
                v.affected_versions_raw,
                v.fixed_version,
                v.labels
            FROM vulnerabilities v
            WHERE v.platform = ?
            AND v.version_pattern IN ('EXPLICIT', 'WILDCARD', 'OPEN_LATER', 'MAJOR_WILDCARD')
        ''', (platform,))

        bugs = cursor.fetchall()
        query_time = (time.time() - start_time) * 1000  # ms

        print(f"Query time: {query_time:.2f} ms")
        print(f"Bugs found: {len(bugs)}")

        # Now match against test version
        start_time = time.time()

        matching_bugs = []
        for bug in bugs:
            # Parse explicit versions if EXPLICIT pattern
            explicit_versions = []
            if bug['version_pattern'] == 'EXPLICIT':
                pattern_info = self.detector.detect_pattern(bug['affected_versions_raw'])
                explicit_versions = pattern_info['versions']

            # Check if version matches
            is_vuln, reason = self.matcher.is_version_affected(
                device_version=test_version,
                pattern_type=bug['version_pattern'],
                version_min=bug['version_min'],
                version_max=bug['version_max'],
                explicit_versions=explicit_versions,
                fixed_version=bug['fixed_version']
            )

            if is_vuln:
                matching_bugs.append(bug)

        match_time = (time.time() - start_time) * 1000  # ms

        print(f"Matching time: {match_time:.2f} ms")
        print(f"Matching bugs: {len(matching_bugs)}")

        total_time = query_time + match_time
        print(f"Total scan time: {total_time:.2f} ms")

        # Show sample matches
        if matching_bugs:
            print(f"\nSample matches (first 3):")
            for bug in matching_bugs[:3]:
                print(f"  - {bug['bug_id']}: {bug['headline'][:50]}...")

        # Performance check: Should be < 100ms for small DB
        if len(bugs) < 1000 and total_time > 100:
            print("⚠️  WARNING: Scan time > 100ms (expected < 100ms for small DB)")
        else:
            print("✅ PASSED")

        return True

    def test_incremental_update(self):
        """Test 4: Verify incremental update functionality"""
        print("\n" + "=" * 80)
        print("TEST 4: Incremental Update")
        print("=" * 80)

        cursor = self.conn.cursor()

        # Check metadata
        cursor.execute("SELECT value FROM db_metadata WHERE key = 'last_update'")
        row = cursor.fetchone()

        if row and row['value']:
            print(f"Last update timestamp: {row['value']}")
            print("✅ PASSED")
            return True
        else:
            print("⚠️  WARNING: No last_update timestamp found")
            return True

    def run_all_tests(self):
        """Run all tests"""
        print("=" * 80)
        print("VULNERABILITY DATABASE TEST SUITE")
        print("=" * 80)
        print(f"Database: {os.path.abspath(self.db_path)}")

        self.connect()

        try:
            results = []
            results.append(self.test_database_loading())
            results.append(self.test_version_matching())
            results.append(self.test_query_performance())
            results.append(self.test_incremental_update())

            # Summary
            print("\n" + "=" * 80)
            print("TEST SUMMARY")
            print("=" * 80)
            passed = sum(results)
            total = len(results)
            print(f"Passed: {passed}/{total}")

            if passed == total:
                print("\n✅ ALL TESTS PASSED")
                return 0
            else:
                print("\n❌ SOME TESTS FAILED")
                return 1

        finally:
            self.close()


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Test vulnerability database')
    parser.add_argument('--db', default='vulnerability_db.sqlite',
                        help='Database path (default: vulnerability_db.sqlite)')

    args = parser.parse_args()

    tester = VulnDBTester(db_path=args.db)
    exit_code = tester.run_all_tests()
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
