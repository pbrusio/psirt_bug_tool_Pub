"""
Cleanup Duplicate Devices in device_inventory

Removes duplicate devices based on (hostname, ip_address) combination.
Keeps the record with:
1. Most complete data (has platform/version/hardware)
2. Most recent update
3. Real ISE ID (not lab-uuid-*)

Usage:
    python scripts/cleanup_duplicate_devices.py
"""

import sqlite3
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

DB_PATH = "vulnerability_db.sqlite"


def find_duplicates(conn: sqlite3.Connection):
    """Find all duplicate devices by hostname+IP"""
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT hostname, ip_address, COUNT(*) as count
        FROM device_inventory
        GROUP BY hostname, ip_address
        HAVING count > 1
        ORDER BY hostname, ip_address
    ''')
    
    duplicates = cursor.fetchall()
    return duplicates


def get_duplicate_records(conn: sqlite3.Connection, hostname: str, ip_address: str):
    """Get all records for a specific hostname+IP combination"""
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, hostname, ip_address, ise_id, platform, version, hardware_model,
               discovery_status, created_at, updated_at, ise_sync_time
        FROM device_inventory
        WHERE hostname = ? AND ip_address = ?
        ORDER BY 
            -- Prefer records with platform/version (discovered devices)
            CASE WHEN platform IS NOT NULL THEN 1 ELSE 2 END,
            -- Prefer real ISE IDs over lab-uuid-*
            CASE WHEN ise_id NOT LIKE 'lab-uuid-%' THEN 1 ELSE 2 END,
            -- Prefer most recent update
            updated_at DESC,
            created_at DESC
    ''', (hostname, ip_address))
    
    return cursor.fetchall()


def choose_best_record(records):
    """Choose the best record to keep from duplicates"""
    if not records:
        return None
    
    # Score each record
    scored = []
    for record in records:
        score = 0
        id_val, hostname, ip, ise_id, platform, version, hardware, status, created, updated, ise_sync = record
        
        # Prefer discovered devices (have platform/version)
        if platform:
            score += 100
        if version:
            score += 50
        if hardware:
            score += 25
        
        # Prefer real ISE IDs
        if ise_id and not ise_id.startswith('lab-uuid-'):
            score += 10
        
        # Prefer successful discovery
        if status == 'success':
            score += 5
        
        # Prefer more recent
        if updated:
            try:
                # Simple timestamp comparison (more recent = higher score)
                score += 1
            except:
                pass
        
        scored.append((score, id_val, record))
    
    # Return the highest scoring record
    scored.sort(reverse=True, key=lambda x: x[0])
    return scored[0][1]  # Return the ID of the best record


def cleanup_duplicates(conn: sqlite3.Connection, dry_run: bool = False):
    """Remove duplicate devices, keeping the best record"""
    cursor = conn.cursor()
    
    duplicates = find_duplicates(conn)
    
    if not duplicates:
        print("✅ No duplicates found!")
        return
    
    print(f"🔍 Found {len(duplicates)} duplicate hostname+IP combinations:\n")
    
    total_removed = 0
    kept_records = []
    removed_records = []
    
    for hostname, ip_address, count in duplicates:
        print(f"  • {hostname} @ {ip_address} ({count} duplicates)")
        
        records = get_duplicate_records(conn, hostname, ip_address)
        best_id = choose_best_record(records)
        
        if not best_id:
            print(f"    ⚠️  Could not determine best record, skipping")
            continue
        
        # Get the best record details
        best_record = next((r for r in records if r[0] == best_id), None)
        if best_record:
            kept_records.append(best_record)
        
        # Remove all other records
        for record in records:
            record_id = record[0]
            if record_id != best_id:
                removed_records.append(record)
                
                if not dry_run:
                    cursor.execute('DELETE FROM device_inventory WHERE id = ?', (record_id,))
                    total_removed += 1
                else:
                    print(f"    [DRY RUN] Would delete: ID {record_id} (ise_id: {record[3]})")
        
        if not dry_run:
            print(f"    ✅ Kept: ID {best_id} (ise_id: {best_record[3] if best_record else 'N/A'})")
        else:
            print(f"    [DRY RUN] Would keep: ID {best_id}")
    
    if not dry_run:
        conn.commit()
        print(f"\n✅ Cleanup complete! Removed {total_removed} duplicate records")
        print(f"   Kept {len(kept_records)} best records")
    else:
        print(f"\n[DRY RUN] Would remove {len(removed_records)} duplicate records")
        print(f"          Would keep {len(kept_records)} best records")
    
    return total_removed


def main():
    """Run cleanup"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Cleanup duplicate devices')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be deleted without actually deleting')
    parser.add_argument('--db', default=DB_PATH, help='Database path')
    args = parser.parse_args()
    
    print(f"📦 Database: {args.db}")
    if args.dry_run:
        print("🔍 DRY RUN MODE - No changes will be made\n")
    
    # Connect to database
    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    
    try:
        # Check current state
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM device_inventory')
        total_before = cursor.fetchone()[0]
        print(f"📊 Total devices before cleanup: {total_before}\n")
        
        # Find and remove duplicates
        removed = cleanup_duplicates(conn, dry_run=args.dry_run)
        
        if not args.dry_run:
            # Check final state
            cursor.execute('SELECT COUNT(*) FROM device_inventory')
            total_after = cursor.fetchone()[0]
            print(f"\n📊 Total devices after cleanup: {total_after}")
            print(f"   Removed: {total_before - total_after} duplicates")
            
            # Verify no duplicates remain
            duplicates = find_duplicates(conn)
            if duplicates:
                print(f"\n⚠️  WARNING: {len(duplicates)} duplicate combinations still exist!")
            else:
                print("\n✅ Verified: No duplicates remain!")
        
    except Exception as e:
        print(f"\n❌ Cleanup failed: {e}")
        conn.rollback()
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()









