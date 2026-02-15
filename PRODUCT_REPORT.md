# Scriptum - Audiobook Generation & Read-Along System

## Product Overview

**Scriptum** is a complete audiobook generation and synchronized reading system that converts documents (DOCX/PDF) into audiobooks with real-time text highlighting - similar to Speechify or Audible's read-along feature.

**Repository:** https://github.com/MertYakar66/Audiobook-system
**Branch:** `main`

---

## Key Features

### 1. Read & Listen Mode
- Synchronized audio playback with sentence-by-sentence text highlighting
- Click any sentence to jump to that position in the audio
- Adjustable playback speed (0.5x - 2.0x)
- Chapter navigation with dropdown selector
- Progress bar with seek functionality

### 2. Read Only Mode
- PDF page viewer for books without audio
- Shared highlights and notes between modes
- DOCX document viewing

### 3. Professional Features
- **Bookmarks:** Save positions with timestamps
- **Highlights:** Multi-color text highlighting (yellow, green, blue, pink, orange)
- **Notes:** Attach notes to highlighted text
- **Search:** Full-text search within books
- **Sleep Timer:** Auto-stop after set time or end of chapter
- **Export:** Export all highlights/notes to file

### 4. PWA Support
- Install as app on desktop/mobile
- Offline reading capability via Service Worker
- Progress synced to localStorage

---

## Project Structure

```
Audiobook-system/
├── web/                              # Web Application
│   ├── index.html                    # Homepage redirect
│   ├── library.html                  # Book library (main entry)
│   ├── library.js                    # Library controller
│   ├── library.css                   # Library styles
│   ├── reader.html                   # Audio reader with highlighting
│   ├── reader.js                     # Reader controller (70KB)
│   ├── reader-text.html              # Text-only reader
│   ├── reader-text.js                # Text reader controller
│   ├── styles.css                    # Reader styles (dark theme)
│   ├── sw.js                         # Service Worker for PWA
│   ├── manifest.json                 # PWA manifest
│   ├── icon-512.png                  # App icon
│   └── books/                        # Generated audiobooks
│       └── the-intelligent-investor/
│           ├── audio/                # ch01.wav - ch23.wav
│           ├── manifest.json         # Book metadata
│           ├── text.json             # Text with sentence IDs
│           ├── timing.json           # Audio-text sync data
│           └── cover.jpg
│
├── scripts/                          # Python Processing
│   ├── main.py                       # CLI entry point
│   ├── create_audiobook.py           # Audiobook creation
│   ├── extract_text.py               # Document text extraction
│   ├── docx_extractor.py             # DOCX processing
│   ├── clean_text.py                 # Text cleanup for TTS
│   ├── clean_docx.py                 # DOCX cleanup
│   ├── generate_audio.py             # Audio generation wrapper
│   ├── generate_audio_tortoise.py    # Tortoise TTS
│   ├── generate_audio_pyttsx3.py     # System TTS fallback
│   ├── convert_to_mp3.py             # WAV to MP3 conversion
│   ├── merge_chapters.py             # Chapter merging
│   ├── metadata.py                   # Book metadata handling
│   ├── diagnose_tts.py               # TTS diagnostics
│   ├── export_partial_book.py        # Partial export
│   │
│   ├── readalong/                    # Read-Along Module
│   │   ├── book_processor.py         # Main processing pipeline
│   │   ├── sentence_splitter.py      # Text to sentences
│   │   ├── timed_tts.py              # TTS engine selector
│   │   ├── timed_tts_edge.py         # Edge TTS (recommended)
│   │   ├── timed_tts_tortoise.py     # Tortoise TTS (slow)
│   │   ├── timed_tts_pyttsx3.py      # System TTS fallback
│   │   └── timing_map.py             # Audio timing generator
│   │
│   └── utils/
│       ├── config.py                 # Configuration
│       └── logger.py                 # Logging utilities
│
├── input/                            # Source Documents
│   ├── DOCXs/                        # Word documents
│   │   └── The Intelligent Investor.docx
│   └── PDFs/                         # PDF documents
│
├── output/                           # Generated Output
│   ├── books.json                    # Book catalog
│   └── readalong/                    # Processed books
│       └── the-intelligent-investor/
│
├── config/
│   └── settings.yaml                 # App configuration
│
├── COMMANDS.txt                      # Quick reference commands
├── requirements.txt                  # Python dependencies
├── serve.py                          # HTTP server with Range support
└── README.md                         # Documentation
```

---

## TTS Engines (Text-to-Speech)

### 1. Edge TTS (Recommended - Default)
- **Speed:** Very fast (~1 second per sentence)
- **Quality:** High (Microsoft neural voices)
- **GPU:** Not required
- **Install:** `pip install edge-tts`

**Recommended Voices:**
- `en-US-DavisNeural` - Male narrator (default, great for audiobooks)
- `en-US-GuyNeural` - Male, friendly
- `en-US-JennyNeural` - Female
- `en-GB-RyanNeural` - British male
- `en-GB-SoniaNeural` - British female

### 2. Tortoise TTS (Highest Quality - Slow)
- **Speed:** Very slow (minutes per sentence with `ultra_fast`, hours with `standard`)
- **Quality:** Highest (neural voice cloning)
- **GPU:** Required (16GB+ VRAM recommended)
- **Use for:** Final production when quality is paramount

