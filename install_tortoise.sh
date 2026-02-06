#!/bin/bash
# Tortoise TTS Installation Script for Python 3.13
# This script installs Tortoise TTS with compatible dependencies

set -e

echo "============================================"
echo "  Tortoise TTS Installation for Python 3.13"
echo "============================================"
echo ""

# Check Python version and path
PYTHON_VERSION=$(python3 --version 2>&1)
PYTHON_PATH=$(python3 -c "import sys; print(sys.executable)" 2>&1)
echo "Python version: $PYTHON_VERSION"
echo "Python path: $PYTHON_PATH"

# Step 1: Upgrade pip
echo ""
echo "[1/6] Upgrading pip..."
python3 -m pip install --upgrade pip

# Step 2: Install PyTorch
echo ""
echo "[2/6] Installing PyTorch..."

# Check for CUDA
if command -v nvidia-smi &> /dev/null; then
    echo "  CUDA detected! Installing PyTorch with CUDA support..."
    python3 -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
else
    echo "  CUDA not detected. Installing CPU-only PyTorch..."
    python3 -m pip install torch torchvision torchaudio
fi

# Step 3: Install compatible transformers and tokenizers FIRST
# NOTE: Tortoise requires transformers <4.40.0 (model_parallel_utils was removed in newer versions)
echo ""
echo "[3/6] Installing transformers with compatible tokenizers..."
python3 -m pip install "tokenizers>=0.14.0,<0.20.0" "transformers>=4.35.0,<4.40.0"

# Step 4: Install other Tortoise dependencies
echo ""
echo "[4/6] Installing Tortoise TTS dependencies..."
python3 -m pip install einops rotary-embedding-torch inflect progressbar2 unidecode scipy librosa soundfile

# Step 5: Uninstall any existing tortoise-tts to avoid conflicts
echo ""
echo "[5/6] Cleaning up old Tortoise installations..."
python3 -m pip uninstall tortoise-tts -y 2>/dev/null || true

# Step 6: Install Tortoise TTS from GitHub (more reliable than PyPI)
echo ""
echo "[6/6] Installing Tortoise TTS from GitHub..."
python3 -m pip install git+https://github.com/neonbjb/tortoise-tts.git

# Verify installation
echo ""
echo "============================================"
echo "  Verifying Installation"
echo "============================================"

python3 -c "
import sys
import site

print('Python paths:')
for p in sys.path[:5]:
    print(f'  {p}')

print()

try:
    import torch
    print(f'  torch: OK (version {torch.__version__})')
    print(f'  CUDA available: {torch.cuda.is_available()}')
    if torch.cuda.is_available():
        print(f'  CUDA device: {torch.cuda.get_device_name(0)}')
except ImportError as e:
    print(f'  torch: FAILED - {e}')
    sys.exit(1)

try:
    import transformers
    print(f'  transformers: OK (version {transformers.__version__})')
except ImportError as e:
    print(f'  transformers: FAILED - {e}')
    sys.exit(1)

try:
    import tortoise
    print(f'  tortoise module: OK (location: {tortoise.__file__})')
except ImportError as e:
    print(f'  tortoise module: FAILED - {e}')
    # Check if it exists in site-packages
    for sp in site.getsitepackages():
        import os
        tortoise_path = os.path.join(sp, 'tortoise')
        if os.path.exists(tortoise_path):
            print(f'    Found tortoise at: {tortoise_path}')
    sys.exit(1)

try:
    from tortoise.api import TextToSpeech
    print('  tortoise.api.TextToSpeech: OK')
except ImportError as e:
    print(f'  tortoise.api.TextToSpeech: FAILED - {e}')
    sys.exit(1)

print()
print('All imports successful!')
"

if [ $? -eq 0 ]; then
    echo ""
    echo "============================================"
    echo "  Installation Complete!"
    echo "============================================"
    echo ""
    echo "You can now generate audiobooks with:"
    echo "  python -m scripts.main convert \"input/The_Intelligent_Investor_Clean.docx\""
    echo ""
    echo "Or test a voice with:"
    echo "  python -m scripts.main test-voice --preset ultra_fast"
else
    echo ""
    echo "============================================"
    echo "  Installation had issues!"
    echo "============================================"
    echo ""
    echo "Run diagnostics: python -m scripts.diagnose_tts"
    echo ""
    echo "Or try a fresh virtual environment:"
    echo "  python3 -m venv tts_venv"
    echo "  source tts_venv/bin/activate"
    echo "  ./install_tortoise.sh"
fi
