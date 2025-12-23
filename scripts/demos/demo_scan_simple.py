#!/usr/bin/env python3
"""
Simple Demo: What vulnerability scanning will look like in the UI

This shows you what Phase 3 UI will do - just without the fancy React interface yet!
"""

import sqlite3
import sys

def simple_scan_demo(device_version="17.10.1"):
    """Simple vulnerability scan - this is what the UI button will do!"""

    print("\n" + "="*80)
    print(f"  🔍 VULNERABILITY SCAN DEMO")
    print("="*80)
    print(f"\n  Device: IOS-XE {device_version}")
    print(f"  Scanning database...")
    print()

    # Connect to database
    db = sqlite3.connect('vulnerability_db.sqlite')
    cursor = db.cursor()

    # Get all bugs for version
    cursor.execute("""
        SELECT advisory_id, summary, severity, affected_versions_raw,
               status, labels, url
        FROM vulnerabilities
        WHERE platform = 'IOS-XE'
    """)

    bugs = cursor.fetchall()
    print(f"  📊 Checking {len(bugs)} bugs in database...\n")

    # For demo, just show bugs that have this version in their affected list
    # (Real scanner uses sophisticated version_matcher.py)
    matching_bugs = []
    for bug in bugs:
        affected = bug[3]  # affected_versions_raw
        if affected and device_version in affected:
            matching_bugs.append(bug)

    print("="*80)
    print(f"  ⚠️  FOUND {len(matching_bugs)} VULNERABILITIES AFFECTING {device_version}")
    print("="*80)
    print()

    if not matching_bugs:
        print("  ✅ No known vulnerabilities found!\n")
        return

    # Group by severity
    critical_high = [b for b in matching_bugs if b[2] in (1, 2)]
    medium_low = [b for b in matching_bugs if b[2] not in (1, 2)]

    # Show Critical/High (this is what UI will emphasize)
    if critical_high:
        print(f"  🔴 CRITICAL / HIGH SEVERITY ({len(critical_high)} bugs)")
        print("  " + "-"*76)
        for i, bug in enumerate(critical_high[:3], 1):  # Show first 3
            advisory_id = bug[0] or "Unknown"
            summary = (bug[1] or "No summary available")[:70]
            status = bug[4] or "Unknown"
            affected = bug[3] or "Unknown"
            labels = bug[5] or ""
            url = bug[6] or ""

            print(f"\n  {i}. {advisory_id} (Severity {bug[2]})")
            print(f"     {summary}...")
            print(f"     Status: {status}")
            print(f"     Affected: {affected}")
            if labels and labels != "[]":
                print(f"     Features: {labels}")
            if url:
                print(f"     Info: {url}")

        if len(critical_high) > 3:
            print(f"\n  ... and {len(critical_high) - 3} more critical bugs")
        print()

    # Show Medium/Low (collapsed in UI)
    if medium_low:
        print(f"  📋 MEDIUM / LOW SEVERITY ({len(medium_low)} bugs)")
        print("  " + "-"*76)
        for i, bug in enumerate(medium_low[:5], 1):
            sev = "MEDIUM" if bug[2] == 3 else "LOW"
            advisory = bug[0] or "Unknown"
            summary = (bug[1] or "No summary")[:50]
            print(f"  • [{sev}] {advisory}: {summary}...")

        if len(medium_low) > 5:
            print(f"  ... and {len(medium_low) - 5} more")
        print()

    # Recommendations (what UI will show)
    print("="*80)
    print("  💡 NEXT STEPS")
    print("="*80)
    print(f"  • Review {len(critical_high)} critical/high bugs immediately")
    print(f"  • Address {len(medium_low)} medium/low bugs during next maintenance")
    print(f"  • Check Cisco advisories for available fixes")
    print()

    db.close()

if __name__ == "__main__":
    version = sys.argv[1] if len(sys.argv) > 1 else "17.10.1"

    print("\n" + "🎬 " * 20)
    print("  THIS IS WHAT THE UI WILL DO IN PHASE 3")
    print("  (Right now it's just a Python script)")
    print("🎬 " * 20)

    simple_scan_demo(version)

    print("\n💡 Try other versions:")
    print("   python demo_scan_simple.py 17.12.4")
    print("   python demo_scan_simple.py 17.15.1")
    print("   python demo_scan_simple.py 99.99.99  # Should find nothing")
    print()
