#!/bin/bash

# Setup script for Mac (Apple Silicon M1/M2/M3/M4)
# 1. Creates venv_mac
# 2. Installs dependencies
# 3. Installs MLX for Apple Silicon acceleration

VENV_NAME="venv_mac"

echo "========================================"
echo "  PSIRT Analysis - Mac Setup"
echo "========================================"
echo ""

# 1. Check Python version and architecture
PYTHON_VERSION=$(python3 --version 2>&1)
ARCH=$(python3 -c "import platform; print(platform.machine())")
echo "Python: $PYTHON_VERSION"
echo "Architecture: $ARCH"

if [ "$ARCH" != "arm64" ]; then
    echo ""
    echo "⚠️  WARNING: Python is running in x86 mode (Rosetta)"
    echo "   MLX requires native ARM64 Python for best performance."
    echo "   Consider: brew install python@3.11"
    echo ""
fi

# 2. Create venv if not exists
if [ ! -d "$VENV_NAME" ]; then
    echo ""
    echo "[1/5] Creating virtual environment: $VENV_NAME"
    python3 -m venv $VENV_NAME
    echo "      Done."
else
    echo ""
    echo "[1/5] Virtual environment $VENV_NAME already exists"
fi

# 3. Activate
source $VENV_NAME/bin/activate
echo "[2/5] Activated $VENV_NAME"

# 4. Upgrade pip
echo "[3/5] Upgrading pip..."
pip install --upgrade pip -q

# 5. Install core dependencies
echo "[4/5] Installing core dependencies..."
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt -q
    echo "      Core requirements installed."
else
    echo "      ERROR: requirements.txt not found!"
    exit 1
fi

# Install backend requirements if separate
if [ -f "backend/requirements.txt" ]; then
    pip install -r backend/requirements.txt -q
    echo "      Backend requirements installed."
fi

# 6. Install MLX (Apple Silicon only)
echo "[5/5] Installing MLX for Apple Silicon..."
if [ -f "requirements-mlx.txt" ]; then
    pip install -r requirements-mlx.txt -q
    echo "      MLX requirements installed."
else
    echo "      Installing mlx and mlx-lm directly..."
    pip install mlx mlx-lm -q
fi

# 7. Verify MLX installation
echo ""
echo "========================================"
echo "  Environment Check"
echo "========================================"
echo ""

# Check MLX
MLX_OK=$(python3 -c "import mlx; print('yes')" 2>/dev/null || echo "no")
if [ "$MLX_OK" = "yes" ]; then
    echo "MLX: Installed"
    python3 -c "import mlx; print(f'  Version: {mlx.__version__}')" 2>/dev/null
else
    echo "MLX: NOT INSTALLED (required for Mac)"
    echo "  Try: pip install mlx mlx-lm"
fi

# Check mlx-lm
MLX_LM_OK=$(python3 -c "import mlx_lm; print('yes')" 2>/dev/null || echo "no")
if [ "$MLX_LM_OK" = "yes" ]; then
    echo "mlx-lm: Installed"
else
    echo "mlx-lm: NOT INSTALLED (required for inference)"
    echo "  Try: pip install mlx-lm"
fi

# Check PyTorch MPS
MPS_OK=$(python3 -c "import torch; print('yes' if torch.backends.mps.is_available() else 'no')" 2>/dev/null || echo "no")
if [ "$MPS_OK" = "yes" ]; then
    echo "PyTorch MPS: Available"
else
    echo "PyTorch MPS: Not available"
fi

echo ""
echo "========================================"
echo "  Setup Complete!"
echo "========================================"
echo ""
echo "To activate:"
echo "  source $VENV_NAME/bin/activate"
echo ""
echo "To start the backend:"
echo "  ./backend/run_server.sh"
echo ""
echo "To start the frontend (separate terminal):"
echo "  cd frontend && npm install && npm run dev"
echo ""
