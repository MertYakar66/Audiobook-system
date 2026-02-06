"""
Timed TTS Generator

Generates audio with precise timing information for each sentence.
Captures start/end timestamps for Read-Along synchronization.

Now uses Tortoise TTS for high-quality, natural speech.
Legacy Kokoro support available via timed_tts_kokoro.py
"""

# Re-export from Tortoise implementation for backwards compatibility
from scripts.readalong.timed_tts_tortoise import (
    TimedTortoiseTTSGenerator as TimedTTSGenerator,
    TimedSegment,
    generate_with_timing,
)

# For direct Tortoise access
from scripts.readalong.timed_tts_tortoise import TimedTortoiseTTSGenerator

__all__ = [
    "TimedTTSGenerator",
    "TimedTortoiseTTSGenerator",
    "TimedSegment",
    "generate_with_timing",
]


if __name__ == "__main__":
    # Test the timed TTS generator
    test_text = """
    The Intelligent Investor teaches that successful investing requires
    patience and discipline. Mr. Market is an emotional character who
    offers you prices every day.

    Sometimes Mr. Market is euphoric and offers high prices. Other times
    he is depressed and offers bargains. The intelligent investor takes
    advantage of Mr. Market's mood swings!
    """

    from pathlib import Path
    output_path = Path("test_timed.wav")

    print("Testing Tortoise Timed TTS Generator...")
    path, segments = generate_with_timing(test_text, output_path)

    print(f"\nGenerated: {path}")
    print(f"Segments: {len(segments)}")
    for seg in segments:
        print(f"  [{seg.start_time:.2f}-{seg.end_time:.2f}] {seg.text[:50]}...")
