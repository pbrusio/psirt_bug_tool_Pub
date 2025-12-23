#!/usr/bin/env python3
"""
Device PSIRT Verification
Connect to network devices and verify PSIRT vulnerability based on:
1. Software version matching
2. Feature configuration presence
"""
import re
from netmiko import ConnectHandler
from typing import Dict, List, Optional, Tuple
import json
from version_matcher import VersionMatcher


class VersionParser:
    """Parse and compare Cisco IOS-XE versions"""

    @staticmethod
    def parse_version(version_str: str) -> Optional[Tuple[int, int, int]]:
        """
        Parse version string to tuple for comparison
        Example: "17.03.05" -> (17, 3, 5)
        """
        # Match patterns like: 17.03.05, 17.3.5, 16.12.4a
        match = re.search(r'(\d+)\.(\d+)\.(\d+)', version_str)
        if match:
            return (int(match.group(1)), int(match.group(2)), int(match.group(3)))
        return None

    @staticmethod
    def version_in_range(device_version: str, affected_range: str, fixed_version: str = None) -> bool:
        """
        Check if device version falls in affected range

        Simple logic:
        - If device version matches affected_range pattern -> VULNERABLE
        - If fixed_version provided and device >= fixed_version -> NOT VULNERABLE
        """
        device_ver = VersionParser.parse_version(device_version)
        if not device_ver:
            return False

        # Check if in affected range
        affected_ver = VersionParser.parse_version(affected_range)
        if not affected_ver:
            return False

        # Simple major.minor match for now
        if device_ver[0] == affected_ver[0] and device_ver[1] == affected_ver[1]:
            # Check if fixed
            if fixed_version:
                fixed_ver = VersionParser.parse_version(fixed_version)
                if fixed_ver and device_ver >= fixed_ver:
                    return False  # Fixed, not vulnerable
            return True  # Vulnerable

        return False  # Different train


class DeviceConnector:
    """Handle SSH connections to network devices"""

    def __init__(self, host: str, username: str, password: str, device_type: str = "cisco_ios"):
        self.device_params = {
            'device_type': device_type,
            'host': host,
            'username': username,
            'password': password,
        }
        self.connection = None

    def connect(self):
        """Establish SSH connection"""
        print(f"🔌 Connecting to {self.device_params['host']}...")
        self.connection = ConnectHandler(**self.device_params)
        print("✅ Connected successfully")

    def disconnect(self):
        """Close SSH connection"""
        if self.connection:
            self.connection.disconnect()
            print("🔌 Disconnected")

    def get_version(self) -> str:
        """Get device software version"""
        output = self.connection.send_command("show version")

        # Parse version from output
        # Example: "Cisco IOS XE Software, Version 17.03.05"
        match = re.search(r'Version (\d+\.\d+\.\d+[a-zA-Z]*)', output)
        if match:
            return match.group(1)
        return "Unknown"

    def get_hostname(self) -> str:
        """Get device hostname"""
        output = self.connection.send_command("show running-config | include hostname")
        match = re.search(r'hostname\s+(\S+)', output)
        if match:
            return match.group(1)
        return "Unknown"

    def check_feature_config(self, config_regex: str) -> bool:
        """
        Check if feature is configured using regex pattern
        Returns True if pattern found in running config
        """
        try:
            output = self.connection.send_command("show running-config")
            return bool(re.search(config_regex, output, re.MULTILINE | re.IGNORECASE))
        except Exception as e:
            print(f"  ⚠️  Error checking config: {e}")
            return False

    def run_show_commands(self, commands: List[str]) -> Dict[str, str]:
        """Execute show commands and return results"""
        results = {}
        for cmd in commands:
            try:
                results[cmd] = self.connection.send_command(cmd)
            except Exception as e:
                results[cmd] = f"ERROR: {e}"
        return results


