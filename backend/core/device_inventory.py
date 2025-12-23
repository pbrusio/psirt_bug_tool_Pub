"""
Device Inventory Management

Manages network device inventory synced from ISE and enriched via SSH discovery.
Provides caching layer for device metadata and vulnerability scanning.
"""

import sqlite3
import json
import logging
from typing import List, Dict, Optional
from datetime import datetime
from pathlib import Path

# Import existing SSH extraction functionality
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from extract_device_features import extract_from_live_device

# Use SafeSQLiteConnection for resilient DB access
from backend.db.utils import get_db_connection

logger = logging.getLogger(__name__)


class DeviceInventoryManager:
    """Manages device inventory database operations"""

    def __init__(self, db_path: str = "vulnerability_db.sqlite"):
        """Initialize inventory manager"""
        self.db_path = db_path
        logger.info(f"DeviceInventoryManager initialized with DB: {db_path}")

    def _get_connection(self):
        """Get database connection using SafeSQLiteConnection context manager"""
        return get_db_connection(self.db_path)

    def sync_from_ise(self, ise_devices: List[Dict]) -> Dict:
        """
        Sync devices from ISE into inventory.

        Args:
            ise_devices: List of device dicts from ISE API

        Returns:
            dict: Sync summary
        """
        added = 0
        updated = 0
        errors = []

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                for device in ise_devices:
                    # Extract primary IP
                    ip_addresses = device.get('ip_addresses', [])
                    primary_ip = ip_addresses[0] if ip_addresses else None

                    if not primary_ip:
                        errors.append(f"Device {device.get('hostname')} has no IP address")
                        continue

                    hostname = device.get('hostname')
                    ise_id = device.get('ise_id')

                    # Check if device exists by hostname+IP (primary check for duplicates)
                    cursor.execute('''
                        SELECT id, ise_id FROM device_inventory
                        WHERE hostname = ? AND ip_address = ?
                    ''', (hostname, primary_ip))
                    existing = cursor.fetchone()

                    if existing:
                        existing_id, existing_ise_id = existing

                        # Update existing device (preserve discovery data if present)
                        cursor.execute('''
                            UPDATE device_inventory
                            SET ise_id = ?,
                                location = ?,
                                device_type = ?,
                                ise_sync_time = ?,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE id = ?
                        ''', (
                            ise_id,  # Update ISE ID if it changed
                            device.get('location'),
                            device.get('device_type'),
                            device.get('ise_sync_time'),
                            existing_id
                        ))
                        updated += 1
                        logger.debug(f"Updated existing device: {hostname} @ {primary_ip} (ID: {existing_id})")
                    else:
                        # Check if ISE ID already exists (different hostname/IP - shouldn't happen but handle it)
                        if ise_id:
                            cursor.execute('SELECT id FROM device_inventory WHERE ise_id = ?', (ise_id,))
                            ise_duplicate = cursor.fetchone()

                            if ise_duplicate:
                                # ISE ID exists but hostname/IP different - update that record instead
                                logger.warning(f"ISE ID {ise_id} exists with different hostname/IP, updating existing record")
                                cursor.execute('''
                                    UPDATE device_inventory
                                    SET hostname = ?,
                                        ip_address = ?,
                                        location = ?,
                                        device_type = ?,
                                        ise_sync_time = ?,
                                        updated_at = CURRENT_TIMESTAMP
                                    WHERE ise_id = ?
                                ''', (
                                    hostname,
                                    primary_ip,
                                    device.get('location'),
                                    device.get('device_type'),
                                    device.get('ise_sync_time'),
                                    ise_id
                                ))
                                updated += 1
                                continue

                        # Insert new device
                        try:
                            cursor.execute('''
                                INSERT INTO device_inventory (
                                    ise_id, hostname, ip_address, location, device_type,
                                    ise_sync_time, discovery_status
                                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                            ''', (
                                ise_id,
                                hostname,
                                primary_ip,
                                device.get('location'),
                                device.get('device_type'),
                                device.get('ise_sync_time'),
                                'pending'  # Needs SSH discovery
                            ))
                            added += 1
                            logger.debug(f"Added new device: {hostname} @ {primary_ip}")
                        except sqlite3.IntegrityError as e:
                            # Unique constraint violation - device with same hostname+IP exists
                            # This shouldn't happen if our check above worked, but handle it gracefully
                            errors.append(f"Duplicate device {hostname} @ {primary_ip} (constraint violation)")
                            logger.warning(f"Integrity error for {hostname} @ {primary_ip}: {e}")
                            continue

                # Note: commit is automatic on successful context manager exit

            summary = {
                'success': True,
                'devices_added': added,
                'devices_updated': updated,
                'total_processed': len(ise_devices),
                'errors': errors,
                'timestamp': datetime.now().isoformat()
            }

            logger.info(f"ISE sync complete: {added} added, {updated} updated")
            return summary

        except Exception as e:
            logger.error(f"ISE sync failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'devices_added': added,
                'devices_updated': updated,
                'errors': errors
            }

    def discover_device_via_ssh(
        self,
        device_id: int,
        ssh_credentials: Dict
    ) -> Dict:
        """
        Discover device details via SSH and update inventory.

        Args:
            device_id: Device inventory ID
            ssh_credentials: {host, username, password, device_type}

        Returns:
            dict: Discovery result including version change detection
        """
        # First, get device info including previous version for change detection
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM device_inventory WHERE id = ?', (device_id,))
            device = cursor.fetchone()

        if not device:
            return {'success': False, 'error': 'Device not found'}

        # Store previous values for change detection
        previous_version = device['version']
        previous_platform = device['platform']

        logger.info(f"Discovering device {device['hostname']} via SSH...")

        try:
            # Use extract_from_live_device to get all device info
            snapshot = extract_from_live_device(
                host=ssh_credentials.get('host', device['ip_address']),
                username=ssh_credentials['username'],
                password=ssh_credentials['password'],
                device_type=ssh_credentials.get('device_type', 'cisco_ios')
            )

            # Extract data from snapshot
            platform = snapshot.get('platform', '')
            version = snapshot.get('version', '')
            hardware_model = snapshot.get('hardware_model', '')
            serial_number = snapshot.get('serial', '')
            uptime = snapshot.get('uptime', '')
            features = snapshot.get('features_present', [])  # Fixed: was 'detected_features'

            # Update database with success
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE device_inventory
                    SET platform = ?,
                        version = ?,
                        hardware_model = ?,
                        serial_number = ?,
                        uptime = ?,
                        features = ?,
                        ssh_discovery_time = ?,
                        discovery_status = ?,
                        discovery_error = NULL,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (
                    platform,
                    version,
                    hardware_model,
                    serial_number,
                    uptime,
                    json.dumps(features),  # Store features as JSON
                    datetime.now().isoformat(),
                    'success',
                    device_id
                ))

            # Detect version change
            version_changed = previous_version and previous_version != version
            platform_changed = previous_platform and previous_platform != platform

            result = {
                'success': True,
                'device_id': device_id,
                'hostname': device['hostname'],
                'platform': platform,
                'version': version,
                'hardware_model': hardware_model,
                'features_detected': len(features),
                'features': features,
                # Version change detection
                'version_changed': version_changed,
                'previous_version': previous_version if version_changed else None,
                'version_change_message': f"Version updated: {previous_version} → {version}" if version_changed else None,
                'platform_changed': platform_changed,
                'previous_platform': previous_platform if platform_changed else None,
            }

            if version_changed:
                logger.info(f"Device {device['hostname']} version changed: {previous_version} → {version}")
            logger.info(f"Device discovery successful: {device['hostname']}")
            return result

        except Exception as e:
            # Mark discovery as failed
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE device_inventory
                    SET discovery_status = ?,
                        discovery_error = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', ('failed', str(e), device_id))

            logger.error(f"Device discovery failed for device {device_id}: {e}")
            return {
                'success': False,
                'device_id': device_id,
                'error': str(e)
            }

    def get_all_devices(
        self,
        platform: Optional[str] = None,
        location: Optional[str] = None,
        discovery_status: Optional[str] = None
    ) -> List[Dict]:
        """
        Get all devices from inventory with optional filters.

        Args:
            platform: Filter by platform (e.g., "IOS-XE")
            location: Filter by location
            discovery_status: Filter by status ("success", "failed", "pending")

        Returns:
            list: Device records
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            query = 'SELECT * FROM device_inventory WHERE 1=1'
            params = []

            if platform:
                query += ' AND platform = ?'
                params.append(platform)

            if location:
                query += ' AND location LIKE ?'
                params.append(f'%{location}%')

            if discovery_status:
                query += ' AND discovery_status = ?'
                params.append(discovery_status)

            query += ' ORDER BY hostname'

            cursor.execute(query, params)
            rows = cursor.fetchall()

            devices = [dict(row) for row in rows]

        return devices

    def get_device_by_ip(self, ip_address: str) -> Optional[Dict]:
        """Get device by IP address"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM device_inventory WHERE ip_address = ?', (ip_address,))
            row = cursor.fetchone()

        if row:
            return dict(row)
        return None

    def get_device_by_hostname(self, hostname: str) -> Optional[Dict]:
        """Get device by hostname"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM device_inventory WHERE hostname = ?', (hostname,))
            row = cursor.fetchone()

        if row:
            return dict(row)
        return None

    def add_device(
        self,
        hostname: str,
        ip_address: str,
        platform: Optional[str] = None,
        version: Optional[str] = None,
        hardware_model: Optional[str] = None,
        location: Optional[str] = None,
        device_type: Optional[str] = "cisco_ios",
        discovery_status: str = "pending",
        source: str = "manual"
    ) -> int:
        """
        Add a device to inventory.

        Args:
            hostname: Device hostname
            ip_address: Device IP address
            platform: Platform (IOS-XE, IOS-XR, ASA, FTD, NX-OS)
            version: Software version
            hardware_model: Hardware model (e.g., Cat9300)
            location: Physical location
            device_type: SSH device type (for netmiko)
            discovery_status: Status - 'pending', 'manual', 'success', 'failed'
            source: How device was added - 'manual', 'ise', 'unknown'

        Returns:
            device_id of created device
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO device_inventory
                (hostname, ip_address, platform, version, hardware_model,
                 location, device_type, discovery_status, source, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                hostname, ip_address, platform, version, hardware_model,
                location, device_type, discovery_status, source,
                datetime.now().isoformat(), datetime.now().isoformat()
            ))
            device_id = cursor.lastrowid

        logger.info(f"Added device: {hostname} @ {ip_address} (ID: {device_id}, source: {source})")
        return device_id

    def delete_device(self, device_id: int) -> Dict[str, int]:
        """
        Delete a device and all associated data.

        Args:
            device_id: Device ID to delete

        Returns:
            Dict with counts of deleted records
        """
        deleted = {'device': 0, 'scan_results': 0}

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Delete scan results first (foreign key would block otherwise)
            cursor.execute('DELETE FROM scan_results WHERE device_id = ?', (device_id,))
            deleted['scan_results'] = cursor.rowcount

            # Delete device
            cursor.execute('DELETE FROM device_inventory WHERE id = ?', (device_id,))
            deleted['device'] = cursor.rowcount

        logger.info(f"Deleted device {device_id}: {deleted['device']} device, {deleted['scan_results']} scan results")
        return deleted

    def update_device(
        self,
        device_id: int,
        hostname: str,
        ip_address: str,
        platform: Optional[str] = None,
        version: Optional[str] = None,
        hardware_model: Optional[str] = None,
        location: Optional[str] = None,
        device_type: Optional[str] = None,
        discovery_status: Optional[str] = None,
        source: Optional[str] = None
    ) -> bool:
        """
        Update an existing device in inventory.

        Args:
            device_id: Device ID to update
            hostname: Device hostname
            ip_address: Device IP address
            platform: Platform (IOS-XE, IOS-XR, ASA, FTD, NX-OS)
            version: Software version
            hardware_model: Hardware model (e.g., Cat9300)
            location: Physical location
            device_type: SSH device type (for netmiko)
            discovery_status: Status - 'pending', 'manual', 'success', 'failed'
            source: How device was added - 'manual', 'ise', 'unknown'

        Returns:
            True if updated successfully
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE device_inventory
                SET hostname = ?,
                    ip_address = ?,
                    platform = COALESCE(?, platform),
                    version = COALESCE(?, version),
                    hardware_model = COALESCE(?, hardware_model),
                    location = COALESCE(?, location),
                    device_type = COALESCE(?, device_type),
                    discovery_status = COALESCE(?, discovery_status),
                    source = COALESCE(?, source),
                    updated_at = ?
                WHERE id = ?
            ''', (
                hostname, ip_address, platform, version, hardware_model,
                location, device_type, discovery_status, source,
                datetime.now().isoformat(), device_id
            ))

        logger.info(f"Updated device {device_id}: {hostname} @ {ip_address}")
        return True

    def get_device_by_id(self, device_id: int) -> Optional[Dict]:
        """
        Get device by ID with parsed features.

        Args:
            device_id: Device inventory ID

        Returns:
            Device dict with features parsed from JSON, or None if not found
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM device_inventory WHERE id = ?', (device_id,))
            row = cursor.fetchone()

        if row:
            device = dict(row)
            # Parse features JSON
            if device.get('features'):
                try:
                    device['features'] = json.loads(device['features'])
                except json.JSONDecodeError:
                    device['features'] = []
            else:
                device['features'] = []
            return device
        return None

    def update_scan_results(
        self,
        device_id: int,
        scan_result: Dict
    ):
        """
        Update device with latest vulnerability scan results.

        Implements rotation: current → previous, new → current
        This supports before/after comparison for change validation.

        Args:
            device_id: Device inventory ID
            scan_result: Full scan result from vulnerability scanner
                {
                    'scan_id': str,
                    'platform': str,
                    'version': str,
                    'hardware_model': str,
                    'features': list,
                    'total_bugs_checked': int,
                    'version_matches': int,
                    'hardware_filtered': int,
                    'feature_filtered': int,
                    'critical_high': int,
                    'medium_low': int,
                    'vulnerabilities': list,
                    'timestamp': datetime,
                    'query_time_ms': float
                }
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # First, get current scan to rotate to previous
                cursor.execute('''
                    SELECT last_scan_result, last_scan_id, last_scan_timestamp
                    FROM device_inventory
                    WHERE id = ?
                ''', (device_id,))

                row = cursor.fetchone()
                if row:
                    current_result = row['last_scan_result']
                    current_id = row['last_scan_id']
                    current_timestamp = row['last_scan_timestamp']
                else:
                    current_result = None
                    current_id = None
                    current_timestamp = None

                # Prepare new scan data
                scan_id = scan_result.get('scan_id')
                scan_timestamp = scan_result.get('timestamp')
                if isinstance(scan_timestamp, datetime):
                    scan_timestamp = scan_timestamp.isoformat()

                # Create compact summary for storage
                # Note: Scanner returns both bugs and PSIRTs with version+feature filtering
                scan_summary = {
                    'scan_id': scan_id,
                    'timestamp': scan_timestamp,
                    'platform': scan_result.get('platform'),
                    'version': scan_result.get('version'),
                    'hardware_model': scan_result.get('hardware_model'),
                    'total_bugs_checked': scan_result.get('total_bugs_checked'),
                    'version_matches': scan_result.get('version_matches'),
                    'hardware_filtered': scan_result.get('hardware_filtered'),
                    'feature_filtered': scan_result.get('feature_filtered'),
                    # Bug counts (from vuln_type='bug')
                    'total_bugs': scan_result.get('bug_count', len(scan_result.get('bugs', []))),
                    'bug_critical_high': scan_result.get('bug_critical_high', 0),
                    # PSIRT counts (from vuln_type='psirt') - properly filtered by version+features
                    'total_psirts': scan_result.get('psirt_count', 0),
                    'psirt_critical_high': scan_result.get('psirt_critical_high', 0),
                    # Combined totals (for backward compatibility)
                    'critical_high': scan_result.get('critical_high', 0),
                    'medium_low': scan_result.get('medium_low', 0),
                    'query_time_ms': scan_result.get('query_time_ms')
                }

                # Update with rotation: current → previous, new → current
                cursor.execute('''
                    UPDATE device_inventory
                    SET last_scan_result = ?,
                        last_scan_id = ?,
                        last_scan_timestamp = ?,
                        previous_scan_result = ?,
                        previous_scan_id = ?,
                        previous_scan_timestamp = ?,
                        last_scanned = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (
                    json.dumps(scan_summary),  # New scan → current
                    scan_id,
                    scan_timestamp,
                    current_result,  # Old current → previous
                    current_id,
                    current_timestamp,
                    datetime.now().isoformat(),
                    device_id
                ))

                # Note: commit is automatic on successful context manager exit

            logger.info(
                f"Updated scan results for device {device_id}: "
                f"scan_id={scan_id}, {scan_summary['total_bugs']} vulnerabilities"
            )

        except Exception as e:
            logger.error(f"Failed to update scan results for device {device_id}: {e}")
            raise

    def get_inventory_stats(self) -> Dict:
        """Get inventory statistics"""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Total devices
            cursor.execute('SELECT COUNT(*) FROM device_inventory')
            total = cursor.fetchone()[0]

            # By discovery status
            cursor.execute('''
                SELECT discovery_status, COUNT(*)
                FROM device_inventory
                GROUP BY discovery_status
            ''')
            status_counts = dict(cursor.fetchall())

            # By platform
            cursor.execute('''
                SELECT platform, COUNT(*)
                FROM device_inventory
                WHERE platform IS NOT NULL
                GROUP BY platform
            ''')
            platform_counts = dict(cursor.fetchall())

            # Devices needing scan (never scanned or scanned >30 days ago)
            cursor.execute('''
                SELECT COUNT(*)
                FROM device_inventory
                WHERE last_scanned IS NULL
                   OR last_scanned < datetime('now', '-30 days')
            ''')
            needs_scan = cursor.fetchone()[0]

        return {
            'total_devices': total,
            'by_status': status_counts,
            'by_platform': platform_counts,
            'needs_scan': needs_scan
        }


# Singleton instance
_inventory_manager = None

def get_inventory_manager() -> DeviceInventoryManager:
    """Get or create inventory manager singleton"""
    global _inventory_manager
    if _inventory_manager is None:
        _inventory_manager = DeviceInventoryManager()
    return _inventory_manager
