# Tortoise TTS Installation Script for Python 3.13
# This script installs Tortoise TTS with compatible dependencies

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Tortoise TTS Installation for Python 3.13" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Check Python version
$pythonVersion = python --version 2>&1
Write-Host "Python version: $pythonVersion" -ForegroundColor Yellow

# Step 1: Upgrade pip
Write-Host "`n[1/5] Upgrading pip..." -ForegroundColor Green
pip install --upgrade pip

# Step 2: Install PyTorch with CUDA (if available)
Write-Host "`n[2/5] Installing PyTorch..." -ForegroundColor Green
Write-Host "  Checking for CUDA..." -ForegroundColor Gray

# Try to detect CUDA
$cudaAvailable = $false
try {
    $nvidiaSmi = nvidia-smi 2>&1
    if ($LASTEXITCODE -eq 0) {
        $cudaAvailable = $true
        Write-Host "  CUDA detected! Installing PyTorch with CUDA support..." -ForegroundColor Green
    }
} catch {
    Write-Host "  CUDA not detected. Installing CPU-only PyTorch..." -ForegroundColor Yellow
}

if ($cudaAvailable) {
    # Install PyTorch with CUDA 12.1
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
} else {
    # Install CPU-only PyTorch
    pip install torch torchvision torchaudio
}

# Step 3: Install compatible transformers and tokenizers FIRST
Write-Host "`n[3/5] Installing transformers with compatible tokenizers..." -ForegroundColor Green
pip install tokenizers>=0.14.0 transformers>=4.35.0

# Step 4: Install other Tortoise dependencies
Write-Host "`n[4/5] Installing Tortoise TTS dependencies..." -ForegroundColor Green
pip install einops rotary-embedding-torch inflect progressbar2 unidecode scipy librosa soundfile

# Step 5: Install Tortoise TTS without dependencies (to avoid version conflicts)
Write-Host "`n[5/5] Installing Tortoise TTS..." -ForegroundColor Green
pip install tortoise-tts --no-deps

# Verify installation
Write-Host "`n============================================" -ForegroundColor Cyan
Write-Host "  Verifying Installation" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

$success = $true

# Test imports
Write-Host "`nTesting imports..." -ForegroundColor Yellow
$testScript = @"
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

print('\nAll imports successful!')
"@

python -c $testScript
if ($LASTEXITCODE -ne 0) {
    $success = $false
}

if ($success) {
    Write-Host "`n============================================" -ForegroundColor Green
    Write-Host "  Installation Complete!" -ForegroundColor Green
    Write-Host "============================================" -ForegroundColor Green
    Write-Host "`nYou can now generate audiobooks with:" -ForegroundColor White
    Write-Host "  python -m scripts.main convert `"input/The_Intelligent_Investor_Clean.docx`"" -ForegroundColor Cyan
    Write-Host "`nOr test a voice with:" -ForegroundColor White
    Write-Host "  python -m scripts.main test-voice --preset ultra_fast" -ForegroundColor Cyan
} else {
    Write-Host "`n============================================" -ForegroundColor Red
    Write-Host "  Installation had issues!" -ForegroundColor Red
    Write-Host "============================================" -ForegroundColor Red
    Write-Host "`nPlease check the error messages above." -ForegroundColor Yellow
}
