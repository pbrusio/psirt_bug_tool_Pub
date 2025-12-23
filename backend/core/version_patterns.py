"""
Version Pattern Detection for Vulnerability Database

Detects version patterns from raw version strings in bug reports:
- EXPLICIT: Specific versions only (e.g., "17.10.1 17.10.5")
- WILDCARD: All versions in a train (e.g., "17.10.x")
- OPEN_LATER: Version X and later in same train (e.g., "17.10.3 and later" → only 17.10.*)
- OPEN_EARLIER: Version X and earlier (e.g., "17.10.4 and earlier")
- MAJOR_WILDCARD: All versions in major release (e.g., "17.x" or "17.10 and later")

Key Logic: "and later" only affects the significant digit
- "17.10.3 and later" = 17.10.3, 17.10.4, 17.10.5... (NOT 17.11.x)
- "17.10 and later" = 17.10.*, 17.11.*, 17.12.* (major wildcard)
"""

import re
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class VersionInfo:
    """Parsed version information"""
    major: int
    minor: Optional[int]
    patch: Optional[int]
    original: str

    def __str__(self):
        if self.patch is not None:
            return f"{self.major}.{self.minor}.{self.patch}"
        elif self.minor is not None:
            return f"{self.major}.{self.minor}"
        else:
            return f"{self.major}"

    def to_tuple(self) -> Tuple[int, int, int]:
        """Convert to comparable tuple (for sorting/comparison)"""
        return (
            self.major,
            self.minor if self.minor is not None else 0,
            self.patch if self.patch is not None else 0
        )


