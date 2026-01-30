# Audiobook Generation System

A private, local audiobook generation system that converts PDF books into high-quality M4B audiobooks with chapter markers, metadata, and cover art. Now with **Read-Along mode** for synchronized audio-text reading.

## Features

- **High-Quality TTS**: Uses Kokoro-82M for natural-sounding narration
- **Chapter Detection**: Automatic chapter detection and embedded chapter markers
- **Metadata Support**: Title, author, narrator, and cover art embedding
- **M4B Output**: Industry-standard audiobook format compatible with all players
- **Read-Along Mode**: Synchronized audio-text reading with sentence highlighting
- **Library Management**: Audiobookshelf integration for library and playback
- **Remote Access**: Tailscale support for secure mobile listening
- **100% Local**: No cloud services, no subscription costs

## Read-Along Mode

The Read-Along feature provides an Everand-like experience where you can:
- **Listen and read simultaneously** with synchronized highlighting
- **Tap any sentence** to jump to that position in the audio
- **Auto-scroll** keeps the current sentence in view
- **Multiple themes**: Light, Sepia, Dark modes
- **Adjustable font size** for comfortable reading
- **Keyboard shortcuts**: Space to play/pause, arrows to navigate

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
│   └── settings.yaml          # Configuration file
├── docker/
│   └── docker-compose.yml     # Audiobookshelf container
├── docs/
│   ├── SETUP.md               # Detailed setup guide
│   └── TAILSCALE.md           # Remote access guide
├── input/                     # Place PDFs/text files here
├── output/                    # Generated audiobooks
│   └── readalong/             # Read-Along processed books
├── scripts/
│   ├── main.py                # CLI entry point
│   ├── extract_text.py        # PDF text extraction
│   ├── clean_text.py          # Text cleaning/normalization
│   ├── generate_audio.py      # TTS generation
│   ├── create_audiobook.py    # M4B creation
│   ├── metadata.py            # Metadata/cover handling
│   └── readalong/             # Read-Along module
│       ├── sentence_splitter.py   # Sentence splitting
│       ├── timed_tts.py           # TTS with timing capture
│       ├── timing_map.py          # Timing JSON generation
│       └── book_processor.py      # Complete pipeline
├── web/                       # Read-Along web reader
│   ├── index.html             # Main reader page
│   ├── styles.css             # Reader styles
│   └── reader.js              # Sync logic
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
# Convert PDF/text to M4B audiobook
python -m scripts.main convert <file>

# Create Read-Along book (synchronized audio-text)
python -m scripts.main readalong <file>

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

### Read-Along Workflow

```bash
# 1. Process a book for Read-Along
python -m scripts.main readalong "input/The Intelligent Investor.pdf"

# 2. Start a local web server
python -m http.server 8000 --directory web

# 3. Open http://localhost:8000 in your browser

# 4. Click "Select Book Folder" and choose output/readalong/<book>/

# 5. Read along with synchronized audio-text highlighting!
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
