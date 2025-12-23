#!/usr/bin/env python3
"""
Test Hardware Filtering Functionality

Tests the complete hardware filtering pipeline:
1. Database has hardware_model column populated
2. Scanner filters bugs correctly by hardware
3. Measure false positive reduction
"""

import sys
from backend.core.vulnerability_scanner import VulnerabilityScanner

def test_hardware_filtering():
    """Test hardware filtering with Cat9200 vs no hardware"""

    print("=" * 70)
    print("HARDWARE FILTERING TEST")
    print("=" * 70)
    print()

    # Initialize scanner
    scanner = VulnerabilityScanner(db_path='vulnerability_db.sqlite')

    # Test case: IOS-XE 17.10.1 (known to have bugs)
    platform = 'IOS-XE'
    version = '17.10.1'

    print(f"Test Device: {platform} {version}")
    print()

    # Test 1: Scan WITHOUT hardware filter (baseline)
    print("=" * 70)
    print("TEST 1: Scan WITHOUT hardware filter (baseline)")
    print("=" * 70)

    result_no_hw = scanner.scan_device(
        platform=platform,
        version=version,
        hardware_model=None
    )

    print(f"  Total bugs checked:     {result_no_hw['total_bugs_checked']:,}")
    print(f"  Version matches:        {result_no_hw['version_matches']}")
    print(f"  Final vulnerabilities:  {len(result_no_hw['vulnerabilities'])}")
    print(f"  Query time:             {result_no_hw['query_time_ms']:.2f}ms")
    print()

    # Show some bug details
    print("  Sample bugs (first 5):")
    for i, bug in enumerate(result_no_hw['vulnerabilities'][:5], 1):
        print(f"    {i}. {bug['bug_id']}: {bug['headline'][:60]}...")
    print()

    # Test 2: Scan WITH Cat9200 hardware filter
    print("=" * 70)
    print("TEST 2: Scan WITH Cat9200 hardware filter")
    print("=" * 70)

    result_cat9200 = scanner.scan_device(
        platform=platform,
        version=version,
        hardware_model='Cat9200'
    )

    print(f"  Total bugs checked:     {result_cat9200['total_bugs_checked']:,}")
    print(f"  Version matches:        {result_cat9200['version_matches']}")
    print(f"  Hardware filtered:      {result_cat9200['hardware_filtered']}")
    print(f"  Hardware filtered out:  {result_cat9200['hardware_filtered_count']}")
    print(f"  Final vulnerabilities:  {len(result_cat9200['vulnerabilities'])}")
    print(f"  Query time:             {result_cat9200['query_time_ms']:.2f}ms")
    print()

    # Calculate reduction
    baseline = result_no_hw['version_matches']
    filtered = result_cat9200['hardware_filtered']
    reduction = baseline - filtered
    reduction_pct = (reduction / baseline * 100) if baseline > 0 else 0

    print("=" * 70)
    print("HARDWARE FILTERING IMPACT")
    print("=" * 70)
    print(f"  Baseline (no hardware):   {baseline} bugs")
    print(f"  With Cat9200 filter:      {filtered} bugs")
    print(f"  Bugs filtered out:        {reduction} bugs")
    print(f"  Reduction:                {reduction_pct:.1f}%")
    print()

    if reduction > 0:
        print(f"  ✅ SUCCESS: Hardware filtering reduced {reduction} bugs ({reduction_pct:.1f}%)")
    else:
        print(f"  ⚠️  WARNING: No bugs filtered (all bugs are generic)")

    print()

    # Test 3: Scan with different hardware (Cat9300)
    print("=" * 70)
    print("TEST 3: Scan WITH Cat9300 hardware filter (different hardware)")
    print("=" * 70)

    result_cat9300 = scanner.scan_device(
        platform=platform,
        version=version,
        hardware_model='Cat9300'
    )

    print(f"  Version matches:        {result_cat9300['version_matches']}")
    print(f"  Hardware filtered:      {result_cat9300['hardware_filtered']}")
    print(f"  Hardware filtered out:  {result_cat9300['hardware_filtered_count']}")
    print(f"  Final vulnerabilities:  {len(result_cat9300['vulnerabilities'])}")
    print()

    # Compare Cat9200 vs Cat9300
    print("=" * 70)
    print("HARDWARE COMPARISON: Cat9200 vs Cat9300")
    print("=" * 70)
    print(f"  Cat9200:  {result_cat9200['hardware_filtered']} bugs")
    print(f"  Cat9300:  {result_cat9300['hardware_filtered']} bugs")

    if result_cat9200['hardware_filtered'] != result_cat9300['hardware_filtered']:
        diff = abs(result_cat9200['hardware_filtered'] - result_cat9300['hardware_filtered'])
        print(f"  Difference: {diff} bugs")
        print(f"  ✅ SUCCESS: Different hardware models show different bugs!")
    else:
        print(f"  ℹ️  Note: Same bug count (all bugs are generic for this version)")

    print()

    # Test 4: Feature-aware filtering WITH hardware
    print("=" * 70)
    print("TEST 4: Combined Hardware + Feature Filtering")
    print("=" * 70)

    result_combined = scanner.scan_device(
        platform=platform,
        version=version,
        hardware_model='Cat9200',
        labels=['MGMT_SSH_HTTP', 'SEC_CoPP', 'RTE_BGP']
    )

    print(f"  Version matches:        {result_combined['version_matches']}")
    print(f"  Hardware filtered:      {result_combined['hardware_filtered']}")
    print(f"  Feature filtered:       {result_combined['feature_filtered']}")
    print(f"  Final vulnerabilities:  {len(result_combined['vulnerabilities'])}")
    print()

    # Calculate combined reduction
    baseline = result_no_hw['version_matches']
    final = result_combined['feature_filtered']
    combined_reduction = baseline - final
    combined_pct = (combined_reduction / baseline * 100) if baseline > 0 else 0

    print(f"  Combined Reduction:")
    print(f"    Baseline:              {baseline} bugs")
    print(f"    After hardware filter: {result_combined['hardware_filtered']} bugs")
    print(f"    After feature filter:  {final} bugs")
    print(f"    Total reduction:       {combined_reduction} bugs ({combined_pct:.1f}%)")
    print()

    if combined_pct > 50:
        print(f"  🎉 EXCELLENT: Combined filtering achieved {combined_pct:.1f}% reduction!")
    elif combined_pct > 0:
        print(f"  ✅ GOOD: Combined filtering achieved {combined_pct:.1f}% reduction")

    print()
    print("=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)


if __name__ == '__main__':
    try:
        test_hardware_filtering()
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
