#!/usr/bin/env python3
"""
Device Feature Extractor - Sidecar Script
==========================================

Extract feature presence from Cisco devices WITHOUT capturing sensitive data.
Supports both live SSH connections and offline config file analysis.

Output: Sanitized JSON snapshot with feature labels only (no IPs, passwords, hostnames, configs)

Usage:
    # Live device
    python extract_device_features.py --host 192.168.1.1 --username admin --output snapshot.json

    # Offline config
    python extract_device_features.py --config running-config.txt --platform IOS-XE --output snapshot.json

    # Batch mode
    python extract_device_features.py --inventory devices.csv --output-dir snapshots/
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import yaml
import getpass

# Import hardware extraction for auto-detection
try:
    from backend.db.hardware_extractor import extract_hardware_model_from_show_version
    HARDWARE_EXTRACTION_AVAILABLE = True
except ImportError:
    HARDWARE_EXTRACTION_AVAILABLE = False
    print("⚠️  Warning: hardware_extractor not available. Hardware auto-detection disabled.")

try:
    from netmiko import ConnectHandler
    NETMIKO_AVAILABLE = True
except ImportError:
    NETMIKO_AVAILABLE = False
    print("⚠️  Warning: netmiko not installed. Only offline mode available.")


class FeatureExtractor:
    """Extract features from device config using taxonomy YAMLs"""

    PLATFORM_FEATURE_FILES = {
        'IOS-XE': 'taxonomies/features.yml',
        'IOS-XR': 'taxonomies/features_iosxr.yml',
        'ASA': 'taxonomies/features_asa.yml',
        'FTD': 'taxonomies/features_asa.yml',
        'NX-OS': 'taxonomies/features_nxos.yml'
    }

    def __init__(self, platform: str, features_dir: str = '.'):
        """
        Initialize feature extractor

        Args:
            platform: Platform name (IOS-XE, IOS-XR, ASA, FTD, NX-OS)
            features_dir: Directory containing features_*.yml files
        """
        self.platform = platform.upper()
        self.features_dir = Path(features_dir)
        self.features = self._load_features()

    def _load_features(self) -> List[Dict]:
        """Load feature taxonomy for platform"""
        feature_file = self.PLATFORM_FEATURE_FILES.get(self.platform)
        if not feature_file:
            raise ValueError(f"Unsupported platform: {self.platform}. "
                           f"Supported: {', '.join(self.PLATFORM_FEATURE_FILES.keys())}")

        feature_path = self.features_dir / feature_file
        if not feature_path.exists():
            raise FileNotFoundError(f"Feature file not found: {feature_path}")

        with open(feature_path, 'r') as f:
            features = yaml.safe_load(f)

        print(f"✅ Loaded {len(features)} features for {self.platform}")
        return features

    def extract_from_config(self, config_text: str) -> Dict:
        """
        Extract features from config text

        Args:
            config_text: Device running configuration

        Returns:
            Dict with snapshot data (NO sensitive info)
        """
        print(f"\n🔍 Scanning configuration for features...")

        features_present = []
        features_checked = 0

        for feature in self.features:
            label = feature.get('label')
            domain = feature.get('domain')
            presence = feature.get('presence', {})
            config_regexes = presence.get('config_regex', [])

            if not config_regexes or not label:
                continue

            features_checked += 1

            # Test if any regex pattern matches
            feature_detected = False
            for pattern in config_regexes:
                try:
                    if re.search(pattern, config_text, re.MULTILINE | re.IGNORECASE):
                        feature_detected = True
                        break
                except re.error as e:
                    print(f"  ⚠️  Invalid regex for {label}: {e}")
                    continue

            if feature_detected:
                features_present.append(label)
                print(f"  ✓ {label} ({domain})")

        snapshot = {
            "snapshot_id": f"snapshot-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
            "platform": self.platform,
            "extracted_at": datetime.now().isoformat(),
            "features_present": sorted(features_present),
            "feature_count": len(features_present),
            "total_checked": features_checked,
            "extractor_version": "1.0.0"
        }

        print(f"\n📊 Summary: {len(features_present)}/{features_checked} features detected")
        return snapshot


class DeviceConnector:
    """Connect to live device via SSH (requires netmiko)"""

    def __init__(self, host: str, username: str, password: str,
                 device_type: str = 'cisco_ios', port: int = 22):
        """
        Initialize device connector

        Args:
            host: Device IP/hostname
            username: SSH username
            password: SSH password
            device_type: Netmiko device type
            port: SSH port
        """
        if not NETMIKO_AVAILABLE:
            raise RuntimeError("netmiko library not installed. Install with: pip install netmiko")

        self.device_params = {
            'device_type': device_type,
            'host': host,
            'username': username,
            'password': password,
            'port': port,
        }
        self.connection = None
        self.show_version_output = None  # Store for hardware detection
        self.hardware_model = None  # Detected hardware model
        self.version = None  # Detected software version

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

    def get_running_config(self) -> str:
        """Retrieve running configuration"""
        print("📥 Downloading running configuration...")
        config = self.connection.send_command("show running-config", read_timeout=120)
        print(f"✅ Retrieved {len(config)} characters")
        return config

    def detect_platform(self) -> str:
        """Auto-detect device platform, hardware model, and version"""
        print("🔍 Detecting platform, hardware, and version...")
        version_output = self.connection.send_command("show version")

        # Store for hardware detection
        self.show_version_output = version_output

        # Platform detection patterns
        if re.search(r'Cisco IOS XE Software', version_output, re.IGNORECASE):
            platform = 'IOS-XE'
        elif re.search(r'Cisco IOS XR Software', version_output, re.IGNORECASE):
            platform = 'IOS-XR'
        elif re.search(r'Cisco Adaptive Security Appliance', version_output, re.IGNORECASE):
            platform = 'ASA'
        elif re.search(r'Cisco Firepower Threat Defense', version_output, re.IGNORECASE):
            platform = 'FTD'
        elif re.search(r'Cisco Nexus Operating System', version_output, re.IGNORECASE):
            platform = 'NX-OS'
        else:
            platform = 'IOS-XE'  # Default fallback

        # Version extraction
        self.version = self._extract_version(version_output, platform)

        # Hardware detection (if available)
        if HARDWARE_EXTRACTION_AVAILABLE:
            self.hardware_model = extract_hardware_model_from_show_version(version_output)
            if self.hardware_model:
                print(f"✅ Detected platform: {platform}, version: {self.version or 'unknown'}, hardware: {self.hardware_model}")
            else:
                print(f"✅ Detected platform: {platform}, version: {self.version or 'unknown'} (generic, no specific hardware)")
        else:
            print(f"✅ Detected platform: {platform}, version: {self.version or 'unknown'}")

        return platform

    def _extract_version(self, version_output: str, platform: str) -> Optional[str]:
        """Extract software version from show version output"""
        # IOS-XE patterns
        if platform == 'IOS-XE':
            # Example: Cisco IOS XE Software, Version 17.10.1
            match = re.search(r'(?:Version|version)\s+([0-9]+\.[0-9]+(?:\.[0-9]+)?(?:[A-Za-z])?)', version_output)
            if match:
                return match.group(1)

        # IOS-XR patterns
        elif platform == 'IOS-XR':
            # Example: Cisco IOS XR Software, Version 7.3.2
            match = re.search(r'(?:Version|version)\s+([0-9]+\.[0-9]+\.[0-9]+)', version_output)
            if match:
                return match.group(1)

        # ASA patterns
        elif platform == 'ASA':
            # Example: Cisco Adaptive Security Appliance Software Version 9.16(4)
            match = re.search(r'(?:Version|version)\s+([0-9]+\.[0-9]+(?:\([0-9]+\))?)', version_output)
            if match:
                return match.group(1)

        # FTD patterns
        elif platform == 'FTD':
            # Example: Cisco Firepower Threat Defense for Firepower 2100 Series Version 7.0.1
            match = re.search(r'(?:Version|version)\s+([0-9]+\.[0-9]+\.[0-9]+)', version_output)
            if match:
                return match.group(1)

        # NX-OS patterns
        elif platform == 'NX-OS':
            # Example: NXOS: version 9.3(8)
            match = re.search(r'(?:version|NXOS:.*version)\s+([0-9]+\.[0-9]+\([0-9]+\))', version_output, re.IGNORECASE)
            if match:
                return match.group(1)

        return None


def extract_from_live_device(host: str, username: str, password: str,
                             platform: Optional[str] = None,
                             device_type: str = 'cisco_ios',
                             features_dir: str = '.') -> Dict:
    """
    Extract features from live device via SSH

    Args:
        host: Device IP/hostname
        username: SSH username
        password: SSH password
        platform: Platform override (auto-detect if None)
        device_type: Netmiko device type
        features_dir: Directory with features_*.yml files

    Returns:
        Feature snapshot dict (includes version, hardware_model if detected)
    """
    connector = DeviceConnector(host, username, password, device_type)

    try:
        connector.connect()

        # Auto-detect platform if not specified
        if not platform:
            platform = connector.detect_platform()

        # Get running config
        config = connector.get_running_config()

        # Extract features
        extractor = FeatureExtractor(platform, features_dir)
        snapshot = extractor.extract_from_config(config)

        # Add version and hardware model to snapshot (if detected)
        snapshot['version'] = connector.version
        snapshot['hardware_model'] = connector.hardware_model

        return snapshot

    finally:
        connector.disconnect()


def extract_from_config_file(config_file: str, platform: str,
                             features_dir: str = '.',
                             hardware_model: Optional[str] = None) -> Dict:
    """
    Extract features from offline config file

    Args:
        config_file: Path to running-config file
        platform: Platform (IOS-XE, IOS-XR, ASA, FTD, NX-OS)
        features_dir: Directory with features_*.yml files
        hardware_model: Optional hardware model (if known)

    Returns:
        Feature snapshot dict
    """
    config_path = Path(config_file)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_file}")

    print(f"📂 Reading config from: {config_path}")
    with open(config_path, 'r') as f:
        config = f.read()

    print(f"✅ Loaded {len(config)} characters")

    # Extract features
    extractor = FeatureExtractor(platform, features_dir)
    snapshot = extractor.extract_from_config(config)

    # Add hardware model (if provided)
    snapshot['hardware_model'] = hardware_model

    return snapshot


def save_snapshot(snapshot: Dict, output_file: str):
    """Save snapshot to JSON file"""
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        json.dump(snapshot, f, indent=2)

    print(f"\n💾 Snapshot saved to: {output_path}")
    print(f"📄 File size: {output_path.stat().st_size} bytes")


def main():
    parser = argparse.ArgumentParser(
        description='Extract device features without capturing sensitive data',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Live device (prompt for password)
  python extract_device_features.py --host 192.168.1.1 --username admin -o snapshot.json

  # Live device with platform override
  python extract_device_features.py --host 192.168.1.1 --username admin --platform IOS-XR -o snapshot.json

  # Offline config file
  python extract_device_features.py --config running-config.txt --platform IOS-XE -o snapshot.json

  # Specify features directory
  python extract_device_features.py --config config.txt --platform ASA --features-dir /path/to/yamls -o snapshot.json
        """
    )

    # Mode selection
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument('--host', help='Device IP/hostname (live mode)')
    mode_group.add_argument('--config', help='Config file path (offline mode)')

    # Common options
    parser.add_argument('--platform',
                       choices=['IOS-XE', 'IOS-XR', 'ASA', 'FTD', 'NX-OS'],
                       help='Platform (auto-detect if not specified in live mode)')
    parser.add_argument('--hardware-model',
                       help='Hardware model (auto-detect in live mode, manual for offline mode, e.g., Cat9200, ASR9K)')
    parser.add_argument('-o', '--output', required=True,
                       help='Output snapshot file (JSON)')
    parser.add_argument('--features-dir', default='.',
                       help='Directory containing features_*.yml files (default: current dir)')

    # Live mode options
    parser.add_argument('--username', help='SSH username (required for live mode)')
    parser.add_argument('--password', help='SSH password (prompt if not provided)')
    parser.add_argument('--device-type', default='cisco_ios',
                       help='Netmiko device type (default: cisco_ios)')
    parser.add_argument('--port', type=int, default=22,
                       help='SSH port (default: 22)')

    args = parser.parse_args()

    # Validate arguments
    if args.host and not args.username:
        parser.error("--username required for live device mode")

    if args.config and not args.platform:
        parser.error("--platform required for offline config mode")

    try:
        print("="*80)
        print("🚀 Device Feature Extractor v1.0.0")
        print("="*80)

        # Live device mode
        if args.host:
            # Get password
            if args.password:
                password = args.password
            else:
                password = getpass.getpass(f"Password for {args.username}@{args.host}: ")

            snapshot = extract_from_live_device(
                host=args.host,
                username=args.username,
                password=password,
                platform=args.platform,
                device_type=args.device_type,
                features_dir=args.features_dir
            )

        # Offline config mode
        else:
            snapshot = extract_from_config_file(
                config_file=args.config,
                platform=args.platform,
                features_dir=args.features_dir,
                hardware_model=args.hardware_model
            )

        # Save snapshot
        save_snapshot(snapshot, args.output)

        print("\n✅ Feature extraction complete!")
        print(f"📊 {snapshot['feature_count']} features detected")
        print(f"🔒 No sensitive data captured")

        return 0

    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        return 130
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
