#!/usr/bin/env python3
"""
Feature-Aware Vulnerability Scanner Demo

Shows the difference between:
1. Version-only scanning (shows ALL bugs for that version)
2. Feature-aware scanning (filters by configured features)

This demonstrates how providing device features reduces false positives.
"""

import sqlite3
import sys
import json
from typing import List, Dict, Tuple


def scan_with_features(device_version: str, device_features: List[str] = None):
    """
    Scan for vulnerabilities with optional feature filtering

    Args:
        device_version: IOS-XE version (e.g., "17.10.1")
        device_features: List of labels for features configured on device
                        (e.g., ["MGMT_SSH_HTTP", "SEC_CoPP", "RTE_BGP"])
    """

    print("\n" + "="*80)
    print(f"  🔍 FEATURE-AWARE VULNERABILITY SCAN")
    print("="*80)
    print(f"\n  Device: IOS-XE {device_version}")

    if device_features:
        print(f"  Features configured: {len(device_features)}")
        print(f"  {', '.join(device_features[:10])}")
        if len(device_features) > 10:
            print(f"  ... and {len(device_features) - 10} more")
    else:
        print(f"  Features: NOT PROVIDED (version-only scan)")

    print(f"\n  Scanning database...")
    print()

    # Connect to database
    db = sqlite3.connect('vulnerability_db.sqlite')
    db.row_factory = sqlite3.Row
    cursor = db.cursor()

    # Get all bugs for platform
    cursor.execute("""
        SELECT bug_id, headline, summary, severity, affected_versions_raw,
               status, labels, url
        FROM vulnerabilities
        WHERE platform = 'IOS-XE'
    """)

    all_bugs = cursor.fetchall()
    print(f"  📊 Total bugs in database: {len(all_bugs)}\n")

    # Step 1: Version matching (get bugs affecting this version)
    version_matches = []
    for bug in all_bugs:
        affected = bug['affected_versions_raw']
        if affected and device_version in affected:
            version_matches.append(bug)

    print(f"  📍 Step 1: Version Matching")
    print(f"     Found {len(version_matches)} bugs affecting version {device_version}")

    # Step 2: Feature filtering (if features provided)
    final_matches = version_matches
    filtered_out = []

    if device_features:
        print(f"\n  🎯 Step 2: Feature Filtering")
        feature_matches = []

        for bug in version_matches:
            bug_labels_str = bug['labels']

            # Parse labels JSON
            try:
                bug_labels = json.loads(bug_labels_str) if bug_labels_str else []
            except json.JSONDecodeError:
                bug_labels = []

            # Check if ANY bug label matches device features
            if bug_labels:
                matches_feature = any(label in device_features for label in bug_labels)
                if matches_feature:
                    feature_matches.append(bug)
                else:
                    filtered_out.append((bug, bug_labels))
            else:
                # No labels = can't determine, keep it (conservative)
                feature_matches.append(bug)

        final_matches = feature_matches
        print(f"     Kept {len(feature_matches)} bugs (feature match)")
        print(f"     Filtered out {len(filtered_out)} bugs (features not configured)")

    print()

    # Show results
    print("="*80)
    if device_features:
        print(f"  ✅ FINAL RESULTS: {len(final_matches)} VULNERABILITIES")
        print(f"  (Reduced from {len(version_matches)} by filtering for configured features)")
    else:
        print(f"  ⚠️  FOUND {len(final_matches)} VULNERABILITIES (VERSION-ONLY)")
    print("="*80)
    print()

    if not final_matches:
        print("  🎉 No vulnerabilities found!")
        print("     Your device is not affected by known bugs for this version/configuration.\n")
        return

    # Group by severity
    critical_high = [b for b in final_matches if b['severity'] in (1, 2)]
    medium_low = [b for b in final_matches if b['severity'] not in (1, 2)]

    # Show Critical/High
    if critical_high:
        print(f"  🔴 CRITICAL / HIGH SEVERITY ({len(critical_high)} bugs)")
        print("  " + "-"*76)
        for i, bug in enumerate(critical_high[:3], 1):
            show_bug_detail(bug, i)

        if len(critical_high) > 3:
            print(f"\n  ... and {len(critical_high) - 3} more critical bugs")
        print()

    # Show Medium/Low
    if medium_low:
        print(f"  📋 MEDIUM / LOW SEVERITY ({len(medium_low)} bugs)")
        print("  " + "-"*76)
        for i, bug in enumerate(medium_low[:5], 1):
            sev = "MEDIUM" if bug['severity'] == 3 else "LOW"
            headline = (bug['headline'] or bug['summary'] or "No summary")[:50]
            print(f"  • [{sev}] {bug['bug_id']}: {headline}...")

        if len(medium_low) > 5:
            print(f"  ... and {len(medium_low) - 5} more")
        print()

    # Show what was filtered out (if feature-aware)
    if device_features and filtered_out:
        print("="*80)
        print(f"  🚫 FILTERED OUT: {len(filtered_out)} bugs (features not configured)")
        print("="*80)
        print()

        for i, (bug, bug_labels) in enumerate(filtered_out[:5], 1):
            headline = (bug['headline'] or bug['summary'] or "No summary")[:50]
            print(f"  {i}. {bug['bug_id']}: {headline}...")
            print(f"     Required features: {', '.join(bug_labels)}")
            print(f"     Status: NOT VULNERABLE (features not present on device)")
            print()

        if len(filtered_out) > 5:
            print(f"  ... and {len(filtered_out) - 5} more filtered bugs\n")

    # Recommendations
    print("="*80)
    print("  💡 NEXT STEPS")
    print("="*80)
    if critical_high:
        print(f"  • ⚠️  Review {len(critical_high)} CRITICAL/HIGH bugs immediately")
    if medium_low:
        print(f"  • 📋 Address {len(medium_low)} medium/low bugs during next maintenance")
    print(f"  • 🔍 Check Cisco advisories for available fixes")

    if not device_features:
        print(f"\n  💡 TIP: Provide device features to reduce false positives!")
        print(f"     Run with --features to see only bugs affecting configured features.")

    print()

    db.close()


