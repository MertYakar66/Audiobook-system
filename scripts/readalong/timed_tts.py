"""
Timed TTS Generator

Generates audio with precise timing information for each sentence.
Captures start/end timestamps for Read-Along synchronization.

Uses Tortoise TTS for high-quality, natural speech (requires GPU).
Falls back to pyttsx3 (system TTS) if Tortoise is not available or GPU unavailable.
"""

import os
import warnings

# Track which TTS engine is being used
_tts_engine = None
_tts_error = None

# Check if CUDA is explicitly disabled (CPU mode requested)
_cuda_disabled = os.environ.get("CUDA_VISIBLE_DEVICES", "") in ["-1", ""]
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

# Use pyttsx3 for CPU mode (Tortoise on CPU is too slow and can crash)
# Only use Tortoise if GPU is available
try:
    if not _torch_available:
        raise ImportError("torch not available")
    if not _cuda_available or _force_cpu:
        raise ImportError("GPU not available - using pyttsx3 for CPU mode")
    from scripts.readalong.timed_tts_tortoise import (
        TimedTortoiseTTSGenerator as TimedTTSGenerator,
        TimedSegment,
        generate_with_timing,
    )
    from scripts.readalong.timed_tts_tortoise import TimedTortoiseTTSGenerator
    _tts_engine = "tortoise"

except ImportError as e:
    _tts_error = str(e)
    # Fall back to pyttsx3
    try:
        from scripts.readalong.timed_tts_pyttsx3 import (
            TimedPyttsx3TTSGenerator as TimedTTSGenerator,
            TimedSegment,
            generate_with_timing,
        )
        from scripts.readalong.timed_tts_pyttsx3 import TimedPyttsx3TTSGenerator

        # Alias for compatibility
        TimedTortoiseTTSGenerator = TimedPyttsx3TTSGenerator

        _tts_engine = "pyttsx3"

        warnings.warn(
            f"Tortoise TTS not available ({_tts_error}), using pyttsx3 fallback. "
            "Quality will be lower. Run 'python -m scripts.diagnose_tts' for help.",
            UserWarning
        )

    except ImportError as e2:
        # Neither TTS is available
        _tts_error = f"Tortoise: {_tts_error}, pyttsx3: {e2}"

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
                "  1. Tortoise TTS: pip install tortoise-tts\n"
                "  2. pyttsx3 (fallback): pip install pyttsx3\n"
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
    "is_tortoise_available",
    "is_pyttsx3_available",
]


if __name__ == "__main__":
    print("Timed TTS Generator")
    print("=" * 50)
    print()
    print(f"Active TTS engine: {_tts_engine or 'NONE'}")

    if _tts_engine == "tortoise":
        print()
        print("Using Tortoise TTS (high quality)")

    elif _tts_engine == "pyttsx3":
        print()
        print("Using pyttsx3 fallback (system TTS)")
        print(f"Tortoise not available: {_tts_error}")
        print()
        print("For higher quality, install Tortoise TTS:")
        print("  .\\install_tortoise.ps1  (Windows)")
        print("  ./install_tortoise.sh   (Linux/Mac)")

    else:
        print()
        print("ERROR: No TTS engine available!")
        print()
        print("Please install one of:")
        print("  1. Tortoise TTS (high quality):")
        print("     .\\install_tortoise.ps1  (Windows)")
        print("     ./install_tortoise.sh   (Linux/Mac)")
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
