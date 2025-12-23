#!/usr/bin/env python3
"""
Get Last Update - CLI Tool

Shows the last update timestamp and database statistics.

Usage:
    python backend/db/get_last_update.py
    python backend/db/get_last_update.py --db path/to/db.sqlite
"""

import sqlite3
import sys
import os
from datetime import datetime


def get_db_metadata(db_path: str = 'vulnerability_db.sqlite'):
    """
    Retrieve and display database metadata.

    Args:
        db_path: Path to SQLite database
    """
    if not os.path.exists(db_path):
        print(f"Error: Database not found at {db_path}")
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get metadata
    cursor.execute("SELECT key, value, updated_at FROM db_metadata")
    metadata = {row['key']: {'value': row['value'], 'updated_at': row['updated_at']}
                for row in cursor.fetchall()}

    # Get counts
    cursor.execute("SELECT COUNT(*) as total FROM vulnerabilities")
    total_vulns = cursor.fetchone()['total']

    cursor.execute("SELECT COUNT(*) as total FROM vulnerabilities WHERE vuln_type = 'bug'")
    total_bugs = cursor.fetchone()['total']

    cursor.execute("SELECT COUNT(*) as total FROM vulnerabilities WHERE vuln_type = 'psirt'")
    total_psirts = cursor.fetchone()['total']

    cursor.execute("SELECT COUNT(*) as total FROM vulnerabilities WHERE labels != '[]'")
    total_with_labels = cursor.fetchone()['total']

    # Platform distribution
    cursor.execute('''
        SELECT platform, COUNT(*) as count
        FROM vulnerabilities
        GROUP BY platform
    ''')
    platforms = cursor.fetchall()

    # Version pattern distribution
    cursor.execute('''
        SELECT version_pattern, COUNT(*) as count
        FROM vulnerabilities
        GROUP BY version_pattern
        ORDER BY count DESC
    ''')
    patterns = cursor.fetchall()

    conn.close()

    # Display results
    print("=" * 80)
    print("VULNERABILITY DATABASE STATUS")
    print("=" * 80)
    print(f"Database: {os.path.abspath(db_path)}")
    print()

    # Metadata
    last_update = metadata.get('last_update', {}).get('value', 'Never')
    schema_version = metadata.get('schema_version', {}).get('value', 'Unknown')

    print(f"Schema Version: {schema_version}")
    print(f"Last Update:    {last_update}")

    if last_update and last_update != 'Never' and last_update != '':
        try:
            # Parse and display in human-readable format
            dt = datetime.fromisoformat(last_update)
            days_ago = (datetime.now() - dt).days
            print(f"                ({days_ago} days ago)")
        except ValueError:
            pass

    print()

    # Counts
    print(f"Total Vulnerabilities: {total_vulns}")
    print(f"  Bugs:                {total_bugs}")
    print(f"  PSIRTs:              {total_psirts}")
    print(f"  With Labels:         {total_with_labels}")
    print()

    # Platforms
    if platforms:
        print("Platform Distribution:")
        for row in platforms:
            print(f"  {row['platform']}: {row['count']}")
        print()

    # Version patterns
    if patterns:
        print("Version Pattern Distribution:")
        for row in patterns:
            print(f"  {row['version_pattern']}: {row['count']}")

    print("=" * 80)


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description='Show last update timestamp and database statistics'
    )
    parser.add_argument(
        '--db',
        default='vulnerability_db.sqlite',
        help='Database path (default: vulnerability_db.sqlite)'
    )

    args = parser.parse_args()

    get_db_metadata(db_path=args.db)


if __name__ == '__main__':
    main()
