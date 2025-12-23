#!/usr/bin/env python3
"""
Migration: Create scan_results table for full vulnerability storage

Purpose:
- Store complete vulnerability lists for each scan
- Enable scan detail viewing
- Support before/after and version comparison

Schema:
- scan_id (TEXT, PRIMARY KEY): Unique scan identifier
- device_id (INTEGER): Foreign key to device_inventory
- timestamp (TEXT): ISO format timestamp
- full_result (TEXT): JSON with complete scan data including vulnerabilities
- retention_days (INTEGER): Days to keep (default 90)

Usage:
    python scripts/migrations/migration_scan_results_table.py
"""

import sqlite3
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

DB_PATH = "vulnerability_db.sqlite"


def create_scan_results_table():
    """Create scan_results table for storing complete scan data"""

    print("=" * 80)
    print("Migration: Create scan_results table")
    print("=" * 80)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Check if table already exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='scan_results'
        """)

        if cursor.fetchone():
            print("✅ scan_results table already exists")
            return

        # Create scan_results table
        print("\n📝 Creating scan_results table...")
        cursor.execute("""
            CREATE TABLE scan_results (
                scan_id TEXT PRIMARY KEY,
                device_id INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                full_result TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (device_id) REFERENCES device_inventory(id) ON DELETE CASCADE
            )
        """)

        # Create indexes for fast queries
        print("📝 Creating indexes...")
        cursor.execute("""
            CREATE INDEX idx_scan_results_device_id
            ON scan_results(device_id)
        """)

        cursor.execute("""
            CREATE INDEX idx_scan_results_timestamp
            ON scan_results(timestamp DESC)
        """)

        conn.commit()

        print("\n✅ Migration complete!")
        print("\nTable structure:")
        print("  - scan_id (TEXT, PRIMARY KEY)")
        print("  - device_id (INTEGER, FK to device_inventory)")
        print("  - timestamp (TEXT)")
        print("  - full_result (TEXT, JSON)")
        print("  - created_at (TEXT, auto)")
        print("\nIndexes:")
        print("  - idx_scan_results_device_id")
        print("  - idx_scan_results_timestamp")

    except Exception as e:
        conn.rollback()
        print(f"\n❌ Migration failed: {e}")
        raise
    finally:
        conn.close()


def verify_migration():
    """Verify the migration was successful"""
    print("\n" + "=" * 80)
    print("Verification")
    print("=" * 80)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Check table exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='scan_results'
        """)

        if not cursor.fetchone():
            print("❌ Table not found!")
            return False

        # Check columns
        cursor.execute("PRAGMA table_info(scan_results)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}

        expected_columns = {
            'scan_id': 'TEXT',
            'device_id': 'INTEGER',
            'timestamp': 'TEXT',
            'full_result': 'TEXT',
            'created_at': 'TEXT'
        }

        print("\n✅ Table exists")
        print("\nColumns:")
        for col, dtype in columns.items():
            status = "✅" if col in expected_columns else "⚠️"
            print(f"  {status} {col}: {dtype}")

        # Check indexes
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='index' AND tbl_name='scan_results'
        """)
        indexes = [row[0] for row in cursor.fetchall()]

        print("\nIndexes:")
        for idx in indexes:
            if idx.startswith('sqlite_autoindex'):
                continue
            print(f"  ✅ {idx}")

        return True

    except Exception as e:
        print(f"❌ Verification failed: {e}")
        return False
    finally:
        conn.close()


if __name__ == "__main__":
    try:
        create_scan_results_table()
        verify_migration()
        print("\n" + "=" * 80)
        print("✅ All done!")
        print("=" * 80)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
