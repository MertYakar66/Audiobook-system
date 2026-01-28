# Complete Setup Guide

This guide walks you through setting up the Audiobook Generation System on Windows.

## Prerequisites

- Windows 10/11 with powerful hardware (8GB+ RAM, GPU recommended)
- **Python 3.12.x** (CRITICAL: Python 3.13+ is NOT supported by Audiblez)
- Docker Desktop
- Git (optional, for updates)

## Step 1: Install Python 3.12

**IMPORTANT:** Audiblez requires Python <3.13. You must use Python 3.12.x.

### If You Have Python 3.13 Installed

1. **Uninstall Python 3.13:**
   - Open Settings > Apps > Installed Apps
   - Search for "Python 3.13"
   - Click Uninstall
   - Also remove from PATH if needed

2. **Install Python 3.12:**

**Option A: Using winget (Recommended)**
```powershell
winget install Python.Python.3.12
```

**Option B: Direct Download**
1. Download Python 3.12.8 from: https://www.python.org/downloads/release/python-3128/
2. Select "Windows installer (64-bit)"
3. Run installer
4. CHECK "Add python.exe to PATH"
5. Click "Install Now"

3. **Verify installation:**
```powershell
py -3.12 --version
# Should show: Python 3.12.x
```

### Multiple Python Versions

If you need both Python 3.12 and 3.13:
- Install Python 3.12 using the steps above
- Use `py -3.12` to specifically use Python 3.12
- The virtual environment will lock in the correct version

## Step 2: Install FFmpeg

FFmpeg is required for audio processing.

**Option A: Using winget (recommended)**
```cmd
winget install FFmpeg
```

**Option B: Manual installation**
1. Download from [ffmpeg.org](https://ffmpeg.org/download.html)
2. Extract to `C:\ffmpeg`
3. Add `C:\ffmpeg\bin` to your PATH

**Verify installation:**
```cmd
ffmpeg -version
ffprobe -version
```

## Step 3: Install Docker Desktop

1. Download Docker Desktop from [docker.com](https://www.docker.com/products/docker-desktop/)
2. Run installer, enable WSL 2 if prompted
3. Restart computer if required
4. Verify installation:
   ```cmd
   docker --version
   ```

## Step 4: Set Up the Project

**Option A: Use the Setup Script (Recommended)**

```powershell
# Navigate to project directory
cd C:\Users\merty\Desktop\Audiobook-system

# Run the setup script
.\setup.ps1
```

**Option B: Manual Setup**

```powershell
# Navigate to project directory
cd C:\Users\merty\Desktop\Audiobook-system

# Create virtual environment with Python 3.12 specifically
py -3.12 -m venv venv

# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Upgrade pip
python -m pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt
```

## Step 5: Install Audiblez + Kokoro

Audiblez is the TTS engine that uses the Kokoro-82M model.

```powershell
# Audiblez is already in requirements.txt, but you can verify:
pip show audiblez

# Verify installation
audiblez --help

# Download Kokoro TTS models (~300MB)
# This downloads the model files on first use
python -c "from kokoro import KPipeline; p = KPipeline(lang_code='a'); print('Models downloaded!')"
```

**Note:** First run will download the Kokoro model (~300MB). This may take a few minutes depending on your internet connection.

## Step 6: Configure Settings

Edit `config/settings.yaml` to customize:

```yaml
voice:
  # Choose your preferred voice
  default: "af_sky"  # or "am_michael" for male voice
  speed: 0.95        # Slightly slower for better comprehension

audio:
  m4b:
    bitrate: "64k"   # Good quality for speech
    channels: 1      # Mono is fine for audiobooks

processing:
  use_gpu: true      # Set to false if no GPU
```

## Step 7: Start Audiobookshelf

```cmd
# Navigate to docker directory
cd docker

# Start Audiobookshelf
docker-compose up -d

# Check status
docker-compose ps
```

**Access Audiobookshelf at:** http://localhost:13378

### First-Time Setup

1. Open http://localhost:13378 in browser
2. Create admin account
3. Add library:
   - Name: "Audiobooks"
   - Folder: `/audiobooks` (maps to your `output` folder)
   - Type: Audiobook

## Step 8: Test the System

```cmd
# Activate virtual environment (if not active)
venv\Scripts\activate

# Test voice generation
python -m scripts.main test-voice --voice af_sky

# Check system info
python -m scripts.main info
```

## Step 9: Convert Your First Book

1. Place a PDF in the `input` folder
2. (Optional) Extract and clean text:
   ```cmd
   python -m scripts.main extract "input/mybook.pdf"
   # Edit input/mybook.txt to remove TOC, index, etc.
   python -m scripts.main clean "input/mybook.txt"
   ```
3. Convert to audiobook:
   ```cmd
   python -m scripts.main convert "input/mybook.pdf"
   ```
4. Refresh Audiobookshelf library

## Troubleshooting

### "audiblez requires Python <3.13" or installation fails

You're using Python 3.13+. Switch to Python 3.12:
```powershell
# Check current Python version
python --version

# If it shows 3.13, use py launcher to target 3.12
py -3.12 --version

# Recreate venv with Python 3.12
Remove-Item -Recurse -Force venv
py -3.12 -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### "audiblez not found"

Make sure you've activated the virtual environment:
```powershell
.\venv\Scripts\Activate.ps1
```

### FFmpeg errors

Ensure FFmpeg is in your PATH:
```cmd
where ffmpeg
```

### GPU not detected

For NVIDIA GPUs, install CUDA:
```cmd
pip install torch --index-url https://download.pytorch.org/whl/cu118
```

### Docker issues

If Audiobookshelf won't start:
```cmd
docker-compose down
docker-compose up -d
docker-compose logs
```

### Out of memory

Reduce chunk size in `config/settings.yaml`:
```yaml
processing:
  chunk_size: 3000  # Smaller chunks use less memory
```

## Updating

```cmd
# Pull latest changes (if using git)
git pull

# Update dependencies
pip install -r requirements.txt --upgrade

# Update Docker containers
cd docker
docker-compose pull
docker-compose up -d
```

## File Locations

| What | Location |
|------|----------|
| Input PDFs | `input/` |
| Output M4B | `output/` |
| Config | `config/settings.yaml` |
| Audiobookshelf data | `docker/volumes/` |

## Next Steps

1. Set up Tailscale for remote access ([TAILSCALE.md](TAILSCALE.md))
2. Install mobile app (Plappa or Audiobookshelf)
3. Configure automatic library scanning
