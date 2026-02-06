# Tortoise TTS Installation Script for Python 3.13
# This script installs Tortoise TTS with compatible dependencies

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Tortoise TTS Installation for Python 3.13" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Check Python version and path
$pythonVersion = python --version 2>&1
$pythonPath = python -c "import sys; print(sys.executable)" 2>&1
Write-Host "Python version: $pythonVersion" -ForegroundColor Yellow
Write-Host "Python path: $pythonPath" -ForegroundColor Yellow

# Step 1: Upgrade pip
Write-Host "`n[1/6] Upgrading pip..." -ForegroundColor Green
python -m pip install --upgrade pip

# Step 2: Install PyTorch with CUDA (if available)
Write-Host "`n[2/6] Installing PyTorch..." -ForegroundColor Green
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
    python -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
} else {
    # Install CPU-only PyTorch
    python -m pip install torch torchvision torchaudio
}

# Step 3: Install compatible transformers and tokenizers FIRST
Write-Host "`n[3/6] Installing transformers with compatible tokenizers..." -ForegroundColor Green
python -m pip install "tokenizers>=0.14.0" "transformers>=4.35.0"

# Step 4: Install other Tortoise dependencies
Write-Host "`n[4/6] Installing Tortoise TTS dependencies..." -ForegroundColor Green
python -m pip install einops rotary-embedding-torch inflect progressbar2 unidecode scipy librosa soundfile

# Step 5: Uninstall any existing tortoise-tts to avoid conflicts
Write-Host "`n[5/6] Cleaning up old Tortoise installations..." -ForegroundColor Green
python -m pip uninstall tortoise-tts -y 2>$null

# Step 6: Install Tortoise TTS from GitHub (more reliable than PyPI)
Write-Host "`n[6/6] Installing Tortoise TTS from GitHub..." -ForegroundColor Green
python -m pip install git+https://github.com/neonbjb/tortoise-tts.git

# Verify installation
Write-Host "`n============================================" -ForegroundColor Cyan
Write-Host "  Verifying Installation" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

$success = $true

# Test imports
Write-Host "`nTesting imports..." -ForegroundColor Yellow
$testScript = @"
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
    Write-Host "`nTrying diagnostic..." -ForegroundColor Yellow
    Write-Host "Run: python -m scripts.diagnose_tts" -ForegroundColor Cyan
    Write-Host "`nOr try a fresh virtual environment:" -ForegroundColor Yellow
    Write-Host "  python -m venv tts_venv" -ForegroundColor Cyan
    Write-Host "  tts_venv\Scripts\activate" -ForegroundColor Cyan
    Write-Host "  .\install_tortoise.ps1" -ForegroundColor Cyan
}
