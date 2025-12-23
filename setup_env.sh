#!/bin/bash
# =============================================================================
# CVE_EVAL_V2 v3.2 - Environment Setup Script
# =============================================================================
# Usage: ./setup_env.sh
# 
# This script creates a fresh virtual environment and installs all dependencies.
# Run from the project root directory.

set -e  # Exit on error

echo "🚀 CVE_EVAL_V2 v3.2 Environment Setup"
echo "======================================"

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
echo "📦 Python version: $PYTHON_VERSION"

if [[ "$PYTHON_VERSION" < "3.10" ]]; then
    echo "⚠️  Warning: Python 3.10+ recommended. You have $PYTHON_VERSION"
fi

# Create virtual environment
VENV_DIR="venv"
echo ""
echo "📁 Creating virtual environment in ./$VENV_DIR..."

if [ -d "$VENV_DIR" ]; then
    echo "   ⚠️  Existing venv found. Remove it first? (y/n)"
    read -r response
    if [[ "$response" == "y" ]]; then
        rm -rf "$VENV_DIR"
    else
        echo "   Keeping existing venv"
    fi
fi

if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
    echo "   ✅ Virtual environment created"
fi

# Activate venv
echo ""
echo "🔌 Activating virtual environment..."
source "$VENV_DIR/bin/activate"

# Upgrade pip
echo ""
echo "📦 Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo ""
echo "📦 Installing core dependencies..."
pip install -r requirements.txt

# Check if MLX installed successfully (Mac-only)
if python -c "import mlx" 2>/dev/null; then
    echo "   ✅ MLX installed (Apple Silicon detected)"
else
    echo "   ⚠️  MLX not available (requires Apple Silicon Mac)"
    echo "      AI inference will use fallback mode"
fi

# Install test dependencies
echo ""
echo "📦 Installing test dependencies..."
pip install -r requirements-test.txt

# Verify installation
echo ""
echo "🔍 Verifying installation..."
python -c "import fastapi; print(f'   ✅ FastAPI {fastapi.__version__}')"
python -c "import pandas; print(f'   ✅ Pandas {pandas.__version__}')"
python -c "import netmiko; print(f'   ✅ Netmiko available')"

# Check for database
echo ""
if [ -f "vulnerability_db.sqlite" ]; then
    echo "📊 Database found: vulnerability_db.sqlite"
    python -c "
import sqlite3
conn = sqlite3.connect('vulnerability_db.sqlite')
cursor = conn.cursor()
cursor.execute('SELECT COUNT(*) FROM vulnerabilities')
count = cursor.fetchone()[0]
print(f'   📈 {count} vulnerabilities in database')
conn.close()
" 2>/dev/null || echo "   ⚠️  Database exists but may need initialization"
else
    echo "📊 No database found."
    echo "   To initialize, run: python backend/db/init_db.py"
    echo "   Or use: scripts/offline_update_packager.py to create from scratch"
fi

# Summary
echo ""
echo "======================================"
echo "✅ Setup complete!"
echo ""
echo "To activate the environment:"
echo "   source $VENV_DIR/bin/activate"
echo ""
echo "To start the backend server:"
echo "   cd backend && ./run_server.sh"
echo "   # Or: uvicorn backend.app:app --reload --port 8000"
echo ""
echo "To start the frontend:"
echo "   cd frontend && npm install && npm run dev"
echo ""
echo "To run tests:"
echo "   pytest tests/ -v"
echo ""
