"""
Version Matching Logic for Vulnerability Scanning

Compares device versions against vulnerability version patterns to determine if affected.

Key Logic:
- Respects version patterns (EXPLICIT, WILDCARD, OPEN_LATER, etc.)
- Checks fixed version: If device >= fixed_version, NOT vulnerable
- Handles train boundaries: "17.10.3 and later" only matches 17.10.* (not 17.11.x)
"""

from typing import Dict, Tuple, Optional
import sys
import os

# Add parent directory to path for standalone testing
if __name__ == '__main__':
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from backend.core.version_patterns import VersionPatternDetector, VersionInfo


class VersionMatcher:
    """
    Matches device versions against vulnerability version patterns.

    Returns (is_vulnerable: bool, reason: str)
    """

    @staticmethod
    def compare_versions(v1: VersionInfo, v2: VersionInfo) -> int:
        """
        Compare two versions.

        Returns:
            -1 if v1 < v2
             0 if v1 == v2
             1 if v1 > v2
        """
        t1 = v1.to_tuple()
        t2 = v2.to_tuple()

        if t1 < t2:
            return -1
        elif t1 > t2:
            return 1
        else:
            return 0

    @staticmethod
    def is_same_train(v1: VersionInfo, v2: VersionInfo, train_level: str = 'minor') -> bool:
        """
        Check if two versions are in the same train.

        Args:
            v1, v2: Versions to compare
            train_level: 'major' (17.x) or 'minor' (17.10.x)

        Returns:
            True if in same train
        """
        if train_level == 'major':
            return v1.major == v2.major
        elif train_level == 'minor':
            return v1.major == v2.major and v1.minor == v2.minor
        else:
            return False

    @classmethod
    def is_version_affected(
        cls,
        device_version: str,
        pattern_type: str,
        version_min: Optional[str],
        version_max: Optional[str],
        explicit_versions: list,
        fixed_version: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Check if device version is affected by vulnerability.

        Args:
            device_version: Device version (e.g., "17.10.1")
            pattern_type: EXPLICIT, WILDCARD, OPEN_LATER, OPEN_EARLIER, MAJOR_WILDCARD, UNKNOWN
            version_min: Minimum affected version
            version_max: Maximum affected version
            explicit_versions: List of explicit versions (for EXPLICIT pattern)
            fixed_version: First fixed release (optional)

        Returns:
            (is_vulnerable, reason)
        """
        # Parse device version
        device_ver = VersionPatternDetector.parse_version(device_version)
        if device_ver is None:
            return (False, f"Invalid device version format: {device_version}")

        # Check fixed version first (if provided)
        if fixed_version:
            fixed_ver = VersionPatternDetector.parse_version(fixed_version)
            if fixed_ver and cls.compare_versions(device_ver, fixed_ver) >= 0:
                return (False, f"Device version {device_version} >= fixed version {fixed_version}")

        # Pattern matching logic
        if pattern_type == 'EXPLICIT':
            # Device must be in explicit list
            normalized_device = str(device_ver)
            if normalized_device in explicit_versions:
                return (True, f"Device version {device_version} matches explicit vulnerable version")
            else:
                return (False, f"Device version {device_version} not in explicit vulnerable list: {explicit_versions}")

        elif pattern_type == 'WILDCARD':
            # All versions in minor train (e.g., 17.10.x)
            if version_min:
                min_ver = VersionPatternDetector.parse_version(version_min)
                if min_ver and cls.is_same_train(device_ver, min_ver, 'minor'):
                    return (True, f"Device version {device_version} in vulnerable train {min_ver.major}.{min_ver.minor}.*")
                else:
                    return (False, f"Device version {device_version} not in vulnerable train {min_ver.major}.{min_ver.minor}.*")
            else:
                return (False, "WILDCARD pattern missing version_min")

        elif pattern_type == 'OPEN_LATER':
            # Version X and later WITHIN SAME MINOR TRAIN
            # Key: "17.10.3 and later" only matches 17.10.* (not 17.11.x)
            if version_min:
                min_ver = VersionPatternDetector.parse_version(version_min)
                if min_ver:
                    # Check if in same minor train
                    if not cls.is_same_train(device_ver, min_ver, 'minor'):
                        return (False, f"Device version {device_version} not in same train as {version_min}")

                    # Check if >= min version
                    if cls.compare_versions(device_ver, min_ver) >= 0:
                        return (True, f"Device version {device_version} >= {version_min} (within same train)")
                    else:
                        return (False, f"Device version {device_version} < {version_min}")
                else:
                    return (False, "OPEN_LATER pattern has invalid version_min")
            else:
                return (False, "OPEN_LATER pattern missing version_min")

        elif pattern_type == 'OPEN_EARLIER':
            # Version X and earlier
            if version_max:
                max_ver = VersionPatternDetector.parse_version(version_max)
                if max_ver:
                    if cls.compare_versions(device_ver, max_ver) <= 0:
                        return (True, f"Device version {device_version} <= {version_max}")
                    else:
                        return (False, f"Device version {device_version} > {version_max}")
                else:
                    return (False, "OPEN_EARLIER pattern has invalid version_max")
            else:
                return (False, "OPEN_EARLIER pattern missing version_max")

        elif pattern_type == 'MAJOR_WILDCARD':
            # All versions in major train (e.g., 17.x or "17.10 and later")
            if version_min:
                min_ver = VersionPatternDetector.parse_version(version_min)
                if min_ver:
                    # Check major version match
                    if device_ver.major != min_ver.major:
                        return (False, f"Device version {device_version} not in major train {min_ver.major}.*")

                    # If min has minor version, check >= min
                    if min_ver.minor is not None:
                        if cls.compare_versions(device_ver, min_ver) >= 0:
                            return (True, f"Device version {device_version} >= {version_min} (major wildcard)")
                        else:
                            return (False, f"Device version {device_version} < {version_min}")
                    else:
                        # No minor version constraint, any version in major train is affected
                        return (True, f"Device version {device_version} in vulnerable major train {min_ver.major}.*")
                else:
                    return (False, "MAJOR_WILDCARD pattern has invalid version_min")
            else:
                return (False, "MAJOR_WILDCARD pattern missing version_min")

        elif pattern_type == 'UNKNOWN':
            return (False, "Unknown version pattern, cannot determine vulnerability")

        else:
            return (False, f"Unsupported pattern type: {pattern_type}")


if __name__ == '__main__':
    # Test cases
    matcher = VersionMatcher()

    print("Version Matching Tests:")
    print("=" * 80)

    # Test 1: EXPLICIT pattern
    print("\n1. EXPLICIT pattern: 17.10.1, 17.12.4, 17.13.1")
    test_versions = ["17.10.1", "17.10.5", "17.12.4", "17.15.1"]
    for version in test_versions:
        result, reason = matcher.is_version_affected(
            device_version=version,
            pattern_type='EXPLICIT',
            version_min='17.10.1',
            version_max='17.13.1',
            explicit_versions=['17.10.1', '17.12.4', '17.13.1']
        )
        print(f"  {version}: {'VULNERABLE' if result else 'NOT VULNERABLE'} - {reason}")

    # Test 2: WILDCARD pattern
    print("\n2. WILDCARD pattern: 17.10.x")
    test_versions = ["17.10.1", "17.10.5", "17.11.1", "17.9.3"]
    for version in test_versions:
        result, reason = matcher.is_version_affected(
            device_version=version,
            pattern_type='WILDCARD',
            version_min='17.10.0',
            version_max=None,
            explicit_versions=[]
        )
        print(f"  {version}: {'VULNERABLE' if result else 'NOT VULNERABLE'} - {reason}")

    # Test 3: OPEN_LATER pattern (KEY TEST - train boundary)
    print("\n3. OPEN_LATER pattern: 17.10.3 and later (only 17.10.* train)")
    test_versions = ["17.10.2", "17.10.3", "17.10.5", "17.11.1"]
    for version in test_versions:
        result, reason = matcher.is_version_affected(
            device_version=version,
            pattern_type='OPEN_LATER',
            version_min='17.10.3',
            version_max=None,
            explicit_versions=[]
        )
        print(f"  {version}: {'VULNERABLE' if result else 'NOT VULNERABLE'} - {reason}")

    # Test 4: Fixed version check
    print("\n4. Fixed version check: 17.10.3 and later, fixed in 17.10.5")
    test_versions = ["17.10.3", "17.10.4", "17.10.5", "17.10.6"]
    for version in test_versions:
        result, reason = matcher.is_version_affected(
            device_version=version,
            pattern_type='OPEN_LATER',
            version_min='17.10.3',
            version_max=None,
            explicit_versions=[],
            fixed_version='17.10.5'
        )
        print(f"  {version}: {'VULNERABLE' if result else 'NOT VULNERABLE'} - {reason}")

    # Test 5: MAJOR_WILDCARD pattern
    print("\n5. MAJOR_WILDCARD pattern: 17.10 and later")
    test_versions = ["17.9.3", "17.10.1", "17.11.1", "17.15.3", "18.1.1"]
    for version in test_versions:
        result, reason = matcher.is_version_affected(
            device_version=version,
            pattern_type='MAJOR_WILDCARD',
            version_min='17.10',
            version_max=None,
            explicit_versions=[]
        )
        print(f"  {version}: {'VULNERABLE' if result else 'NOT VULNERABLE'} - {reason}")
