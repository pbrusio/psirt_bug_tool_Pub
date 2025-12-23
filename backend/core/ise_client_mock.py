"""
Mock ISE Client for Development/Testing

Use this when ISE ERS API is not available or for testing purposes.
Returns sample device data that mimics real ISE responses.
"""

import logging
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class MockISEClient:
    """Mock ISE Client that returns sample data"""

    def __init__(self, host: str, username: str, password: str, **kwargs):
        """Initialize mock client"""
        self.host = host
        self.username = username
        logger.info(f"Mock ISE Client initialized for {host}")

    def test_connection(self) -> bool:
        """Always returns True for mock"""
        logger.info("Mock ISE connection test - always succeeds")
        return True

    def get_all_devices(self, max_devices: Optional[int] = None) -> List[Dict]:
        """
        Return lab device data.

        Returns devices from the lab network for testing vulnerability scanning.
        """
        mock_devices = [
            # ===== Real Lab Devices =====
            {
                'ise_id': 'lab-uuid-001',
                'hostname': 'C9200L',
                'description': 'Catalyst 9200L Lab Switch - IOS-XE',
                'ip_addresses': ['192.168.0.33'],
                'location': 'Lab',
                'device_type': 'Cisco Catalyst 9200L',
                'ise_sync_time': datetime.now().isoformat()
            },
            {
                'ise_id': 'lab-uuid-002',
                'hostname': '8Kv-1',
                'description': 'Cisco 8000 Series Virtual Router',
                'ip_addresses': ['192.168.0.134'],
                'location': 'Lab',
                'device_type': 'Cisco 8000v',
                'ise_sync_time': datetime.now().isoformat()
            },
            {
                'ise_id': 'lab-uuid-003',
                'hostname': 'CSRv33',
                'description': 'CSR1000v Virtual Router - IOS-XE',
                'ip_addresses': ['192.168.30.133'],
                'location': 'Lab',
                'device_type': 'Cisco CSR1000v',
                'ise_sync_time': datetime.now().isoformat()
            },
            {
                'ise_id': 'lab-uuid-004',
                'hostname': 'FPR1010',
                'description': 'Firepower 1010 - FTD',
                'ip_addresses': ['192.168.0.151'],
                'location': 'Lab',
                'device_type': 'Cisco Firepower 1010',
                'ise_sync_time': datetime.now().isoformat()
            },
        ]

        if max_devices:
            mock_devices = mock_devices[:max_devices]

        logger.info(f"Mock ISE returning {len(mock_devices)} devices")
        return mock_devices

    def sync_devices(self, max_devices: Optional[int] = None) -> Dict:
        """Mock sync - returns sample devices"""
        try:
            devices = self.get_all_devices(max_devices=max_devices)

            summary = {
                'success': True,
                'total_devices': len(devices),
                'devices': devices,
                'sync_time': datetime.now().isoformat(),
                'ise_host': self.host,
                'mock': True  # Flag to indicate this is mock data
            }

            logger.info(f"Mock ISE sync completed: {len(devices)} devices")
            return summary

        except Exception as e:
            logger.error(f"Mock ISE sync failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'total_devices': 0,
                'devices': [],
                'sync_time': datetime.now().isoformat(),
                'mock': True
            }


def test_mock_ise():
    """Test mock ISE client"""
    client = MockISEClient(
        host='192.168.0.30',
        username='ersAdmin',
        password='Pa22word'
    )

    print("Testing Mock ISE Client...")
    print("✅ Mock connection always succeeds\n")

    print("Fetching mock devices...")
    result = client.sync_devices(max_devices=5)

    if result['success']:
        print(f"✅ Retrieved {result['total_devices']} mock devices\n")
        print("Sample devices:")
        for device in result['devices']:
            print(f"  • {device['hostname']:20} | {device['ip_addresses'][0]:15} | {device['location']}")
    else:
        print(f"❌ Sync failed: {result.get('error')}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_mock_ise()
