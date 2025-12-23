#!/usr/bin/env python3
"""
Version Matcher for Cisco PSIRT Verification
Parses product names and matches device versions against affected ranges
"""
import re
from typing import Optional, Tuple, List, Dict


class VersionParser:
    """Parse and normalize Cisco software versions"""

    # Platform name mappings
    PLATFORM_PATTERNS = {
        'IOS-XE': [
            r'IOS\s*XE',
            r'Cisco\s+Catalyst',
        ],
        'IOS-XR': [
            r'IOS\s*XR',
        ],
        'ASA': [
            r'ASA',
            r'Adaptive\s+Security\s+Appliance',
        ],
        'FTD': [
            r'FTD',
            r'Firepower\s+Threat\s+Defense',
        ],
        'NX-OS': [
            r'NX-?OS',
            r'Nexus',
        ]
    }

    @staticmethod
    def normalize_version(version_str: str) -> Optional[Tuple[int, int, int]]:
        """
        Normalize version string to tuple for comparison

        Examples:
            "17.03.05" → (17, 3, 5)
            "17.3.5"   → (17, 3, 5)
            "17.3"     → (17, 3, 0)
            "17"       → (17, 0, 0)
            "16.12.4a" → (16, 12, 4)  # Ignore letter suffix
        """
        if not version_str:
            return None

        # Extract numeric parts: major.minor.patch
        # Match patterns like: 17.03.05, 17.3.5, 17.3, 17
        match = re.search(r'(\d+)(?:\.(\d+))?(?:\.(\d+))?', str(version_str))

        if not match:
            return None

        major = int(match.group(1))
        minor = int(match.group(2)) if match.group(2) else 0
        patch = int(match.group(3)) if match.group(3) else 0

        return (major, minor, patch)

    @staticmethod
    def compare_versions(v1: Tuple[int, int, int], v2: Tuple[int, int, int]) -> int:
        """
        Compare two version tuples

        Returns:
            -1 if v1 < v2
             0 if v1 == v2
             1 if v1 > v2
        """
        if v1 < v2:
            return -1
        elif v1 > v2:
            return 1
        else:
            return 0

    @staticmethod
    def extract_platform(product_name: str) -> Optional[str]:
        """
        Extract platform from product name

        Examples:
            "Cisco IOS XE Software, Version 17.3.1" → "IOS-XE"
            "Cisco Adaptive Security Appliance (ASA) 9.12" → "ASA"
            "Cisco Firepower Threat Defense Software 6.2.3" → "FTD"
        """
        if not product_name:
            return None

        for platform, patterns in VersionParser.PLATFORM_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, product_name, re.IGNORECASE):
                    return platform

        return None

    @staticmethod
    def extract_version_from_product(product_name: str) -> Optional[str]:
        """
        Extract version string from product name

        Examples:
            "Cisco IOS XE Software, Version 17.3.1" → "17.3.1"
            "Cisco IOS XE 17.6.4" → "17.6.4"
            "Cisco ASA Software 9.12.1" → "9.12.1"
        """
        if not product_name:
            return None

        # Try different patterns
        patterns = [
            r'Version\s+(\d+\.\d+(?:\.\d+)?)',  # "Version 17.3.1"
            r'Release\s+(\d+\.\d+(?:\.\d+)?)',  # "Release 7.3.2"
            r'(?:IOS XE|IOS XR|ASA|FTD|NX-OS)\s+(?:Software\s+)?(\d+\.\d+(?:\.\d+)?)',  # "IOS XE 17.3.1"
            r'(\d+\.\d+(?:\.\d+)?)\s*$',  # "... 9.12.1" (version at end)
        ]

        for pattern in patterns:
            match = re.search(pattern, product_name, re.IGNORECASE)
            if match:
                return match.group(1)

        return None


class ProductNameParser:
    """Parse Cisco product names to extract platform and version info"""

    @staticmethod
    def parse_product_names(product_names: List[str], target_platform: str) -> List[str]:
        """
        Parse product names and return list of versions for target platform

        Args:
            product_names: List of product name strings from PSIRT
            target_platform: Platform to filter for (e.g., "IOS-XE")

        Returns:
            List of version strings for the target platform
        """
        versions = []

        for product in product_names:
            # Extract platform
            platform = VersionParser.extract_platform(product)

            # Skip if not target platform
            if platform != target_platform:
                continue

            # Extract version
            version = VersionParser.extract_version_from_product(product)
            if version:
                versions.append(version)

        return versions


