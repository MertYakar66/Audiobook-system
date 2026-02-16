# Audio-Text Synchronization: Next Steps Report

**Date:** February 15, 2026  
**Status:** Ready to execute – all code is in place, awaiting cleaned book file

---

## Problem Statement

The audiobook reader's text highlighting does not match the audio playback. When playing a chapter, the highlighted sentence drifts further and further from what is actually being spoken. This is because the current `timing.json` has `start: 0, end: 0` for every sentence entry, forcing the reader to estimate sentence positions using a proportional word-count heuristic — which is inherently inaccurate.

## Root Cause

The audio files (ch01.mp3–ch41.mp3) were generated outside the timed TTS pipeline, so no per-sentence timestamps were captured. The `timing.json` file was created as a structural skeleton (correct sentence IDs, text, paragraph info) but with all timing values set to zero.

The reader's `computeChapterTimings()` function detected these zeros and fell back to dividing the total audio duration proportionally by word count per sentence. This is a rough approximation that accumulates error because TTS doesn't speak at a perfectly constant words-per-minute rate — pauses, punctuation, emphasis, and paragraph breaks all cause drift.

## Solution: Regenerate Audio with the Existing Timed TTS Pipeline

The project already has a complete, production-ready pipeline that generates audio **sentence by sentence** and records **exact millisecond-accurate timestamps** for each one. No new code needs to be written — only the audio needs to be regenerated.

### Pipeline Architecture

```
Input DOCX
  → scripts/readalong/book_processor.py (orchestrator)
    → scripts/extract_text.py (extract text from DOCX)
    → scripts/clean_text.py (clean text, detect chapters)
    → scripts/readalong/sentence_splitter.py (split chapters into sentences)
    → scripts/readalong/timed_tts.py (TTS engine selector)
      → scripts/readalong/timed_tts_edge.py (Edge TTS – DEFAULT)
        • Generates audio for EACH SENTENCE individually
        • Records exact start_time and end_time for each sentence
        • Adds calibrated pauses between sentences (0.3s) and paragraphs (0.8s)
        • Concatenates all sentence audio into one chapter WAV file
    → scripts/readalong/timing_map.py (builds timing.json with real timestamps)
    → Outputs: timing.json, text.json, manifest.json, audio/*.wav
  → scripts/convert_to_mp3.py (WAV → MP3, updates timing.json references)
```

### How It Produces Exact Timestamps

The key file is `scripts/readalong/timed_tts_edge.py`, class `TimedEdgeTTSGenerator`:

1. **Sentence splitting**: Text is split into individual sentences with paragraph tracking
2. **Per-sentence TTS**: Each sentence is sent to Edge TTS independently, producing a standalone audio segment
3. **Timestamp recording**: As each sentence audio is generated:
   - `start_time` = cumulative position in the chapter audio stream
   - `end_time` = start_time + (audio_samples / sample_rate)
   - Between sentences: 0.3s silence padding
   - Between paragraphs: 0.8s silence padding
4. **Concatenation**: All sentence audio segments + pauses are concatenated into one WAV file per chapter
5. **Timing map**: The `TimingMap` builder collects all `TimedSegment` objects and writes `timing.json` with the real timestamps

This means the timestamps are **not estimated** — they are the actual byte offsets of the audio data, converted to seconds. There is zero drift.

### How the Reader Uses Real Timestamps

The reader (`web/reader.js`) has been updated (already committed) with a smart detection mechanism in `computeChapterTimings()`:

```javascript
// Check if timing.json already has real timestamps
const hasRealTimings = chapter.entries.some(e => e.start > 0 || e.end > 0);

if (hasRealTimings) {
    // Use the real timestamps from timing.json — no overwriting!
    chapter._timingsDuration = duration;
    return;
}

// Fallback: proportional estimation by word count (only when timestamps are zeros)
```

When real timestamps are present, the reader uses them directly for:
- **Sentence highlighting**: `highlightCurrentSentence()` scans entries to find which sentence matches `currentTime`
- **Click-to-seek**: `seekToSentence()` uses `entry.start` to jump to the exact audio position
- **Progress bar**: Maps audio position → sentence index for visual feedback

---

## Execution Steps

### Prerequisites
```powershell
pip install edge-tts soundfile numpy python-docx scipy
```

Also need `ffmpeg` installed for WAV→MP3 conversion:
```powershell
winget install ffmpeg
```

### Step 1: Prepare Clean Book
Place the cleaned DOCX file in `input/DOCXs/`. The cleaner the text, the better the sentence splitting and audio quality. Remove:
- Headers/footers that repeat on every page
- Page numbers
- Footnote markers and footnote text
- Duplicate chapter titles
- Table of contents entries
- Any non-body text artifacts

### Step 2: Delete Old Audio and Data
```powershell
# Delete old audio files
Remove-Item output/readalong/the-intelligent-investor/audio/*.mp3
Remove-Item output/readalong/the-intelligent-investor/audio/*.wav

# Delete old data files (will be regenerated)
Remove-Item output/readalong/the-intelligent-investor/timing.json
Remove-Item output/readalong/the-intelligent-investor/text.json
Remove-Item output/readalong/the-intelligent-investor/manifest.json

# Delete processing state (forces fresh start)
Remove-Item output/readalong/the-intelligent-investor/processing_state.json -ErrorAction SilentlyContinue
```

### Step 3: Run the Pipeline
```powershell
cd c:\Users\merty\Desktop\Audiobook
python -m scripts.readalong.book_processor "input/DOCXs/YourCleanedBook.docx"
```

