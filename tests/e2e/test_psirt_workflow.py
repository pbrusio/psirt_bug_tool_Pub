"""
End-to-end tests for complete PSIRT analysis workflow
"""
import pytest
import requests
import json
from time import sleep


@pytest.mark.e2e
@pytest.mark.slow
class TestCompletePSIRTWorkflow:
    """Test complete workflow from analysis to verification"""

    def test_analyze_and_retrieve_workflow(self, api_test_url, sample_psirt):
        """Test: Analyze PSIRT → Retrieve results"""

        # Step 1: Analyze PSIRT
        print("\n📝 Step 1: Analyzing PSIRT...")
        analysis_request = {
            "summary": sample_psirt["summary"],
            "platform": sample_psirt["platform"],
            "advisory_id": sample_psirt["bug_id"]
        }

        analysis_response = requests.post(
            f"{api_test_url}/api/v1/analyze-psirt",
            json=analysis_request
        )

        assert analysis_response.status_code == 200
        analysis_data = analysis_response.json()

        print(f"✅ Analysis ID: {analysis_data['analysis_id']}")
        print(f"   Predicted Labels: {analysis_data['predicted_labels']}")
        print(f"   Confidence: {analysis_data['confidence']}%")

        # Step 2: Retrieve cached result
        print("\n📥 Step 2: Retrieving cached result...")
        analysis_id = analysis_data["analysis_id"]

        retrieve_response = requests.get(
            f"{api_test_url}/api/v1/results/{analysis_id}"
        )

        assert retrieve_response.status_code == 200
        retrieved_data = retrieve_response.json()

        print(f"✅ Retrieved result for: {retrieved_data['analysis_id']}")

        # Step 3: Verify data consistency
        print("\n✔️  Step 3: Verifying data consistency...")
        assert retrieved_data["analysis_id"] == analysis_data["analysis_id"]
        assert retrieved_data["predicted_labels"] == analysis_data["predicted_labels"]
        assert retrieved_data["platform"] == analysis_data["platform"]

        print("✅ Workflow completed successfully!")

    @pytest.mark.requires_device
    def test_full_analysis_to_verification_workflow(self, api_test_url, sample_psirt):
        """Test: Analyze PSIRT → Verify on device → Get final status"""

        # Step 1: Analyze PSIRT
        print("\n📝 Step 1: Analyzing PSIRT...")
        analysis_request = {
            "summary": sample_psirt["summary"],
            "platform": sample_psirt["platform"],
            "advisory_id": sample_psirt["bug_id"]
        }

        analysis_response = requests.post(
            f"{api_test_url}/api/v1/analyze-psirt",
            json=analysis_request
        )

        assert analysis_response.status_code == 200
        analysis_data = analysis_response.json()
        analysis_id = analysis_data["analysis_id"]

        print(f"✅ Analysis complete")
        print(f"   Labels: {analysis_data['predicted_labels']}")
        print(f"   Config checks: {len(analysis_data['config_regex'])} patterns")
        print(f"   Show commands: {len(analysis_data['show_commands'])} commands")

        # Step 2: Verify on device
        print("\n🔐 Step 2: Verifying on device...")
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
        verify_data = verify_response.json()

        print(f"✅ Verification complete")
        print(f"   Device: {verify_data['device_hostname']}")
        print(f"   Version: {verify_data['device_version']}")
        print(f"   Status: {verify_data['overall_status']}")
        print(f"   Reason: {verify_data['reason']}")

        # Step 3: Validate results
        print("\n✔️  Step 3: Validating workflow results...")
        assert "verification_id" in verify_data
        assert verify_data["overall_status"] in [
            "VULNERABLE",
            "NOT VULNERABLE",
            "POTENTIALLY VULNERABLE",
            "LIKELY NOT VULNERABLE"
        ]

        # Version check should have run
        assert "version_check" in verify_data
        assert "affected" in verify_data["version_check"]

        # Feature check should have run
        assert "feature_check" in verify_data
        assert "present" in verify_data["feature_check"]
        assert "absent" in verify_data["feature_check"]

        print("✅ Full workflow completed successfully!")

    def test_multiple_psirts_workflow(self, api_test_url):
        """Test analyzing multiple PSIRTs in sequence"""

        psirts = [
            {
                "summary": "IOx vulnerability in IOS XE",
                "platform": "IOS-XE",
                "advisory_id": "test-iox-1"
            },
            {
                "summary": "SSH vulnerability in IOS XR",
                "platform": "IOS-XR",
                "advisory_id": "test-ssh-2"
            },
            {
                "summary": "Firewall policy bypass in ASA",
                "platform": "ASA",
                "advisory_id": "test-asa-3"
            }
        ]

        results = []

        for i, psirt in enumerate(psirts, 1):
            print(f"\n📝 Analyzing PSIRT {i}/{len(psirts)}: {psirt['advisory_id']}")

            response = requests.post(
                f"{api_test_url}/api/v1/analyze-psirt",
                json=psirt
            )

            assert response.status_code == 200
            data = response.json()
            results.append(data)

            print(f"✅ {psirt['platform']}: {len(data['predicted_labels'])} labels")

        # Verify all were processed
        assert len(results) == len(psirts)

        # Verify each has unique analysis ID
        analysis_ids = [r["analysis_id"] for r in results]
        assert len(analysis_ids) == len(set(analysis_ids))

        print(f"\n✅ Successfully analyzed {len(psirts)} PSIRTs")