class VersionMatcher:
    """Match device versions against PSIRT affected version ranges"""

    def __init__(self):
        self.parser = VersionParser()
        self.product_parser = ProductNameParser()

    def is_version_affected(
        self,
        device_version: str,
        device_platform: str,
        psirt_product_names: List[str]
    ) -> Dict:
        """
        Check if device version is affected by PSIRT

        Args:
            device_version: Device software version (e.g., "17.03.05")
            device_platform: Device platform (e.g., "IOS-XE")
            psirt_product_names: List of affected product names from PSIRT

        Returns:
            Dict with:
                - affected: bool
                - reason: str
                - affected_versions: list of matching versions
                - device_version_normalized: tuple
        """
        result = {
            'affected': False,
            'reason': '',
            'affected_versions': [],
            'device_version_normalized': None
        }

        # Normalize device version
        device_ver = self.parser.normalize_version(device_version)
        if not device_ver:
            result['reason'] = f"Could not parse device version: {device_version}"
            return result

        result['device_version_normalized'] = device_ver

        # Parse product names for this platform
        affected_versions = self.product_parser.parse_product_names(
            psirt_product_names, device_platform
        )

        if not affected_versions:
            result['reason'] = f"No affected versions found for {device_platform}"
            return result

        result['affected_versions'] = affected_versions

        # Check if device version matches any affected version range
        # Strategy: If device version is in same major.minor as any affected version,
        # consider it potentially affected
        for affected_ver_str in affected_versions:
            affected_ver = self.parser.normalize_version(affected_ver_str)
            if not affected_ver:
                continue

            # Same major.minor = potentially affected
            if device_ver[0] == affected_ver[0] and device_ver[1] == affected_ver[1]:
                result['affected'] = True
                result['reason'] = f"Device version {device_version} matches affected range (same train as {affected_ver_str})"
                return result

        # If we get here, device is not in any affected version range
        result['reason'] = f"Device version {device_version} not in affected ranges: {', '.join(affected_versions)}"
        return result

    def is_version_fixed(
        self,
        device_version: str,
        fixed_version: str
    ) -> bool:
        """
        Check if device version has the fix applied

        Args:
            device_version: Device software version
            fixed_version: Fixed software version from PSIRT

        Returns:
            True if device version >= fixed version
        """
        device_ver = self.parser.normalize_version(device_version)
        fixed_ver = self.parser.normalize_version(fixed_version)

        if not device_ver or not fixed_ver:
            return False

        return device_ver >= fixed_ver


def test_version_parser():
    """Test version parsing and matching"""
    print("="*80)
    print("VERSION PARSER TESTS")
    print("="*80)

    # Test version normalization
    print("\n1. Version Normalization:")
    test_versions = [
        "17.03.05",
        "17.3.5",
        "17.3",
        "17",
        "16.12.4a",
        "9.12.1"
    ]

    for ver in test_versions:
        normalized = VersionParser.normalize_version(ver)
        print(f"  {ver:15} → {normalized}")

    # Test platform extraction
    print("\n2. Platform Extraction:")
    test_products = [
        "Cisco IOS XE Software, Version 17.3.1",
        "Cisco Adaptive Security Appliance (ASA) Software 9.12",
        "Cisco Firepower Threat Defense Software 6.2.3",
        "Cisco IOS XR Software Release 7.3.2",
        "Cisco Nexus 9000 Series Switches NX-OS 9.3.1"
    ]

    for product in test_products:
        platform = VersionParser.extract_platform(product)
        version = VersionParser.extract_version_from_product(product)
        print(f"  {product[:50]:50} → {platform:8} v{version}")

    # Test version matching
    print("\n3. Version Matching:")
    matcher = VersionMatcher()

    test_cases = [
        {
            'device': '17.03.05',
            'platform': 'IOS-XE',
            'products': [
                'Cisco IOS XE Software, Version 17.3.1',
                'Cisco IOS XE Software, Version 17.6.4'
            ]
        },
        {
            'device': '17.03.05',
            'platform': 'IOS-XE',
            'products': [
                'Cisco IOS XE Software, Version 16.12.4',
                'Cisco IOS XE Software, Version 16.12.5'
            ]
        },
        {
            'device': '9.12.1',
            'platform': 'ASA',
            'products': [
                'Cisco Adaptive Security Appliance (ASA) Software 9.12',
                'Cisco Adaptive Security Appliance (ASA) Software 9.14'
            ]
        }
    ]

    for i, test in enumerate(test_cases, 1):
        print(f"\n  Test {i}:")
        print(f"    Device: {test['platform']} {test['device']}")
        print(f"    PSIRT affects: {[p[:40]+'...' for p in test['products']]}")

        result = matcher.is_version_affected(
            test['device'],
            test['platform'],
            test['products']
        )

        print(f"    Result: {'AFFECTED ⚠️' if result['affected'] else 'NOT AFFECTED ✅'}")
        print(f"    Reason: {result['reason']}")


if __name__ == '__main__':
    test_version_parser()
