"""
Database Migration: Add unique constraint on (hostname, ip_address)

This migration adds a unique constraint to prevent duplicate devices
with the same hostname and IP address combination.

IMPORTANT: Run cleanup_duplicate_devices.py FIRST to remove existing duplicates!

Usage:
    python scripts/migrations/migration_add_device_unique_constraint.py
"""

import sqlite3
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

DB_PATH = "vulnerability_db.sqlite"


def check_for_duplicates(conn: sqlite3.Connection) -> bool:
    """Check if duplicates exist before adding constraint"""
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT hostname, ip_address, COUNT(*) as count
        FROM device_inventory
        GROUP BY hostname, ip_address
        HAVING count > 1
    ''')
    
    duplicates = cursor.fetchall()
    
    if duplicates:
        print(f"⚠️  Found {len(duplicates)} duplicate hostname+IP combinations:")
        for hostname, ip, count in duplicates:
            print(f"   • {hostname} @ {ip} ({count} records)")
        print("\n❌ Cannot add unique constraint while duplicates exist!")
        print("   Please run: python scripts/cleanup_duplicate_devices.py")
        return True
    
    return False


def add_unique_constraint(conn: sqlite3.Connection):
    """Add unique constraint on (hostname, ip_address)"""
    cursor = conn.cursor()
    
    try:
        # SQLite doesn't support ALTER TABLE ADD CONSTRAINT directly
        # We need to:
        # 1. Create a new table with the constraint
        # 2. Copy data
        # 3. Drop old table
        # 4. Rename new table
        
        print("🔄 Creating new table with unique constraint...")
        
        # Step 1: Create new table with unique constraint
        cursor.execute('''
            CREATE TABLE device_inventory_new (
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
                last_scan_result TEXT,
                last_scan_id TEXT,
                last_scan_timestamp TEXT,
                previous_scan_result TEXT,
                previous_scan_id TEXT,
                previous_scan_timestamp TEXT,

                -- ISE Sync Metadata
                ise_sync_time TIMESTAMP,               -- Last ISE sync time
                ssh_discovery_time TIMESTAMP,          -- Last SSH discovery time
                discovery_status TEXT,                 -- "success", "failed", "pending"
                discovery_error TEXT,                  -- Error message if discovery failed

                -- Timestamps
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                
                -- UNIQUE CONSTRAINT on hostname + ip_address
                UNIQUE(hostname, ip_address)
            )
        ''')
        
        print("📋 Copying data to new table...")
        
        # Step 2: Copy all data
        cursor.execute('''
            INSERT INTO device_inventory_new
            SELECT * FROM device_inventory
        ''')
        
        print("🗑️  Dropping old table...")
        
        # Step 3: Drop old table
        cursor.execute('DROP TABLE device_inventory')
        
        print("🔄 Renaming new table...")
        
        # Step 4: Rename new table
        cursor.execute('ALTER TABLE device_inventory_new RENAME TO device_inventory')
        
        # Recreate indexes
        print("🔧 Recreating indexes...")
        
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
        
        # Create index on the unique constraint for faster lookups
        cursor.execute('''
            CREATE UNIQUE INDEX IF NOT EXISTS idx_device_hostname_ip
            ON device_inventory(hostname, ip_address)
        ''')
        
        conn.commit()
        print("✅ Unique constraint added successfully!")
        
    except sqlite3.IntegrityError as e:
        conn.rollback()
        print(f"❌ Integrity error: {e}")
        print("   This means duplicates still exist. Run cleanup script first!")
        raise
    except Exception as e:
        conn.rollback()
        print(f"❌ Migration failed: {e}")
        raise


def verify_constraint(conn: sqlite3.Connection):
    """Verify the unique constraint was added"""
    cursor = conn.cursor()
    
    # Check for unique index
    cursor.execute('''
        SELECT name, sql FROM sqlite_master
        WHERE type='index' AND tbl_name='device_inventory'
        AND name='idx_device_hostname_ip'
    ''')
    
    index = cursor.fetchone()
    
    if index:
        print("✅ Unique index verified: idx_device_hostname_ip")
        return True
    else:
        print("❌ Unique index not found!")
        return False


def main():
    """Run migration"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Add unique constraint to device_inventory')
    parser.add_argument('--db', default=DB_PATH, help='Database path')
    parser.add_argument('--force', action='store_true', help='Skip duplicate check (dangerous!)')
    args = parser.parse_args()
    
    print(f"📦 Database: {args.db}\n")
    
    # Connect to database
    conn = sqlite3.connect(args.db)
    
    try:
        if not args.force:
            print("🔍 Checking for duplicates...")
            if check_for_duplicates(conn):
                sys.exit(1)
            print("✅ No duplicates found, proceeding...\n")
        
        print("🚀 Running migration...")
        add_unique_constraint(conn)
        
        print("\n🔍 Verifying constraint...")
        if verify_constraint(conn):
            print("\n✅ Migration completed successfully!")
        else:
            print("\n❌ Migration verification failed!")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()









