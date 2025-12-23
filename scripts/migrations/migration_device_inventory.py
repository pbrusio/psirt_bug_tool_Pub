"""
Database Migration: Add device_inventory table

This migration creates the device_inventory table for caching network device
information from ISE and SSH discovery.

Usage:
    python scripts/migrations/migration_device_inventory.py
"""

import sqlite3
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

DB_PATH = "vulnerability_db.sqlite"


def create_device_inventory_table(conn: sqlite3.Connection):
    """Create device_inventory table"""

    cursor = conn.cursor()

    # Create device_inventory table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS device_inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            -- ISE Information
            ise_id TEXT UNIQUE,                    -- ISE device UUID
            hostname TEXT NOT NULL,                -- Device hostname
            ip_address TEXT NOT NULL,              -- Primary IP address
            location TEXT,                         -- Physical location from ISE
            device_type TEXT,                      -- Device type from ISE

            -- Device Information (from SSH discovery)
            platform TEXT,                         -- IOS-XE, IOS-XR, ASA, etc.
            version TEXT,                          -- Software version (e.g., "17.10.1")
            hardware_model TEXT,                   -- Hardware model (e.g., "Cat9300")
            serial_number TEXT,                    -- Device serial number
            uptime TEXT,                           -- Device uptime

            -- Feature Detection (JSON array of detected feature labels)
            features TEXT,                         -- JSON: ["MGMT_SSH_HTTP", "RTE_BGP", ...]

            -- Vulnerability Scanning Cache
            last_scanned TIMESTAMP,                -- Last vulnerability scan time
            scan_result_summary TEXT,              -- JSON: {total_vulns, critical, high, ...}

            -- ISE Sync Metadata
            ise_sync_time TIMESTAMP,               -- Last ISE sync time
            ssh_discovery_time TIMESTAMP,          -- Last SSH discovery time
            discovery_status TEXT,                 -- "success", "failed", "pending"
            discovery_error TEXT,                  -- Error message if discovery failed

            -- Timestamps
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Create indexes for common queries
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_device_ip
        ON device_inventory(ip_address)
    ''')

    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_device_platform_version
        ON device_inventory(platform, version)
    ''')

    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_device_hostname
        ON device_inventory(hostname)
    ''')

    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_device_location
        ON device_inventory(location)
    ''')

    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_device_last_scanned
        ON device_inventory(last_scanned)
    ''')

    conn.commit()
    print("✅ Created device_inventory table with indexes")


def verify_migration(conn: sqlite3.Connection):
    """Verify the migration was successful"""
    cursor = conn.cursor()

    # Check table exists
    cursor.execute('''
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='device_inventory'
    ''')

    if cursor.fetchone():
        print("✅ device_inventory table verified")

        # Show table schema
        cursor.execute('PRAGMA table_info(device_inventory)')
        columns = cursor.fetchall()
        print(f"\nTable schema ({len(columns)} columns):")
        for col in columns:
            print(f"  • {col[1]:25} {col[2]:15}")

        # Show indexes
        cursor.execute('''
            SELECT name FROM sqlite_master
            WHERE type='index' AND tbl_name='device_inventory'
        ''')
        indexes = cursor.fetchall()
        print(f"\nIndexes ({len(indexes)} total):")
        for idx in indexes:
            print(f"  • {idx[0]}")

        return True
    else:
        print("❌ device_inventory table not found!")
        return False


def rollback_migration(conn: sqlite3.Connection):
    """Rollback the migration (drop table)"""
    cursor = conn.cursor()
    cursor.execute('DROP TABLE IF EXISTS device_inventory')
    conn.commit()
    print("✅ Rolled back device_inventory table")


def main():
    """Run migration"""
    import argparse

    parser = argparse.ArgumentParser(description='Device inventory table migration')
    parser.add_argument('--rollback', action='store_true', help='Rollback migration')
    parser.add_argument('--db', default=DB_PATH, help='Database path')
    args = parser.parse_args()

    print(f"📦 Database: {args.db}")

    # Connect to database
    conn = sqlite3.connect(args.db)

    try:
        if args.rollback:
            print("\n🔄 Rolling back migration...")
            rollback_migration(conn)
        else:
            print("\n🚀 Running migration...")
            create_device_inventory_table(conn)

            print("\n🔍 Verifying migration...")
            if verify_migration(conn):
                print("\n✅ Migration completed successfully!")
            else:
                print("\n❌ Migration verification failed!")
                sys.exit(1)

    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        conn.rollback()
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
