"""
TTS Audio Generation Module using pyttsx3 (Fallback)

Simple, reliable TTS that works on all platforms.
Lower quality than Tortoise but requires no special setup.

Install: pip install pyttsx3
"""

import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import List, Optional, Tuple, Generator

import numpy as np

os.environ["OMP_NUM_THREADS"] = "4"

from scripts.utils.config import config
from scripts.utils import logger


class VoiceNotFoundError(Exception):
    """Raised when a requested voice is not available."""
    pass


class TTSGenerationError(Exception):
    """Raised when TTS generation fails."""
    pass


class Pyttsx3TTSGenerator:
    """
    Generate audio from text using pyttsx3.

    This is a fallback TTS engine that uses the system's built-in
    text-to-speech capabilities. It's not as high quality as Tortoise
    but works reliably on all platforms without GPU.

    On Windows: Uses SAPI5 voices
    On macOS: Uses NSSpeechSynthesizer
    On Linux: Uses espeak
    """

    SAMPLE_RATE = 22050  # Standard rate for most system TTS

    def __init__(
        self,
        voice: Optional[str] = None,
        speed: Optional[float] = None,
        preset: str = "fast",  # Ignored for compatibility
        normalize_audio: bool = True,
        target_db: float = -20.0,
    ):
        """
        Initialize the pyttsx3 TTS generator.

        Args:
            voice: Voice ID to use (system-specific)
            speed: Speech speed multiplier (0.5 to 2.0)
            preset: Ignored (for Tortoise compatibility)
            normalize_audio: Whether to normalize audio levels
            target_db: Target dB level for normalization
        """
        self.voice = voice
        self.speed = speed or config.voice_speed
        self.preset = preset  # For compatibility
        self.normalize_audio = normalize_audio
        self.target_db = target_db
        self._engine = None

    def _get_engine(self):
        """Lazy load pyttsx3 engine."""
        if self._engine is None:
            try:
                import pyttsx3
                self._engine = pyttsx3.init()

                # Set voice if specified
                if self.voice:
                    voices = self._engine.getProperty('voices')
                    for v in voices:
                        if self.voice.lower() in v.id.lower() or self.voice.lower() in v.name.lower():
                            self._engine.setProperty('voice', v.id)
                            logger.info(f"Using voice: {v.name}")
                            break

                # Set rate (default is ~200 wpm)
                base_rate = self._engine.getProperty('rate')
                self._engine.setProperty('rate', int(base_rate * self.speed))

                logger.info("pyttsx3 engine initialized")

            except ImportError:
                raise TTSGenerationError(
                    "pyttsx3 not installed. Install with:\n"
                    "  pip install pyttsx3"
                )
            except Exception as e:
                raise TTSGenerationError(f"Failed to initialize pyttsx3: {e}")

        return self._engine

    def generate_audio(
        self,
        text: str,
        output_path: Path,
        show_progress: bool = True,
        add_trailing_silence: float = 0.5,
        max_retries: int = 3,
    ) -> Tuple[Path, float]:
        """
        Generate audio for a text string.

        Args:
            text: Text to convert to speech
            output_path: Path for output audio file
            show_progress: Whether to show progress indicator
            add_trailing_silence: Seconds of silence to add at end
            max_retries: Number of retry attempts on failure

        Returns:
            Tuple of (path to generated audio file, duration in seconds)
        """
        output_path = Path(output_path).with_suffix(".wav")
        output_path.parent.mkdir(parents=True, exist_ok=True)

        text = text.strip()
        if not text:
            raise TTSGenerationError("Cannot generate audio from empty text")

        engine = self._get_engine()
        last_error = None

        for attempt in range(max_retries):
            try:
                if show_progress:
                    logger.info(f"Generating audio (pyttsx3 fallback)")

                # Save to file
                engine.save_to_file(text, str(output_path))
                engine.runAndWait()

                # Get duration
                import wave
                with wave.open(str(output_path), 'rb') as wf:
                    frames = wf.getnframes()
                    rate = wf.getframerate()
                    duration = frames / float(rate)

                if show_progress:
                    logger.success(f"Generated: {output_path.name} ({duration:.1f}s)")

                return output_path, duration

            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.warning(f"Attempt {attempt + 1} failed, retrying in {wait_time}s: {e}")
                    time.sleep(wait_time)
                else:
                    logger.error(f"All {max_retries} attempts failed")

        raise TTSGenerationError(f"TTS generation failed: {last_error}")

    def generate_chapter_audio(
        self,
        chapter: dict,
        output_dir: Path,
        chapter_num: int,
        total_chapters: int = 0,
    ) -> Tuple[Path, float]:
        """Generate audio for a single chapter."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        filename = f"chapter_{chapter_num:03d}.wav"
        output_path = output_dir / filename

        progress_str = f"[{chapter_num}/{total_chapters}] " if total_chapters else ""
        logger.step(f"{progress_str}Chapter: {chapter['title'][:60]}")

        return self.generate_audio(chapter["text"], output_path, show_progress=False)

    @classmethod
    def list_voices(cls, voices_dir: Optional[Path] = None) -> dict:
        """Return all available system voices."""
        voices = {}

        try:
            import pyttsx3
            engine = pyttsx3.init()

            for v in engine.getProperty('voices'):
                voices[v.id] = {
                    "type": "system",
                    "description": v.name
                }

            engine.stop()

        except Exception as e:
            logger.warning(f"Could not list voices: {e}")

        return voices


# Compatibility aliases
TTSGenerator = Pyttsx3TTSGenerator


def generate_from_text(
    text: str,
    output_path: Path,
    voice: Optional[str] = None,
    speed: Optional[float] = None,
    preset: str = "fast",
    use_chunking: bool = True,
    chunk_threshold: int = 5000,
) -> Tuple[Path, float]:
    """
    Generate audio from text using pyttsx3.

    Args:
        text: Text to convert to audio
        output_path: Output file path
        voice: Voice ID to use
        speed: Speech speed multiplier
        preset: Ignored (for Tortoise compatibility)
        use_chunking: Whether to split long texts
        chunk_threshold: Character count for chunking

    Returns:
        Tuple of (path to audio file, duration in seconds)
    """
    generator = Pyttsx3TTSGenerator(voice=voice, speed=speed, preset=preset)
    return generator.generate_audio(text, output_path)


def generate_from_file(
    input_path: Path,
    output_path: Path,
    voice: Optional[str] = None,
    speed: Optional[float] = None,
    preset: str = "fast",
) -> Tuple[Path, float]:
    """Generate audio from a text file."""
    input_path = Path(input_path)

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    text = input_path.read_text(encoding="utf-8")
    return generate_from_text(text, output_path, voice=voice, speed=speed, preset=preset)


if __name__ == "__main__":
    print("pyttsx3 TTS Generator (Fallback)")
    print("=" * 50)
    print()
    print("This is a fallback TTS engine using system voices.")
    print("It's simpler than Tortoise but works on all platforms.")
    print()
    print("Install: pip install pyttsx3")
    print()
    print("Available voices:")

    try:
        voices = Pyttsx3TTSGenerator.list_voices()
        for voice_id, info in list(voices.items())[:10]:
            print(f"  - {info['description']}")
        if len(voices) > 10:
            print(f"  ... and {len(voices) - 10} more")
    except Exception as e:
        print(f"  (Could not list voices: {e})")
