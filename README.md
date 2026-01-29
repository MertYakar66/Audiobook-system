# Audiobook Generation System

A private, local audiobook generation system that converts PDF books into high-quality M4B audiobooks with chapter markers, metadata, and cover art.

## Features

- **High-Quality TTS**: Uses Kokoro-82M for natural-sounding narration
- **Chapter Detection**: Automatic chapter detection and embedded chapter markers
- **Metadata Support**: Title, author, narrator, and cover art embedding
- **M4B Output**: Industry-standard audiobook format compatible with all players
- **Library Management**: Audiobookshelf integration for library and playback
- **Remote Access**: Tailscale support for secure mobile listening
- **100% Local**: No cloud services, no subscription costs

## Requirements

**CRITICAL: Python 3.12.x is required** (Kokoro TTS does not support Python 3.13+)

- Python 3.12.x (NOT 3.13)
- FFmpeg
- Docker Desktop (for Audiobookshelf)
- ~4GB RAM for TTS processing
- GPU recommended but not required

## Quick Start (Windows)

```powershell
# 1. Run the setup script (handles Python 3.12, venv, dependencies)
.\setup.ps1

# 2. Activate virtual environment
.\venv\Scripts\Activate.ps1

# 3. Verify installation
python -m scripts.main info

# 4. Convert a PDF to audiobook
python -m scripts.main convert "input\My Book.pdf"

# 5. Start Audiobookshelf
cd docker && docker-compose up -d
```

Or manually:
```powershell
# Create virtual environment with Python 3.12
py -3.12 -m venv venv
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Download Kokoro TTS models (first run downloads ~300MB)
python -c "from kokoro import KPipeline; KPipeline(lang_code='a')"
```

## Project Structure

```
Audiobook-system/
├── config/
│   └── settings.yaml      # Configuration file
├── docker/
│   └── docker-compose.yml # Audiobookshelf container
├── docs/
│   ├── SETUP.md           # Detailed setup guide
│   └── TAILSCALE.md       # Remote access guide
├── input/                 # Place PDFs/text files here
├── output/                # Generated audiobooks
├── scripts/
│   ├── main.py            # CLI entry point
│   ├── extract_text.py    # PDF text extraction
│   ├── clean_text.py      # Text cleaning/normalization
│   ├── generate_audio.py  # TTS generation
│   ├── create_audiobook.py# M4B creation
│   └── metadata.py        # Metadata/cover handling
├── requirements.txt
└── README.md
```

## Usage

### Convert PDF to Audiobook

```bash
# Basic conversion
python -m scripts.main convert "input/book.pdf"

# With custom options
python -m scripts.main convert "input/book.pdf" \
    --voice am_michael \
    --title "My Book Title" \
    --author "Author Name" \
    --cover "cover.jpg"
```

### Available Commands

```bash
# Convert PDF/text to audiobook
python -m scripts.main convert <file>

# Extract text from PDF (for manual editing)
python -m scripts.main extract <pdf>

# Clean extracted text
python -m scripts.main clean <text_file>

# Preview chapter detection
python -m scripts.main chapters <text_file>

# Test a voice
python -m scripts.main test-voice --voice af_sky

# List available voices
python -m scripts.main list-voices

# Show system info
python -m scripts.main info
```

### Available Voices

**Female (calm, recommended for audiobooks):**
- `af_sky` - Calm, neutral (default)
- `af_bella` - Warm, expressive
- `af_nicole` - Professional
- `af_sarah` - Friendly

**Male (calm, recommended for audiobooks):**
- `am_michael` - Calm, neutral
- `am_adam` - Deep, authoritative
- `am_fenrir` - Casual

## Workflow

1. **Prepare PDF**: Manually clean the PDF text (remove TOC, index, headers) - ~5 min
2. **Convert**: Run the conversion script
3. **Library**: Audiobookshelf automatically picks up new audiobooks
4. **Listen**: Use mobile app (Plappa/ABS) to listen
5. **Sync**: Progress syncs across devices

## Configuration

Edit `config/settings.yaml` to customize:

```yaml
voice:
  default: "af_sky"  # Change default voice
  speed: 0.95        # Adjust speech rate

chapters:
  pause_between: 1.5 # Seconds between chapters

audio:
  m4b:
    bitrate: "64k"   # Audio quality
```

## Documentation

- [Detailed Setup Guide](docs/SETUP.md)
- [Tailscale Remote Access](docs/TAILSCALE.md)

## License

For personal use only. Respect copyright laws when converting books.
