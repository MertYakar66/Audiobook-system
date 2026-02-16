"""
Timed TTS Generator

Generates audio with precise timing information for each sentence.
Captures start/end timestamps for Read-Along synchronization.

Uses Edge TTS (fast, high-quality neural voices, no GPU needed).
"""

import os

# Track which TTS engine is being used
_tts_engine = None
_tts_error = None


def _try_edge_tts():
    """Try to load edge-tts."""
    global _tts_engine, _tts_error
    try:
        from scripts.readalong.timed_tts_edge import (
            TimedEdgeTTSGenerator as TimedTTSGenerator,
            TimedSegment,
            generate_with_timing,
        )
        from scripts.readalong.timed_tts_edge import TimedEdgeTTSGenerator
        _tts_engine = "edge"
        return TimedTTSGenerator, TimedEdgeTTSGenerator, TimedSegment, generate_with_timing
    except ImportError as e:
        _tts_error = str(e)
        return None


def _try_pyttsx3():
    """Try to load pyttsx3 fallback."""
    global _tts_engine, _tts_error
    try:
        from scripts.readalong.timed_tts_pyttsx3 import (
            TimedPyttsx3TTSGenerator as TimedTTSGenerator,
            TimedSegment,
            generate_with_timing,
        )
        from scripts.readalong.timed_tts_pyttsx3 import TimedPyttsx3TTSGenerator
        _tts_engine = "pyttsx3"
        return TimedTTSGenerator, TimedPyttsx3TTSGenerator, TimedSegment, generate_with_timing
    except ImportError as e:
        _tts_error = f"pyttsx3: {e}"
        return None


# Load TTS engine: Edge TTS first, then pyttsx3 fallback
_loaded = _try_edge_tts()
if not _loaded:
    import warnings
    warnings.warn(
        f"Edge TTS not available ({_tts_error}), trying pyttsx3 fallback...",
        UserWarning
    )
    _loaded = _try_pyttsx3()

# Set up exports
if _loaded:
    TimedTTSGenerator, _TimedEngineGenerator, TimedSegment, generate_with_timing = _loaded
else:
    # No TTS available
    from dataclasses import dataclass
    from typing import Optional
    import numpy as np

    @dataclass
    class TimedSegment:
        """Audio segment with timing information."""
        sentence_id: str
        text: str
        start_time: float
        end_time: float
        audio_data: Optional[np.ndarray] = None

        @property
        def duration(self) -> float:
            return self.end_time - self.start_time

    class TTSNotAvailableError(Exception):
        pass

    def generate_with_timing(*args, **kwargs):
        raise TTSNotAvailableError(
            "No TTS engine available!\n"
            "Please install one of:\n"
            "  1. edge-tts (recommended): pip install edge-tts\n"
            "  2. pyttsx3 (fallback): pip install pyttsx3\n"
            f"\nOriginal errors: {_tts_error}"
        )

    class TimedTTSGenerator:
        def __init__(self, *args, **kwargs):
            raise TTSNotAvailableError("No TTS engine available")

    _tts_engine = None


def get_tts_engine():
    """Return the name of the currently active TTS engine."""
    return _tts_engine


def is_edge_available():
    """Check if Edge TTS is available."""
    return _tts_engine == "edge"


def is_pyttsx3_available():
    """Check if pyttsx3 fallback is active."""
    return _tts_engine == "pyttsx3"


__all__ = [
    "TimedTTSGenerator",
    "TimedSegment",
    "generate_with_timing",
    "get_tts_engine",
    "is_edge_available",
    "is_pyttsx3_available",
]


if __name__ == "__main__":
    print("Timed TTS Generator")
    print("=" * 50)
    print()
    print(f"Active TTS engine: {_tts_engine or 'NONE'}")

    if _tts_engine == "edge":
        print()
        print("Using Edge TTS (fast, neural voices)")

    elif _tts_engine == "pyttsx3":
        print()
        print("Using pyttsx3 fallback (system TTS)")
        print()
        print("For better quality, install edge-tts:")
        print("  pip install edge-tts")

    else:
        print()
        print("ERROR: No TTS engine available!")
        print()
        print("Please install one of:")
        print("  1. Edge TTS (recommended, fast):")
        print("     pip install edge-tts")
        print()
        print("  2. pyttsx3 (fallback, lower quality):")
        print("     pip install pyttsx3")
        print()
        if _tts_error:
            print(f"Original error: {_tts_error}")

    # Test generation
    if _tts_engine:
        print()
        print("-" * 50)
        print("Testing TTS generation...")

        test_text = """
        The Intelligent Investor teaches that successful investing requires
        patience and discipline.
        """

        from pathlib import Path
        output_path = Path("test_timed.wav")

        try:
            path, segments = generate_with_timing(test_text, output_path)
            print(f"Generated: {path}")
            print(f"Segments: {len(segments)}")
            for seg in segments:
                print(f"  [{seg.start_time:.2f}-{seg.end_time:.2f}] {seg.text[:40]}...")
        except Exception as e:
            print(f"Test failed: {e}")