@pytest.mark.e2e
class TestErrorRecoveryWorkflow:
    """Test error handling and recovery in workflows"""

    def test_invalid_analysis_then_valid(self, api_test_url, sample_psirt):
        """Test recovery after failed analysis attempt"""

        # Step 1: Try invalid request
        print("\n❌ Step 1: Attempting invalid request...")
        invalid_request = {
            "summary": "",  # Empty summary
            "platform": "IOS-XE"
        }

        response1 = requests.post(
            f"{api_test_url}/api/v1/analyze-psirt",
            json=invalid_request
        )

        # Should fail
        assert response1.status_code in [400, 422]
        print("✅ Invalid request properly rejected")

        # Step 2: Send valid request
        print("\n✔️  Step 2: Sending valid request...")
        valid_request = {
            "summary": sample_psirt["summary"],
            "platform": sample_psirt["platform"],
            "advisory_id": sample_psirt["bug_id"]
        }

        response2 = requests.post(
            f"{api_test_url}/api/v1/analyze-psirt",
            json=valid_request
        )

        # Should succeed
        assert response2.status_code == 200
        print("✅ Valid request succeeded after error")

    def test_retrieve_before_analyze(self, api_test_url):
        """Test attempting to retrieve non-existent analysis"""

        # Try to retrieve non-existent result
        fake_id = "nonexistent-12345"

        response = requests.get(
            f"{api_test_url}/api/v1/results/{fake_id}"
        )

        # Should return 404
        assert response.status_code == 404
        print("✅ Non-existent result properly returns 404")


@pytest.mark.e2e
@pytest.mark.slow
class TestPerformanceWorkflow:
    """Test performance characteristics of workflows"""

    def test_concurrent_analyses(self, api_test_url):
        """Test handling multiple concurrent analysis requests"""
        import concurrent.futures

        def analyze_psirt(advisory_id):
            """Helper to analyze a single PSIRT"""
            request = {
                "summary": f"Test vulnerability {advisory_id}",
                "platform": "IOS-XE",
                "advisory_id": advisory_id
            }

            response = requests.post(
                f"{api_test_url}/api/v1/analyze-psirt",
                json=request
            )

            return response.status_code, response.json()

        # Submit 5 concurrent requests
        print("\n⚡ Testing 5 concurrent analysis requests...")
        num_requests = 5

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(analyze_psirt, f"test-{i}")
                for i in range(num_requests)
            ]

            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # All should succeed
        assert all(status == 200 for status, _ in results)

        # All should have unique IDs
        analysis_ids = [data["analysis_id"] for _, data in results]
        assert len(analysis_ids) == len(set(analysis_ids))

        print(f"✅ All {num_requests} concurrent requests succeeded")

    @pytest.mark.requires_gpu
    def test_analysis_performance(self, api_test_url, sample_psirt):
        """Test analysis performance timing"""
        import time

        print("\n⏱️  Testing analysis performance...")

        request_data = {
            "summary": sample_psirt["summary"],
            "platform": sample_psirt["platform"],
            "advisory_id": sample_psirt["bug_id"]
        }

        # Measure time
        start_time = time.time()

        response = requests.post(
            f"{api_test_url}/api/v1/analyze-psirt",
            json=request_data
        )

        elapsed_time = time.time() - start_time

        assert response.status_code == 200

        print(f"✅ Analysis completed in {elapsed_time:.2f}s")

        # Should complete in reasonable time (adjust threshold as needed)
        # With 8-bit SEC-8B, expect ~3-5 seconds
        assert elapsed_time < 10.0, f"Analysis took too long: {elapsed_time:.2f}s"
