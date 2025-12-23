"""
ISE ERS API Client for Network Device Inventory

Connects to Cisco Identity Services Engine (ISE) External RESTful Services (ERS) API
to retrieve network device inventory for vulnerability scanning.

References:
- ISE ERS API: https://developer.cisco.com/docs/identity-services-engine/
- Network Device endpoint: GET /ers/config/networkdevice
"""

import requests
import logging
from typing import List, Dict, Optional
from datetime import datetime
import urllib3

# Disable SSL warnings for lab/enterprise environments with self-signed certs
# TODO: Future enhancement - add ISE_VERIFY_SSL env var and cert store support
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)


class ISEClient:
    """Client for Cisco ISE ERS API"""

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        verify_ssl: bool = False,
        timeout: int = 30
    ):
        """
        Initialize ISE API client.

        Args:
            host: ISE hostname or IP (e.g., "192.168.0.30")
            username: ERS Admin username (e.g., "ersAdmin")
            password: ERS Admin password
            verify_ssl: Verify SSL certificates (False for lab/self-signed - typical in enterprise)
            timeout: Request timeout in seconds
        """
        self.host = host
        self.base_url = f"https://{host}:9060/ers/config"
        self.username = username
        self.password = password
        self.verify_ssl = verify_ssl
        self.timeout = timeout

        # ERS API requires these headers
        self.headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }

        self.session = requests.Session()
        self.session.auth = (username, password)
        self.session.headers.update(self.headers)
        self.session.verify = verify_ssl

        logger.info(f"ISE Client initialized for {host}")

    def test_connection(self) -> bool:
        """
        Test ISE API connectivity.

        Returns:
            bool: True if connection successful
        """
        try:
            url = f"{self.base_url}/networkdevice"
            response = self.session.get(url, timeout=self.timeout, params={'size': 1})
            response.raise_for_status()
            logger.info(f"ISE connection test successful: {self.host}")
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"ISE connection test failed: {e}")
            return False

    def get_network_devices(self, page: int = 1, size: int = 100) -> Dict:
        """
        Get network devices from ISE.

        Args:
            page: Page number (1-indexed)
            size: Number of devices per page (max 100)

        Returns:
            dict: ISE API response with device list

        Response format:
        {
            "SearchResult": {
                "total": 42,
                "resources": [
                    {
                        "id": "uuid",
                        "name": "device-hostname",
                        "link": {
                            "rel": "self",
                            "href": "...",
                            "type": "application/json"
                        }
                    },
                    ...
                ]
            }
        }
        """
        try:
            url = f"{self.base_url}/networkdevice"
            params = {
                'page': page,
                'size': size
            }

            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()

            data = response.json()
            total = data.get('SearchResult', {}).get('total', 0)
            resources = data.get('SearchResult', {}).get('resources', [])

            logger.info(f"Retrieved {len(resources)} devices from ISE (total: {total})")
            return data

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get network devices: {e}")
            raise

    def get_device_details(self, device_id: str) -> Dict:
        """
        Get detailed information for a specific device.

        Args:
            device_id: ISE device UUID

        Returns:
            dict: Device details

        Response format:
        {
            "NetworkDevice": {
                "id": "uuid",
                "name": "device-hostname",
                "description": "Device description",
                "NetworkDeviceIPList": [
                    {"ipaddress": "192.168.1.1", "mask": 32}
                ],
                "NetworkDeviceGroupList": ["Location#All Locations#Site1"],
                "profileName": "Cisco"
            }
        }
        """
        try:
            url = f"{self.base_url}/networkdevice/{device_id}"
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()

            data = response.json()
            logger.debug(f"Retrieved device details: {device_id}")
            return data

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get device details for {device_id}: {e}")
            raise

    def get_all_devices(self, max_devices: Optional[int] = None) -> List[Dict]:
        """
        Get all network devices from ISE with pagination.

        Args:
            max_devices: Maximum number of devices to retrieve (None = all)

        Returns:
            list: List of device detail dictionaries
        """
        all_devices = []
        page = 1
        page_size = 100

        while True:
            # Get device list page
            result = self.get_network_devices(page=page, size=page_size)
            resources = result.get('SearchResult', {}).get('resources', [])
            total = result.get('SearchResult', {}).get('total', 0)

            if not resources:
                break

            # Fetch details for each device
            for resource in resources:
                device_id = resource.get('id')
                device_name = resource.get('name')

                try:
                    details = self.get_device_details(device_id)
                    device_data = details.get('NetworkDevice', {})

                    # Extract useful information
                    device_info = {
                        'ise_id': device_id,
                        'hostname': device_name,
                        'description': device_data.get('description', ''),
                        'ip_addresses': [
                            ip.get('ipaddress')
                            for ip in device_data.get('NetworkDeviceIPList', [])
                        ],
                        'location': self._extract_location(device_data.get('NetworkDeviceGroupList', [])),
                        'device_type': device_data.get('profileName', 'Unknown'),
                        'ise_sync_time': datetime.now().isoformat()
                    }

                    all_devices.append(device_info)

                    # Check max_devices limit
                    if max_devices and len(all_devices) >= max_devices:
                        logger.info(f"Reached max_devices limit: {max_devices}")
                        return all_devices

                except Exception as e:
                    logger.warning(f"Failed to get details for device {device_name}: {e}")
                    continue

            # Check if we've retrieved all devices
            if len(all_devices) >= total:
                break

            page += 1

        logger.info(f"Retrieved {len(all_devices)} devices from ISE")
        return all_devices

    def _extract_location(self, group_list: List[str]) -> Optional[str]:
        """
        Extract location from NetworkDeviceGroupList.

        Args:
            group_list: List of device group strings (e.g., ["Location#All Locations#Site1"])

        Returns:
            str: Location string or None
        """
        for group in group_list:
            if group.startswith('Location#'):
                # Parse "Location#All Locations#Site1" -> "Site1"
                parts = group.split('#')
                if len(parts) > 2:
                    return parts[-1]  # Return last part (most specific location)
        return None

    def sync_devices(self, max_devices: Optional[int] = None) -> Dict:
        """
        Sync all devices from ISE and return summary.

        Args:
            max_devices: Maximum number of devices to sync

        Returns:
            dict: Sync summary with device list and statistics
        """
        try:
            devices = self.get_all_devices(max_devices=max_devices)

            summary = {
                'success': True,
                'total_devices': len(devices),
                'devices': devices,
                'sync_time': datetime.now().isoformat(),
                'ise_host': self.host
            }

            logger.info(f"ISE sync completed: {len(devices)} devices retrieved")
            return summary

        except Exception as e:
            logger.error(f"ISE sync failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'total_devices': 0,
                'devices': [],
                'sync_time': datetime.now().isoformat()
            }