class PSIRTVerifier:
    """Verify if device is vulnerable to specific PSIRT"""

    def __init__(self, device_connector: DeviceConnector):
        self.device = device_connector
        self.version_matcher = VersionMatcher()

    def verify_psirt(self, psirt: Dict) -> Dict:
        """
        Verify if device is vulnerable to PSIRT

        Args:
            psirt: Dict with keys:
                - bug_id: PSIRT ID
                - affected_versions: Version pattern (e.g., "17.3")
                - fixed_version: Fixed version (e.g., "17.6.1")
                - labels: List of feature labels
                - config_regex: List of regex patterns to check
                - show_cmds: List of show commands

        Returns:
            Dict with verification results
        """
        print(f"\n{'='*80}")
        print(f"🔍 Verifying PSIRT: {psirt.get('bug_id', 'Unknown')}")
        print(f"{'='*80}")

        # Get device info
        hostname = self.device.get_hostname()
        device_version = self.device.get_version()

        print(f"📱 Device: {hostname}")
        print(f"📦 Version: {device_version}")
        print(f"🎯 PSIRT: {psirt.get('summary', 'N/A')[:80]}...")

        results = {
            'device': hostname,
            'device_version': device_version,
            'psirt_id': psirt.get('bug_id'),
            'version_vulnerable': False,
            'features_present': [],
            'features_absent': [],
            'overall_status': 'NOT VULNERABLE',
            'reason': ''
        }

        # Step 1: Check version using product names
        print("\n📋 Step 1: Version Check")
        product_names = psirt.get('product_names', [])

        if product_names:
            # Use version matcher to check against product names
            version_result = self.version_matcher.is_version_affected(
                device_version,
                psirt.get('platform', hostname.split('-')[0]),  # Try to infer platform
                product_names
            )

            results['version_vulnerable'] = version_result['affected']
            results['version_check_detail'] = version_result

            if version_result['affected']:
                print(f"  ⚠️  Version {device_version} IS AFFECTED")
                print(f"     Matched versions: {', '.join(version_result['affected_versions'][:3])}")
            else:
                print(f"  ✅ Version {device_version} NOT AFFECTED")
                print(f"     Reason: {version_result['reason'][:80]}")
                if not version_result['affected_versions']:
                    # No version info, continue with feature check
                    print(f"     Note: No version data found, checking features only")
                else:
                    # Version clearly not affected, device is safe
                    results['reason'] = version_result['reason']
                    results['overall_status'] = 'NOT VULNERABLE'
                    return results
        else:
            print("  ℹ️  No product version info in PSIRT, checking features only")
            results['version_vulnerable'] = None  # Unknown

        # Step 2: Check features
        print("\n📋 Step 2: Feature Configuration Check")
        labels = psirt.get('labels', [])
        config_patterns = psirt.get('config_regex', [])

        if not config_patterns:
            print("  ℹ️  No config patterns to check")
            results['reason'] = "No feature checks available"
            return results

        for i, (label, pattern) in enumerate(zip(labels, config_patterns)):
            print(f"  [{i+1}/{len(labels)}] Checking {label}...")
            if self.device.check_feature_config(pattern):
                print(f"      ✅ Feature PRESENT")
                results['features_present'].append(label)
            else:
                print(f"      ❌ Feature ABSENT")
                results['features_absent'].append(label)

        # Step 3: Determine overall status
        print("\n📋 Step 3: Overall Assessment")

        # Handle case where version check was skipped
        if results['version_vulnerable'] is None:
            # No version info provided - report based on feature presence only
            if results['features_present']:
                results['overall_status'] = 'POTENTIALLY VULNERABLE'
                feature_list = ', '.join(results['features_present'])
                results['reason'] = (f"Vulnerable features DETECTED: {feature_list}. "
                                   f"⚠️ Version verification required - device may be vulnerable if running affected software version.")
                print(f"  ⚠️  POTENTIALLY VULNERABLE: Features present but version not verified")
            else:
                results['overall_status'] = 'LIKELY NOT VULNERABLE'
                feature_list = ', '.join(results['features_absent'])
                results['reason'] = (f"Required features NOT configured: {feature_list}. "
                                   f"Device appears safe, but version verification recommended for certainty.")
                print(f"  ✅ LIKELY NOT VULNERABLE: Required features not configured")

        # Version check was performed
        elif results['version_vulnerable'] and results['features_present']:
            results['overall_status'] = 'VULNERABLE'
            results['reason'] = f"Version vulnerable + Features present: {', '.join(results['features_present'])}"
            print(f"  🚨 VULNERABLE: Version affected and feature(s) present")
        elif results['version_vulnerable'] and not results['features_present']:
            results['overall_status'] = 'NOT VULNERABLE'
            results['reason'] = "Version vulnerable but required features not configured"
            print(f"  ✅ NOT VULNERABLE: Required features not configured")
        else:
            results['overall_status'] = 'NOT VULNERABLE'
            results['reason'] = "Version not affected"
            print(f"  ✅ NOT VULNERABLE: Version not affected")

        # Optional: Run show commands for evidence
        show_cmds = psirt.get('show_cmds', [])
        if show_cmds and results['overall_status'] == 'VULNERABLE':
            print("\n📋 Step 4: Collecting Evidence")
            results['evidence'] = self.device.run_show_commands(show_cmds[:3])  # Limit to 3

        return results


def main():
    """Test device verification"""
    import os

    # Device credentials from environment variables
    password = os.getenv('DEVICE_PASSWORD')
    if not password:
        print("❌ DEVICE_PASSWORD environment variable is required")
        print("\nSet credentials via environment variables:")
        print("  export DEVICE_HOST='192.168.0.33'")
        print("  export DEVICE_USERNAME='admin'")
        print("  export DEVICE_PASSWORD='your-password'")
        return

    DEVICE = {
        'host': os.getenv('DEVICE_HOST', '192.168.0.33'),
        'username': os.getenv('DEVICE_USERNAME', 'admin'),
        'password': password,
        'device_type': os.getenv('DEVICE_TYPE', 'cisco_ios')
    }

    # Test PSIRT (we'll find a real one from the dataset)
    test_psirt = {
        'bug_id': 'TEST-PSIRT-001',
        'summary': 'Test vulnerability in SSH',
        'affected_versions': '17.3',  # Matches 17.03.05
        'fixed_version': '17.6.1',
        'labels': ['MGMT_SSH_HTTP'],
        'config_regex': [r'ip\s+ssh'],
        'show_cmds': ['show ip ssh', 'show running-config | include ssh']
    }

    try:
        # Connect to device
        connector = DeviceConnector(**DEVICE)
        connector.connect()

        # Verify PSIRT
        verifier = PSIRTVerifier(connector)
        results = verifier.verify_psirt(test_psirt)

        # Print summary
        print(f"\n{'='*80}")
        print("📊 VERIFICATION SUMMARY")
        print(f"{'='*80}")
        print(f"Status: {results['overall_status']}")
        print(f"Reason: {results['reason']}")

        if results['features_present']:
            print(f"\nFeatures Present: {', '.join(results['features_present'])}")
        if results['features_absent']:
            print(f"Features Absent: {', '.join(results['features_absent'])}")

        # Save results
        with open('device_verification_result.json', 'w') as f:
            json.dump(results, f, indent=2)
        print("\n💾 Results saved to device_verification_result.json")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        connector.disconnect()


if __name__ == '__main__':
    main()
