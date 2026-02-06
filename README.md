# Audiobook Generation System

A private, local audiobook generation system that converts PDF books into high-quality M4B audiobooks with chapter markers, metadata, and cover art. Now with **Read-Along mode** for synchronized audio-text reading and **voice cloning** support.

## Features

- **High-Quality TTS**: Uses Tortoise TTS for natural, expressive narration
- **Voice Cloning**: Clone any voice from audio samples
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
- **View original pages**: Side-by-side view of PDF pages

## Requirements

- Python 3.10-3.13
- FFmpeg
- Docker Desktop (for Audiobookshelf)
- ~8GB RAM for TTS processing
- **GPU highly recommended** (NVIDIA with CUDA)

## Quick Start (Windows)

```powershell
# 1. Install Tortoise TTS and dependencies
.\install_tortoise.ps1

# 2. Verify installation
python -m scripts.main info

# 3. Test voice generation (quick test)
python -m scripts.main test-voice --preset ultra_fast

# 4. Convert a book to audiobook
python -m scripts.main convert "input\The_Intelligent_Investor_Clean.docx"

# 5. Start Audiobookshelf
cd docker && docker-compose up -d
```

Or manually:
```powershell
# Upgrade pip
pip install --upgrade pip

# Install PyTorch with CUDA (if you have NVIDIA GPU)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# Or CPU-only:
pip install torch torchvision torchaudio

# Install compatible transformers (IMPORTANT: do this BEFORE tortoise-tts)
pip install "tokenizers>=0.14.0" "transformers>=4.35.0"

# Install other dependencies
pip install -r requirements.txt

# Install Tortoise TTS without conflicting dependencies
pip install tortoise-tts --no-deps
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
├── input/                     # Place PDFs/DOCX/text files here
├── output/                    # Generated audiobooks
│   └── readalong/             # Read-Along processed books
├── voices/                    # Custom voice samples for cloning
├── scripts/
│   ├── main.py                # CLI entry point
│   ├── extract_text.py        # PDF text extraction
│   ├── clean_text.py          # Text cleaning/normalization
│   ├── generate_audio.py      # TTS generation (Tortoise)
│   ├── create_audiobook.py    # M4B creation
│   ├── metadata.py            # Metadata/cover handling
│   └── readalong/             # Read-Along module
│       ├── sentence_splitter.py   # Sentence splitting
│       ├── timed_tts.py           # TTS with timing capture
│       ├── timing_map.py          # Timing JSON generation
│       └── book_processor.py      # Complete pipeline
├── web/                       # Read-Along web reader
│   ├── reader.html            # Main reader page
│   ├── library.html           # Book library
│   ├── styles.css             # Reader styles
│   └── reader.js              # Sync logic
├── install_tortoise.ps1       # Windows installation script
├── install_tortoise.sh        # Linux/Mac installation script
├── requirements.txt
└── README.md
```

## Usage

### Convert PDF/DOCX to Audiobook

```bash
# Basic conversion
python -m scripts.main convert "input/book.pdf"

# With quality preset
python -m scripts.main convert "input/book.pdf" --preset standard

# With custom options
python -m scripts.main convert "input/book.pdf" \
    --voice train_dotrice \
    --preset high_quality \
    --title "My Book Title" \
    --author "Author Name"
```

### Quality Presets

| Preset | Speed | Quality | Use Case |
|--------|-------|---------|----------|
| `ultra_fast` | Fastest | Lower | Testing/preview |
| `fast` | Moderate | Good | Development |
| `standard` | Slow | High | Production |
| `high_quality` | Slowest | Best | Final audiobooks |

### Available Commands

```bash
# Convert PDF/text to M4B audiobook
python -m scripts.main convert <file> [--preset fast]

# Create Read-Along book (synchronized audio-text)
python -m scripts.main readalong <file> [--preset fast]

# Extract text from PDF (for manual editing)
python -m scripts.main extract <pdf>

# Clean extracted text
python -m scripts.main clean <text_file>

# Preview chapter detection
python -m scripts.main chapters <text_file>

# Test a voice
python -m scripts.main test-voice --voice train_dotrice --preset ultra_fast

# List available voices
python -m scripts.main list-voices

# Show system info
python -m scripts.main info
```

### Read-Along Workflow

```bash
# 1. Process a book for Read-Along
python -m scripts.main readalong "input/The_Intelligent_Investor_Clean.docx" --preset fast

# 2. Start a local web server
python -m http.server 8000 --directory web

# 3. Open http://localhost:8000 in your browser

# 4. Click "Select Book Folder" and choose output/readalong/<book>/

# 5. Read along with synchronized audio-text highlighting!
```

### Voice Cloning

Clone any voice by providing reference audio samples:

```bash
# 1. Create a voice folder
mkdir voices\my_narrator

# 2. Add 3-10 WAV files (6-10 seconds each) of clear speech
# Place them in voices\my_narrator\

# 3. Use your cloned voice
python -m scripts.main convert "input/book.pdf" --voice my_narrator
```

### Built-in Voices

**Recommended for Audiobooks:**
- `train_dotrice` - British, narrator-style (default)
- `train_kennard` - Male, warm and clear
- `train_grace` - Female, elegant

**Male Voices:**
- `freeman` - Deep, authoritative
- `deniro` - Casual, conversational
- `tom` - Clear, neutral
- `william` - British, refined
- `geralt` - Deep, dramatic

**Female Voices:**
- `emma` - British, warm
- `halle` - American, professional
- `jlaw` - American, casual
- `angie` - Expressive
- `mol` - Clear, neutral

## Configuration

Edit `config/settings.yaml` to customize:

```yaml
voice:
  default: "train_dotrice"  # Default voice
  speed: 1.0                # Speech rate
  preset: "fast"            # Quality preset

chapters:
  pause_between: 1.5        # Seconds between chapters

audio:
  m4b:
    bitrate: "64k"          # Audio quality
```

## Documentation

- [Detailed Setup Guide](docs/SETUP.md)
- [Tailscale Remote Access](docs/TAILSCALE.md)

## Troubleshooting

### Tortoise TTS Installation Issues

If you get errors about `tokenizers` or `Rust compiler`:

```powershell
# Make sure to install transformers FIRST with newer versions
pip install "tokenizers>=0.14.0" "transformers>=4.35.0"

# Then install tortoise-tts without dependencies
pip install tortoise-tts --no-deps
```

### Out of Memory (OOM) Errors

Tortoise TTS requires significant VRAM. If you get OOM errors:

1. Use `--preset ultra_fast` for testing
2. Process shorter chapters
3. Use CPU mode (slower but works): set `CUDA_VISIBLE_DEVICES=""`

### Slow Generation

Tortoise TTS is slower than other TTS systems but produces higher quality:

- Use GPU (10-20x faster than CPU)
- Use `ultra_fast` preset for quick tests
- Use `fast` preset for good balance
- Reserve `high_quality` for final production

## License

For personal use only. Respect copyright laws when converting books.
