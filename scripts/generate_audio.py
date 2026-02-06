"""
TTS Audio Generation Module

This module provides the TTS generation interface.
Uses Tortoise TTS for high-quality, natural speech with voice cloning.
Falls back to pyttsx3 (system TTS) if Tortoise is not available.

Tortoise TTS Features:
- Voice cloning from reference audio samples
- Multiple built-in voices (train_dotrice, emma, freeman, etc.)
- Quality presets (ultra_fast, fast, standard, high_quality)
- More natural and expressive speech

For voice cloning:
1. Create folder: voices/<voice_name>/
2. Add 3-10 WAV files (6-10 seconds each) of the target voice
3. Use voice name in config or CLI: --voice my_voice
"""

import sys

# Track which TTS engine is being used
_tts_engine = None
_tts_error = None

# Try to import Tortoise TTS first
try:
    from scripts.generate_audio_tortoise import (
        TortoiseTTSGenerator as TTSGenerator,
        ChunkedTortoiseTTSGenerator as ChunkedTTSGenerator,
        VoiceNotFoundError,
        TTSGenerationError,
        generate_from_text,
        generate_from_file,
    )
    from scripts.generate_audio_tortoise import (
        TortoiseTTSGenerator,
        ChunkedTortoiseTTSGenerator,
    )
    _tts_engine = "tortoise"

except ImportError as e:
    _tts_error = str(e)
    # Fall back to pyttsx3
    try:
        from scripts.generate_audio_pyttsx3 import (
            Pyttsx3TTSGenerator as TTSGenerator,
            VoiceNotFoundError,
            TTSGenerationError,
            generate_from_text,
            generate_from_file,
        )
        from scripts.generate_audio_pyttsx3 import Pyttsx3TTSGenerator

        # Alias for compatibility
        TortoiseTTSGenerator = Pyttsx3TTSGenerator
        ChunkedTTSGenerator = Pyttsx3TTSGenerator
        ChunkedTortoiseTTSGenerator = Pyttsx3TTSGenerator

        _tts_engine = "pyttsx3"

        import warnings
        warnings.warn(
            f"Tortoise TTS not available ({_tts_error}), using pyttsx3 fallback. "
            "Quality will be lower. Run 'python -m scripts.diagnose_tts' for help.",
            UserWarning
        )

    except ImportError:
        # Neither TTS is available
        class TTSGenerationError(Exception):
            pass

        class VoiceNotFoundError(Exception):
            pass

        def generate_from_text(*args, **kwargs):
            raise TTSGenerationError(
                "No TTS engine available!\n"
                "Please install one of:\n"
                "  1. Tortoise TTS: pip install tortoise-tts\n"
                "  2. pyttsx3 (fallback): pip install pyttsx3\n"
                f"\nOriginal error: {_tts_error}"
            )

        def generate_from_file(*args, **kwargs):
            raise TTSGenerationError("No TTS engine available")

        class TTSGenerator:
            def __init__(self, *args, **kwargs):
                raise TTSGenerationError("No TTS engine available")

        TortoiseTTSGenerator = TTSGenerator
        ChunkedTTSGenerator = TTSGenerator
        ChunkedTortoiseTTSGenerator = TTSGenerator

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
    "TTSGenerator",
    "ChunkedTTSGenerator",
    "TortoiseTTSGenerator",
    "ChunkedTortoiseTTSGenerator",
    "VoiceNotFoundError",
    "TTSGenerationError",
    "generate_from_text",
    "generate_from_file",
    "get_tts_engine",
    "is_tortoise_available",
    "is_pyttsx3_available",
]


if __name__ == "__main__":
    print("TTS Audio Generator")
    print("=" * 50)
    print()
    print(f"Active TTS engine: {_tts_engine or 'NONE'}")

    if _tts_engine == "tortoise":
        print()
        print("Using Tortoise TTS (high quality)")
        print()
        print("Available voices:")
        voices = TortoiseTTSGenerator.list_voices()
        for voice in list(voices.keys())[:15]:
            print(f"  - {voice}")
        print("  ... and more")
        print()
        print("Quality presets:")
        for preset in ["ultra_fast", "fast", "standard", "high_quality"]:
            print(f"  - {preset}")
        print()
        print("Voice cloning:")
        print("  1. Create folder: voices/<voice_name>/")
        print("  2. Add 3-10 WAV files (6-10 seconds each)")
        print("  3. Use: --voice <voice_name>")

    elif _tts_engine == "pyttsx3":
        print()
        print("Using pyttsx3 fallback (system TTS)")
        print(f"Tortoise not available: {_tts_error}")
        print()
        print("For higher quality, install Tortoise TTS:")
        print("  .\\install_tortoise.ps1  (Windows)")
        print("  ./install_tortoise.sh   (Linux/Mac)")
        print()
        print("Or run diagnostics:")
        print("  python -m scripts.diagnose_tts")
        print()
        print("Available system voices:")
        try:
            voices = TTSGenerator.list_voices()
            for voice_id, info in list(voices.items())[:10]:
                print(f"  - {info['description']}")
            if len(voices) > 10:
                print(f"  ... and {len(voices) - 10} more")
        except Exception as e:
            print(f"  (Could not list voices: {e})")

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
