"""
Device verification wrapper for API
Wraps the existing DeviceConnector and PSIRTVerifier for FastAPI usage
"""
import sys
from pathlib import Path

# Add parent directory to path to import existing modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from device_verifier import DeviceConnector, PSIRTVerifier
import uuid
from datetime import datetime


class DeviceVerificationService:
    """Service for device verification"""

    def verify_device(
        self,
        analysis_id: str,
        device_config: dict,
        psirt_metadata: dict,
        predicted_labels: list,
        config_regex: list,
        show_commands: list
    ) -> dict:
        """
        Verify device against PSIRT

        Args:
            analysis_id: ID from previous analysis
            device_config: {host, username, password, device_type}
            psirt_metadata: {product_names, bug_id}
            predicted_labels: Labels from SEC-8B
            config_regex: Config patterns to check
            show_commands: Show commands to run

        Returns:
            {
                'verification_id': str,
                'analysis_id': str,
                'device_hostname': str,
                'device_version': str,
                'device_platform': str,
                'version_check': {...},
                'feature_check': {...},
                'overall_status': str,
                'reason': str,
                'evidence': dict,
                'timestamp': datetime
            }
        """
        # Connect to device
        try:
            connector = DeviceConnector(**device_config)
            connector.connect()
        except Exception as e:
            # Connection failed
            verification_id = str(uuid.uuid4())
            return {
                'verification_id': verification_id,
                'analysis_id': analysis_id,
                'device_hostname': None,
                'device_version': None,
                'device_platform': None,
                'version_check': None,
                'feature_check': None,
                'overall_status': 'ERROR',
                'reason': f'Failed to connect to device: {str(e)}',
                'evidence': {},
                'timestamp': datetime.now(),
                'error': str(e)
            }

        try:
            # Get device info
            hostname = connector.get_hostname()
            version = connector.get_version()

            # Infer platform from device_type
            device_type = device_config.get('device_type', 'cisco_ios')
            platform_map = {
                'cisco_ios': 'IOS-XE',
                'cisco_xe': 'IOS-XE',
                'cisco_xr': 'IOS-XR',
                'cisco_asa': 'ASA',
                'cisco_nxos': 'NX-OS',
                'cisco_ftd': 'FTD'
            }
            platform = platform_map.get(device_type, 'IOS-XE')

            # Build PSIRT dict for verifier
            psirt = {
                'bug_id': psirt_metadata.get('bug_id', 'unknown'),
                'summary': 'API verification',
                'platform': platform,  # Add platform for version matching
                'labels': predicted_labels,
                'config_regex': config_regex,
                'show_cmds': show_commands,
                'product_names': psirt_metadata.get('product_names', []),
                'fixed_versions': [],  # Not used in current logic
                'affected_versions': None
            }

            # Run verification
            verifier = PSIRTVerifier(connector)
            result = verifier.verify_psirt(psirt)

            # Format response
            verification_id = str(uuid.uuid4())

            # Handle version check (can be None if no version info provided)
            version_vulnerable = result.get('version_vulnerable')
            if version_vulnerable is None:
                # No version check performed
                version_check = None
            else:
                version_check = {
                    'affected': version_vulnerable,
                    'reason': result.get('version_check_detail', {}).get('reason', 'Version check performed'),
                    'matched_versions': result.get('version_check_detail', {}).get('affected_versions', [])
                }

            return {
                'verification_id': verification_id,
                'analysis_id': analysis_id,
                'device_hostname': hostname,
                'device_version': version,
                'device_platform': platform,
                'version_check': version_check,
                'feature_check': {
                    'present': result['features_present'],
                    'absent': result['features_absent']
                },
                'overall_status': result['overall_status'],
                'reason': result['reason'],
                'evidence': result.get('evidence', {}),
                'timestamp': datetime.now()
            }

        finally:
            connector.disconnect()


# Global singleton instance
_verifier_instance = None

def get_verifier():
    """Get or create device verifier singleton"""
    global _verifier_instance
    if _verifier_instance is None:
        _verifier_instance = DeviceVerificationService()
    return _verifier_instance
