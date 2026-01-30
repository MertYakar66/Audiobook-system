# Audiobookshelf Startup Script
# Starts the Audiobookshelf Docker container for audiobook playback

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "     Starting Audiobookshelf" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if Docker is running
Write-Host "[1/4] Checking Docker..." -ForegroundColor Yellow
try {
    $dockerInfo = docker info 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Docker not responding"
    }
    Write-Host "  Docker is running" -ForegroundColor Green
} catch {
    Write-Host ""
    Write-Host "  ERROR: Docker is not running!" -ForegroundColor Red
    Write-Host ""
    Write-Host "  Please:" -ForegroundColor Yellow
    Write-Host "  1. Open Docker Desktop" -ForegroundColor White
    Write-Host "  2. Wait for it to fully start (check system tray)" -ForegroundColor White
    Write-Host "  3. Run this script again" -ForegroundColor White
    Write-Host ""
    exit 1
}

# Create necessary directories
Write-Host "[2/4] Creating directories..." -ForegroundColor Yellow

# Script is in project root, so use $PSScriptRoot directly
$projectRoot = $PSScriptRoot
$dockerDir = Join-Path $projectRoot "docker"
$outputDir = Join-Path $projectRoot "output"

$directories = @(
    (Join-Path $dockerDir "volumes"),
    (Join-Path $dockerDir "volumes\config"),
    (Join-Path $dockerDir "volumes\metadata"),
    (Join-Path $dockerDir "volumes\podcasts"),
    $outputDir
)

foreach ($dir in $directories) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        Write-Host "  Created: $dir" -ForegroundColor Gray
    }
}
Write-Host "  Directories ready" -ForegroundColor Green

# Navigate to docker directory
Write-Host "[3/4] Starting Audiobookshelf container..." -ForegroundColor Yellow
Set-Location $dockerDir

# Pull latest image and start
docker-compose pull --quiet 2>$null
docker-compose up -d

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "  ERROR: Failed to start container" -ForegroundColor Red
    Write-Host "  Try running: docker-compose logs" -ForegroundColor Yellow
    exit 1
}

Write-Host "  Container started" -ForegroundColor Green

# Wait for service to be ready
Write-Host "[4/4] Waiting for service to be ready..." -ForegroundColor Yellow
$maxAttempts = 30
$attempt = 0
$ready = $false

while ($attempt -lt $maxAttempts -and -not $ready) {
    Start-Sleep -Seconds 1
    $attempt++

    try {
        $response = Invoke-WebRequest -Uri "http://localhost:13378" -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
        if ($response.StatusCode -eq 200) {
            $ready = $true
        }
    } catch {
        # Still starting up
        Write-Host "  Waiting... ($attempt/$maxAttempts)" -ForegroundColor Gray -NoNewline
        Write-Host "`r" -NoNewline
    }
}

if ($ready) {
    Write-Host "  Service is ready!                    " -ForegroundColor Green
} else {
    Write-Host "  Service may still be starting..." -ForegroundColor Yellow
}

# Get local IP for mobile access
$localIP = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -notmatch "Loopback" -and $_.IPAddress -notmatch "^169" } | Select-Object -First 1).IPAddress

# Success message
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "     Audiobookshelf is Running!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "ACCESS FROM THIS COMPUTER:" -ForegroundColor Cyan
Write-Host "  http://localhost:13378" -ForegroundColor White
Write-Host ""
if ($localIP) {
    Write-Host "ACCESS FROM PHONE (same WiFi):" -ForegroundColor Cyan
    Write-Host "  http://${localIP}:13378" -ForegroundColor White
    Write-Host ""
}
Write-Host "FIRST TIME SETUP:" -ForegroundColor Cyan
Write-Host "  1. Open the URL above in your browser" -ForegroundColor White
Write-Host "  2. Create an admin account" -ForegroundColor White
Write-Host "  3. Click 'Add Library'" -ForegroundColor White
Write-Host "  4. Name: Audiobooks" -ForegroundColor White
Write-Host "  5. Folder: /audiobooks" -ForegroundColor White
Write-Host "  6. Type: Audiobook" -ForegroundColor White
Write-Host "  7. Click 'Add'" -ForegroundColor White
Write-Host ""
Write-Host "MOBILE APPS:" -ForegroundColor Cyan
Write-Host "  iPhone:  Search 'Plappa' in App Store" -ForegroundColor White
Write-Host "  Android: Search 'Audiobookshelf' in Play Store" -ForegroundColor White
Write-Host ""
Write-Host "COMMANDS:" -ForegroundColor Cyan
Write-Host "  Stop:    cd docker; docker-compose down" -ForegroundColor Gray
Write-Host "  Logs:    cd docker; docker-compose logs -f" -ForegroundColor Gray
Write-Host "  Restart: cd docker; docker-compose restart" -ForegroundColor Gray
Write-Host ""

# Open browser
$openBrowser = Read-Host "Open Audiobookshelf in browser now? (Y/n)"
if ($openBrowser -ne "n" -and $openBrowser -ne "N") {
    Start-Process "http://localhost:13378"
}
