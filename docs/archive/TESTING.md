# Testing Guide

Comprehensive testing framework for the PSIRT Analysis System.

## Quick Start

```bash
# Install test dependencies
pip install pytest pytest-cov requests

# Run fast tests (unit + integration, no slow/device/GPU)
./run_tests.sh

# Run all tests
./run_tests.sh all
```

## Test Organization

```
tests/
├── conftest.py           # Shared fixtures and configuration
├── unit/                 # Unit tests (fast, no external dependencies)
│   ├── test_version_matcher.py
│   ├── test_taxonomy_loader.py
│   ├── test_feature_detection.py
│   └── test_label_validation.py
├── integration/          # Integration tests (API endpoints)
│   └── test_api_endpoints.py
└── e2e/                  # End-to-end workflow tests
    └── test_psirt_workflow.py
```

## Test Categories

### Unit Tests (`tests/unit/`)

Test individual components in isolation:
- **Version matching logic** - Normalization, parsing, matching
- **Taxonomy loading** - YAML parsing, structure validation
- **Feature detection** - Regex pattern matching
- **Label validation** - Taxonomy filtering, enrichment

**Run:** `./run_tests.sh unit`

### Integration Tests (`tests/integration/`)

Test API endpoints with real HTTP requests:
- Health check endpoint
- PSIRT analysis endpoint
- Results retrieval endpoint
- Device verification endpoint
- Error handling
- CORS configuration

**Run:** `./run_tests.sh integration`

**Note:** Requires backend server running (`./backend/run_server.sh`)

### End-to-End Tests (`tests/e2e/`)

Test complete workflows:
- Analyze → Retrieve results
- Analyze → Verify on device
- Multiple concurrent requests
- Error recovery
- Performance testing

**Run:** `./run_tests.sh e2e`

## Test Markers

Tests are marked for conditional execution:

- `@pytest.mark.unit` - Unit tests (fast)
- `@pytest.mark.integration` - Integration tests (requires API server)
- `@pytest.mark.e2e` - End-to-end tests
- `@pytest.mark.slow` - Slow tests (ML model loading)
- `@pytest.mark.requires_device` - Needs SSH access to device
- `@pytest.mark.requires_gpu` - Needs GPU for inference

## Running Tests

### Basic Usage

```bash
# Fast tests only (default)
./run_tests.sh

# Unit tests only
./run_tests.sh unit

# Integration tests only
./run_tests.sh integration

# End-to-end tests
./run_tests.sh e2e

# All tests including slow
./run_tests.sh all
```

### Advanced Usage

```bash
# Tests requiring device access
./run_tests.sh device

# Tests requiring GPU
./run_tests.sh gpu

# Complete test suite (all markers)
./run_tests.sh full

# Run with coverage report
./run_tests.sh coverage
```

### Direct pytest Commands

```bash
# Run specific test file
pytest tests/unit/test_version_matcher.py -v

# Run specific test class
pytest tests/unit/test_version_matcher.py::TestVersionNormalization -v

# Run specific test method
pytest tests/unit/test_version_matcher.py::TestVersionNormalization::test_normalize_with_leading_zeros -v

# Run with custom markers
pytest tests/ -v -m "unit and not slow"

# Run with verbose output
pytest tests/ -vv

# Stop on first failure
pytest tests/ -x

# Show local variables on failure
pytest tests/ -l

# Run last failed tests
pytest tests/ --lf
```

## Test Fixtures

Shared test data in `tests/conftest.py`:

- `sample_psirt` - Sample PSIRT advisory
- `sample_bug` - Sample bug report
- `sample_taxonomy` - Sample feature taxonomy
- `sample_device_config` - Sample device configuration
- `sample_device_version` - Sample version output
- `mock_faiss_results` - Mock FAISS similarity results
- `api_test_url` - API base URL

## Writing New Tests

### Unit Test Template

```python
import pytest

@pytest.mark.unit
class TestMyComponent:
    """Test MyComponent functionality"""

    def test_basic_functionality(self):
        """Test basic operation"""
        # Arrange
        input_data = "test"

        # Act
        result = my_function(input_data)

        # Assert
        assert result == "expected"

    def test_edge_case(self):
        """Test edge case handling"""
        assert my_function("") is None
```

