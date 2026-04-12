#!/usr/bin/env python3
"""
Generates silent MP3 files matching each chapter's duration from timing.json.

Required for automated browser tests that verify audio playback, seeking,
speed control, and text-sync behavior. The audio/ subdirectory is missing
in dev containers, so we create placeholder silence of the correct length.
"""

import json
import os
import sys
from pathlib import Path

import lameenc

ROOT = Path(__file__).resolve().parents[2]
BOOK_DIR = ROOT / "output" / "readalong" / "The_Intelligent_Investor"
AUDIO_DIR = BOOK_DIR / "audio"
SAMPLE_RATE = 44100
CHANNELS = 1
BITRATE = 64


def encode_silent_mp3(duration_seconds: float) -> bytes:
    """Encode a mono silent MP3 of the given duration."""
    encoder = lameenc.Encoder()
    encoder.set_bit_rate(BITRATE)
    encoder.set_in_sample_rate(SAMPLE_RATE)
    encoder.set_channels(CHANNELS)
    encoder.set_quality(7)  # 2=best, 7=fast
    encoder.silence()

    total_samples = int(duration_seconds * SAMPLE_RATE)
    # Feed silence in chunks (16-bit PCM)
    chunk_samples = SAMPLE_RATE  # 1s chunks
    silence_chunk = b"\x00\x00" * chunk_samples

    parts = []
    remaining = total_samples
    while remaining > 0:
        n = min(chunk_samples, remaining)
        if n == chunk_samples:
            parts.append(encoder.encode(silence_chunk))
        else:
            parts.append(encoder.encode(b"\x00\x00" * n))
        remaining -= n
    parts.append(encoder.flush())
    return b"".join(parts)


def main() -> int:
    if not BOOK_DIR.exists():
        print(f"ERROR: {BOOK_DIR} not found", file=sys.stderr)
        return 1

    manifest = json.loads((BOOK_DIR / "manifest.json").read_text())
    AUDIO_DIR.mkdir(exist_ok=True)

    chapters = manifest["chapters"]
    print(f"Generating {len(chapters)} silent MP3s in {AUDIO_DIR}")

    for ch in chapters:
        audio_rel = ch["audioFile"]  # e.g. "audio/ch01.mp3"
        duration = float(ch["duration"])
        out_path = BOOK_DIR / audio_rel
        if out_path.exists() and out_path.stat().st_size > 0:
            print(f"  skip {audio_rel} (exists, {out_path.stat().st_size} bytes)")
            continue

        data = encode_silent_mp3(duration)
        out_path.write_bytes(data)
        print(f"  wrote {audio_rel}: {duration:.1f}s -> {len(data)} bytes")

    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