def test_ise_connection():
    """Test ISE connection with credentials from environment variables"""
    import os

    host = os.getenv('ISE_HOST', '192.168.0.30')
    username = os.getenv('ISE_USERNAME', 'ersAdmin')
    password = os.getenv('ISE_PASSWORD')

    if not password:
        print("❌ ISE_PASSWORD environment variable is required")
        print("\nSet credentials via environment variables:")
        print("  export ISE_HOST='your-ise-server'")
        print("  export ISE_USERNAME='ersAdmin'")
        print("  export ISE_PASSWORD='your-password'")
        return

    client = ISEClient(
        host=host,
        username=username,
        password=password
    )

    print("Testing ISE connection...")
    print("\n⚠️  If you get 401 Unauthorized, please verify:")
    print("   1. ERS API is enabled in ISE: Administration > System > Settings > ERS Settings")
    print("   2. ersAdmin user has ERS Admin group permissions")
    print("   3. Credentials are correct\n")

    if client.test_connection():
        print("✅ Connection successful!")

        print("\nFetching devices...")
        result = client.sync_devices(max_devices=5)  # Test with 5 devices

        if result['success']:
            print(f"✅ Retrieved {result['total_devices']} devices")
            print("\nSample devices:")
            for device in result['devices'][:3]:
                print(f"  • {device['hostname']} ({device['ip_addresses'][0] if device['ip_addresses'] else 'No IP'})")
        else:
            print(f"❌ Sync failed: {result.get('error')}")
    else:
        print("❌ Connection failed! Please check ISE ERS API configuration.")


if __name__ == "__main__":
    # Enable logging for testing
    logging.basicConfig(level=logging.INFO)
    test_ise_connection()
