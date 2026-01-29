# Audiobook Generation System - Windows Setup Script
# Requires: Windows PowerShell 5.1+ or PowerShell 7+

param(
    [switch]$SkipPythonCheck,
    [switch]$Force
)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Audiobook Generation System Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Check Python version
Write-Host "[1/6] Checking Python version..." -ForegroundColor Yellow

$pythonCmd = $null
$pythonVersion = $null

# Try py launcher first (preferred on Windows)
try {
    $pyVersion = & py -3.12 --version 2>&1
    if ($pyVersion -match "Python 3\.12") {
        $pythonCmd = "py -3.12"
        $pythonVersion = $pyVersion
        Write-Host "  Found Python 3.12 via py launcher" -ForegroundColor Green
    }
} catch {
    # py launcher not available or 3.12 not installed
}

# Try python command if py didn't work
if (-not $pythonCmd) {
    try {
        $pyVersion = & python --version 2>&1
        if ($pyVersion -match "Python 3\.12") {
            $pythonCmd = "python"
            $pythonVersion = $pyVersion
            Write-Host "  Found: $pythonVersion" -ForegroundColor Green
        } elseif ($pyVersion -match "Python 3\.1[3-9]|Python 3\.[2-9][0-9]") {
            Write-Host ""
            Write-Host "  ERROR: $pyVersion detected" -ForegroundColor Red
            Write-Host "  Kokoro TTS requires Python 3.12.x (NOT 3.13+)" -ForegroundColor Red
            Write-Host ""
            Write-Host "  To fix this:" -ForegroundColor Yellow
            Write-Host "  1. Install Python 3.12:" -ForegroundColor White
            Write-Host "     winget install Python.Python.3.12" -ForegroundColor Gray
            Write-Host ""
            Write-Host "  2. Or download from:" -ForegroundColor White
            Write-Host "     https://www.python.org/downloads/release/python-3128/" -ForegroundColor Gray
            Write-Host ""
            Write-Host "  3. Then run this script again" -ForegroundColor White
            Write-Host ""
            exit 1
        } elseif ($pyVersion -match "Python 3\.(10|11)") {
            $pythonCmd = "python"
            $pythonVersion = $pyVersion
            Write-Host "  Found: $pythonVersion (compatible)" -ForegroundColor Green
        }
    } catch {
        # python command not available
    }
}

if (-not $pythonCmd) {
    Write-Host ""
    Write-Host "  ERROR: Python 3.12 not found" -ForegroundColor Red
    Write-Host ""
    Write-Host "  Install Python 3.12:" -ForegroundColor Yellow
    Write-Host "  winget install Python.Python.3.12" -ForegroundColor Gray
    Write-Host ""
    Write-Host "  Or download from:" -ForegroundColor White
    Write-Host "  https://www.python.org/downloads/release/python-3128/" -ForegroundColor Gray
    Write-Host ""
    exit 1
}

# Step 2: Check FFmpeg
Write-Host "[2/6] Checking FFmpeg..." -ForegroundColor Yellow
$ffmpegPath = Get-Command ffmpeg -ErrorAction SilentlyContinue
if ($ffmpegPath) {
    Write-Host "  FFmpeg found: $($ffmpegPath.Source)" -ForegroundColor Green
} else {
    Write-Host "  FFmpeg not found. Installing via winget..." -ForegroundColor Yellow
    try {
        winget install FFmpeg --accept-source-agreements --accept-package-agreements
        Write-Host "  FFmpeg installed successfully" -ForegroundColor Green
        Write-Host "  NOTE: You may need to restart your terminal for FFmpeg to be in PATH" -ForegroundColor Yellow
    } catch {
        Write-Host "  WARNING: Could not install FFmpeg automatically" -ForegroundColor Yellow
        Write-Host "  Please install manually from: https://ffmpeg.org/download.html" -ForegroundColor Yellow
    }
}

# Step 3: Create virtual environment
Write-Host "[3/6] Creating virtual environment..." -ForegroundColor Yellow
$venvPath = Join-Path $PSScriptRoot "venv"

if ((Test-Path $venvPath) -and -not $Force) {
    Write-Host "  Virtual environment already exists" -ForegroundColor Yellow
    $response = Read-Host "  Recreate it? (y/N)"
    if ($response -eq "y" -or $response -eq "Y") {
        Remove-Item -Recurse -Force $venvPath
    } else {
        Write-Host "  Keeping existing venv" -ForegroundColor Green
    }
}

if (-not (Test-Path $venvPath)) {
    if ($pythonCmd -eq "py -3.12") {
        & py -3.12 -m venv $venvPath
    } else {
        & $pythonCmd -m venv $venvPath
    }
    Write-Host "  Created virtual environment" -ForegroundColor Green
}

# Step 4: Activate and upgrade pip
Write-Host "[4/6] Activating environment and upgrading pip..." -ForegroundColor Yellow
$activateScript = Join-Path $venvPath "Scripts\Activate.ps1"
. $activateScript

python -m pip install --upgrade pip --quiet
Write-Host "  Pip upgraded" -ForegroundColor Green

# Step 5: Install requirements
Write-Host "[5/6] Installing dependencies..." -ForegroundColor Yellow
Write-Host "  This may take a few minutes..." -ForegroundColor Gray

$requirementsPath = Join-Path $PSScriptRoot "requirements.txt"
pip install -r $requirementsPath

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "  ERROR: Failed to install dependencies" -ForegroundColor Red
    Write-Host "  Check the error messages above" -ForegroundColor Yellow
    exit 1
}
Write-Host "  Dependencies installed" -ForegroundColor Green

# Step 6: Download Kokoro models
Write-Host "[6/6] Downloading Kokoro TTS models..." -ForegroundColor Yellow
Write-Host "  This downloads ~300MB of model files..." -ForegroundColor Gray

$downloadScript = @"
try:
    from kokoro import KPipeline
    print('  Initializing Kokoro pipeline...')
    pipeline = KPipeline(lang_code='a')
    print('  Models downloaded successfully!')
except Exception as e:
    print(f'  Note: Model download may complete on first use: {e}')
"@

python -c $downloadScript

# Success!
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Setup Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host ""
Write-Host "1. Activate the virtual environment:" -ForegroundColor White
Write-Host "   .\venv\Scripts\Activate.ps1" -ForegroundColor Gray
Write-Host ""
Write-Host "2. Verify installation:" -ForegroundColor White
Write-Host "   python -m scripts.main info" -ForegroundColor Gray
Write-Host ""
Write-Host "3. Test voice generation:" -ForegroundColor White
Write-Host "   python -m scripts.main test-voice" -ForegroundColor Gray
Write-Host ""
Write-Host "4. Convert a PDF:" -ForegroundColor White
Write-Host "   python -m scripts.main convert `"input\book.pdf`"" -ForegroundColor Gray
Write-Host ""
Write-Host "5. Start Audiobookshelf (requires Docker):" -ForegroundColor White
Write-Host "   cd docker; docker-compose up -d" -ForegroundColor Gray
Write-Host ""
