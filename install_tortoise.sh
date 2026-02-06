#!/bin/bash
# Tortoise TTS Installation Script for Python 3.13
# This script installs Tortoise TTS with compatible dependencies

set -e

echo "============================================"
echo "  Tortoise TTS Installation for Python 3.13"
echo "============================================"
echo ""

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1)
echo "Python version: $PYTHON_VERSION"

# Step 1: Upgrade pip
echo ""
echo "[1/5] Upgrading pip..."
pip install --upgrade pip

# Step 2: Install PyTorch
echo ""
echo "[2/5] Installing PyTorch..."

# Check for CUDA
if command -v nvidia-smi &> /dev/null; then
    echo "  CUDA detected! Installing PyTorch with CUDA support..."
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
else
    echo "  CUDA not detected. Installing CPU-only PyTorch..."
    pip install torch torchvision torchaudio
fi

# Step 3: Install compatible transformers and tokenizers FIRST
echo ""
echo "[3/5] Installing transformers with compatible tokenizers..."
pip install "tokenizers>=0.14.0" "transformers>=4.35.0"

# Step 4: Install other Tortoise dependencies
echo ""
echo "[4/5] Installing Tortoise TTS dependencies..."
pip install einops rotary-embedding-torch inflect progressbar2 unidecode scipy librosa soundfile

# Step 5: Install Tortoise TTS without dependencies
echo ""
echo "[5/5] Installing Tortoise TTS..."
pip install tortoise-tts --no-deps

# Verify installation
echo ""
echo "============================================"
echo "  Verifying Installation"
echo "============================================"

python3 -c "
import sys
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
    from tortoise.api import TextToSpeech
    print('  tortoise: OK')
except ImportError as e:
    print(f'  tortoise: FAILED - {e}')
    sys.exit(1)

print()
print('All imports successful!')
"

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
