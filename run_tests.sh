#!/bin/bash
# Test runner script for PSIRT Analysis System

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  PSIRT Analysis System - Test Suite  ${NC}"
echo -e "${BLUE}========================================${NC}\n"

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    echo -e "${YELLOW}Activating virtual environment...${NC}"
    source venv/bin/activate
fi

# Check if pytest is installed
if ! command -v pytest &> /dev/null; then
    echo -e "${RED}Error: pytest not found${NC}"
    echo "Install with: pip install pytest pytest-cov"
    exit 1
fi

# Default test mode
TEST_MODE="${1:-fast}"

case "$TEST_MODE" in
    "fast")
        echo -e "${GREEN}Running fast tests (unit + integration, no slow/device/GPU)${NC}\n"
        pytest tests/ -v -m "not slow and not requires_device and not requires_gpu"
        ;;

    "unit")
        echo -e "${GREEN}Running unit tests only${NC}\n"
        pytest tests/unit/ -v
        ;;

    "integration")
        echo -e "${GREEN}Running integration tests only${NC}\n"
        pytest tests/integration/ -v
        ;;

    "e2e")
        echo -e "${GREEN}Running end-to-end tests${NC}\n"
        pytest tests/e2e/ -v --slow
        ;;

    "all")
        echo -e "${GREEN}Running ALL tests (including slow tests)${NC}\n"
        pytest tests/ -v --slow
        ;;

    "device")
        echo -e "${GREEN}Running tests that require device access${NC}\n"
        pytest tests/ -v --device --slow
        ;;

    "gpu")
        echo -e "${GREEN}Running tests that require GPU${NC}\n"
        pytest tests/ -v --gpu --slow
        ;;

    "full")
        echo -e "${GREEN}Running FULL test suite (slow + device + GPU)${NC}\n"
        pytest tests/ -v --slow --device --gpu
        ;;

    "coverage")
        echo -e "${GREEN}Running tests with coverage report${NC}\n"
        pytest tests/ -v --cov=. --cov-report=html --cov-report=term
        echo -e "\n${BLUE}Coverage report generated: htmlcov/index.html${NC}"
        ;;

    *)
        echo -e "${RED}Unknown test mode: $TEST_MODE${NC}"
        echo ""
        echo "Usage: ./run_tests.sh [mode]"
        echo ""
        echo "Available modes:"
        echo "  fast        - Fast tests only (default, no slow/device/GPU)"
        echo "  unit        - Unit tests only"
        echo "  integration - Integration tests only"
        echo "  e2e         - End-to-end tests"
        echo "  all         - All tests including slow"
        echo "  device      - Tests requiring device access"
        echo "  gpu         - Tests requiring GPU"
        echo "  full        - Complete test suite (slow + device + GPU)"
        echo "  coverage    - Run with coverage report"
        exit 1
        ;;
esac

# Check exit code
if [ $? -eq 0 ]; then
    echo -e "\n${GREEN}✅ All tests passed!${NC}"
else
    echo -e "\n${RED}❌ Some tests failed${NC}"
    exit 1
fi