This will take a while (depends on book length — roughly 1-3 minutes per chapter with Edge TTS). The pipeline has **resume capability**: if it crashes or is interrupted, re-run the same command and it picks up from the last completed chapter.

Output will be in `output/readalong/the-intelligent-investor/`:
- `audio/ch01.wav`, `audio/ch02.wav`, ... (one WAV per chapter)
- `timing.json` — with **real timestamps** for every sentence
- `text.json` — structured text data for the reader
- `manifest.json` — book metadata for the reader

### Step 4: Convert WAV to MP3
```powershell
python scripts/convert_to_mp3.py output/readalong/the-intelligent-investor
```

This converts all WAV files to MP3 (64kbps mono, ~10x smaller) and updates `timing.json` to reference `.mp3` instead of `.wav`.

### Step 5: Clean Up WAV Files (Optional)
```powershell
Remove-Item output/readalong/the-intelligent-investor/audio/*.wav
```

### Step 6: Test
1. Start the server: `python serve.py`
2. Navigate to `http://localhost:8080`
3. Open the book from the library
4. Open browser console — you should see:
   ```
   [Reader] Using real timings for ch0: 180 entries, 2729.1s
   ```
   (NOT "estimating by word count")
5. Play audio — highlighting should be perfectly synchronized
6. Click any sentence — audio should jump to exactly that point
7. Drag the progress bar — highlighting should follow accurately

---

## Technical Details for Other AI Agents

### Key Files to Understand
| File | Purpose |
|------|---------|
| `scripts/readalong/book_processor.py` | Main orchestrator — `process_book()` runs the full pipeline |
| `scripts/readalong/timed_tts_edge.py` | Edge TTS engine — generates audio + timestamps per sentence |
| `scripts/readalong/timed_tts.py` | TTS engine selector (Edge → Tortoise → pyttsx3 fallback) |
| `scripts/readalong/timing_map.py` | Builds and saves `timing.json` from `TimedSegment` objects |
| `scripts/readalong/sentence_splitter.py` | Splits chapter text into sentence objects with IDs |
| `scripts/convert_to_mp3.py` | WAV → MP3 conversion + timing.json reference update |
| `web/reader.js` | Web reader — `computeChapterTimings()` detects real vs. estimated timestamps |

### Data Format: timing.json
```json
{
  "version": "1.0",
  "bookId": "the-intelligent-investor",
  "title": "The Intelligent Investor",
  "author": "Benjamin Graham",
  "totalDuration": 67953.4,
  "chapterCount": 21,
  "chapters": [
    {
      "chapterId": "ch01",
      "title": "Chapter 1: Investment vs. Speculation",
      "audioFile": "audio/ch01.mp3",
      "duration": 3241.5,
      "entries": [
        {
          "id": "ch01_p000_s000",
          "start": 0.0,
          "end": 2.847,
          "text": "The Intelligent Investor teaches that ...",
          "paragraph": 0
        },
        {
          "id": "ch01_p000_s001",
          "start": 3.147,
          "end": 5.923,
          "text": "Successful investing requires patience.",
          "paragraph": 0
        }
      ]
    }
  ]
}
```

The `start` and `end` values will be **real seconds** (e.g., `2.847`, not `0`). The gap between one entry's `end` and the next entry's `start` is the inter-sentence pause (0.3s) or paragraph pause (0.8s).

### TTS Voice Configuration
- Default voice: `en-US-DavisNeural` (natural male narrator, good for audiobooks)
- Available voices in `timed_tts_edge.py`: GuyNeural, JennyNeural, RyanNeural (British), SoniaNeural (British), DavisNeural
- Speed is configurable via `config.voice_speed` or constructor parameter
- To change: modify `DEFAULT_VOICE` in `timed_tts_edge.py` or pass `voice="en-US-JennyNeural"` to the processor

### Resume Capability
The pipeline saves `processing_state.json` in the output directory after each chapter completes. If interrupted:
- Re-run the same command
- It detects completed chapters and skips them
- On full completion, `processing_state.json` is deleted

### Potential Issues
1. **Network required**: Edge TTS requires internet access (it's a cloud service)
2. **Rate limiting**: If processing many chapters quickly, Edge TTS may throttle. The pipeline handles retries gracefully.
3. **Sentence splitting quality**: If the cleaned DOCX has unusual formatting (e.g., single-word sentences, merged paragraphs), sentence splitting may produce suboptimal boundaries. Clean text = better results.
4. **Chapter detection**: The pipeline auto-detects chapters from the DOCX structure. If chapter detection fails, you may need to adjust `scripts/clean_text.py`'s `ChapterDetector`.

---

## Recent Bug Fixes (Already Committed & Pushed)

These fixes are in the current codebase and will work immediately after audio regeneration:

1. **Progress bar seeking**: Fixed flicker/reset during drag with `isDragging` flag
2. **Mobile scrubbing**: Added touch event handlers (touchstart, touchmove, touchend)
3. **Click-to-seek**: Fixed by computing timings, resetting played state, and cancelling pending seek listeners
4. **Stuck highlights**: Fixed by clearing ALL `.active` elements when doing a fresh seek
5. **Service Worker Range bypass**: SW now passes through Range requests directly to the server (required for audio seeking)
6. **Library path fix**: Book data path corrected from `books/` to `../output/readalong/`
7. **Cache busting**: CSS `?v=4`, JS `?v=5`, SW cache `v4`
8. **Active sentence glow**: Purple glow effect on the currently playing sentence
9. **Real timestamp detection**: `computeChapterTimings()` preserves real timestamps instead of overwriting
