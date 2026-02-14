#!/usr/bin/env python3
"""
Convert WAV audio files to MP3 for faster web loading.

WAV files are ~10x larger than MP3. This script converts all chapter
audio files from WAV to MP3 while preserving the originals.

Usage: python scripts/convert_to_mp3.py [book-folder]
Example: python scripts/convert_to_mp3.py output/readalong/The-Intelligent-Investor

Requires: ffmpeg (install via 'winget install ffmpeg' or download from ffmpeg.org)
"""

import os
import sys
import json
import subprocess
import shutil
from pathlib import Path


def find_ffmpeg():
    """Find ffmpeg executable."""
    if shutil.which("ffmpeg"):
        return "ffmpeg"
    # Check common Windows locations
    common_paths = [
        r"C:\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
        os.path.expanduser(r"~\scoop\apps\ffmpeg\current\bin\ffmpeg.exe"),
    ]
    for p in common_paths:
        if os.path.isfile(p):
            return p
    return None


def convert_wav_to_mp3(wav_path, mp3_path, bitrate="64k"):
    """Convert a single WAV file to MP3."""
    cmd = [
        find_ffmpeg(), "-y", "-i", str(wav_path),
        "-codec:a", "libmp3lame",
        "-b:a", bitrate,
        "-ac", "1",  # mono for audiobooks
        str(mp3_path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0


def main():
    # Determine book folder
    if len(sys.argv) > 1:
        book_folder = Path(sys.argv[1])
    else:
        # Auto-detect from output/readalong/
        readalong_dir = Path("output/readalong")
        if not readalong_dir.exists():
            print("No output/readalong/ directory found.")
            print("Usage: python scripts/convert_to_mp3.py <book-folder>")
            sys.exit(1)

        books = [d for d in readalong_dir.iterdir() if d.is_dir()]
        if not books:
            print("No books found in output/readalong/")
            sys.exit(1)

        for i, book in enumerate(books):
            print(f"  [{i+1}] {book.name}")

        if len(books) == 1:
            book_folder = books[0]
        else:
            choice = input("Select book number: ").strip()
            book_folder = books[int(choice) - 1]

    audio_dir = book_folder / "audio"
    if not audio_dir.exists():
        print(f"No audio/ directory found in {book_folder}")
        sys.exit(1)

    # Check ffmpeg
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        print("ffmpeg not found. Install it:")
        print("  Windows: winget install ffmpeg")
        print("  Mac: brew install ffmpeg")
        print("  Linux: sudo apt install ffmpeg")
        sys.exit(1)

    # Find all WAV files
    wav_files = sorted(audio_dir.glob("*.wav"))
    if not wav_files:
        print("No WAV files found in", audio_dir)
        sys.exit(1)

    print(f"Converting {len(wav_files)} WAV files to MP3...")
    print(f"Book: {book_folder.name}")
    print()

    total_wav_size = 0
    total_mp3_size = 0
    converted = 0

    for wav_path in wav_files:
        mp3_path = wav_path.with_suffix(".mp3")
        wav_size = wav_path.stat().st_size
        total_wav_size += wav_size

        print(f"  [{converted+1}/{len(wav_files)}] {wav_path.name} ({wav_size / 1024 / 1024:.1f} MB)...", end=" ", flush=True)

        if convert_wav_to_mp3(wav_path, mp3_path):
            mp3_size = mp3_path.stat().st_size
            total_mp3_size += mp3_size
            ratio = mp3_size / wav_size * 100
            print(f"-> {mp3_size / 1024 / 1024:.1f} MB ({ratio:.0f}%)")
            converted += 1
        else:
            print("FAILED")

    print()
    print(f"Done! Converted {converted}/{len(wav_files)} files.")
    print(f"WAV total: {total_wav_size / 1024 / 1024:.0f} MB")
    print(f"MP3 total: {total_mp3_size / 1024 / 1024:.0f} MB")
    print(f"Space saved: {(total_wav_size - total_mp3_size) / 1024 / 1024:.0f} MB ({(1 - total_mp3_size / total_wav_size) * 100:.0f}%)")

    # Update timing.json to reference MP3 files
    timing_path = book_folder / "timing.json"
    if timing_path.exists():
        print("\nUpdating timing.json references...")
        with open(timing_path, "r", encoding="utf-8") as f:
            timing = json.load(f)

        for chapter in timing.get("chapters", []):
            if "audioFile" in chapter:
                chapter["audioFile"] = chapter["audioFile"].replace(".wav", ".mp3")

        with open(timing_path, "w", encoding="utf-8") as f:
            json.dump(timing, f, indent=2, ensure_ascii=False)
        print("timing.json updated.")

    print("\nYou can now delete the WAV files to save space:")
    print(f'  del "{audio_dir}\\*.wav"  (Windows)')
    print(f"  rm {audio_dir}/*.wav     (Mac/Linux)")


if __name__ == "__main__":
    main()
