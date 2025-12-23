"""
Unit tests for version parsing logic
"""
import pytest
from version_matcher import VersionParser


@pytest.mark.unit
class TestVersionNormalization:
    """Test version string normalization"""

    def test_normalize_with_leading_zeros(self):
        """Test that leading zeros are handled correctly"""
        assert VersionParser.normalize_version("17.03.05") == (17, 3, 5)
        assert VersionParser.normalize_version("17.3.5") == (17, 3, 5)
        assert VersionParser.normalize_version("17.03.5") == (17, 3, 5)

    def test_normalize_partial_versions(self):
        """Test partial version strings"""
        assert VersionParser.normalize_version("17.3") == (17, 3, 0)
        assert VersionParser.normalize_version("17") == (17, 0, 0)

    def test_normalize_with_letter_suffix(self):
        """Test that letter suffixes are ignored"""
        assert VersionParser.normalize_version("17.3.1a") == (17, 3, 1)
        assert VersionParser.normalize_version("17.3.1MD") == (17, 3, 1)

    def test_normalize_invalid_version(self):
        """Test handling of invalid version strings"""
        assert VersionParser.normalize_version("invalid") is None
        assert VersionParser.normalize_version("") is None
        assert VersionParser.normalize_version(None) is None


@pytest.mark.unit
class TestVersionComparison:
    """Test version comparison logic"""

    def test_equal_versions(self):
        """Test equal versions"""
        v1 = (17, 3, 5)
        v2 = (17, 3, 5)
        assert VersionParser.compare_versions(v1, v2) == 0

    def test_less_than(self):
        """Test v1 < v2"""
        v1 = (17, 3, 4)
        v2 = (17, 3, 5)
        assert VersionParser.compare_versions(v1, v2) == -1

    def test_greater_than(self):
        """Test v1 > v2"""
        v1 = (17, 3, 6)
        v2 = (17, 3, 5)
        assert VersionParser.compare_versions(v1, v2) == 1

    def test_major_version_difference(self):
        """Test major version comparison"""
        v1 = (16, 9, 9)
        v2 = (17, 1, 1)
        assert VersionParser.compare_versions(v1, v2) == -1

    def test_minor_version_difference(self):
        """Test minor version comparison"""
        v1 = (17, 2, 9)
        v2 = (17, 3, 1)
        assert VersionParser.compare_versions(v1, v2) == -1


@pytest.mark.unit
class TestVersionParsing:
    """Test version parsing from strings"""

    def test_parse_standard_format(self):
        """Test parsing standard version string"""
        version = VersionParser.normalize_version("17.3.1")
        assert version == (17, 3, 1)

    def test_parse_cisco_format(self):
        """Test parsing Cisco-style version from product string"""
        # Extract version from product name string
        import re
        product_name = "Cisco IOS XE Software, Version 17.3.1"
        match = re.search(r'(\d+\.\d+(?:\.\d+)?)', product_name)
        if match:
            version = VersionParser.normalize_version(match.group(1))
            assert version == (17, 3, 1)

    def test_parse_with_patch_letters(self):
        """Test parsing versions with patch letter suffixes"""
        assert VersionParser.normalize_version("17.9.3a") == (17, 9, 3)
        assert VersionParser.normalize_version("16.12.4b") == (16, 12, 4)
