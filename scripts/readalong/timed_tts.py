"""
Timed TTS Generator

Generates audio with precise timing information for each sentence.
Captures start/end timestamps for Read-Along synchronization.

TTS Engine Priority:
1. edge-tts (fast, high-quality neural voices, no GPU needed) - DEFAULT
2. Tortoise TTS (highest quality, but very slow, requires GPU)
3. pyttsx3 (system TTS fallback, lower quality)

Set TTS_ENGINE environment variable to override:
  TTS_ENGINE=edge      # Use Edge TTS (default)
  TTS_ENGINE=tortoise  # Use Tortoise TTS (slow but highest quality)
  TTS_ENGINE=pyttsx3   # Use system TTS
"""

import os
import warnings

# Track which TTS engine is being used
_tts_engine = None
_tts_error = None

# Check user preference
_preferred_engine = os.environ.get("TTS_ENGINE", "edge").lower()

# Check if CUDA is explicitly disabled (CPU mode requested)
_cuda_env = os.environ.get("CUDA_VISIBLE_DEVICES")
_cuda_disabled = _cuda_env == "-1"  # Only disabled if explicitly set to -1
_force_cpu = os.environ.get("FORCE_CPU_TTS", "").lower() in ["1", "true", "yes"]

# Check if torch and CUDA are available
_torch_available = False
_cuda_available = False
try:
    import torch
    _torch_available = True
    _cuda_available = torch.cuda.is_available() and not _cuda_disabled
except ImportError:
    pass


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


def _try_tortoise_tts():
    """Try to load Tortoise TTS (requires GPU)."""
    global _tts_engine, _tts_error
    if not _torch_available:
        _tts_error = "torch not available"
        return None
    if not _cuda_available or _force_cpu:
        _tts_error = "GPU not available - Tortoise requires GPU"
        return None
    try:
        from scripts.readalong.timed_tts_tortoise import (
            TimedTortoiseTTSGenerator as TimedTTSGenerator,
            TimedSegment,
            generate_with_timing,
        )
        from scripts.readalong.timed_tts_tortoise import TimedTortoiseTTSGenerator
        _tts_engine = "tortoise"
        return TimedTTSGenerator, TimedTortoiseTTSGenerator, TimedSegment, generate_with_timing
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


# Load TTS engine based on preference
_loaded = None

if _preferred_engine == "tortoise":
    # User explicitly wants Tortoise
    _loaded = _try_tortoise_tts()
    if not _loaded:
        warnings.warn(
            f"Tortoise TTS not available ({_tts_error}), trying edge-tts...",
            UserWarning
        )
        _loaded = _try_edge_tts()

elif _preferred_engine == "pyttsx3":
    # User explicitly wants pyttsx3
    _loaded = _try_pyttsx3()

else:
    # Default: try edge-tts first (fast and good quality)
    _loaded = _try_edge_tts()
    if not _loaded:
        warnings.warn(
            f"Edge TTS not available ({_tts_error}), trying Tortoise...",
            UserWarning
        )
        _loaded = _try_tortoise_tts()

# Fallback to pyttsx3 if nothing else worked
if not _loaded:
    _loaded = _try_pyttsx3()

# Set up exports
if _loaded:
    TimedTTSGenerator, TimedTortoiseTTSGenerator, TimedSegment, generate_with_timing = _loaded
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
            "  2. Tortoise TTS: pip install tortoise-tts\n"
            "  3. pyttsx3 (fallback): pip install pyttsx3\n"
            f"\nOriginal errors: {_tts_error}"
        )

    class TimedTTSGenerator:
        def __init__(self, *args, **kwargs):
            raise TTSNotAvailableError("No TTS engine available")

    TimedTortoiseTTSGenerator = TimedTTSGenerator

    _tts_engine = None


def get_tts_engine():
    """Return the name of the currently active TTS engine."""
    return _tts_engine


def is_edge_available():
    """Check if Edge TTS is available."""
    return _tts_engine == "edge"


def is_tortoise_available():
    """Check if Tortoise TTS is available."""
    return _tts_engine == "tortoise"


def is_pyttsx3_available():
    """Check if pyttsx3 fallback is active."""
    return _tts_engine == "pyttsx3"


__all__ = [
    "TimedTTSGenerator",
    "TimedTortoiseTTSGenerator",
    "TimedSegment",
    "generate_with_timing",
    "get_tts_engine",
    "is_edge_available",
    "is_tortoise_available",
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
        print("To use Tortoise instead: set TTS_ENGINE=tortoise")

    elif _tts_engine == "tortoise":
        print()
        print("Using Tortoise TTS (high quality, slow)")
        print("To use Edge TTS instead: set TTS_ENGINE=edge")

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
        print("  2. Tortoise TTS (high quality, slow):")
        print("     pip install tortoise-tts")
        print()
        print("  3. pyttsx3 (fallback, lower quality):")
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