class VersionPatternDetector:
    """
    Detects version patterns from raw version strings.

    Examples:
        "17.10.1 17.10.5" → EXPLICIT
        "17.10.x" → WILDCARD
        "17.10.3 and later" → OPEN_LATER (only 17.10.* train)
        "17.10 and later" → MAJOR_WILDCARD (17.10+)
        "17.10.4 and earlier" → OPEN_EARLIER
    """

    @staticmethod
    def normalize_version(version_str: str) -> str:
        """
        Normalize version string: remove leading zeros, standardize format.

        Examples:
            "17.03.05" → "17.3.5"
            "17.3" → "17.3"
            "17.10.1a" → "17.10.1" (strip letter suffix)
        """
        version_str = version_str.strip()

        # Strip letter suffix (e.g., 17.10.1a → 17.10.1)
        version_str = re.sub(r'[a-zA-Z]+$', '', version_str)

        # Split and remove leading zeros
        parts = version_str.split('.')
        normalized_parts = [str(int(p)) for p in parts if p.isdigit()]

        return '.'.join(normalized_parts)

    @staticmethod
    def parse_version(version_str: str) -> Optional[VersionInfo]:
        """
        Parse version string into VersionInfo object.

        Args:
            version_str: Version string (e.g., "17.10.1", "17.3")

        Returns:
            VersionInfo object or None if invalid
        """
        normalized = VersionPatternDetector.normalize_version(version_str)
        parts = normalized.split('.')

        if len(parts) == 0 or not parts[0].isdigit():
            return None

        try:
            major = int(parts[0])
            minor = int(parts[1]) if len(parts) > 1 else None
            patch = int(parts[2]) if len(parts) > 2 else None

            return VersionInfo(major, minor, patch, version_str)
        except (ValueError, IndexError):
            return None

    @classmethod
    def detect_pattern(cls, affected_versions_raw: str) -> Dict:
        """
        Detect version pattern from raw version string.

        Args:
            affected_versions_raw: Raw version string from CSV
                                  (e.g., "17.10.1 17.12.4", "17.10.x", "17.10.3 and later")

        Returns:
            Dict with:
                - pattern: Pattern type (EXPLICIT, WILDCARD, OPEN_LATER, etc.)
                - version_min: Minimum affected version
                - version_max: Maximum affected version (if applicable)
                - versions: List of explicit versions (for EXPLICIT pattern)
                - description: Human-readable description
        """
        if not affected_versions_raw or affected_versions_raw.strip() == '':
            return {
                'pattern': 'UNKNOWN',
                'version_min': None,
                'version_max': None,
                'versions': [],
                'description': 'No version information available'
            }

        raw = affected_versions_raw.strip().lower()

        # Pattern 1: Wildcard (e.g., "17.10.x", "17.x")
        if 'x' in raw:
            wildcard_match = re.search(r'(\d+)\.(\d+)\.x', raw)
            if wildcard_match:
                major, minor = wildcard_match.groups()
                return {
                    'pattern': 'WILDCARD',
                    'version_min': f"{major}.{minor}.0",
                    'version_max': None,  # Open-ended within minor train
                    'versions': [],
                    'description': f"All versions {major}.{minor}.*"
                }

            # Major wildcard (e.g., "17.x")
            major_wildcard_match = re.search(r'(\d+)\.x', raw)
            if major_wildcard_match:
                major = major_wildcard_match.group(1)
                return {
                    'pattern': 'MAJOR_WILDCARD',
                    'version_min': f"{major}.0.0",
                    'version_max': None,
                    'versions': [],
                    'description': f"All versions {major}.*"
                }

        # Pattern 2: "and later" (e.g., "17.10.3 and later", "17.10 and later")
        if 'and later' in raw or 'or later' in raw:
            # Extract version before "and later"
            later_match = re.search(r'([\d.]+)\s+(?:and|or)\s+later', raw)
            if later_match:
                version_str = later_match.group(1)
                version_info = cls.parse_version(version_str)

                if version_info:
                    # Check if patch version specified → OPEN_LATER (only this minor train)
                    if version_info.patch is not None:
                        return {
                            'pattern': 'OPEN_LATER',
                            'version_min': str(version_info),
                            'version_max': None,
                            'versions': [],
                            'description': f"{version_info} and later (within {version_info.major}.{version_info.minor}.* train)"
                        }
                    else:
                        # No patch version → MAJOR_WILDCARD (crosses minor trains)
                        return {
                            'pattern': 'MAJOR_WILDCARD',
                            'version_min': str(version_info),
                            'version_max': None,
                            'versions': [],
                            'description': f"{version_info} and later (all subsequent trains)"
                        }

        # Pattern 3: "and earlier" (e.g., "17.10.4 and earlier")
        if 'and earlier' in raw or 'or earlier' in raw:
            earlier_match = re.search(r'([\d.]+)\s+(?:and|or)\s+earlier', raw)
            if earlier_match:
                version_str = earlier_match.group(1)
                version_info = cls.parse_version(version_str)

                if version_info:
                    return {
                        'pattern': 'OPEN_EARLIER',
                        'version_min': None,  # Unbounded lower end
                        'version_max': str(version_info),
                        'versions': [],
                        'description': f"{version_info} and earlier"
                    }

        # Pattern 4: EXPLICIT - Space-separated versions (e.g., "17.10.1 17.12.4 17.13.1")
        # Extract all version-like strings
        version_matches = re.findall(r'\d+\.\d+(?:\.\d+)?', affected_versions_raw)

        if version_matches:
            versions = [cls.parse_version(v) for v in version_matches]
            versions = [v for v in versions if v is not None]  # Filter out None

            if versions:
                # Sort versions to find min/max
                versions_sorted = sorted(versions, key=lambda v: v.to_tuple())

                return {
                    'pattern': 'EXPLICIT',
                    'version_min': str(versions_sorted[0]),
                    'version_max': str(versions_sorted[-1]),
                    'versions': [str(v) for v in versions_sorted],
                    'description': f"Explicit versions: {', '.join(str(v) for v in versions_sorted)}"
                }

        # Fallback: Unknown pattern
        return {
            'pattern': 'UNKNOWN',
            'version_min': None,
            'version_max': None,
            'versions': [],
            'description': f'Unknown pattern: {affected_versions_raw}'
        }


if __name__ == '__main__':
    # Test cases
    detector = VersionPatternDetector()

    test_cases = [
        "17.10.1 17.12.4 17.13.1",
        "17.10.x",
        "17.10.3 and later",
        "17.10 and later",
        "17.10.4 and earlier",
        "17.x",
        "17.03.05",  # Leading zeros
        "",  # Empty
    ]

    print("Version Pattern Detection Tests:")
    print("=" * 80)

    for test in test_cases:
        result = detector.detect_pattern(test)
        print(f"\nInput: '{test}'")
        print(f"Pattern: {result['pattern']}")
        print(f"Description: {result['description']}")
        print(f"Min: {result['version_min']}, Max: {result['version_max']}")
        if result['versions']:
            print(f"Explicit versions: {result['versions']}")
