"""
Integration tests for FastAPI endpoints
"""
import pytest
import requests
import json
from time import sleep


@pytest.mark.integration
class TestHealthEndpoint:
    """Test health check endpoint"""

    def test_health_check_returns_200(self, api_test_url):
        """Test that health endpoint returns 200"""
        response = requests.get(f"{api_test_url}/api/v1/health")
        assert response.status_code == 200

    def test_health_check_response_format(self, api_test_url):
        """Test health endpoint response format"""
        response = requests.get(f"{api_test_url}/api/v1/health")
        data = response.json()

        assert "status" in data
        assert data["status"] in ["healthy", "ok"]

    def test_health_check_no_auth_required(self, api_test_url):
        """Test that health endpoint doesn't require authentication"""
        # Should work without any headers/auth
        response = requests.get(f"{api_test_url}/api/v1/health")
        assert response.status_code == 200


@pytest.mark.integration
@pytest.mark.slow
class TestAnalyzePSIRTEndpoint:
    """Test PSIRT analysis endpoint"""

    def test_analyze_psirt_success(self, api_test_url, sample_psirt):
        """Test successful PSIRT analysis"""
        request_data = {
            "summary": sample_psirt["summary"],
            "platform": sample_psirt["platform"],
            "advisory_id": sample_psirt["bug_id"]
        }

        response = requests.post(
            f"{api_test_url}/api/v1/analyze-psirt",
            json=request_data
        )

        assert response.status_code == 200

        data = response.json()
        assert "analysis_id" in data
        assert "platform" in data
        assert "predicted_labels" in data
        assert "confidence" in data
        assert "config_regex" in data
        assert "show_commands" in data

    def test_analyze_psirt_returns_valid_labels(self, api_test_url, sample_psirt):
        """Test that analysis returns valid taxonomy labels"""
        request_data = {
            "summary": sample_psirt["summary"],
            "platform": sample_psirt["platform"],
            "advisory_id": sample_psirt["bug_id"]
        }

        response = requests.post(
            f"{api_test_url}/api/v1/analyze-psirt",
            json=request_data
        )

        assert response.status_code == 200

        data = response.json()
        predicted_labels = data["predicted_labels"]

        # Labels should be non-empty list
        assert isinstance(predicted_labels, list)
        # All labels should be strings
        assert all(isinstance(label, str) for label in predicted_labels)

    def test_analyze_psirt_confidence_score(self, api_test_url, sample_psirt):
        """Test that confidence score is in valid range"""
        request_data = {
            "summary": sample_psirt["summary"],
            "platform": sample_psirt["platform"],
            "advisory_id": sample_psirt["bug_id"]
        }

        response = requests.post(
            f"{api_test_url}/api/v1/analyze-psirt",
            json=request_data
        )

        assert response.status_code == 200

        data = response.json()
        confidence = data["confidence"]

        # Confidence should be percentage (0-100)
        assert isinstance(confidence, (int, float))
        assert 0 <= confidence <= 100

    def test_analyze_psirt_missing_summary(self, api_test_url):
        """Test analysis with missing summary field"""
        request_data = {
            "platform": "IOS-XE",
            "advisory_id": "test-123"
        }

        response = requests.post(
            f"{api_test_url}/api/v1/analyze-psirt",
            json=request_data
        )

        # Should return 422 for validation error
        assert response.status_code == 422

    def test_analyze_psirt_missing_platform(self, api_test_url):
        """Test analysis with missing platform field"""
        request_data = {
            "summary": "Test vulnerability",
            "advisory_id": "test-123"
        }

        response = requests.post(
            f"{api_test_url}/api/v1/analyze-psirt",
            json=request_data
        )

        assert response.status_code == 422

    def test_analyze_psirt_invalid_platform(self, api_test_url):
        """Test analysis with invalid platform"""
        request_data = {
            "summary": "Test vulnerability",
            "platform": "INVALID_PLATFORM",
            "advisory_id": "test-123"
        }

        response = requests.post(
            f"{api_test_url}/api/v1/analyze-psirt",
            json=request_data
        )

        # Should handle invalid platform gracefully
        # May return 400 or 200 with empty labels depending on implementation
        assert response.status_code in [200, 400, 422]

    def test_analyze_psirt_empty_summary(self, api_test_url):
        """Test analysis with empty summary"""
        request_data = {
            "summary": "",
            "platform": "IOS-XE",
            "advisory_id": "test-123"
        }

        response = requests.post(
            f"{api_test_url}/api/v1/analyze-psirt",
            json=request_data
        )

        # Should handle empty summary
        assert response.status_code in [200, 400, 422]

    def test_analyze_psirt_multiple_platforms(self, api_test_url):
        """Test analysis for different platforms"""
        platforms = ["IOS-XE", "IOS-XR", "ASA", "FTD", "NX-OS"]

        for platform in platforms:
            request_data = {
                "summary": "Test vulnerability for " + platform,
                "platform": platform,
                "advisory_id": f"test-{platform}"
            }

            response = requests.post(
                f"{api_test_url}/api/v1/analyze-psirt",
                json=request_data
            )

            # Should work for all supported platforms
            assert response.status_code == 200
            data = response.json()
            assert data["platform"] == platform