def show_bug_detail(bug, number):
    """Show detailed bug information"""
    headline = (bug['headline'] or bug['summary'] or "No summary")[:70]
    status = bug['status'] or "Unknown"
    affected = bug['affected_versions_raw'] or "Unknown"
    labels_str = bug['labels'] or "[]"
    url = bug['url'] or ""

    try:
        labels = json.loads(labels_str)
    except json.JSONDecodeError:
        labels = []

    print(f"\n  {number}. {bug['bug_id']} (Severity {bug['severity']})")
    print(f"     {headline}...")
    print(f"     Status: {status}")
    print(f"     Affected versions: {affected}")
    if labels:
        print(f"     Required features: {', '.join(labels)}")
    if url:
        print(f"     Info: {url}")


def parse_features_from_snapshot(snapshot_file: str) -> List[str]:
    """Parse features from a snapshot JSON file"""
    try:
        with open(snapshot_file, 'r') as f:
            snapshot = json.load(f)
        return snapshot.get('features_present', [])
    except Exception as e:
        print(f"Error loading snapshot: {e}")
        return []


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description='Feature-aware vulnerability scanner',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Version-only scan (shows ALL bugs for version)
  python demo_scan_feature_aware.py 17.10.1

  # Feature-aware scan (manual feature list)
  python demo_scan_feature_aware.py 17.10.1 --features MGMT_SSH_HTTP SEC_CoPP RTE_BGP

  # Feature-aware scan (from snapshot file)
  python demo_scan_feature_aware.py 17.10.1 --snapshot device-snapshot.json
        """
    )

    parser.add_argument('version', help='IOS-XE version (e.g., 17.10.1)')
    parser.add_argument('--features', nargs='+', help='List of configured features')
    parser.add_argument('--snapshot', help='Path to device snapshot JSON file')

    args = parser.parse_args()

    # Get features from snapshot or command line
    features = None
    if args.snapshot:
        features = parse_features_from_snapshot(args.snapshot)
        if not features:
            print(f"⚠️  Warning: No features found in snapshot file")
    elif args.features:
        features = args.features

    print("\n" + "🔬 " * 20)
    print("  FEATURE-AWARE VULNERABILITY SCANNING")
    print("  Shows how device features reduce false positives")
    print("🔬 " * 20)

    scan_with_features(args.version, features)

    if not features:
        print("\n💡 Try again with features to see the difference:")
        print(f"   python demo_scan_feature_aware.py {args.version} --features MGMT_SSH_HTTP SEC_CoPP RTE_BGP")

    print()
