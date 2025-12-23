# Device Inventory Duplicate Cleanup Summary

## Problem
The `device_inventory` table had duplicate devices with the same `hostname` and `ip_address` combination. This occurred because:
- Lab devices were added with mock `ise_id` values (e.g., `lab-uuid-001`)
- Real ISE devices were synced with actual UUIDs
- The sync logic only checked for duplicates by `ise_id`, not by `hostname+IP`

## Solution Implemented

### 1. Cleanup Script (`scripts/cleanup_duplicate_devices.py`)
- **Purpose**: Removes duplicate devices, keeping the best record
- **Selection Criteria** (in priority order):
  1. Devices with platform/version/hardware (discovered devices)
  2. Real ISE IDs (not `lab-uuid-*`)
  3. Successful discovery status
  4. Most recent update timestamp

### 2. Database Migration (`scripts/migrations/migration_add_device_unique_constraint.py`)
- **Purpose**: Adds `UNIQUE(hostname, ip_address)` constraint
- **Method**: Creates new table with constraint, copies data, replaces old table
- **Index**: Creates `idx_device_hostname_ip` unique index for fast lookups

### 3. Updated Sync Logic (`backend/core/device_inventory.py`)
- **Before**: Only checked for duplicates by `ise_id`
- **After**: Checks for duplicates by `hostname+IP` first (primary check)
- **Behavior**:
  - If device exists (same hostname+IP): Updates ISE metadata, preserves discovery data
  - If device doesn't exist: Inserts new device
  - Handles `IntegrityError` gracefully if constraint violation occurs

## Results

### Before Cleanup
- **Total devices**: 14
- **Duplicates**: 4 hostname+IP combinations with 2 records each
  - `8Kv-1 @ 192.168.0.134`
  - `C9200L @ 192.168.0.33`
  - `CSRv33 @ 192.168.30.133`
  - `FPR1010 @ 192.168.0.151`

### After Cleanup
- **Total devices**: 10
- **Duplicates removed**: 4
- **Unique constraint**: ✅ Active
- **Verification**: ✅ All 10 devices have unique hostname+IP combinations

## Usage

### Cleanup Existing Duplicates
```bash
# Dry run (see what would be deleted)
python scripts/cleanup_duplicate_devices.py --dry-run

# Actual cleanup
python scripts/cleanup_duplicate_devices.py
```

### Add Unique Constraint (if not already done)
```bash
# Will fail if duplicates exist - run cleanup first!
python scripts/migrations/migration_add_device_unique_constraint.py
```

## Future Protection

The unique constraint prevents new duplicates from being inserted:
- **Database level**: `UNIQUE(hostname, ip_address)` constraint
- **Application level**: Sync logic checks for duplicates before insert
- **Error handling**: Gracefully handles constraint violations

## Notes

- The cleanup script prioritizes **discovered devices** (those with platform/version data) over ISE-only records
- If a device is discovered via SSH, that record is kept even if a newer ISE sync has a different `ise_id`
- The sync logic now updates ISE metadata on existing devices without overwriting discovery data









