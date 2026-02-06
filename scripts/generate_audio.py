"""
TTS Audio Generation Module

This module provides the TTS generation interface.
Now uses Tortoise TTS for high-quality, natural speech with voice cloning.

Tortoise TTS Features:
- Voice cloning from reference audio samples
- Multiple built-in voices (train_dotrice, emma, freeman, etc.)
- Quality presets (ultra_fast, fast, standard, high_quality)
- More natural and expressive speech than Kokoro

For voice cloning:
1. Create folder: voices/<voice_name>/
2. Add 3-10 WAV files (6-10 seconds each) of the target voice
3. Use voice name in config or CLI: --voice my_voice

Legacy Kokoro support is available via generate_audio_kokoro.py
"""

# Re-export from Tortoise implementation for backwards compatibility
from scripts.generate_audio_tortoise import (
    TortoiseTTSGenerator as TTSGenerator,
    ChunkedTortoiseTTSGenerator as ChunkedTTSGenerator,
    VoiceNotFoundError,
    TTSGenerationError,
    generate_from_text,
    generate_from_file,
)

# For direct Tortoise access
from scripts.generate_audio_tortoise import (
    TortoiseTTSGenerator,
    ChunkedTortoiseTTSGenerator,
)

__all__ = [
    "TTSGenerator",
    "ChunkedTTSGenerator",
    "TortoiseTTSGenerator",
    "ChunkedTortoiseTTSGenerator",
    "VoiceNotFoundError",
    "TTSGenerationError",
    "generate_from_text",
    "generate_from_file",
]


if __name__ == "__main__":
    # Show help when run directly
    print("Tortoise TTS Audio Generator")
    print("=" * 50)
    print()
    print("This module now uses Tortoise TTS for audio generation.")
    print()
    print("Available voices:")
    voices = TortoiseTTSGenerator.list_voices()
    for voice in list(voices.keys())[:15]:
        print(f"  - {voice}")
    print("  ... and more")
    print()
    print("Quality presets:")
    for preset, params in TortoiseTTSGenerator.PRESETS.items():
        print(f"  - {preset}")
    print()
    print("Voice cloning:")
    print("  1. Create folder: voices/<voice_name>/")
    print("  2. Add 3-10 WAV files (6-10 seconds each)")
    print("  3. Use: --voice <voice_name>")
