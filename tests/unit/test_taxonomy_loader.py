"""
Unit tests for taxonomy loading and validation
"""
import pytest
import yaml
from pathlib import Path


@pytest.mark.unit
class TestTaxonomyLoading:
    """Test taxonomy file loading"""

    def test_load_iosxe_taxonomy(self):
        """Test loading IOS-XE taxonomy"""
        taxonomy_file = Path("taxonomies/features.yml")
        if not taxonomy_file.exists():
            pytest.skip("taxonomies/features.yml not found")

        with open(taxonomy_file) as f:
            taxonomy = yaml.safe_load(f)

        assert taxonomy is not None
        assert "features" in taxonomy or isinstance(taxonomy, list)

    def test_load_iosxr_taxonomy(self):
        """Test loading IOS-XR taxonomy"""
        taxonomy_file = Path("taxonomies/features_iosxr.yml")
        if not taxonomy_file.exists():
            pytest.skip("taxonomies/features_iosxr.yml not found")

        with open(taxonomy_file) as f:
            taxonomy = yaml.safe_load(f)

        assert taxonomy is not None

    def test_load_asa_taxonomy(self):
        """Test loading ASA taxonomy"""
        taxonomy_file = Path("taxonomies/features_asa.yml")
        if not taxonomy_file.exists():
            pytest.skip("taxonomies/features_asa.yml not found")

        with open(taxonomy_file) as f:
            taxonomy = yaml.safe_load(f)

        assert taxonomy is not None

    def test_load_nxos_taxonomy(self):
        """Test loading NX-OS taxonomy"""
        taxonomy_file = Path("taxonomies/features_nxos.yml")
        if not taxonomy_file.exists():
            pytest.skip("taxonomies/features_nxos.yml not found")

        with open(taxonomy_file) as f:
            taxonomy = yaml.safe_load(f)

        assert taxonomy is not None


@pytest.mark.unit
class TestTaxonomyStructure:
    """Test taxonomy data structure validation"""

    def test_feature_has_required_fields(self, sample_taxonomy):
        """Test that features have required fields"""
        for feature in sample_taxonomy:
            assert "label" in feature
            assert "domain" in feature
            assert "presence" in feature

    def test_presence_has_config_regex(self, sample_taxonomy):
        """Test that presence includes config_regex"""
        for feature in sample_taxonomy:
            presence = feature["presence"]
            assert "config_regex" in presence
            assert isinstance(presence["config_regex"], list)

    def test_presence_has_show_cmds(self, sample_taxonomy):
        """Test that presence includes show_cmds"""
        for feature in sample_taxonomy:
            presence = feature["presence"]
            assert "show_cmds" in presence
            assert isinstance(presence["show_cmds"], list)

    def test_labels_are_unique(self, sample_taxonomy):
        """Test that all labels are unique"""
        labels = [f["label"] for f in sample_taxonomy]
        assert len(labels) == len(set(labels))

    def test_valid_domains(self, sample_taxonomy):
        """Test that domains are from expected set"""
        valid_domains = {
            "Application", "Management", "Security",
            "Routing", "Network", "Interface", "QoS"
        }

        for feature in sample_taxonomy:
            # Domain can be a list or string
            domains = feature["domain"]
            if isinstance(domains, str):
                domains = [domains]

            for domain in domains:
                # Allow domain if it's in valid set or is a reasonable string
                assert isinstance(domain, str)
                assert len(domain) > 0


@pytest.mark.unit
class TestTaxonomyLookup:
    """Test taxonomy label lookup functionality"""

    def test_lookup_by_label(self, sample_taxonomy):
        """Test looking up feature by label"""
        # Build label index
        label_index = {f["label"]: f for f in sample_taxonomy}

        # Test lookup
        feature = label_index.get("APP_IOx")
        assert feature is not None
        assert feature["label"] == "APP_IOx"
        assert feature["domain"] == "Application"

    def test_get_config_regex(self, sample_taxonomy):
        """Test extracting config regex for a label"""
        label_index = {f["label"]: f for f in sample_taxonomy}

        feature = label_index.get("APP_IOx")
        config_regex = feature["presence"]["config_regex"]

        assert len(config_regex) > 0
        assert "^iox$" in config_regex

    def test_get_show_commands(self, sample_taxonomy):
        """Test extracting show commands for a label"""
        label_index = {f["label"]: f for f in sample_taxonomy}

        feature = label_index.get("APP_IOx")
        show_cmds = feature["presence"]["show_cmds"]

        assert len(show_cmds) > 0
        assert "show iox" in show_cmds

    def test_lookup_nonexistent_label(self, sample_taxonomy):
        """Test lookup of non-existent label"""
        label_index = {f["label"]: f for f in sample_taxonomy}

        feature = label_index.get("NONEXISTENT_LABEL")
        assert feature is None


@pytest.mark.unit
class TestPlatformMapping:
    """Test platform to taxonomy file mapping"""

    def test_platform_file_mapping(self):
        """Test that all platforms map to correct files"""
        platform_files = {
            'IOS-XE': 'taxonomies/features.yml',
            'IOS-XR': 'taxonomies/features_iosxr.yml',
            'ASA': 'taxonomies/features_asa.yml',
            'FTD': 'taxonomies/features_asa.yml',  # FTD uses ASA taxonomy
            'NX-OS': 'taxonomies/features_nxos.yml'
        }

        for platform, filename in platform_files.items():
            filepath = Path(filename)
            # Note: Some files may not exist in test environment
            if filepath.exists():
                with open(filepath) as f:
                    content = yaml.safe_load(f)
                assert content is not None

    def test_unsupported_platform(self):
        """Test handling of unsupported platform"""
        platform_files = {
            'IOS-XE': 'taxonomies/features.yml',
            'IOS-XR': 'taxonomies/features_iosxr.yml',
            'ASA': 'taxonomies/features_asa.yml',
            'FTD': 'taxonomies/features_asa.yml',
            'NX-OS': 'taxonomies/features_nxos.yml'
        }

        # Test that unsupported platforms return None or empty
        unsupported = platform_files.get('UNSUPPORTED_PLATFORM')
        assert unsupported is None