### 3. pyttsx3 (Fallback)
- **Speed:** Instant
- **Quality:** Low (system TTS - robotic)
- **GPU:** Not required
- **Use for:** Testing, CPU-only systems

**Engine Selection:**
```bash
# Default (Edge TTS)
python -m scripts.main readalong "input/DOCXs/book.docx"

# Force Tortoise
set TTS_ENGINE=tortoise
python -m scripts.main readalong "input/DOCXs/book.docx" --preset ultra_fast

# Force pyttsx3
set TTS_ENGINE=pyttsx3
python -m scripts.main readalong "input/DOCXs/book.docx"
```

---

## Quick Start Commands

### Update from GitHub
```powershell
git pull origin main
```

### Install Dependencies
```powershell
pip install -r requirements.txt
pip install edge-tts
```

### Generate Audiobook
```powershell
python -m scripts.main readalong "input\DOCXs\The Intelligent Investor.docx"
```

### Start Web Server
```powershell
python -m http.server 8000 --directory web
```
Then open: http://localhost:8000

### Test a Voice Sample
```powershell
edge-tts --voice en-US-DavisNeural --text "Hello, this is a test." --write-media test.mp3
start test.mp3
```

### List Available Voices
```powershell
edge-tts --list-voices
```

---

## Book Data Format

### manifest.json
```json
{
  "version": "2.0",
  "bookId": "the-intelligent-investor",
  "title": "The Intelligent Investor",
  "author": "Benjamin Graham",
  "cover": "cover.jpg",
  "timing": "timing.json",
  "text": "text.json",
  "totalDuration": 31461.52,
  "chapterCount": 23,
  "chapters": [
    {
      "id": "ch01",
      "title": "Chapter 1",
      "duration": 1796.98,
      "sentenceCount": 223
    }
  ]
}
```

### text.json
```json
{
  "chapters": [
    {
      "id": "ch01",
      "title": "Chapter 1",
      "paragraphs": [
        {
          "id": "ch01_p000",
          "sentences": [
            {
              "id": "ch01_s0000",
              "text": "The purpose of this book..."
            }
          ]
        }
      ]
    }
  ]
}
```

### timing.json
```json
{
  "chapters": {
    "ch01": {
      "sentences": {
        "ch01_s0000": { "start": 0.0, "end": 3.5 },
        "ch01_s0001": { "start": 3.8, "end": 7.2 }
      }
    }
  }
}
```

---

## Web Application Architecture

### Library Page (library.html)
- Displays two sections: "Read & Listen" (with audio) and "Read Only" (without)
- Book cards with cover, title, author, duration
- Aggregated highlights/notes from all books
- Export functionality

### Reader Page (reader.html)
- Header: Home, Bookmarks, Title, Search, Settings
- Main content: Chapter nav, synchronized text display
- Footer: Audio controls (play/pause, skip, speed, bookmark, sleep timer)
- Side panels: Bookmarks, Highlights, Notes with tabs
- Modals: Search, Sleep Timer, Note Editor

### Key JavaScript Classes
- `ScriptumLibrary` - Library page controller
- `ReadAlongReader` - Main reader with all features

---

## Current Book: The Intelligent Investor

- **Author:** Benjamin Graham
- **Chapters:** 23 (including commentary sections)
- **Total Duration:** ~8.7 hours
- **Format:** WAV audio files
- **Location:** `web/books/the-intelligent-investor/`

**Chapter Titles:**
- Chapters 1-14: Main chapters
- Commentary on Chapter 14, 15, 17: Jason Zweig's commentary sections
- Chapters 15-20: Remaining main chapters

---

## Important Notes

### File Paths
- Books served from `web/books/` (relative to web server root)
- `library.js` and `reader.js` use path: `books/the-intelligent-investor`
- Do NOT use `../output/readalong/` paths (outside server root)

### Git Ignored Files
- `input/DOCXs/` and `input/PDFs/` - Source documents (large)
- `output/readalong/` - Generated audiobooks (large)
- `web/books/` - Served audiobooks (large)

### Known Considerations
- Tortoise TTS is extremely slow - use Edge TTS for faster generation
- GPU OOM errors on Tortoise: System has sentence chunking (max 200 chars) built in
- CPU mode for Tortoise: Auto-falls back to pyttsx3 to prevent crashes

---

## Development Notes

### Adding a New Book
1. Place DOCX/PDF in `input/DOCXs/` or `input/PDFs/`
2. Run: `python -m scripts.main readalong "input/DOCXs/NewBook.docx"`
3. Output goes to `output/readalong/new-book/`
4. Copy to `web/books/new-book/` for serving
5. Add entry to `READ_LISTEN_BOOKS` in `library.js`

### Theming
- Default: Dark theme (`data-theme="dark"`)
- Options: light, sepia, dark
- Controlled in Settings panel

### Audio Seeking
- Uses HTTP Range requests for seeking
- `serve.py` provides Range support (use instead of simple http.server for production)

---

## Contact & Resources

- **GitHub:** https://github.com/MertYakar66/Audiobook-system
- **Commands Reference:** See `COMMANDS.txt` in project root
- **Edge TTS Docs:** https://github.com/rany2/edge-tts
