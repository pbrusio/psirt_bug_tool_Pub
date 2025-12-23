#!/usr/bin/env python3
"""
Backfill hardware_model column for all existing bugs in database

This script processes all bugs in the vulnerability database and extracts
hardware platform identifiers from their headlines and summaries.

Usage:
    python backfill_hardware_models.py [--dry-run]

Options:
    --dry-run    Show what would be updated without making changes

Output:
    - Number of bugs updated per hardware model
    - Number of generic bugs (no hardware detected)
    - Total processing statistics
"""

import sqlite3
import sys
from pathlib import Path
from collections import Counter

# Import hardware extraction logic
from backend.db.hardware_extractor import extract_hardware_model

DB_PATH = Path(__file__).parent / "vulnerability_db.sqlite"


def backfill(dry_run=False):
    """
    Backfill hardware_model for all existing bugs.

    Args:
        dry_run: If True, don't commit changes (just show what would happen)
    """

    if not DB_PATH.exists():
        print(f"❌ ERROR: Database not found at {DB_PATH}")
        print("   Make sure you're running this from the project root.")
        sys.exit(1)

    print(f"🔧 Backfilling hardware models from {DB_PATH}")
    if dry_run:
        print("   [DRY RUN MODE - No changes will be saved]")
    print()

    db = sqlite3.connect(DB_PATH)
    cursor = db.cursor()

    try:
        # Get all bugs (vuln_type = 'bug')
        cursor.execute("""
            SELECT id, platform, headline, summary
            FROM vulnerabilities
            WHERE vuln_type = 'bug'
        """)
        bugs = cursor.fetchall()

        print(f"📊 Found {len(bugs):,} bugs to process")
        print()

        # Track statistics
        hardware_counts = Counter()
        updated_count = 0
        generic_count = 0

        # Process each bug
        for i, (bug_id, platform, headline, summary) in enumerate(bugs, 1):
            # Combine headline + summary for extraction
            text = (headline or '') + ' ' + (summary or '')

            # Extract hardware model
            hardware = extract_hardware_model(text, platform)

            # Update database (if not dry run)
            if hardware:
                hardware_counts[hardware] += 1
                updated_count += 1

                if not dry_run:
                    cursor.execute(
                        'UPDATE vulnerabilities SET hardware_model = ? WHERE id = ?',
                        (hardware, bug_id)
                    )
            else:
                generic_count += 1

            # Progress indicator (every 500 bugs)
            if i % 500 == 0:
                print(f"   Processed {i:,}/{len(bugs):,} bugs ({i/len(bugs)*100:.1f}%)...")

        print(f"   Processed {len(bugs):,}/{len(bugs):,} bugs (100.0%)")
        print()

        # Commit changes (if not dry run)
        if not dry_run:
            db.commit()
            print("✅ Changes committed to database")
        else:
            print("ℹ️  Changes NOT committed (dry run mode)")

        print()
        print("=" * 70)
        print("📊 BACKFILL RESULTS")
        print("=" * 70)
        print()
        print(f"Total bugs processed:        {len(bugs):,}")
        print(f"Bugs with hardware detected: {updated_count:,} ({updated_count/len(bugs)*100:.1f}%)")
        print(f"Generic bugs (no hardware):  {generic_count:,} ({generic_count/len(bugs)*100:.1f}%)")
        print()

        if hardware_counts:
            print("Hardware distribution:")
            print("-" * 70)
            # Sort by count (descending)
            for hardware, count in hardware_counts.most_common():
                pct = count / len(bugs) * 100
                print(f"  {hardware:20s} {count:5,} bugs ({pct:5.1f}%)")

        print()
        print("=" * 70)

        if not dry_run:
            print("✅ Backfill complete!")
            print()
            print("Next steps:")
            print("  1. Verify results: python3 -c \"import sqlite3; db=sqlite3.connect('vulnerability_db.sqlite'); c=db.cursor(); c.execute('SELECT hardware_model, COUNT(*) FROM vulnerabilities WHERE vuln_type=\\\"bug\\\" GROUP BY hardware_model ORDER BY COUNT(*) DESC'); print('\\n'.join([f\\\"{h or 'Generic':20s} {cnt:,}\\\" for h, cnt in c.fetchall()]))\"")
            print("  2. Test scanner: python demo_scan_device.py")
            print("  3. Continue to Phase 2: Update load_bugs.py")

    except Exception as e:
        print(f"❌ Backfill failed: {e}")
        db.rollback()
        sys.exit(1)
    finally:
        db.close()


def verify_backfill():
    """
    Verify that backfill completed successfully by showing current stats.
    """
    if not DB_PATH.exists():
        print(f"❌ ERROR: Database not found at {DB_PATH}")
        sys.exit(1)

    db = sqlite3.connect(DB_PATH)
    cursor = db.cursor()

    print("📊 Current hardware model distribution:")
    print()

    cursor.execute("""
        SELECT hardware_model, COUNT(*) as cnt
        FROM vulnerabilities
        WHERE vuln_type = 'bug'
        GROUP BY hardware_model
        ORDER BY cnt DESC
    """)

    results = cursor.fetchall()

    for hardware, count in results:
        hardware_label = hardware or "Generic (no hardware)"
        print(f"  {hardware_label:30s}: {count:,} bugs")

    cursor.execute("SELECT COUNT(*) FROM vulnerabilities WHERE vuln_type = 'bug'")
    total = cursor.fetchone()[0]

    print()
    print(f"Total bugs: {total:,}")

    db.close()


if __name__ == '__main__':
    if len(sys.argv) > 1:
        if sys.argv[1] == '--dry-run':
            backfill(dry_run=True)
        elif sys.argv[1] == '--verify':
            verify_backfill()
        elif sys.argv[1] == '--help':
            print(__doc__)
        else:
            print(f"Unknown option: {sys.argv[1]}")
            print("Usage: python backfill_hardware_models.py [--dry-run|--verify|--help]")
            sys.exit(1)
    else:
        backfill(dry_run=False)
