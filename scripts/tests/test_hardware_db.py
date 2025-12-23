#!/usr/bin/env python3
"""
Test Hardware Filtering at Database Level

Direct database queries to verify hardware filtering works correctly.
No LLM dependencies required.
"""

import sqlite3
import json


def test_hardware_db():
    """Test hardware filtering directly in database"""

    print("=" * 70)
    print("HARDWARE FILTERING DATABASE TEST")
    print("=" * 70)
    print()

    # Connect to database
    db = sqlite3.connect('vulnerability_db.sqlite')
    db.row_factory = sqlite3.Row
    cursor = db.cursor()

    # Get overall stats
    print("DATABASE STATISTICS:")
    print("-" * 70)

    cursor.execute("SELECT COUNT(*) FROM vulnerabilities WHERE vuln_type = 'bug'")
    total_bugs = cursor.fetchone()[0]
    print(f"  Total bugs in database: {total_bugs:,}")

    cursor.execute("SELECT COUNT(*) FROM vulnerabilities WHERE vuln_type = 'bug' AND hardware_model IS NOT NULL")
    hw_bugs = cursor.fetchone()[0]
    print(f"  Hardware-specific bugs: {hw_bugs:,} ({hw_bugs/total_bugs*100:.1f}%)")

    cursor.execute("SELECT COUNT(*) FROM vulnerabilities WHERE vuln_type = 'bug' AND hardware_model IS NULL")
    generic_bugs = cursor.fetchone()[0]
    print(f"  Generic bugs (NULL):    {generic_bugs:,} ({generic_bugs/total_bugs*100:.1f}%)")
    print()

    # Hardware distribution
    print("HARDWARE DISTRIBUTION (Top 10):")
    print("-" * 70)
    cursor.execute("""
        SELECT hardware_model, COUNT(*) as cnt
        FROM vulnerabilities
        WHERE vuln_type = 'bug' AND hardware_model IS NOT NULL
        GROUP BY hardware_model
        ORDER BY cnt DESC
        LIMIT 10
    """)
    for row in cursor.fetchall():
        print(f"  {row['hardware_model']:20s}: {row['cnt']:,} bugs")
    print()

    # Test Case: IOS-XE 17.10.1
    platform = 'IOS-XE'
    version = '17.10.1'

    print(f"TEST CASE: {platform} {version}")
    print("=" * 70)
    print()

    # Test 1: All bugs for platform/version (no hardware filter)
    print("TEST 1: Scan without hardware filter")
    print("-" * 70)

    cursor.execute("""
        SELECT bug_id, headline, hardware_model
        FROM vulnerabilities
        WHERE platform = ?
          AND vuln_type = 'bug'
          AND affected_versions_raw LIKE ?
    """, (platform, f'%{version}%'))

    all_matches = cursor.fetchall()
    print(f"  Version matches: {len(all_matches)}")

    # Count by hardware
    hw_breakdown = {}
    for bug in all_matches:
        hw = bug['hardware_model'] or 'Generic'
        hw_breakdown[hw] = hw_breakdown.get(hw, 0) + 1

    print(f"  Breakdown:")
    for hw, count in sorted(hw_breakdown.items(), key=lambda x: x[1], reverse=True):
        print(f"    {hw:20s}: {count} bugs")
    print()

    # Test 2: Scan with Cat9200 hardware filter
    print("TEST 2: Scan WITH Cat9200 hardware filter")
    print("-" * 70)

    cursor.execute("""
        SELECT bug_id, headline, hardware_model
        FROM vulnerabilities
        WHERE platform = ?
          AND vuln_type = 'bug'
          AND affected_versions_raw LIKE ?
          AND (hardware_model IS NULL OR hardware_model = ?)
    """, (platform, f'%{version}%', 'Cat9200'))

    cat9200_matches = cursor.fetchall()
    print(f"  Version matches: {len(cat9200_matches)}")

    # Count by hardware
    hw_breakdown_cat9200 = {}
    for bug in cat9200_matches:
        hw = bug['hardware_model'] or 'Generic'
        hw_breakdown_cat9200[hw] = hw_breakdown_cat9200.get(hw, 0) + 1

    print(f"  Breakdown:")
    for hw, count in sorted(hw_breakdown_cat9200.items(), key=lambda x: x[1], reverse=True):
        print(f"    {hw:20s}: {count} bugs")

    # Calculate reduction
    filtered_out = len(all_matches) - len(cat9200_matches)
    reduction_pct = (filtered_out / len(all_matches) * 100) if len(all_matches) > 0 else 0

    print()
    print(f"  Filtered out: {filtered_out} bugs ({reduction_pct:.1f}%)")
    print()

    if filtered_out > 0:
        print(f"  ✅ SUCCESS: Hardware filtering working!")
        print(f"     Filtered out {filtered_out} hardware-specific bugs")
    else:
        print(f"  ℹ️  Note: All bugs for this version are generic (hardware_model = NULL)")
        print(f"     This means no hardware-specific bugs match this version")
    print()

    # Test 3: Compare Cat9200 vs Cat9300
    print("TEST 3: Compare Cat9200 vs Cat9300")
    print("-" * 70)

    cursor.execute("""
        SELECT bug_id, headline, hardware_model
        FROM vulnerabilities
        WHERE platform = ?
          AND vuln_type = 'bug'
          AND affected_versions_raw LIKE ?
          AND (hardware_model IS NULL OR hardware_model = ?)
    """, (platform, f'%{version}%', 'Cat9300'))

    cat9300_matches = cursor.fetchall()

    print(f"  Cat9200 matches: {len(cat9200_matches)}")
    print(f"  Cat9300 matches: {len(cat9300_matches)}")

    # Check if there are hardware-specific differences
    cat9200_only = [b['bug_id'] for b in cat9200_matches if b['hardware_model'] == 'Cat9200']
    cat9300_only = [b['bug_id'] for b in cat9300_matches if b['hardware_model'] == 'Cat9300']

    print(f"  Cat9200-specific bugs: {len(cat9200_only)}")
    print(f"  Cat9300-specific bugs: {len(cat9300_only)}")

    if cat9200_only or cat9300_only:
        print(f"  ✅ SUCCESS: Different hardware models show different bugs!")
    else:
        print(f"  ℹ️  Note: No hardware-specific bugs for this version")
    print()

    # Show example hardware-specific bugs if any
    if hw_bugs > 0:
        print("EXAMPLE HARDWARE-SPECIFIC BUGS:")
        print("-" * 70)

        cursor.execute("""
            SELECT bug_id, headline, hardware_model, platform
            FROM vulnerabilities
            WHERE vuln_type = 'bug'
              AND hardware_model IS NOT NULL
            LIMIT 10
        """)

        for i, bug in enumerate(cursor.fetchall(), 1):
            headline_short = bug['headline'][:60] if bug['headline'] else 'No headline'
            print(f"  {i}. {bug['bug_id']} ({bug['hardware_model']})")
            print(f"     {headline_short}...")
        print()

    db.close()

    print("=" * 70)
    print("TEST COMPLETE ✅")
    print("=" * 70)


if __name__ == '__main__':
    try:
        test_hardware_db()
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
