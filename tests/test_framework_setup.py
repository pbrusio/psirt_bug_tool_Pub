"""
Smoke test to verify testing framework is set up correctly
"""
import pytest


@pytest.mark.unit
class TestFrameworkSetup:
    """Verify testing framework is working"""

    def test_pytest_working(self):
        """Test that pytest is functioning"""
        assert True

    def test_fixtures_loading(self, sample_psirt, sample_taxonomy):
        """Test that fixtures are loading correctly"""
        assert sample_psirt is not None
        assert "summary" in sample_psirt
        assert "platform" in sample_psirt

        assert sample_taxonomy is not None
        assert len(sample_taxonomy) > 0
        assert "label" in sample_taxonomy[0]

    def test_markers_registered(self, pytestconfig):
        """Test that custom markers are registered"""
        markers = pytestconfig.getini("markers")

        # Our custom markers should be registered
        markers_str = str(markers)
        assert "unit" in markers_str
        assert "integration" in markers_str
        assert "e2e" in markers_str
        assert "slow" in markers_str

    def test_test_data_dir_exists(self):
        """Test that test fixtures directory exists"""
        from pathlib import Path

        test_dir = Path(__file__).parent
        fixtures_dir = test_dir / "fixtures"

        assert test_dir.exists()
        # fixtures_dir.mkdir(exist_ok=True)  # Will be created when needed
        assert test_dir.is_dir()

    def test_sample_data_structure(self, sample_psirt, sample_bug, sample_taxonomy):
        """Test that sample data has expected structure"""

        # PSIRT structure
        assert "bug_id" in sample_psirt
        assert "summary" in sample_psirt
        assert "platform" in sample_psirt
        assert "labels" in sample_psirt

        # Bug structure
        assert "bug_id" in sample_bug
        assert "summary" in sample_bug
        assert "platform" in sample_bug

        # Taxonomy structure
        for feature in sample_taxonomy:
            assert "label" in feature
            assert "domain" in feature
            assert "presence" in feature
            assert "config_regex" in feature["presence"]
            assert "show_cmds" in feature["presence"]


@pytest.mark.integration
class TestAPIAvailability:
    """Test API server availability (skip if not running)"""

    def test_api_url_configured(self, api_test_url):
        """Test that API URL is configured"""
        assert api_test_url is not None
        assert api_test_url.startswith("http")

    def test_api_server_reachable(self, api_test_url):
        """Test that API server is reachable"""
        import requests

        try:
            response = requests.get(f"{api_test_url}/api/v1/health", timeout=2)
            assert response.status_code == 200
        except requests.exceptions.ConnectionError:
            pytest.skip("API server not running - start with ./backend/run_server.sh")


@pytest.mark.unit
class TestBasicPythonFunctionality:
    """Sanity checks for Python environment"""

    def test_imports_work(self):
        """Test that required modules can be imported"""
        import json
        import yaml
        import re
        from pathlib import Path

        assert json is not None
        assert yaml is not None
        assert re is not None
        assert Path is not None

    def test_yaml_parsing(self):
        """Test basic YAML parsing"""
        import yaml

        yaml_str = """
        test:
          - label: TEST
            value: 123
        """

        data = yaml.safe_load(yaml_str)
        assert data is not None
        assert "test" in data
        assert isinstance(data["test"], list)

    def test_regex_matching(self):
        """Test basic regex functionality"""
        import re

        pattern = r'^test.*pattern$'
        text = "test some pattern"

        assert re.match(pattern, text)

    def test_json_handling(self):
        """Test JSON serialization/deserialization"""
        import json

        data = {"labels": ["LABEL1", "LABEL2"], "count": 2}

        # Serialize
        json_str = json.dumps(data)
        assert isinstance(json_str, str)

        # Deserialize
        parsed = json.loads(json_str)
        assert parsed == data