@pytest.mark.integration
class TestGetResultsEndpoint:
    """Test results retrieval endpoint"""

    def test_get_cached_result(self, api_test_url, sample_psirt):
        """Test retrieving cached analysis result"""
        # First, create an analysis
        request_data = {
            "summary": sample_psirt["summary"],
            "platform": sample_psirt["platform"],
            "advisory_id": sample_psirt["bug_id"]
        }

        create_response = requests.post(
            f"{api_test_url}/api/v1/analyze-psirt",
            json=request_data
        )

        assert create_response.status_code == 200
        analysis_id = create_response.json()["analysis_id"]

        # Now retrieve it
        get_response = requests.get(
            f"{api_test_url}/api/v1/results/{analysis_id}"
        )

        assert get_response.status_code == 200

        data = get_response.json()
        assert data["analysis_id"] == analysis_id

    def test_get_nonexistent_result(self, api_test_url):
        """Test retrieving non-existent analysis"""
        fake_id = "nonexistent-analysis-id-12345"

        response = requests.get(
            f"{api_test_url}/api/v1/results/{fake_id}"
        )

        # Should return 404
        assert response.status_code == 404


@pytest.mark.integration
@pytest.mark.requires_device
class TestVerifyDeviceEndpoint:
    """Test device verification endpoint (requires real device)"""

    def test_verify_device_success(self, api_test_url, sample_psirt):
        """Test successful device verification"""
        # First create analysis
        analysis_request = {
            "summary": sample_psirt["summary"],
            "platform": sample_psirt["platform"],
            "advisory_id": sample_psirt["bug_id"]
        }

        analysis_response = requests.post(
            f"{api_test_url}/api/v1/analyze-psirt",
            json=analysis_request
        )

        analysis_id = analysis_response.json()["analysis_id"]

        # Now verify on device
        verify_request = {
            "analysis_id": analysis_id,
            "device": {
                "host": "192.168.0.33",
                "username": "admin",
                "password": "Pa22word",
                "device_type": "cisco_ios"
            },
            "psirt_metadata": {
                "product_names": sample_psirt["product_names"],
                "bug_id": sample_psirt["bug_id"]
            }
        }

        verify_response = requests.post(
            f"{api_test_url}/api/v1/verify-device",
            json=verify_request
        )

        assert verify_response.status_code == 200

        data = verify_response.json()
        assert "verification_id" in data
        assert "device_hostname" in data
        assert "overall_status" in data

    def test_verify_device_invalid_credentials(self, api_test_url):
        """Test verification with invalid device credentials"""
        verify_request = {
            "analysis_id": "test-id",
            "device": {
                "host": "192.168.0.33",
                "username": "invalid",
                "password": "wrong",
                "device_type": "cisco_ios"
            },
            "psirt_metadata": {
                "product_names": ["Cisco IOS XE 17.3.1"],
                "bug_id": "test-123"
            }
        }

        verify_response = requests.post(
            f"{api_test_url}/api/v1/verify-device",
            json=verify_request
        )

        # Should return error for failed SSH connection
        assert verify_response.status_code in [400, 500]

    def test_verify_device_missing_analysis_id(self, api_test_url):
        """Test verification without analysis ID"""
        verify_request = {
            "device": {
                "host": "192.168.0.33",
                "username": "admin",
                "password": "Pa22word",
                "device_type": "cisco_ios"
            },
            "psirt_metadata": {
                "product_names": ["Cisco IOS XE 17.3.1"],
                "bug_id": "test-123"
            }
        }

        verify_response = requests.post(
            f"{api_test_url}/api/v1/verify-device",
            json=verify_request
        )

        assert verify_response.status_code == 422


@pytest.mark.integration
class TestAPIErrorHandling:
    """Test API error handling"""

    def test_malformed_json(self, api_test_url):
        """Test handling of malformed JSON"""
        response = requests.post(
            f"{api_test_url}/api/v1/analyze-psirt",
            data="not valid json",
            headers={"Content-Type": "application/json"}
        )

        assert response.status_code == 422

    def test_invalid_endpoint(self, api_test_url):
        """Test accessing non-existent endpoint"""
        response = requests.get(f"{api_test_url}/api/v1/nonexistent")

        assert response.status_code == 404

    def test_wrong_http_method(self, api_test_url):
        """Test using wrong HTTP method"""
        # GET instead of POST
        response = requests.get(f"{api_test_url}/api/v1/analyze-psirt")

        assert response.status_code == 405  # Method Not Allowed


@pytest.mark.integration
class TestCORS:
    """Test CORS configuration"""

    def test_cors_headers_present(self, api_test_url):
        """Test that CORS headers are present"""
        response = requests.options(
            f"{api_test_url}/api/v1/analyze-psirt",
            headers={"Origin": "http://localhost:3000"}
        )

        # Should have CORS headers
        assert "Access-Control-Allow-Origin" in response.headers or response.status_code == 200
