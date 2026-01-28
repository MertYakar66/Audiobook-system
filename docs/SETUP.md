# Complete Setup Guide

This guide walks you through setting up the Audiobook Generation System on Windows.

## Prerequisites

- Windows 10/11 with powerful hardware (8GB+ RAM, GPU recommended)
- Python 3.10 or higher
- Docker Desktop
- Git (optional, for updates)

## Step 1: Install Python

1. Download Python 3.10+ from [python.org](https://www.python.org/downloads/)
2. Run installer, check "Add Python to PATH"
3. Verify installation:
   ```cmd
   python --version
   ```

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

```cmd
# Navigate to project directory
cd C:\Users\merty\Audiobook-system

# Create virtual environment
python -m venv venv

# Activate virtual environment
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Step 5: Install Audiblez + Kokoro

Audiblez is the TTS engine that uses the Kokoro-82M model.

```cmd
# Install audiblez (includes kokoro)
pip install audiblez

# Verify installation
audiblez --help
```

**First run will download the Kokoro model (~300MB)**

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

### "audiblez not found"

Make sure you've activated the virtual environment:
```cmd
venv\Scripts\activate
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
