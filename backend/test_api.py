#!/usr/bin/env python3
"""
Test script for PSIRT Analysis API
"""
import requests
import json

BASE_URL = "http://localhost:8000"


def test_health():
    """Test health endpoint"""
    print("\n" + "="*80)
    print("🏥 Testing Health Endpoint")
    print("="*80)

    response = requests.get(f"{BASE_URL}/api/v1/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")

    assert response.status_code == 200
    print("✅ Health check passed")


def test_analyze_psirt():
    """Test PSIRT analysis endpoint"""
    print("\n" + "="*80)
    print("🔍 Testing PSIRT Analysis")
    print("="*80)

    request = {
        "summary": "A vulnerability in the IOx application hosting subsystem of Cisco IOS XE Software could allow an authenticated, remote attacker to cause a denial of service (DoS) condition on an affected device.",
        "platform": "IOS-XE",
        "advisory_id": "cisco-sa-iox-dos-95Fqnf7b"
    }

    print(f"\n📤 Request:")
    print(json.dumps(request, indent=2))

    response = requests.post(f"{BASE_URL}/api/v1/analyze-psirt", json=request)
    print(f"\n📥 Status: {response.status_code}")

    if response.status_code == 200:
        result = response.json()
        print(f"\n✅ Analysis Result:")
        print(f"  Analysis ID: {result['analysis_id']}")
        print(f"  Platform: {result['platform']}")
        print(f"  Predicted Labels: {result['predicted_labels']}")
        print(f"  Confidence: {result['confidence']}")
        print(f"  Config Regex: {result['config_regex']}")
        print(f"  Show Commands: {result['show_commands']}")

        return result['analysis_id']
    else:
        print(f"❌ Error: {response.text}")
        return None


def test_verify_device(analysis_id):
    """Test device verification endpoint"""
    print("\n" + "="*80)
    print("🔐 Testing Device Verification")
    print("="*80)

    # Note: Update with your device credentials
    request = {
        "analysis_id": analysis_id,
        "device": {
            "host": "192.168.0.33",
            "username": "admin",
            "password": "Pa22word",
            "device_type": "cisco_ios"
        },
        "psirt_metadata": {
            "product_names": ["Cisco IOS XE Software, Version 17.3.1"],
            "bug_id": "cisco-sa-iox-dos-95Fqnf7b"
        }
    }

    print(f"\n📤 Request:")
    print(f"  Analysis ID: {request['analysis_id']}")
    print(f"  Device: {request['device']['host']}")

    response = requests.post(f"{BASE_URL}/api/v1/verify-device", json=request)
    print(f"\n📥 Status: {response.status_code}")

    if response.status_code == 200:
        result = response.json()
        print(f"\n✅ Verification Result:")
        print(f"  Verification ID: {result['verification_id']}")
        print(f"  Device: {result['device_hostname']}")
        print(f"  Version: {result['device_version']}")
        print(f"  Platform: {result['device_platform']}")
        print(f"\n  Version Check:")
        print(f"    Affected: {result['version_check']['affected']}")
        print(f"    Reason: {result['version_check']['reason']}")
        print(f"\n  Feature Check:")
        print(f"    Present: {result['feature_check']['present']}")
        print(f"    Absent: {result['feature_check']['absent']}")
        print(f"\n  Overall Status: {result['overall_status']}")
        print(f"  Reason: {result['reason']}")
    else:
        print(f"❌ Error: {response.text}")


def test_get_results(analysis_id):
    """Test get results endpoint"""
    print("\n" + "="*80)
    print("📊 Testing Get Results")
    print("="*80)

    response = requests.get(f"{BASE_URL}/api/v1/results/{analysis_id}")
    print(f"Status: {response.status_code}")

    if response.status_code == 200:
        result = response.json()
        print(f"\n✅ Cached Result:")
        print(f"  Analysis ID: {result['analysis_id']}")
        print(f"  Labels: {result['predicted_labels']}")
    else:
        print(f"❌ Error: {response.text}")


def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("🧪 PSIRT Analysis API Test Suite")
    print("="*80)
    print(f"Base URL: {BASE_URL}")

    try:
        # Test 1: Health check
        test_health()

        # Test 2: Analyze PSIRT
        analysis_id = test_analyze_psirt()

        if analysis_id:
            # Test 3: Get results
            test_get_results(analysis_id)

            # Test 4: Verify device (optional - requires device access)
            verify_device = input("\n🔐 Run device verification test? (requires SSH access) [y/N]: ")
            if verify_device.lower() == 'y':
                test_verify_device(analysis_id)

        print("\n" + "="*80)
        print("✅ All tests completed")
        print("="*80)

    except requests.exceptions.ConnectionError:
        print("\n❌ Error: Cannot connect to API")
        print("   Make sure the server is running: ./backend/run_server.sh")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
