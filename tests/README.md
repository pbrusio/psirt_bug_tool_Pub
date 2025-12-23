# Test Suite - PSIRT Analysis System

Comprehensive testing framework with unit, integration, and end-to-end tests.

## Quick Start

```bash
# Run fast tests (recommended for development)
./run_tests.sh

# Run all tests
./run_tests.sh all

# Run with coverage
./run_tests.sh coverage
```

## Test Structure

```
tests/
├── conftest.py                    # Shared fixtures
├── test_framework_setup.py        # Framework smoke tests
├── unit/                          # Unit tests
│   ├── test_version_matcher.py    # Version matching logic
│   ├── test_taxonomy_loader.py    # Taxonomy loading/validation
│   ├── test_feature_detection.py  # Config regex matching
│   └── test_label_validation.py   # Label filtering/enrichment
├── integration/                   # Integration tests
│   └── test_api_endpoints.py      # FastAPI endpoint tests
└── e2e/                           # End-to-end tests
    └── test_psirt_workflow.py     # Complete workflows
```

## Test Categories

- **Unit Tests**: Fast, isolated component tests
- **Integration Tests**: API endpoint tests (requires server running)
- **E2E Tests**: Complete workflow tests (slow, requires GPU/device)

## Test Modes

```bash
./run_tests.sh fast        # Unit + integration (no slow/device/GPU)
./run_tests.sh unit        # Unit tests only
./run_tests.sh integration # Integration tests only
./run_tests.sh e2e         # End-to-end tests
./run_tests.sh all         # All tests including slow
./run_tests.sh device      # Tests requiring device access
./run_tests.sh gpu         # Tests requiring GPU
./run_tests.sh full        # Complete suite (slow + device + GPU)
./run_tests.sh coverage    # Run with coverage report
```

## Writing Tests

See [TESTING.md](../TESTING.md) for detailed guide on writing tests.

## Status

**Framework Status**: ✅ Complete and functional

**Test Coverage**:
- ✅ Framework setup validated
- ✅ Unit test templates created
- ✅ Integration test templates created
- ✅ E2E test templates created
- 🚧 Tests need updating to match actual implementation

**Next Steps**:
1. Update unit tests to match version_matcher.py interface
2. Add backend-specific component tests
3. Add frontend React component tests
4. Run full test suite and validate coverage
