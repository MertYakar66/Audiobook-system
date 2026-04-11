"""
Audio Regeneration Script

Regenerates all chapter audio files from text.json using edge-tts.
Captures real per-sentence timestamps for timing.json.
Produces MP3 files with accurate timing data for click-to-seek.

Usage:
    python scripts/regenerate_audio.py [--resume] [--chapter N] [--start N]
"""

import asyncio
import json
import os
import sys
import tempfile
import time
from pathlib import Path

import edge_tts
from pydub import AudioSegment

# ── Configuration ──────────────────────────────────────────────────
VOICE = "en-US-GuyNeural"          # Natural male narrator voice
RATE = "+0%"                        # Speech rate adjustment
SENTENCE_PAUSE_MS = 350             # Silence between sentences (ms)
PARAGRAPH_PAUSE_MS = 600            # Silence between paragraphs (ms)
HEADING_PAUSE_MS = 800              # Silence after headings (ms)
MAX_RETRIES = 3                     # Retries per sentence on TTS failure
RETRY_DELAY = 2.0                   # Seconds to wait between retries

# Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
BOOK_DIR = PROJECT_ROOT / "output" / "readalong" / "The_Intelligent_Investor"
TEXT_JSON = BOOK_DIR / "text.json"
TIMING_JSON = BOOK_DIR / "timing.json"
MANIFEST_JSON = BOOK_DIR / "manifest.json"
AUDIO_DIR = BOOK_DIR / "audio"
PROGRESS_FILE = BOOK_DIR / ".audio_progress.json"


def load_text_data():
    """Load and return the text.json data."""
    with open(TEXT_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


def load_progress():
    """Load resume progress if available."""
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, "r") as f:
            return json.load(f)
    return {"completed_chapters": [], "timing_chapters": []}


def save_progress(progress):
    """Save current progress for resume capability."""
    with open(PROGRESS_FILE, "w") as f:
        json.dump(progress, f, indent=2)


async def generate_sentence_audio(text: str, output_path: str) -> bool:
    """Generate audio for a single sentence using edge-tts with retries."""
    for attempt in range(MAX_RETRIES):
        try:
            communicate = edge_tts.Communicate(text, VOICE, rate=RATE)
            await communicate.save(output_path)
            # Verify file was actually created and has content
            if os.path.exists(output_path) and os.path.getsize(output_path) > 100:
                return True
            else:
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY)
                continue
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY * (attempt + 1))
            else:
                print(f"    ⚠ TTS failed after {MAX_RETRIES} attempts: {e}")
    return False


async def process_chapter_async(chapter_data, chapter_index, text_chapter_id):
    """
    Process a single chapter: generate audio for each sentence,
    concatenate with pauses, and return (AudioSegment, timing_entries).
    """
    paragraphs = chapter_data.get("paragraphs", [])
    title = chapter_data.get("title", f"Chapter {chapter_index + 1}")

    # Collect all sentences with paragraph context
    sentences = []
    for para in paragraphs:
        is_heading = para.get("isHeading", False)
        para_sentences = para.get("sentences", [])
        for i, sent in enumerate(para_sentences):
            sentences.append({
                "id": sent["id"],
                "text": sent["text"],
                "is_heading": is_heading,
                "is_last_in_para": (i == len(para_sentences) - 1),
                "is_heading_para": is_heading,
            })

    if not sentences:
        print(f"  ⚠ Chapter {chapter_index} has no sentences, creating silence")
        silence = AudioSegment.silent(duration=1000)
        return silence, []

    print(f"  📖 {title}")
    print(f"     {len(sentences)} sentences across {len(paragraphs)} paragraphs")

    chapter_audio = AudioSegment.empty()
    timing_entries = []
    current_time_ms = 0
    failed_count = 0

    for i, sent_info in enumerate(sentences):
        sent_id = sent_info["id"]
        sent_text = sent_info["text"].strip()

        # Skip very short/empty text fragments (< 2 chars)
        if not sent_text or len(sent_text) < 2:
            timing_entries.append({
                "id": sent_id,
                "text": sent_info["text"],
                "start": current_time_ms / 1000.0,
                "end": current_time_ms / 1000.0,
            })
            continue

        # Progress indicator
        if (i + 1) % 10 == 0 or i == 0 or i == len(sentences) - 1:
            pct = (i + 1) / len(sentences) * 100
            print(f"     [{pct:5.1f}%] Sentence {i + 1}/{len(sentences)}...", end="\r")

        # Generate audio for this sentence
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            success = await generate_sentence_audio(sent_text, tmp_path)

            if success:
                try:
                    sentence_audio = AudioSegment.from_mp3(tmp_path)
                except Exception as e:
                    print(f"\n    ⚠ Error loading MP3 for sentence {i}: {e}")
                    sentence_audio = AudioSegment.silent(duration=500)
                    failed_count += 1
            else:
                sentence_audio = AudioSegment.silent(duration=500)
                failed_count += 1
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

        # Record timing
        duration_ms = len(sentence_audio)
        start_time = current_time_ms / 1000.0
        end_time = (current_time_ms + duration_ms) / 1000.0

        timing_entries.append({
            "id": sent_id,
            "text": sent_info["text"],
            "start": round(start_time, 3),
            "end": round(end_time, 3),
        })

        # Append sentence audio
        chapter_audio += sentence_audio
        current_time_ms += duration_ms

        # Add appropriate pause
        if sent_info["is_last_in_para"]:
            if sent_info["is_heading_para"]:
                pause_ms = HEADING_PAUSE_MS
            else:
                pause_ms = PARAGRAPH_PAUSE_MS
        else:
            pause_ms = SENTENCE_PAUSE_MS

        chapter_audio += AudioSegment.silent(duration=pause_ms)
        current_time_ms += pause_ms

    total_seconds = len(chapter_audio) / 1000.0
    print(f"     [100.0%] {len(sentences)} sentences, {total_seconds:.1f}s total" + " " * 20)
    if failed_count > 0:
        print(f"     ⚠ {failed_count} sentences used fallback silence")

    return chapter_audio, timing_entries


