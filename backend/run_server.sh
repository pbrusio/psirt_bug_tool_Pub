#!/bin/bash
# Start FastAPI server with environment validation

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check for Mac venv first, then standard venv
target_dir="$(dirname "$0")/.."
cd "$target_dir"

echo ""
echo "========================================"
echo "  PSIRT Analysis API Server"
echo "========================================"
echo ""

# Activate virtual environment
if [ -d "venv_mac" ]; then
    source venv_mac/bin/activate
    echo -e "${GREEN}✓${NC} Activated venv_mac environment"
elif [ -d "venv" ]; then
    source venv/bin/activate
    echo -e "${GREEN}✓${NC} Activated venv environment"
else
    echo -e "${YELLOW}⚠${NC} No virtual environment found (venv_mac or venv)"
fi

# ======================================
# Environment Variable Validation
# ======================================
echo ""
echo "Checking configuration..."

# Check DEV_MODE (defaults to true if not set)
if [ -z "$DEV_MODE" ]; then
    export DEV_MODE="true"
    echo -e "${YELLOW}⚠${NC} DEV_MODE not set, defaulting to: true"
else
    echo -e "${GREEN}✓${NC} DEV_MODE: $DEV_MODE"
fi

# Check ALLOWED_ORIGINS (defaults to localhost:3000)
if [ -z "$ALLOWED_ORIGINS" ]; then
    export ALLOWED_ORIGINS="http://localhost:3000"
    echo -e "${YELLOW}⚠${NC} ALLOWED_ORIGINS not set, defaulting to: http://localhost:3000"
else
    echo -e "${GREEN}✓${NC} ALLOWED_ORIGINS: $ALLOWED_ORIGINS"
fi

# Check ADMIN_API_KEY (required in production mode)
if [ "$DEV_MODE" != "true" ]; then
    if [ -z "$ADMIN_API_KEY" ]; then
        echo -e "${RED}✗${NC} ADMIN_API_KEY required when DEV_MODE=false"
        echo ""
        echo "Set ADMIN_API_KEY to enable API authentication:"
        echo "  export ADMIN_API_KEY='your-secure-key-here'"
        echo ""
        echo "Or run in development mode:"
        echo "  export DEV_MODE=true"
        echo ""
        exit 1
    else
        echo -e "${GREEN}✓${NC} ADMIN_API_KEY: [configured]"
    fi
else
    if [ -n "$ADMIN_API_KEY" ]; then
        echo -e "${YELLOW}⚠${NC} ADMIN_API_KEY set but DEV_MODE=true (auth disabled)"
    else
        echo -e "${GREEN}✓${NC} ADMIN_API_KEY: [not required in DEV_MODE]"
    fi
fi

# ======================================
# Model Backend Configuration
# ======================================
echo ""

# Check for --local flag (uses local MPS/CUDA acceleration)
if [ "$1" = "--local" ]; then
    export PSIRT_BACKEND="transformers_local"
    export SEC8B_MODEL="foundation-sec-8b"
    echo -e "${GREEN}✓${NC} Backend: Local Transformers (MPS/CUDA)"
else
    echo -e "${GREEN}✓${NC} Backend: Transformers (Default)"
fi

# Check PSIRT_BACKEND if explicitly set
if [ -n "$PSIRT_BACKEND" ]; then
    echo -e "${GREEN}✓${NC} PSIRT_BACKEND: $PSIRT_BACKEND"
fi

# Check SEC8B_MODEL if explicitly set
if [ -n "$SEC8B_MODEL" ]; then
    echo -e "${GREEN}✓${NC} SEC8B_MODEL: $SEC8B_MODEL"
fi

# ======================================
# Database Check
# ======================================
echo ""
if [ -f "vulnerability_db.sqlite" ]; then
    db_size=$(du -h vulnerability_db.sqlite | cut -f1)
    echo -e "${GREEN}✓${NC} Database: vulnerability_db.sqlite ($db_size)"
else
    echo -e "${YELLOW}⚠${NC} Database: vulnerability_db.sqlite not found"
    echo "  Some features may not work without the database"
fi

# ======================================
# Start Server
# ======================================
echo ""
echo "========================================"
echo -e "${GREEN}Starting server...${NC}"
echo "========================================"
echo ""
echo "  API:  http://localhost:8000"
echo "  Docs: http://localhost:8000/docs"
echo "  Health: http://localhost:8000/api/v1/health"
echo "  DB Health: http://localhost:8000/api/v1/health/db"
echo ""

uvicorn backend.app:app --reload --host 0.0.0.0 --port 8000