### Integration Test Template

```python
import pytest
import requests

@pytest.mark.integration
class TestMyEndpoint:
    """Test /api/v1/my-endpoint"""

    def test_success_case(self, api_test_url):
        """Test successful request"""
        response = requests.post(
            f"{api_test_url}/api/v1/my-endpoint",
            json={"key": "value"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "result" in data
```

### E2E Test Template

```python
import pytest
import requests

@pytest.mark.e2e
@pytest.mark.slow
class TestMyWorkflow:
    """Test complete workflow"""

    def test_workflow(self, api_test_url):
        """Test: Step 1 → Step 2 → Step 3"""

        # Step 1: Initial request
        response1 = requests.post(...)
        assert response1.status_code == 200

        # Step 2: Follow-up action
        response2 = requests.get(...)
        assert response2.status_code == 200

        # Step 3: Verify results
        assert response2.json()["status"] == "complete"
```

## Prerequisites for Different Test Types

### Unit Tests
- ✅ No prerequisites (run anywhere)

### Integration Tests
- 🔧 Backend server must be running:
  ```bash
  cd backend
  ./run_server.sh
  ```

### E2E Tests (basic)
- 🔧 Backend server running
- ⏱️  Allow extra time (slow marker)

### E2E Tests (full)
- 🔧 Backend server running
- 🖥️  SSH access to test device (192.168.0.33)
- 🎮 GPU available for inference
- ⏱️  Allow significant time

## Continuous Integration

The test suite is CI-ready:

```yaml
# Example GitHub Actions workflow
name: Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.12'
      - run: pip install -r requirements.txt
      - run: pip install pytest pytest-cov
      - run: pytest tests/unit/ -v
      - run: pytest tests/integration/ -v  # Requires API mock
```

## Coverage Reports

Generate coverage reports:

```bash
# HTML report
./run_tests.sh coverage
open htmlcov/index.html

# Terminal report only
pytest tests/ --cov=. --cov-report=term

# XML report (for CI)
pytest tests/ --cov=. --cov-report=xml
```

## Troubleshooting

### Integration tests fail with connection error
**Problem:** `ConnectionError: Cannot connect to API`

**Solution:** Start the backend server:
```bash
cd backend
./run_server.sh
```

### Slow tests taking too long
**Problem:** Tests timeout or take excessive time

**Solution:**
- Use `./run_tests.sh fast` for development
- Only run full suite before commits
- Check GPU availability for model tests

### Device tests fail
**Problem:** SSH connection errors

**Solution:**
- Verify device is reachable: `ping 192.168.0.33`
- Check credentials in test fixtures
- Skip device tests: `pytest -m "not requires_device"`

### ImportError for project modules
**Problem:** `ModuleNotFoundError: No module named 'version_matcher'`

**Solution:** Run pytest from project root:
```bash
cd /path/to/cve_EVAL_V2
pytest tests/
```

## Best Practices

1. **Keep unit tests fast** - No network calls, no ML model loading
2. **Mock external dependencies** - Use fixtures for API responses, DB queries
3. **Test edge cases** - Empty inputs, invalid data, boundary conditions
4. **Use descriptive names** - `test_version_matching_with_leading_zeros` not `test_1`
5. **One assertion per concept** - Multiple asserts OK if testing same concept
6. **Clean up after tests** - Use fixtures with yield for setup/teardown
7. **Mark slow tests** - Use `@pytest.mark.slow` for tests >1s
8. **Document test purpose** - Use docstrings to explain what's being tested

## Test Metrics

Target coverage and quality metrics:

- **Unit test coverage:** >80%
- **Integration test coverage:** >60%
- **Critical paths:** 100% coverage
- **Test execution time:**
  - Unit tests: <5s total
  - Integration tests: <30s (with server running)
  - E2E tests: <2min (basic), <5min (full)

## Next Steps

1. **Add backend-specific tests** - Test device_verifier.py, version_matcher.py directly
2. **Add frontend tests** - React component tests with Jest/React Testing Library
3. **Add performance benchmarks** - Track inference time, API latency
4. **Add load tests** - Use locust or k6 for stress testing
5. **Add security tests** - SQL injection, XSS, authentication bypass attempts
