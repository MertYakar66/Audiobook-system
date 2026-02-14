#!/usr/bin/env python3
"""
Export partial book from processing_state.json to website format.

Creates timing.json and text.json from completed chapters.
"""

import json
import sys
from pathlib import Path


def export_partial_book(book_dir):
    """Export completed chapters to website format."""
    book_dir = Path(book_dir)
    state_file = book_dir / "processing_state.json"

    if not state_file.exists():
        print(f"Error: {state_file} not found")
        return False

    # Load processing state
    with open(state_file, "r", encoding="utf-8") as f:
        state = json.load(f)

    # Extract chapter data
    chapters = []
    text_chapters = []
    total_duration = 0

    for ch_num in sorted(state["completed_chapters"]):
        ch_key = str(ch_num)
        ch_data = state["chapter_data"][ch_key]

        # Get chapter title from first sentence
        ch_title = f"Chapter {ch_num}"
        if ch_data["timing_entries"]:
            ch_title = ch_data["timing_entries"][0]["text"][:50]

        # Timing data
        chapters.append({
            "chapterId": f"ch{ch_num:02d}",
            "title": ch_title,
            "audioFile": f"audio/ch{ch_num:02d}.mp3",  # Use MP3
            "duration": round(ch_data["duration"], 3),
            "entries": [
                {
                    "id": entry["id"],
                    "start": round(entry["start"], 3),
                    "end": round(entry["end"], 3),
                    "text": entry["text"],
                    "paragraph": 0
                }
                for entry in ch_data["timing_entries"]
            ]
        })

        # Text data (for search and display)
        text_chapters.append({
            "title": ch_title,
            "paragraphs": [
                {
                    "sentences": [
                        {
                            "id": entry["id"],
                            "text": entry["text"]
                        }
                        for entry in ch_data["timing_entries"]
                    ]
                }
            ]
        })

        total_duration += ch_data["duration"]

    # Create timing.json
    timing_data = {
        "version": "1.0",
        "bookId": state["book_id"],
        "title": state["title"],
        "author": state["author"],
        "totalDuration": round(total_duration, 3),
        "chapterCount": len(chapters),
        "chapters": chapters
    }

    timing_path = book_dir / "timing.json"
    with open(timing_path, "w", encoding="utf-8") as f:
        json.dump(timing_data, f, indent=2, ensure_ascii=False)
    print(f"✓ Created {timing_path}")

    # Create text.json
    text_data = {
        "title": state["title"],
        "author": state["author"],
        "chapters": text_chapters
    }

    text_path = book_dir / "text.json"
    with open(text_path, "w", encoding="utf-8") as f:
        json.dump(text_data, f, indent=2, ensure_ascii=False)
    print(f"✓ Created {text_path}")

    # Create simple manifest.json for library
    manifest = {
        "id": state["book_id"],
        "title": state["title"],
        "author": state["author"],
        "timing": "timing.json",
        "text": "text.json",
        "totalDuration": round(total_duration, 3),
        "chapterCount": len(chapters)
    }

    manifest_path = book_dir / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    print(f"✓ Created {manifest_path}")

    print(f"\n✓ Exported {len(chapters)} chapters ({total_duration:.1f}s)")
    print(f"Book ready at: {book_dir}")
    return True


if __name__ == "__main__":
    if len(sys.argv) > 1:
        book_dir = sys.argv[1]
    else:
        print("Usage: python export_partial_book.py <book-directory>")
        sys.exit(1)

    if not export_partial_book(book_dir):
        sys.exit(1)