async def main_async():
    """Async main entry point."""
    import argparse
    parser = argparse.ArgumentParser(description="Regenerate audiobook audio from text.json")
    parser.add_argument("--resume", action="store_true", help="Resume from last completed chapter")
    parser.add_argument("--chapter", type=int, default=None, help="Process only this chapter (0-indexed)")
    parser.add_argument("--start", type=int, default=0, help="Start from this chapter (0-indexed)")
    args = parser.parse_args()

    print("=" * 60)
    print("  Audiobook Audio Regeneration")
    print(f"  Voice: {VOICE}")
    print("  Source: text.json")
    print("=" * 60)
    print()

    # Load text data
    if not TEXT_JSON.exists():
        print(f"❌ text.json not found at {TEXT_JSON}")
        sys.exit(1)

    text_data = load_text_data()
    chapters = text_data.get("chapters", [])
    total_chapters = len(chapters)
    print(f"📚 Found {total_chapters} chapters in text.json")
    print()

    # Create audio directory
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    # Load or initialize progress
    progress = load_progress() if args.resume else {"completed_chapters": [], "timing_chapters": []}

    # Load existing timing data if resuming
    timing_chapters = progress.get("timing_chapters", [None] * total_chapters)
    while len(timing_chapters) < total_chapters:
        timing_chapters.append(None)

    # Determine which chapters to process
    if args.chapter is not None:
        chapters_to_process = [args.chapter]
    else:
        chapters_to_process = list(range(args.start, total_chapters))

    # Process chapters
    overall_start = time.time()
    completed = 0
    skipped = 0

    for ch_idx in chapters_to_process:
        if ch_idx >= total_chapters:
            print(f"⚠ Chapter {ch_idx} doesn't exist (total: {total_chapters})")
            continue

        chapter = chapters[ch_idx]
        ch_id = chapter.get("id", f"ch{ch_idx:02d}")
        audio_num = ch_idx + 1  # Audio files are 1-indexed
        audio_filename = f"ch{audio_num:02d}.mp3"
        audio_path = AUDIO_DIR / audio_filename

        # Skip if already completed (resume mode)
        if args.resume and ch_idx in progress.get("completed_chapters", []):
            print(f"  ⏭ Chapter {ch_idx} ({ch_id}) — already completed, skipping")
            skipped += 1
            continue

        ch_start = time.time()
        print(f"\n{'─' * 60}")
        print(f"  Chapter {ch_idx + 1}/{total_chapters} ({ch_id}) → {audio_filename}")
        print(f"{'─' * 60}")

        # Generate audio with timing
        chapter_audio, timing_entries = await process_chapter_async(chapter, ch_idx, ch_id)

        # Export as MP3
        print(f"     Exporting {audio_filename}...", end=" ")
        chapter_audio.export(
            str(audio_path),
            format="mp3",
            bitrate="192k",
            parameters=["-ar", "24000"]
        )
        file_size_mb = audio_path.stat().st_size / (1024 * 1024)
        print(f"({file_size_mb:.1f} MB)")

        # Store timing data for this chapter
        timing_chapters[ch_idx] = {
            "title": chapter.get("title", f"Chapter {ch_idx + 1}"),
            "audioFile": f"audio/{audio_filename}",
            "entries": timing_entries,
        }

        # Update progress
        if ch_idx not in progress["completed_chapters"]:
            progress["completed_chapters"].append(ch_idx)
        progress["timing_chapters"] = timing_chapters
        save_progress(progress)

        ch_elapsed = time.time() - ch_start
        completed += 1
        print(f"     ⏱ Chapter done in {ch_elapsed:.1f}s")

        # ETAs
        if completed > 0:
            avg_time = (time.time() - overall_start) / completed
            remaining = len(chapters_to_process) - completed - skipped
            eta_minutes = (avg_time * remaining) / 60
            print(f"     📊 ETA: ~{eta_minutes:.0f} min remaining ({remaining} chapters left)")

    # ── Write final timing.json ──────────────────────────────────
    print(f"\n{'═' * 60}")
    print("  Writing timing.json...")

    final_timing = {"chapters": []}
    for ch_idx in range(total_chapters):
        if timing_chapters[ch_idx] is not None:
            final_timing["chapters"].append(timing_chapters[ch_idx])
        else:
            chapter = chapters[ch_idx]
            audio_num = ch_idx + 1
            final_timing["chapters"].append({
                "title": chapter.get("title", f"Chapter {ch_idx + 1}"),
                "audioFile": f"audio/ch{audio_num:02d}.mp3",
                "entries": [],
            })

    with open(TIMING_JSON, "w", encoding="utf-8") as f:
        json.dump(final_timing, f, indent=2, ensure_ascii=False)
    print(f"  ✓ timing.json written ({len(final_timing['chapters'])} chapters)")

    # ── Write updated manifest.json ──────────────────────────────
    print("  Writing manifest.json...")

    manifest_chapters = []
    total_duration = 0
    for ch_idx in range(total_chapters):
        chapter = chapters[ch_idx]
        audio_num = ch_idx + 1
        audio_filename = f"ch{audio_num:02d}.mp3"
        audio_path = AUDIO_DIR / audio_filename

        duration = 0
        sentence_count = 0
        if audio_path.exists():
            try:
                audio = AudioSegment.from_mp3(str(audio_path))
                duration = len(audio) / 1000.0
            except Exception:
                pass

        if timing_chapters[ch_idx] is not None:
            sentence_count = len(timing_chapters[ch_idx].get("entries", []))

        total_duration += duration
        manifest_chapters.append({
            "id": chapter.get("id", f"ch{ch_idx:02d}"),
            "title": chapter.get("title", f"Chapter {ch_idx + 1}"),
            "audioFile": f"audio/{audio_filename}",
            "duration": round(duration, 2),
            "sentenceCount": sentence_count,
        })

    manifest = {
        "version": "2.0",
        "bookId": "the-intelligent-investor",
        "title": "The Intelligent Investor",
        "author": "Benjamin Graham",
        "cover": "../../input/intelligentcover.jpg",
        "timing": "timing.json",
        "text": "text.json",
        "totalDuration": round(total_duration, 2),
        "chapterCount": total_chapters,
        "chapters": manifest_chapters,
        "generated": {
            "tts_engine": "edge-tts",
            "voice": VOICE,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        },
    }

    with open(MANIFEST_JSON, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    print(f"  ✓ manifest.json written (total duration: {total_duration / 60:.1f} min)")

    # ── Summary ──────────────────────────────────────────────────
    total_elapsed = time.time() - overall_start
    print(f"\n{'═' * 60}")
    print(f"  ✅ Audio regeneration complete!")
    print(f"     Chapters processed: {completed}")
    print(f"     Chapters skipped:   {skipped}")
    print(f"     Total time:         {total_elapsed / 60:.1f} minutes")
    print(f"     Total audio:        {total_duration / 60:.1f} minutes")
    print(f"{'═' * 60}")

    # Clean up progress file
    if PROGRESS_FILE.exists():
        PROGRESS_FILE.unlink()
        print("  🧹 Cleaned up progress file")


def main():
    """Entry point — runs the async main."""
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
