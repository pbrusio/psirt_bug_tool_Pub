#!/usr/bin/env python3
"""
Database migration: Add hardware_model column to vulnerabilities table

This migration adds hardware-based filtering capability to reduce false positives
by 40-60% when scanning devices.

Usage:
    python migration_add_hardware_model.py

Safety:
    - Idempotent (safe to run multiple times)
    - NULL values = generic bugs (apply to all hardware)
    - Includes rollback instructions if needed
"""

import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).parent / "vulnerability_db.sqlite"


def check_column_exists(cursor) -> bool:
    """Check if hardware_model column already exists."""
    cursor.execute("PRAGMA table_info(vulnerabilities)")
    columns = [row[1] for row in cursor.fetchall()]
    return "hardware_model" in columns


def migrate():
    """Add hardware_model column and index to vulnerabilities table."""

    if not DB_PATH.exists():
        print(f"❌ ERROR: Database not found at {DB_PATH}")
        print("   Make sure you're running this from the project root.")
        sys.exit(1)

    print(f"🔧 Starting migration on {DB_PATH}")
    print()

    db = sqlite3.connect(DB_PATH)
    cursor = db.cursor()

    try:
        # Check if migration already applied
        if check_column_exists(cursor):
            print("⚠️  Migration already applied (hardware_model column exists)")
            print("   Skipping to avoid errors.")
            db.close()
            sys.exit(0)

        # Step 1: Add column
        print("📝 Adding hardware_model column...")
        cursor.execute("""
            ALTER TABLE vulnerabilities
            ADD COLUMN hardware_model TEXT
        """)
        print("   ✅ Column added")

        # Step 2: Create index
        print("📊 Creating index on hardware_model...")
        cursor.execute("""
            CREATE INDEX idx_hardware_model
            ON vulnerabilities(hardware_model)
        """)
        print("   ✅ Index created")

        # Step 3: Get stats
        cursor.execute("SELECT COUNT(*) FROM vulnerabilities WHERE vuln_type = 'bug'")
        total_bugs = cursor.fetchone()[0]

        db.commit()
        print()
        print("=" * 60)
        print("✅ Migration complete!")
        print("=" * 60)
        print(f"📊 Database now has hardware_model column")
        print(f"📊 Total bugs to backfill: {total_bugs:,}")
        print()
        print("Next steps:")
        print("  1. Run: python backfill_hardware_models.py")
        print("  2. Verify: sqlite3 vulnerability_db.sqlite 'SELECT COUNT(*), hardware_model FROM vulnerabilities GROUP BY hardware_model'")
        print()

    except Exception as e:
        print(f"❌ Migration failed: {e}")
        db.rollback()
        sys.exit(1)
    finally:
        db.close()


def rollback():
    """
    Rollback instructions (manual, SQLite doesn't support DROP COLUMN easily).

    To rollback this migration:
    1. Backup database: cp vulnerability_db.sqlite vulnerability_db.sqlite.backup
    2. Create new table without hardware_model
    3. Copy data from old table
    4. Drop old table, rename new table
    """
    print("Rollback not automated due to SQLite limitations.")
    print("See migration script comments for manual rollback instructions.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--rollback":
        rollback()
    else:
        migrate()
