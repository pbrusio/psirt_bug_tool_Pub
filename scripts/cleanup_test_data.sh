#!/bin/bash
# Cleanup test data from vulnerability_db.sqlite before committing
#
# This script removes dynamic/test data while preserving the core vulnerability database:
# - device_inventory: Test devices synced from ISE or discovered via SSH
# - scan_results: Vulnerability scan results from testing
#
# Usage: ./scripts/cleanup_test_data.sh

set -e

DB_PATH="vulnerability_db.sqlite"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Check if database exists
if [ ! -f "$DB_PATH" ]; then
    echo "Database not found: $DB_PATH"
    echo "Run from project root directory."
    exit 1
fi

echo ""
echo "=========================================="
echo "  Cleanup Test Data from Database"
echo "=========================================="
echo ""

# Show current counts
echo "Current data:"
echo -n "  - device_inventory: "
sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM device_inventory;" 2>/dev/null || echo "0 (table doesn't exist)"
echo -n "  - scan_results: "
sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM scan_results;" 2>/dev/null || echo "0 (table doesn't exist)"
echo ""

# Confirm
read -p "Delete all test data and VACUUM? (y/N) " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 0
fi

echo ""
echo "Cleaning up..."

# Delete test data
sqlite3 "$DB_PATH" <<EOF
-- Clear device inventory (test devices)
DELETE FROM device_inventory;

-- Clear scan results (test scans)
DELETE FROM scan_results;

-- Reclaim disk space
VACUUM;
EOF

echo -e "${GREEN}Done!${NC}"
echo ""

# Show database size
SIZE=$(du -h "$DB_PATH" | cut -f1)
echo "Database size: $SIZE"

# Show preserved data
echo ""
echo "Preserved vulnerability data:"
echo -n "  - vulnerabilities: "
sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM vulnerabilities;"
echo ""
echo -e "${YELLOW}Note:${NC} WAL/SHM files may still exist until the database is closed."
echo "      They are gitignored and won't be committed."
echo ""
