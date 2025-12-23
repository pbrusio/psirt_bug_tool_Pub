#!/bin/bash

# Setup script for Linux (NVIDIA GPU / CPU)
# 1. Creates venv
# 2. Installs dependencies
# 3. Verifies CUDA if available

VENV_NAME="venv"

echo "========================================"
echo "  PSIRT Analysis - Linux Setup"
echo "========================================"
echo ""

# 1. Check Python version
PYTHON_VERSION=$(python3 --version 2>&1)
echo "Python: $PYTHON_VERSION"

# 2. Create venv if not exists
if [ ! -d "$VENV_NAME" ]; then
    echo ""
    echo "[1/4] Creating virtual environment: $VENV_NAME"
    python3 -m venv $VENV_NAME
    echo "      Done."
else
    echo ""
    echo "[1/4] Virtual environment $VENV_NAME already exists"
fi

# 3. Activate
source $VENV_NAME/bin/activate
echo "[2/4] Activated $VENV_NAME"

# 4. Upgrade pip
echo "[3/4] Upgrading pip..."
pip install --upgrade pip -q

# 5. Install dependencies
echo "[4/4] Installing dependencies..."
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

# 6. Check for CUDA
echo ""
echo "========================================"
echo "  Environment Check"
echo "========================================"
echo ""

# Check CUDA availability via nvidia-smi
if command -v nvidia-smi &> /dev/null; then
    echo "CUDA: Available"
    nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null | head -1

    # Check PyTorch CUDA
    TORCH_CUDA=$(python3 -c "import torch; print('yes' if torch.cuda.is_available() else 'no')" 2>/dev/null)
    if [ "$TORCH_CUDA" = "yes" ]; then
        echo "PyTorch CUDA: Enabled"
        python3 -c "import torch; print(f'PyTorch: {torch.__version__}')"
    else
        echo "PyTorch CUDA: Not enabled (may need CUDA-specific PyTorch)"
        echo ""
        echo "To install CUDA-enabled PyTorch:"
        echo "  pip install torch --index-url https://download.pytorch.org/whl/cu118"
    fi
else
    echo "CUDA: Not detected (will use CPU)"
    echo "Note: CPU inference is ~10x slower than GPU"
fi

# Check for PEFT (needed for LoRA adapters on Linux)
PEFT_INSTALLED=$(python3 -c "import peft; print('yes')" 2>/dev/null || echo "no")
if [ "$PEFT_INSTALLED" = "no" ]; then
    echo ""
    echo "Installing PEFT for LoRA adapter support..."
    pip install peft -q
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
