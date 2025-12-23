"""
API Routes for Device Inventory Management

Provides endpoints for:
- ISE synchronization
- Device discovery (SSH)
- Inventory listing and filtering
- Bulk bug scanning
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, status, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import logging
import sqlite3
import traceback
import csv
import io
import uuid

# Import inventory components
from ..core.device_inventory import get_inventory_manager
from ..core.ise_client_mock import MockISEClient  # Use mock for now
# When ISE is ready: from ..core.ise_client import ISEClient

logger = logging.getLogger(__name__)


def handle_db_error(e: Exception, operation: str) -> HTTPException:
    """Handle database errors with appropriate status codes"""
    error_msg = str(e).lower()

    # Database is locked/busy - return 503 (Service Unavailable)
    if isinstance(e, sqlite3.OperationalError):
        if 'locked' in error_msg or 'busy' in error_msg:
            logger.error(f"{operation} - DB locked: {e}\n{traceback.format_exc()}")
            return HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database is busy, please retry in a moment"
            )
        else:
            logger.error(f"{operation} - DB error: {e}\n{traceback.format_exc()}")
            return HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Database error: {str(e)}"
            )

    # General error - return 500
    logger.error(f"{operation} failed: {e}\n{traceback.format_exc()}")
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"{operation} failed: {str(e)}"
    )

router = APIRouter(prefix="/api/v1/inventory", tags=["inventory"])


# ============================================================================
# Request/Response Models
# ============================================================================

class ISESyncRequest(BaseModel):
    """Request to sync devices from ISE"""
    max_devices: Optional[int] = None  # Limit devices synced
    use_mock: bool = True  # Use mock ISE client for development
    # ISE connection details (required when use_mock=False)
    ise_host: Optional[str] = None
    ise_username: Optional[str] = None
    ise_password: Optional[str] = None


class DeviceDiscoveryRequest(BaseModel):
    """Request to discover device via SSH"""
    device_id: int
    username: str
    password: str
    device_type: str = "cisco_ios"  # cisco_ios, cisco_xe, cisco_xr, cisco_asa


class InventoryFilterRequest(BaseModel):
    """Filter options for inventory listing"""
    platform: Optional[str] = None
    location: Optional[str] = None
    discovery_status: Optional[str] = None  # success, failed, pending


class BulkScanRequest(BaseModel):
    """Request to scan multiple devices"""
    device_ids: Optional[List[int]] = None  # Specific devices, or None for all
    platforms: Optional[List[str]] = None  # Filter by platforms


class AddDeviceRequest(BaseModel):
    """Request to manually add a device to inventory"""
    hostname: str
    ip_address: str
    platform: Optional[str] = None      # IOS-XE, IOS-XR, ASA, FTD, NX-OS
    version: Optional[str] = None       # e.g., "17.9.4"
    hardware_model: Optional[str] = None  # e.g., "Cat9300"
    location: Optional[str] = None      # e.g., "Building A, Floor 2"
    device_type: Optional[str] = "cisco_ios"  # For SSH discovery later


class CSVImportResponse(BaseModel):
    """Response from CSV import"""
    success: bool
    total_rows: int
    imported: int
    updated: int
    skipped: int
    errors: List[str]


# ============================================================================
# Background Job Store for Bulk Scans
# ============================================================================

# In-memory job store for tracking bulk scan progress
# Note: This is reset on server restart. For production, consider Redis/DB.
_bulk_scan_jobs: Dict[str, Dict] = {}


def _run_bulk_scan(
    job_id: str,
    devices: List[Dict],
    db_path: str = "vulnerability_db.sqlite"
):
    """
    Background task to scan multiple devices.

    Updates _bulk_scan_jobs with progress as devices are scanned.
    """
    import json
    from datetime import datetime
    from ..core.vulnerability_scanner import VulnerabilityScanner

    try:
        inventory = get_inventory_manager()
        scanner = VulnerabilityScanner(db_path=db_path)

        scan_results = []
        scanned_count = 0
        failed_count = 0
        total_bugs = 0
        critical_high_total = 0
        medium_low_total = 0

        # Update job status to running
        _bulk_scan_jobs[job_id] = {
            'status': 'running',
            'total_devices': len(devices),
            'scanned': 0,
            'failed': 0,
            'current_device': None,
            'progress_percent': 0,
            'scan_results': [],
            'summary': {},
            'started_at': datetime.now().isoformat(),
            'completed_at': None,
            'error': None
        }

        for idx, device in enumerate(devices):
            device_result = {
                'device_id': device['id'],
                'hostname': device['hostname'],
                'ip_address': device.get('ip_address'),
                'platform': device['platform'],
                'version': device['version'],
                'hardware_model': device.get('hardware_model'),
                'progress': f"{idx + 1}/{len(devices)}"
            }

            # Update progress
            _bulk_scan_jobs[job_id]['current_device'] = device['hostname']
            _bulk_scan_jobs[job_id]['progress_percent'] = int((idx / len(devices)) * 100)

            # Skip devices that haven't been discovered
            if not device.get('platform') or not device.get('version'):
                device_result['scan_status'] = 'skipped'
                device_result['error'] = 'Device not fully discovered (missing platform or version)'
                failed_count += 1
                scan_results.append(device_result)
                _bulk_scan_jobs[job_id]['failed'] = failed_count
                _bulk_scan_jobs[job_id]['scan_results'] = scan_results
                continue

            try:
                # Parse features from JSON if available
                features = []
                if device.get('features'):
                    try:
                        features = json.loads(device['features'])
                    except json.JSONDecodeError:
                        features = []

                # Run vulnerability scan
                result = scanner.scan_device(
                    platform=device['platform'],
                    version=device['version'],
                    labels=features,
                    hardware_model=device.get('hardware_model')
                )

                # Save scan results to inventory
                inventory.update_scan_results(device['id'], result)

                # Save full results to scan_results table
                _save_full_scan_results(device['id'], result)

                # Aggregate stats
                device_result['scan_status'] = 'success'
                device_result['scan_id'] = result['scan_id']
                device_result['total_bugs'] = len(result['bugs'])
                device_result['critical_high'] = result['critical_high']
                device_result['medium_low'] = result['medium_low']
                device_result['query_time_ms'] = result['query_time_ms']

                scanned_count += 1
                total_bugs += len(result['bugs'])
                critical_high_total += result['critical_high']
                medium_low_total += result['medium_low']

            except Exception as e:
                device_result['scan_status'] = 'failed'
                device_result['error'] = str(e)
                failed_count += 1
                logger.error(f"Scan failed for device {device['hostname']}: {e}")

            scan_results.append(device_result)

            # Update job progress
            _bulk_scan_jobs[job_id]['scanned'] = scanned_count
            _bulk_scan_jobs[job_id]['failed'] = failed_count
            _bulk_scan_jobs[job_id]['scan_results'] = scan_results

        # Mark job as completed
        _bulk_scan_jobs[job_id].update({
            'status': 'completed',
            'progress_percent': 100,
            'current_device': None,
            'completed_at': datetime.now().isoformat(),
            'summary': {
                'total_bugs': total_bugs,
                'critical_high': critical_high_total,
                'medium_low': medium_low_total,
                'devices_with_critical': sum(1 for r in scan_results if r.get('critical_high', 0) > 0)
            }
        })

        logger.info(f"Bulk scan {job_id} completed: {scanned_count} scanned, {failed_count} failed")

    except Exception as e:
        logger.error(f"Bulk scan {job_id} failed: {e}\n{traceback.format_exc()}")
        _bulk_scan_jobs[job_id].update({
            'status': 'failed',
            'error': str(e),
            'completed_at': datetime.now().isoformat()
        })


# ============================================================================
# ISE Sync Endpoints
# ============================================================================

@router.post("/sync-ise")
async def sync_from_ise(
    request: ISESyncRequest,
    background_tasks: BackgroundTasks
):
    """
    Sync network devices from ISE.

    This pulls device inventory from ISE ERS API and caches it in the database.
    Devices will be marked as "pending" until SSH discovery is run.

    Args:
        request: ISE sync configuration

    Returns:
        Sync summary with device list

    Example:
        POST /api/v1/inventory/sync-ise
        {
            "max_devices": 100,
            "use_mock": true
        }
    """
    try:
        # Initialize ISE client (mock or real)
        if request.use_mock:
            logger.info("Using Mock ISE client (Lab Devices)")
            ise_client = MockISEClient(
                host="lab-devices",
                username="mock",
                password="mock"
            )
        else:
            # Validate ISE credentials provided
            if not request.ise_host or not request.ise_username or not request.ise_password:
                raise HTTPException(
                    status_code=400, 
                    detail="ISE credentials required: ise_host, ise_username, ise_password"
                )
            
            logger.info(f"Using Real ISE client: {request.ise_host}")
            from ..core.ise_client import ISEClient
            ise_client = ISEClient(
                host=request.ise_host,
                username=request.ise_username,
                password=request.ise_password
            )

        # Sync devices from ISE
        ise_result = ise_client.sync_devices(max_devices=request.max_devices)

        if not ise_result['success']:
            raise HTTPException(status_code=500, detail=f"ISE sync failed: {ise_result.get('error')}")

        # Store devices in inventory database
        inventory = get_inventory_manager()
        db_result = inventory.sync_from_ise(ise_result['devices'])

        return {
            'success': True,
            'ise_host': ise_result['ise_host'],
            'devices_from_ise': ise_result['total_devices'],
            'devices_added': db_result['devices_added'],
            'devices_updated': db_result['devices_updated'],
            'sync_time': ise_result['sync_time'],
            'mock_data': ise_result.get('mock', False)
        }

    except HTTPException:
        raise
    except sqlite3.OperationalError as e:
        raise handle_db_error(e, "ISE sync")
    except Exception as e:
        raise handle_db_error(e, "ISE sync")


# ============================================================================
# Device Discovery Endpoints
# ============================================================================

@router.post("/discover-device")
async def discover_device(request: DeviceDiscoveryRequest):
    """
    Discover device details via SSH.

    Connects to device, runs "show version" and extracts config to detect:
    - Platform (IOS-XE, IOS-XR, ASA, etc.)
    - Software version
    - Hardware model
    - Configured features

    Args:
        request: Device ID and SSH credentials

    Returns:
        Discovery result

    Example:
        POST /api/v1/inventory/discover-device
        {
            "device_id": 1,
            "username": "admin",
            "password": "Pa22word",
            "device_type": "cisco_ios"
        }
    """
    try:
        inventory = get_inventory_manager()

        result = inventory.discover_device_via_ssh(
            device_id=request.device_id,
            ssh_credentials={
                'username': request.username,
                'password': request.password,
                'device_type': request.device_type
            }
        )

        if not result['success']:
            # Return failure result so frontend can display the error
            return result

        return result

    except HTTPException:
        raise
    except sqlite3.OperationalError as e:
        raise handle_db_error(e, "Device discovery")
    except Exception as e:
        raise handle_db_error(e, "Device discovery")


# ============================================================================
# Device Management Endpoints
# ============================================================================

@router.post("/devices")
async def add_device(request: AddDeviceRequest):
    """
    Add or update a single device in inventory (upsert).

    If device with same IP or hostname exists, it will be updated.
    Device will be marked as 'pending' if platform/version not provided,
    or 'manual' if fully specified. Use /discover-device to populate
    details via SSH.

    Args:
        request: Device details

    Returns:
        Created/updated device with ID

    Example:
        POST /api/v1/inventory/devices
        {
            "hostname": "core-sw-01",
            "ip_address": "10.1.1.1",
            "platform": "IOS-XE",
            "version": "17.9.4",
            "hardware_model": "Cat9300",
            "location": "DC1-Rack-A1"
        }
    """
    try:
        inventory = get_inventory_manager()

        # Check for existing device by IP or hostname
        existing_by_ip = inventory.get_device_by_ip(request.ip_address)
        existing_by_hostname = inventory.get_device_by_hostname(request.hostname)

        # Determine discovery status
        if request.platform and request.version:
            discovery_status = "manual"  # Fully specified, ready to scan
        else:
            discovery_status = "pending"  # Needs SSH discovery

        # Upsert logic
        if existing_by_ip or existing_by_hostname:
            # Update existing device
            existing = existing_by_ip or existing_by_hostname
            device_id = existing['id']

            updated = inventory.update_device(
                device_id=device_id,
                hostname=request.hostname,
                ip_address=request.ip_address,
                platform=request.platform,
                version=request.version,
                hardware_model=request.hardware_model,
                location=request.location,
                device_type=request.device_type,
                discovery_status=discovery_status,
                source="manual"
            )

            return {
                'success': True,
                'device_id': device_id,
                'hostname': request.hostname,
                'ip_address': request.ip_address,
                'discovery_status': discovery_status,
                'action': 'updated',
                'message': f"Device updated. {'Ready to scan.' if discovery_status == 'manual' else 'Run discovery to populate platform/version.'}"
            }
        else:
            # Insert new device
            device_id = inventory.add_device(
                hostname=request.hostname,
                ip_address=request.ip_address,
                platform=request.platform,
                version=request.version,
                hardware_model=request.hardware_model,
                location=request.location,
                device_type=request.device_type,
                discovery_status=discovery_status,
                source="manual"
            )

            return {
                'success': True,
                'device_id': device_id,
                'hostname': request.hostname,
                'ip_address': request.ip_address,
                'discovery_status': discovery_status,
                'action': 'created',
                'message': f"Device added. {'Ready to scan.' if discovery_status == 'manual' else 'Run discovery to populate platform/version.'}"
            }

    except Exception as e:
        raise handle_db_error(e, "Add/update device")


# ============================================================================
# Inventory Listing Endpoints
# ============================================================================

@router.get("/devices")
async def get_devices(
    platform: Optional[str] = None,
    location: Optional[str] = None,
    discovery_status: Optional[str] = None
):
    """
    Get all devices from inventory with optional filters.

    Args:
        platform: Filter by platform (e.g., "IOS-XE")
        location: Filter by location (substring match)
        discovery_status: Filter by status ("success", "failed", "pending")

    Returns:
        List of devices

    Example:
        GET /api/v1/inventory/devices?platform=IOS-XE&discovery_status=success
    """
    try:
        inventory = get_inventory_manager()

        devices = inventory.get_all_devices(
            platform=platform,
            location=location,
            discovery_status=discovery_status
        )

        return {
            'success': True,
            'total_devices': len(devices),
            'devices': devices
        }

    except sqlite3.OperationalError as e:
        raise handle_db_error(e, "Get devices")
    except Exception as e:
        raise handle_db_error(e, "Get devices")


@router.get("/devices/template")
async def download_device_template():
    """
    Download CSV template for bulk device import.

    Returns a CSV file with headers for all supported fields.
    Required fields: hostname, ip_address
    Optional fields: platform, version, hardware_model, location

    Example:
        GET /api/v1/inventory/devices/template

    Returns:
        CSV file download with headers and example row
    """
    # Create CSV content
    output = io.StringIO()
    writer = csv.writer(output)

    # Write header row
    headers = ['hostname', 'ip_address', 'platform', 'version', 'hardware_model', 'location']
    writer.writerow(headers)

    # Write example row
    example = ['core-switch-01', '10.1.1.1', 'IOS-XE', '17.9.4', 'Cat9300', 'DC1-Rack-A1']
    writer.writerow(example)

    # Add a comment row with field descriptions
    writer.writerow([])
    writer.writerow(['# Field Descriptions:'])
    writer.writerow(['# hostname (required) - Device hostname'])
    writer.writerow(['# ip_address (required) - Device IP address'])
    writer.writerow(['# platform (optional) - IOS-XE, IOS-XR, ASA, FTD, or NX-OS'])
    writer.writerow(['# version (optional) - Software version (e.g., 17.9.4)'])
    writer.writerow(['# hardware_model (optional) - Hardware model (e.g., Cat9300, ASR9K)'])
    writer.writerow(['# location (optional) - Physical location'])

    # Reset to beginning
    output.seek(0)

    # Return as downloadable file
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=device_import_template.csv"}
    )


@router.post("/devices/import", response_model=CSVImportResponse)
async def import_devices_csv(file: UploadFile = File(...)):
    """
    Import devices from CSV file (bulk upsert).

    If a device with the same IP or hostname exists, it will be updated.
    Otherwise, a new device will be created.

    Expected CSV format:
    - Header row required
    - Required columns: hostname, ip_address
    - Optional columns: platform, version, hardware_model, location

    Args:
        file: CSV file upload

    Returns:
        CSVImportResponse with counts and any errors

    Example:
        POST /api/v1/inventory/devices/import
        Content-Type: multipart/form-data
        file: (CSV file)
    """
    # Validate file type
    if not file.filename.endswith('.csv'):
        raise HTTPException(
            status_code=400,
            detail="File must be a CSV file (.csv extension)"
        )

    try:
        # Read file content
        content = await file.read()
        text_content = content.decode('utf-8')

        # Parse CSV
        reader = csv.DictReader(io.StringIO(text_content))

        # Validate headers
        required_fields = {'hostname', 'ip_address'}
        if not reader.fieldnames:
            raise HTTPException(status_code=400, detail="CSV file is empty or has no headers")

        headers_lower = {h.lower().strip() for h in reader.fieldnames}
        missing = required_fields - headers_lower
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"Missing required columns: {', '.join(missing)}"
            )

        # Create field mapping (handle case-insensitive headers)
        field_map = {}
        for h in reader.fieldnames:
            field_map[h] = h.lower().strip()

        inventory = get_inventory_manager()

        total_rows = 0
        imported = 0
        updated = 0
        skipped = 0
        errors = []

        for row_num, row in enumerate(reader, start=2):  # Start at 2 (header is row 1)
            total_rows += 1

            # Skip comment rows
            hostname_val = row.get('hostname', '').strip()
            if hostname_val.startswith('#'):
                skipped += 1
                continue

            # Extract and validate fields
            hostname = hostname_val
            ip_address = row.get('ip_address', '').strip()

            if not hostname or not ip_address:
                errors.append(f"Row {row_num}: Missing hostname or ip_address")
                skipped += 1
                continue

            # Optional fields
            platform = row.get('platform', '').strip() or None
            version = row.get('version', '').strip() or None
            hardware_model = row.get('hardware_model', '').strip() or None
            location = row.get('location', '').strip() or None

            # Validate platform if provided
            valid_platforms = {'IOS-XE', 'IOS-XR', 'ASA', 'FTD', 'NX-OS'}
            if platform and platform not in valid_platforms:
                errors.append(f"Row {row_num}: Invalid platform '{platform}'. Valid: {', '.join(valid_platforms)}")
                skipped += 1
                continue

            # Determine discovery status
            if platform and version:
                discovery_status = "manual"
            else:
                discovery_status = "pending"

            try:
                # Check for existing device (upsert logic)
                existing_by_ip = inventory.get_device_by_ip(ip_address)
                existing_by_hostname = inventory.get_device_by_hostname(hostname)

                if existing_by_ip or existing_by_hostname:
                    # Update existing device
                    existing = existing_by_ip or existing_by_hostname
                    inventory.update_device(
                        device_id=existing['id'],
                        hostname=hostname,
                        ip_address=ip_address,
                        platform=platform,
                        version=version,
                        hardware_model=hardware_model,
                        location=location,
                        discovery_status=discovery_status,
                        source="manual"
                    )
                    updated += 1
                else:
                    # Insert new device
                    inventory.add_device(
                        hostname=hostname,
                        ip_address=ip_address,
                        platform=platform,
                        version=version,
                        hardware_model=hardware_model,
                        location=location,
                        discovery_status=discovery_status,
                        source="manual"
                    )
                    imported += 1

            except Exception as e:
                errors.append(f"Row {row_num}: {str(e)}")
                skipped += 1

        logger.info(f"CSV import complete: {imported} imported, {updated} updated, {skipped} skipped")

        return CSVImportResponse(
            success=True,
            total_rows=total_rows,
            imported=imported,
            updated=updated,
            skipped=skipped,
            errors=errors[:10]  # Limit errors to first 10
        )

    except HTTPException:
        raise
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File encoding error. Please use UTF-8 encoded CSV.")
    except Exception as e:
        logger.error(f"CSV import failed: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"CSV import failed: {str(e)}")


@router.get("/devices/{device_id}")
async def get_device(device_id: int):
    """Get single device by ID"""
    try:
        inventory = get_inventory_manager()
        with inventory._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM device_inventory WHERE id = ?', (device_id,))
            row = cursor.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Device not found")

        return dict(row)

    except HTTPException:
        raise
    except sqlite3.OperationalError as e:
        raise handle_db_error(e, "Get device")
    except Exception as e:
        raise handle_db_error(e, "Get device")


@router.delete("/devices/{device_id}")
async def delete_device(device_id: int):
    """
    Delete a device from inventory.

    Also removes:
    - Associated scan results

    Args:
        device_id: Device inventory ID

    Returns:
        Confirmation message

    Example:
        DELETE /api/v1/inventory/devices/42
    """
    try:
        inventory = get_inventory_manager()

        # Check device exists
        with inventory._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT hostname FROM device_inventory WHERE id = ?', (device_id,))
            row = cursor.fetchone()

        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Device {device_id} not found"
            )

        hostname = row['hostname']

        # Delete device and associated data
        deleted = inventory.delete_device(device_id)

        return {
            'success': True,
            'device_id': device_id,
            'hostname': hostname,
            'message': f"Device '{hostname}' deleted successfully",
            'cleanup': deleted
        }

    except HTTPException:
        raise
    except Exception as e:
        raise handle_db_error(e, "Delete device")


@router.get("/stats")
async def get_inventory_stats():
    """
    Get inventory statistics.

    Returns:
        Statistics summary

    Example response:
        {
            "total_devices": 42,
            "by_status": {"success": 30, "pending": 10, "failed": 2},
            "by_platform": {"IOS-XE": 25, "IOS-XR": 10, "ASA": 7},
            "needs_scan": 15
        }
    """
    try:
        inventory = get_inventory_manager()
        stats = inventory.get_inventory_stats()

        return {
            'success': True,
            **stats
        }

    except sqlite3.OperationalError as e:
        raise handle_db_error(e, "Get stats")
    except Exception as e:
        raise handle_db_error(e, "Get stats")


# ============================================================================
# Helper Functions
# ============================================================================

def _save_full_scan_results(device_id: int, scan_result: Dict):
    """
    Save full scan results to scan_results table

    Args:
        device_id: Device inventory ID
        scan_result: Complete scan result dictionary
    """
    import json
    from datetime import datetime
    from ..db.utils import get_db_connection

    try:
        scan_id = scan_result.get('scan_id')
        timestamp = scan_result.get('timestamp')

        logger.debug(f"Saving scan results - scan_id={scan_id}, device_id={device_id}, timestamp={timestamp}")

        # Convert datetime to ISO string if needed
        if isinstance(timestamp, datetime):
            timestamp = timestamp.isoformat()
            # Update timestamp in scan_result dict before JSON serialization
            scan_result['timestamp'] = timestamp

        # Store full result as JSON
        full_result_json = json.dumps(scan_result)

        logger.debug(f"JSON length={len(full_result_json)}")

        # Use SafeSQLiteConnection
        with get_db_connection("vulnerability_db.sqlite") as conn:
            cursor = conn.cursor()

            # Insert into scan_results table
            cursor.execute('''
                INSERT OR REPLACE INTO scan_results (scan_id, device_id, timestamp, full_result)
                VALUES (?, ?, ?, ?)
            ''', (scan_id, device_id, timestamp, full_result_json))

        logger.info(f"Saved full scan results: scan_id={scan_id}, device_id={device_id}")

    except Exception as e:
        logger.error(f"Failed to save full scan results: {e}\n{traceback.format_exc()}")
        # Don't fail the whole scan if storage fails


def _compare_bug_lists(current_bugs: List[Dict], previous_bugs: List[Dict]) -> Dict:
    """
    Compare two bug lists and categorize differences.

    Args:
        current_bugs: List of bugs from current scan
        previous_bugs: List of bugs from previous scan

    Returns:
        Dict with categorized bugs (fixed, new, unchanged)
    """
    # Create sets of bug_ids for comparison
    current_ids = {v['bug_id'] for v in current_bugs}
    previous_ids = {v['bug_id'] for v in previous_bugs}

    # Calculate differences
    fixed_ids = previous_ids - current_ids
    new_ids = current_ids - previous_ids
    unchanged_ids = current_ids & previous_ids

    # Build full bug objects for each category
    fixed_bugs = [v for v in previous_bugs if v['bug_id'] in fixed_ids]
    new_bugs = [v for v in current_bugs if v['bug_id'] in new_ids]
    unchanged_bugs = [v for v in current_bugs if v['bug_id'] in unchanged_ids]

    # Calculate severity breakdown
    def count_by_severity(bugs):
        counts = {'Critical': 0, 'High': 0, 'Medium': 0, 'Low': 0}
        for bug in bugs:
            severity = bug.get('severity', 'Medium')
            counts[severity] = counts.get(severity, 0) + 1
        return counts

    return {
        'fixed_bugs': sorted(fixed_bugs, key=lambda x: (
            {'Critical': 0, 'High': 1, 'Medium': 2, 'Low': 3}.get(x.get('severity', 'Medium'), 4),
            x['bug_id']
        )),
        'new_bugs': sorted(new_bugs, key=lambda x: (
            {'Critical': 0, 'High': 1, 'Medium': 2, 'Low': 3}.get(x.get('severity', 'Medium'), 4),
            x['bug_id']
        )),
        'unchanged_bugs': sorted(unchanged_bugs, key=lambda x: (
            {'Critical': 0, 'High': 1, 'Medium': 2, 'Low': 3}.get(x.get('severity', 'Medium'), 4),
            x['bug_id']
        )),
        'summary': {
            'total_fixed': len(fixed_bugs),
            'total_new': len(new_bugs),
            'total_unchanged': len(unchanged_bugs),
            'net_change': len(current_bugs) - len(previous_bugs),
            'fixed_by_severity': count_by_severity(fixed_bugs),
            'new_by_severity': count_by_severity(new_bugs)
        }
    }


# ============================================================================
# Scanning Endpoints
# ============================================================================

@router.post("/scan-device/{device_id}")
async def scan_inventory_device(device_id: int):
    """
    Scan a single device from inventory and save results.

    This endpoint:
    1. Retrieves device details from inventory
    2. Runs vulnerability scan using cached device metadata
    3. Saves scan results to database (with rotation)
    4. Returns scan summary

    Args:
        device_id: Device inventory ID

    Returns:
        Scan result summary

    Example:
        POST /api/v1/inventory/scan-device/7
    """
    try:
        from ..core.vulnerability_scanner import VulnerabilityScanner

        inventory = get_inventory_manager()

        # Get device
        with inventory._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM device_inventory WHERE id = ?', (device_id,))
            device = cursor.fetchone()

        if not device:
            raise HTTPException(status_code=404, detail="Device not found")

        device_dict = dict(device)

        # Validate device has been discovered
        if not device_dict.get('platform') or not device_dict.get('version'):
            raise HTTPException(
                status_code=400,
                detail="Device must be discovered first (platform and version required)"
            )

        # Parse features from JSON
        import json
        features = []
        if device_dict.get('features'):
            try:
                features = json.loads(device_dict['features'])
            except json.JSONDecodeError:
                features = []

        # Run scan
        scanner = VulnerabilityScanner(db_path="vulnerability_db.sqlite")
        scan_result = scanner.scan_device(
            platform=device_dict['platform'],
            version=device_dict['version'],
            labels=features,
            hardware_model=device_dict.get('hardware_model')
        )

        # Save scan results to inventory with rotation
        inventory.update_scan_results(device_id, scan_result)

        # Save full scan results to scan_results table
        _save_full_scan_results(device_id, scan_result)

        logger.info(
            f"Scan complete for device {device_id} ({device_dict['hostname']}): "
            f"{len(scan_result['bugs'])} bugs"
        )

        return {
            'success': True,
            'device_id': device_id,
            'hostname': device_dict['hostname'],
            'scan_summary': {
                'scan_id': scan_result['scan_id'],
                'total_bugs': len(scan_result['bugs']),
                'critical_high': scan_result['critical_high'],
                'medium_low': scan_result['medium_low'],
                'version_matches': scan_result['version_matches'],
                'hardware_filtered': scan_result.get('hardware_filtered'),
                'query_time_ms': scan_result['query_time_ms']
            },
            'scan_result': scan_result  # Full result for immediate display
        }

    except HTTPException:
        raise
    except sqlite3.OperationalError as e:
        raise handle_db_error(e, "Device scan")
    except Exception as e:
        raise handle_db_error(e, "Device scan")


@router.get("/scan-results/{scan_id}")
async def get_scan_results(scan_id: str):
    """
    Retrieve full scan results by scan_id.

    Args:
        scan_id: Unique scan identifier

    Returns:
        Complete scan result with bugs

    Example:
        GET /api/v1/inventory/scan-results/scan-355d0bd0
    """
    try:
        import json
        from ..db.utils import get_db_connection

        with get_db_connection("vulnerability_db.sqlite") as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM scan_results
                WHERE scan_id = ?
            ''', (scan_id,))
            row = cursor.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail=f"Scan results not found: {scan_id}")

        # Parse full_result JSON
        full_result = json.loads(row['full_result'])

        return {
            'success': True,
            'scan_id': row['scan_id'],
            'device_id': row['device_id'],
            'timestamp': row['timestamp'],
            'result': full_result
        }

    except HTTPException:
        raise
    except sqlite3.OperationalError as e:
        raise handle_db_error(e, "Get scan results")
    except Exception as e:
        raise handle_db_error(e, "Get scan results")


@router.post("/compare-scans")
async def compare_scans(current_scan_id: str, previous_scan_id: str):
    """
    Compare two scan results to show what changed.

    Use cases:
    - Config change validation (did enabling CoPP introduce new vulns?)
    - Patch verification (did the upgrade fix what we expected?)
    - Change management audit trail

    Args:
        current_scan_id: Scan ID of current/latest scan
        previous_scan_id: Scan ID of previous/baseline scan

    Returns:
        Comparison result with categorized bugs

    Example:
        POST /api/v1/inventory/compare-scans?current_scan_id=scan-abc&previous_scan_id=scan-xyz
    """
    try:
        import json
        from ..db.utils import get_db_connection

        with get_db_connection("vulnerability_db.sqlite") as conn:
            cursor = conn.cursor()

            # Fetch current scan
            cursor.execute('SELECT * FROM scan_results WHERE scan_id = ?', (current_scan_id,))
            current_row = cursor.fetchone()
            if not current_row:
                raise HTTPException(status_code=404, detail=f"Current scan not found: {current_scan_id}")

            # Fetch previous scan
            cursor.execute('SELECT * FROM scan_results WHERE scan_id = ?', (previous_scan_id,))
            previous_row = cursor.fetchone()
            if not previous_row:
                raise HTTPException(status_code=404, detail=f"Previous scan not found: {previous_scan_id}")

        # Parse JSON results
        current_result = json.loads(current_row['full_result'])
        previous_result = json.loads(previous_row['full_result'])

        # Compare bug lists
        comparison = _compare_bug_lists(
            current_result.get('bugs', []),
            previous_result.get('bugs', [])
        )

        # Build response
        return {
            'success': True,
            'comparison_id': f"comp-{current_scan_id[-8:]}-{previous_scan_id[-8:]}",
            'current_scan': {
                'scan_id': current_scan_id,
                'timestamp': current_result.get('timestamp'),
                'platform': current_result.get('platform'),
                'version': current_result.get('version'),
                'hardware_model': current_result.get('hardware_model'),
                'total_bugs': len(current_result.get('bugs', []))
            },
            'previous_scan': {
                'scan_id': previous_scan_id,
                'timestamp': previous_result.get('timestamp'),
                'platform': previous_result.get('platform'),
                'version': previous_result.get('version'),
                'hardware_model': previous_result.get('hardware_model'),
                'total_bugs': len(previous_result.get('bugs', []))
            },
            'fixed_bugs': comparison['fixed_bugs'],
            'new_bugs': comparison['new_bugs'],
            'unchanged_bugs': comparison['unchanged_bugs'],
            'summary': comparison['summary']
        }

    except HTTPException:
        raise
    except sqlite3.OperationalError as e:
        raise handle_db_error(e, "Scan comparison")
    except Exception as e:
        raise handle_db_error(e, "Scan comparison")


class VersionComparisonRequest(BaseModel):
    """Request model for version comparison"""
    platform: str
    current_version: str
    target_version: str
    hardware_model: Optional[str] = None
    features: Optional[List[str]] = None


@router.post("/compare-versions")
async def compare_versions(request: VersionComparisonRequest):
    """
    Compare vulnerabilities between two software versions for upgrade planning.

    Use cases:
    - Upgrade planning (what bugs will be fixed by upgrading?)
    - Downgrade risk assessment (what new bugs would I get?)
    - Version selection (compare multiple target versions)

    Args:
        request: VersionComparisonRequest with platform, current/target versions,
                 optional hardware_model and features for filtering

    Returns:
        Comparison showing fixed/new/unchanged bugs between versions

    Example:
        POST /api/v1/inventory/compare-versions
        {
            "platform": "IOS-XE",
            "current_version": "17.9.1",
            "target_version": "17.12.1",
            "hardware_model": "Cat9300",
            "features": ["MGMT_SSH_HTTP", "SEC_CoPP"]
        }
    """
    try:
        from ..core.vulnerability_scanner import VulnerabilityScanner

        # Validate inputs
        if not request.platform or not request.current_version or not request.target_version:
            raise HTTPException(
                status_code=400,
                detail="platform, current_version, and target_version are required"
            )

        if request.current_version == request.target_version:
            raise HTTPException(
                status_code=400,
                detail="current_version and target_version must be different"
            )

        # Initialize scanner
        scanner = VulnerabilityScanner(db_path="vulnerability_db.sqlite")

        # Run scan for current version
        current_result = scanner.scan_device(
            platform=request.platform,
            version=request.current_version,
            labels=request.features or [],
            hardware_model=request.hardware_model
        )

        # Run scan for target version
        target_result = scanner.scan_device(
            platform=request.platform,
            version=request.target_version,
            labels=request.features or [],
            hardware_model=request.hardware_model
        )

        # Compare bug lists
        comparison = _compare_bug_lists(
            target_result.get('bugs', []),  # "current" = target (what we'd have after upgrade)
            current_result.get('bugs', [])  # "previous" = current (what we have now)
        )

        # Build response (keys match frontend VersionComparisonResult type)
        return {
            'success': True,
            'comparison_id': str(uuid.uuid4()),
            'comparison_type': 'version',
            'platform': request.platform,
            'hardware_model': request.hardware_model,
            'features_filtered': request.features or [],
            'current_version_scan': {
                'version': request.current_version,
                'platform': request.platform,
                'hardware_model': request.hardware_model,
                'total_bugs': len(current_result.get('bugs', [])),
                'critical_high': current_result.get('critical_high', 0),
                'medium_low': current_result.get('medium_low', 0),
                'query_time_ms': current_result.get('query_time_ms', 0)
            },
            'target_version_scan': {
                'version': request.target_version,
                'platform': request.platform,
                'hardware_model': request.hardware_model,
                'total_bugs': len(target_result.get('bugs', [])),
                'critical_high': target_result.get('critical_high', 0),
                'medium_low': target_result.get('medium_low', 0),
                'query_time_ms': target_result.get('query_time_ms', 0)
            },
            'fixed_in_upgrade': comparison['fixed_bugs'],  # Bugs fixed by upgrading
            'new_in_upgrade': comparison['new_bugs'],      # Bugs introduced by upgrading
            'still_present': comparison['unchanged_bugs'],  # Bugs present in both
            'summary': comparison['summary'],
            'upgrade_recommendation': _generate_upgrade_recommendation(comparison['summary'])
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Version comparison failed: {e}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"Version comparison failed: {str(e)}"
        )


def _generate_upgrade_recommendation(summary: Dict) -> Dict[str, Any]:
    """Generate upgrade recommendation with risk assessment.

    Returns:
        Dict with risk_level (LOW/MEDIUM/HIGH), risk_score (0-100), and recommendation text
    """
    fixed = summary['total_fixed']
    new = summary['total_new']
    net = summary['net_change']

    fixed_critical = summary['fixed_by_severity'].get('Critical', 0)
    fixed_high = summary['fixed_by_severity'].get('High', 0)
    new_critical = summary['new_by_severity'].get('Critical', 0)
    new_high = summary['new_by_severity'].get('High', 0)

    # Calculate risk score (0-100, lower is better)
    risk_score = 0
    risk_score += new_critical * 30  # Critical bugs are heavily weighted
    risk_score += new_high * 15      # High bugs moderately weighted
    risk_score += max(0, net) * 5    # Penalty for net increase in bugs
    risk_score = min(100, risk_score)  # Cap at 100

    # Determine risk level
    if new_critical > 0 or risk_score >= 50:
        risk_level = "HIGH"
    elif new_high > fixed_high or risk_score >= 25:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"

    # Generate recommendation text
    if new_critical > 0:
        recommendation = f"Upgrade introduces {new_critical} Critical bugs. Review carefully before proceeding."
    elif new_high > fixed_high and new > fixed:
        recommendation = f"Upgrade fixes {fixed} bugs but introduces {new} new ones (net change: {net:+d}). Review new High severity bugs."
    elif fixed > 0 and new == 0:
        recommendation = f"Upgrade fixes {fixed} bugs with no new bugs introduced. Recommended."
    elif fixed > new:
        recommendation = f"Upgrade fixes {fixed} bugs, introduces {new} new ones (net improvement: {-net}). Favorable."
    elif fixed == 0 and new == 0:
        recommendation = "No bug changes between versions."
    else:
        recommendation = f"Upgrade introduces more bugs ({new}) than it fixes ({fixed}). Net change: {net:+d}. Review required."

    return {
        'risk_level': risk_level,
        'risk_score': risk_score,
        'recommendation': recommendation,
        'metrics': {
            'total_fixed': fixed,
            'total_new': new,
            'net_change': net,
            'critical_fixed': fixed_critical,
            'high_fixed': fixed_high,
            'critical_new': new_critical,
            'high_new': new_high
        }
    }


@router.post("/scan-all")
async def scan_all_devices(request: BulkScanRequest, background_tasks: BackgroundTasks):
    """
    Scan multiple devices for bugs (async).

    Launches a background task to scan devices and returns immediately
    with a job_id for progress tracking via /scan-status/{job_id}.

    Args:
        request: Device IDs or filters

    Returns:
        Job handle for polling progress

    Example:
        POST /api/v1/inventory/scan-all
        {
            "platforms": ["IOS-XE"],
            "device_ids": null  // null = scan all IOS-XE devices
        }

        Response:
        {
            "success": true,
            "job_id": "bulk-abc12345",
            "status": "running",
            "total_devices": 10,
            "message": "Scan started. Poll /scan-status/bulk-abc12345 for progress."
        }
    """
    import uuid
    from datetime import datetime

    try:
        inventory = get_inventory_manager()

        # Generate job ID for tracking
        job_id = f"bulk-{uuid.uuid4().hex[:8]}"

        # Get devices to scan
        if request.device_ids:
            # Scan specific devices
            with inventory._get_connection() as conn:
                cursor = conn.cursor()
                placeholders = ','.join('?' * len(request.device_ids))
                cursor.execute(f'SELECT * FROM device_inventory WHERE id IN ({placeholders})', request.device_ids)
                devices = [dict(row) for row in cursor.fetchall()]
        else:
            # Scan all devices (with optional platform filter)
            platform_filter = request.platforms[0] if request.platforms else None
            devices = inventory.get_all_devices(
                platform=platform_filter,
                discovery_status="success"  # Only scan successfully discovered devices
            )

        if not devices:
            return {
                'success': True,
                'job_id': job_id,
                'status': 'completed',
                'message': 'No devices found matching criteria',
                'total_devices': 0,
                'scanned': 0,
                'failed': 0,
                'scan_results': [],
                'timestamp': datetime.now().isoformat()
            }

        # Initialize job status
        _bulk_scan_jobs[job_id] = {
            'status': 'queued',
            'total_devices': len(devices),
            'scanned': 0,
            'failed': 0,
            'current_device': None,
            'progress_percent': 0,
            'scan_results': [],
            'summary': {},
            'started_at': None,
            'completed_at': None,
            'error': None
        }

        # Launch background task
        background_tasks.add_task(_run_bulk_scan, job_id, devices)

        logger.info(f"Bulk scan {job_id} queued for {len(devices)} devices")

        # Return immediately with job handle
        return {
            'success': True,
            'job_id': job_id,
            'status': 'running',
            'total_devices': len(devices),
            'message': f"Scan started. Poll /api/v1/inventory/scan-status/{job_id} for progress.",
            'timestamp': datetime.now().isoformat()
        }

    except HTTPException:
        raise
    except sqlite3.OperationalError as e:
        raise handle_db_error(e, "Bulk scan")
    except Exception as e:
        raise handle_db_error(e, "Bulk scan")


@router.get("/scan-status/{job_id}")
async def get_scan_status(job_id: str):
    """
    Get the status of a bulk scan job.

    Poll this endpoint to track progress of a /scan-all request.

    Args:
        job_id: The job ID returned by /scan-all

    Returns:
        Job status including progress, results (if completed), and any errors

    Example:
        GET /api/v1/inventory/scan-status/bulk-abc12345

        Response (running):
        {
            "success": true,
            "job_id": "bulk-abc12345",
            "status": "running",
            "total_devices": 10,
            "scanned": 3,
            "failed": 0,
            "progress_percent": 30,
            "current_device": "router-04"
        }

        Response (completed):
        {
            "success": true,
            "job_id": "bulk-abc12345",
            "status": "completed",
            "total_devices": 10,
            "scanned": 9,
            "failed": 1,
            "progress_percent": 100,
            "summary": {...},
            "scan_results": [...]
        }
    """
    if job_id not in _bulk_scan_jobs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found. Jobs are cleared on server restart."
        )

    job = _bulk_scan_jobs[job_id]

    return {
        'success': True,
        'job_id': job_id,
        **job
    }
