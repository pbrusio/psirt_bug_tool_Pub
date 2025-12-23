"""
Unit tests for feature detection using regex patterns
"""
import pytest
import re


@pytest.mark.unit
class TestConfigRegexMatching:
    """Test config regex pattern matching"""

    def test_iox_detection(self, sample_device_config):
        """Test IOx feature detection"""
        # IOx patterns
        patterns = [r'^iox$', r'^app-hosting']

        # This config doesn't have IOx
        matches = []
        for pattern in patterns:
            if re.search(pattern, sample_device_config, re.MULTILINE):
                matches.append(pattern)

        assert len(matches) == 0  # Sample config has no IOx

    def test_ssh_detection(self, sample_device_config):
        """Test SSH feature detection"""
        # SSH patterns
        patterns = [r'^ip ssh', r'transport input ssh']

        matches = []
        for pattern in patterns:
            if re.search(pattern, sample_device_config, re.MULTILINE):
                matches.append(pattern)

        # Sample config has SSH
        assert len(matches) > 0

    def test_copp_detection(self, sample_device_config):
        """Test CoPP (Control Plane Policing) detection"""
        # CoPP patterns
        patterns = [r'^control-plane', r'service-policy input']

        matches = []
        for pattern in patterns:
            if re.search(pattern, sample_device_config, re.MULTILINE):
                matches.append(pattern)

        # Sample config has CoPP
        assert len(matches) > 0

    def test_case_sensitivity(self):
        """Test that regex patterns are case-sensitive"""
        config = "IP SSH version 2\nip ssh version 2"
        pattern = r'^ip ssh'

        # Should match lowercase but not uppercase
        matches = re.findall(pattern, config, re.MULTILINE)
        assert len(matches) == 1

    def test_multiline_regex(self):
        """Test multiline regex patterns"""
        config = """
control-plane
 service-policy input copp-system-policy
!
"""
        # Pattern that spans lines
        pattern = r'control-plane.*?service-policy'

        match = re.search(pattern, config, re.DOTALL)
        assert match is not None


@pytest.mark.unit
class TestFeaturePresenceLogic:
    """Test logic for determining feature presence"""

    def test_any_pattern_matches(self):
        """Test that any matching pattern indicates presence"""
        config = "ip ssh version 2"
        patterns = [r'^iox$', r'^ip ssh', r'^crypto']

        # At least one pattern matches
        is_present = any(
            re.search(pattern, config, re.MULTILINE)
            for pattern in patterns
        )

        assert is_present is True

    def test_no_pattern_matches(self):
        """Test that no matches indicates absence"""
        config = "ip route 0.0.0.0 0.0.0.0 192.168.1.1"
        patterns = [r'^iox$', r'^ip ssh', r'^crypto']

        is_present = any(
            re.search(pattern, config, re.MULTILINE)
            for pattern in patterns
        )

        assert is_present is False

    def test_empty_patterns(self):
        """Test handling of empty pattern list"""
        config = "ip ssh version 2"
        patterns = []

        is_present = any(
            re.search(pattern, config, re.MULTILINE)
            for pattern in patterns
        )

        assert is_present is False

    def test_empty_config(self):
        """Test handling of empty config"""
        config = ""
        patterns = [r'^ip ssh']

        is_present = any(
            re.search(pattern, config, re.MULTILINE)
            for pattern in patterns
        )

        assert is_present is False


@pytest.mark.unit
class TestRegexPatternValidation:
    """Test that regex patterns are valid"""

    def test_patterns_compile(self, sample_taxonomy):
        """Test that all taxonomy regex patterns compile"""
        for feature in sample_taxonomy:
            patterns = feature["presence"]["config_regex"]

            for pattern in patterns:
                try:
                    re.compile(pattern)
                except re.error as e:
                    pytest.fail(f"Invalid regex in {feature['label']}: {pattern} - {e}")

    def test_pattern_not_too_greedy(self):
        """Test that patterns aren't overly greedy"""
        # Example of overly greedy pattern
        greedy_pattern = r'.*'

        config = "ip ssh version 2\nip http server\nip domain name cisco.com"

        # This would match entire config
        match = re.search(greedy_pattern, config)

        # Should avoid such patterns in taxonomy
        assert match.group() != config  # Not matching everything

    def test_anchor_patterns_work(self):
        """Test that ^ and $ anchors work as expected"""
        config = "  iox\niox\n"

        # ^ should only match start of line
        pattern_start = r'^iox'
        matches = re.findall(pattern_start, config, re.MULTILINE)

        # Should match "iox" at line start, not "  iox"
        assert len(matches) == 1
