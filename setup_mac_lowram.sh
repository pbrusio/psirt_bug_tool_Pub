#!/bin/bash

# Setup script for Mac (Apple Silicon) - LOW RAM VERSION (16GB)
# 1. Creates venv_mac
# 2. Installs dependencies
# 3. Downloads and quantizes Foundation-Sec-8B to 4-bit (~5GB)
#
# Use this if you have 16GB RAM. For 32GB+ RAM, use setup_mac_env.sh instead.

VENV_NAME="venv_mac"
QUANTIZED_MODEL_PATH="models/foundation-sec-8b-4bit"

echo "========================================"
echo "  PSIRT Analysis - Mac Low-RAM Setup"
echo "  (For 16GB Macs - 4-bit Quantization)"
echo "========================================"
echo ""

# 1. Check Python version and architecture
PYTHON_VERSION=$(python3 --version 2>&1)
ARCH=$(python3 -c "import platform; print(platform.machine())")
echo "Python: $PYTHON_VERSION"
echo "Architecture: $ARCH"

if [ "$ARCH" != "arm64" ]; then
    echo ""
    echo "WARNING: Python is running in x86 mode (Rosetta)"
    echo "   MLX requires native ARM64 Python for best performance."
    echo "   Consider: brew install python@3.11"
    echo ""
fi

# Check available RAM
RAM_GB=$(sysctl -n hw.memsize 2>/dev/null | awk '{print int($1/1024/1024/1024)}')
echo "Available RAM: ${RAM_GB}GB"

if [ "$RAM_GB" -ge 32 ]; then
    echo ""
    echo "NOTE: You have 32GB+ RAM. Consider using setup_mac_env.sh instead"
    echo "      for better accuracy (full precision model)."
    echo ""
    read -p "Continue with 4-bit quantized model anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Exiting. Run ./setup_mac_env.sh for full precision setup."
        exit 0
    fi
fi

# 2. Create venv if not exists
if [ ! -d "$VENV_NAME" ]; then
    echo ""
    echo "[1/6] Creating virtual environment: $VENV_NAME"
    python3 -m venv $VENV_NAME
    echo "      Done."
else
    echo ""
    echo "[1/6] Virtual environment $VENV_NAME already exists"
fi

# 3. Activate
source $VENV_NAME/bin/activate
echo "[2/6] Activated $VENV_NAME"

# 4. Upgrade pip
echo "[3/6] Upgrading pip..."
pip install --upgrade pip -q

# 5. Install core dependencies
echo "[4/6] Installing core dependencies..."
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
echo "[5/6] Installing MLX for Apple Silicon..."
if [ -f "requirements-mlx.txt" ]; then
    pip install -r requirements-mlx.txt -q
    echo "      MLX requirements installed."
else
    echo "      Installing mlx and mlx-lm directly..."
    pip install mlx mlx-lm -q
fi

# 7. Create quantized model
echo "[6/6] Creating 4-bit quantized model..."
echo "      This downloads ~16GB and converts to ~5GB (one-time)."
echo ""

if [ -d "$QUANTIZED_MODEL_PATH" ]; then
    echo "      Quantized model already exists at $QUANTIZED_MODEL_PATH"
    echo "      Skipping conversion."
else
    echo "      Downloading and quantizing Foundation-Sec-8B..."
    echo "      (This may take 10-20 minutes depending on internet speed)"
    echo ""

    # Use mlx_lm CLI to convert and quantize
    python3 -m mlx_lm.convert \
        --hf-path fdtn-ai/Foundation-Sec-8B \
        --mlx-path "$QUANTIZED_MODEL_PATH" \
        -q \
        --q-bits 4 \
        --q-group-size 64

    if [ $? -ne 0 ]; then
        echo ""
        echo "ERROR: Quantization failed!"
        echo "Try running manually:"
        echo "  source $VENV_NAME/bin/activate"
        echo "  python -m mlx_lm.convert --hf-path fdtn-ai/Foundation-Sec-8B -q --q-bits 4 --mlx-path $QUANTIZED_MODEL_PATH"
        exit 1
    fi
fi

# 8. Create config file to indicate low-RAM mode
echo '{"model_mode": "quantized_4bit", "model_path": "models/foundation-sec-8b-4bit"}' > models/lowram_config.json
echo "      Low-RAM config saved."

# 9. Verify installation
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
    echo "MLX: NOT INSTALLED"
    echo "  Try: pip install mlx mlx-lm"
fi

# Check quantized model
if [ -d "$QUANTIZED_MODEL_PATH" ]; then
    MODEL_SIZE=$(du -sh "$QUANTIZED_MODEL_PATH" 2>/dev/null | cut -f1)
    echo "Quantized Model: $QUANTIZED_MODEL_PATH ($MODEL_SIZE)"
else
    echo "Quantized Model: NOT FOUND"
fi

echo ""
echo "========================================"
echo "  Setup Complete! (Low-RAM Mode)"
echo "========================================"
echo ""
echo "Memory usage: ~8-10GB (vs ~32GB for full precision)"
echo "Accuracy: ~65% (vs ~71% for full precision)"
echo ""
echo "To activate:"
echo "  source $VENV_NAME/bin/activate"
echo ""
echo "To start the backend:"
echo "  LOWRAM_MODE=true ./backend/run_server.sh"
echo ""
echo "To start the frontend (separate terminal):"
echo "  cd frontend && npm install && npm run dev"
echo ""
