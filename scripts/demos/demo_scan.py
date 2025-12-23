#!/usr/bin/env python3
"""
Demo script to show vulnerability scanning in action
This simulates what the UI will do in Phase 3
"""

import sqlite3
import sys
from backend.core.version_matcher import VersionMatcher

def demo_scan(device_version, device_platform="IOS-XE"):
    """
    Simulate scanning a device for vulnerabilities
    This is what the API will do when you click "Scan Device" in the UI
    """
    print("=" * 80)
    print(f"🔍 SCANNING DEVICE")
    print("=" * 80)
    print(f"Platform: {device_platform}")
    print(f"Version:  {device_version}")
    print()

    # Connect to database
    db = sqlite3.connect('vulnerability_db.sqlite')
    db.row_factory = sqlite3.Row
    cursor = db.cursor()

    # Query all bugs for this platform
    cursor.execute("""
        SELECT * FROM vulnerabilities
        WHERE platform = ?
        ORDER BY severity
    """, (device_platform,))

    all_bugs = cursor.fetchall()
    print(f"📊 Database: {len(all_bugs)} total bugs for {device_platform}")
    print()

    # Check which bugs affect this version
    matcher = VersionMatcher()
    vulnerable_bugs = []

    print("🔎 Checking version matches...")
    for bug in all_bugs:
        is_vuln, reason = matcher.is_vulnerable(device_version, dict(bug))
        if is_vuln:
            vulnerable_bugs.append((bug, reason))

    print()
    print("=" * 80)
    print(f"⚠️  FOUND {len(vulnerable_bugs)} VULNERABILITIES")
    print("=" * 80)
    print()

    if not vulnerable_bugs:
        print("✅ No known vulnerabilities found for this device!")
        return

    # Group by severity
    critical_high = [(b, r) for b, r in vulnerable_bugs if b['severity'] in (1, 2)]
    medium_low = [(b, r) for b, r in vulnerable_bugs if b['severity'] not in (1, 2)]

    # Show Critical/High (full details)
    if critical_high:
        print(f"🔴 CRITICAL / HIGH SEVERITY ({len(critical_high)})")
        print("=" * 80)
        for i, (bug, reason) in enumerate(critical_high[:5], 1):  # Show first 5
            print(f"\n{i}. {bug['advisory_id']} (Severity {bug['severity']})")
            print(f"   Summary: {bug['summary'][:100]}...")
            print(f"   Version Match: {reason}")
            print(f"   Affected: {bug['affected_versions_raw']}")
            if bug['fixed_versions_raw']:
                print(f"   Fixed In: {bug['fixed_versions_raw']}")
            print(f"   Status: {bug['bug_status']}")
            print(f"   URL: {bug['url']}")

            # Show labels if available
            if bug['labels'] and bug['labels'] != '[]':
                print(f"   Labels: {bug['labels']}")

        if len(critical_high) > 5:
            print(f"\n   ... and {len(critical_high) - 5} more critical/high severity bugs")

    # Show Medium/Low (collapsed)
    if medium_low:
        print()
        print(f"📋 MEDIUM / LOW SEVERITY ({len(medium_low)})")
        print("=" * 80)
        for i, (bug, reason) in enumerate(medium_low[:10], 1):  # Show first 10
            sev_label = "MEDIUM" if bug['severity'] == 3 else "LOW"
            print(f"{i}. [{sev_label}] {bug['advisory_id']}: {bug['summary'][:60]}...")

        if len(medium_low) > 10:
            print(f"\n... and {len(medium_low) - 10} more medium/low severity bugs")

    print()
    print("=" * 80)
    print("💡 RECOMMENDATIONS")
    print("=" * 80)

    # Find earliest fixed version
    fixed_versions = []
    for bug, _ in critical_high:
        if bug['fixed_versions_raw']:
            fixed_versions.append(bug['fixed_versions_raw'])

    if fixed_versions:
        print(f"• Upgrade to a fixed release")
        print(f"  Fixed versions available: {', '.join(set(fixed_versions))}")

    print(f"• Review {len(critical_high)} critical/high severity bugs first")
    print(f"• Total vulnerabilities to address: {len(vulnerable_bugs)}")
    print()

    db.close()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        version = sys.argv[1]
    else:
        version = "17.10.1"

    demo_scan(version)
