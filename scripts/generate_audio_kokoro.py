"""
TTS Audio Generation Module

Generates audio from text using Kokoro-82M TTS model directly.
Professional-grade implementation with:
- Robust error handling and retry logic
- Progress tracking with Rich progress bars
- Audio normalization for consistent volume
- Memory-efficient chunked processing
- Voice validation and quality controls
"""

# =============================================================================
# CRITICAL: Thread constraints for Windows stability
# Must be set BEFORE any PyTorch/NumPy/MKL imports to prevent system freezes
# during long AVX-heavy TTS workloads. Force assignment (not setdefault) to
# override any pre-existing values from Conda, IDE, or system environment.
# =============================================================================
import os

# Force thread counts to prevent thread oversubscription
# 8 threads = physical core count for Ryzen 7 9800X3D
os.environ["OMP_NUM_THREADS"] = "8"
os.environ["MKL_NUM_THREADS"] = "8"
os.environ["NUMEXPR_MAX_THREADS"] = "8"

# Prevent busy-waiting which can cause scheduler issues
os.environ["OMP_WAIT_POLICY"] = "PASSIVE"

# NOTE: Do NOT set MKL_THREADING_LAYER on Windows - it can cause hangs
# if it mismatches the OpenMP runtime bundled with PyTorch.

import subprocess
import tempfile
import time
from pathlib import Path
from typing import List, Optional, Generator, Tuple

import numpy as np
import soundfile as sf
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

# Import torch early and set thread limits immediately
import torch
torch.set_num_threads(8)       # Intra-op parallelism (physical cores)
torch.set_num_interop_threads(4)  # Inter-op parallelism

from scripts.utils.config import config
from scripts.utils import logger

# Diagnostic print (runs once at module load)
logger.info(f"Thread settings: OMP={os.environ.get('OMP_NUM_THREADS')}, "
            f"MKL={os.environ.get('MKL_NUM_THREADS')}, "
            f"torch={torch.get_num_threads()}/{torch.get_num_interop_threads()}")


class VoiceNotFoundError(Exception):
    """Raised when a requested voice is not available."""
    pass


class TTSGenerationError(Exception):
    """Raised when TTS generation fails."""
    pass


class TTSGenerator:
    """
    Generate audio from text using Kokoro TTS.

    Uses the Kokoro-82M model directly via Python API for high-quality TTS.
    Includes audio normalization, retry logic, and progress tracking.
    """

    # Available Kokoro voices with descriptions
    VOICES = {
        # American Female voices
        "af_sky": {"lang": "a", "gender": "female", "style": "calm, neutral"},
        "af_bella": {"lang": "a", "gender": "female", "style": "warm, expressive"},
        "af_nicole": {"lang": "a", "gender": "female", "style": "professional"},
        "af_sarah": {"lang": "a", "gender": "female", "style": "friendly"},
        "af_heart": {"lang": "a", "gender": "female", "style": "gentle"},
        # American Male voices
        "am_michael": {"lang": "a", "gender": "male", "style": "calm, neutral"},
        "am_adam": {"lang": "a", "gender": "male", "style": "deep, authoritative"},
        "am_fenrir": {"lang": "a", "gender": "male", "style": "casual"},
        # British Female voices
        "bf_emma": {"lang": "b", "gender": "female", "style": "refined"},
        "bf_isabella": {"lang": "b", "gender": "female", "style": "elegant"},
        # British Male voices
        "bm_george": {"lang": "b", "gender": "male", "style": "distinguished"},
        "bm_lewis": {"lang": "b", "gender": "male", "style": "warm"},
    }

    # Kokoro's native sample rate
    SAMPLE_RATE = 24000

    def __init__(
        self,
        voice: Optional[str] = None,
        speed: Optional[float] = None,
        normalize_audio: bool = True,
        target_db: float = -20.0,
    ):
        """
        Initialize the TTS generator.

        Args:
            voice: Voice to use (e.g., 'af_sky', 'am_michael')
            speed: Speech speed multiplier (0.5 to 2.0, default from config)
            normalize_audio: Whether to normalize audio levels
            target_db: Target dB level for normalization (default -20)
        """
        self.voice = voice or config.voice
        self.speed = speed or config.voice_speed
        self.normalize_audio = normalize_audio
        self.target_db = target_db

        # Validate voice
        self._validate_voice()

        # Get language from voice
        self.lang = self.VOICES[self.voice]["lang"]

        # Lazy load the pipeline
        self._pipeline = None

    def _validate_voice(self) -> None:
        """Validate that the voice exists."""
        if self.voice not in self.VOICES:
            available = ", ".join(sorted(self.VOICES.keys()))
            raise VoiceNotFoundError(
                f"Voice '{self.voice}' not found. Available voices: {available}"
            )

    def _get_pipeline(self):
        """Lazy load Kokoro pipeline with proper error handling."""
        if self._pipeline is None:
            try:
                from kokoro import KPipeline

                logger.info(f"Loading Kokoro TTS model (voice: {self.voice})...")
                self._pipeline = KPipeline(lang_code=self.lang)
                logger.success("Kokoro TTS model loaded")

            except ImportError as e:
                logger.error("Kokoro TTS not installed")
                raise TTSGenerationError(
                    "Kokoro not found. Install with: pip install kokoro>=0.3.0"
                ) from e

            except Exception as e:
                logger.error(f"Failed to load Kokoro: {e}")
                raise TTSGenerationError(f"Failed to initialize TTS: {e}") from e

        return self._pipeline

    def _normalize(self, audio: np.ndarray) -> np.ndarray:
        """
        Normalize audio to target dB level.

        This ensures consistent volume across all generated audio.
        """
        if not self.normalize_audio:
            return audio

        # Calculate current RMS
        rms = np.sqrt(np.mean(audio ** 2))
        if rms == 0:
            return audio

        # Calculate current dB
        current_db = 20 * np.log10(rms)

        # Calculate gain needed
        gain_db = self.target_db - current_db
        gain = 10 ** (gain_db / 20)

        # Apply gain with clipping prevention
        normalized = audio * gain
        normalized = np.clip(normalized, -1.0, 1.0)

        return normalized

    def _add_silence(self, audio: np.ndarray, seconds: float) -> np.ndarray:
        """Add silence to the end of audio."""
        silence_samples = int(seconds * self.SAMPLE_RATE)
        silence = np.zeros(silence_samples, dtype=audio.dtype)
        return np.concatenate([audio, silence])

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

        Raises:
            TTSGenerationError: If generation fails after all retries
        """
        output_path = Path(output_path).with_suffix(".wav")
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Validate input
        text = text.strip()
        if not text:
            raise TTSGenerationError("Cannot generate audio from empty text")

        pipeline = self._get_pipeline()
        last_error = None

        for attempt in range(max_retries):
            try:
                if show_progress:
                    logger.info(f"Generating audio (voice: {self.voice}, speed: {self.speed}x)")

                audio_segments = []
                segment_count = 0

                # Generate audio segments
                for gs, ps, audio in pipeline(text, voice=self.voice, speed=self.speed):
                    if audio is not None and len(audio) > 0:
                        audio_segments.append(audio)
                        segment_count += 1

                if not audio_segments:
                    raise TTSGenerationError("TTS generated no audio segments")

                # Concatenate all segments
                full_audio = np.concatenate(audio_segments)

                # Normalize audio levels
                full_audio = self._normalize(full_audio)

                # Add trailing silence
                if add_trailing_silence > 0:
                    full_audio = self._add_silence(full_audio, add_trailing_silence)

                # Calculate duration
                duration = len(full_audio) / self.SAMPLE_RATE

                # Save to file
                sf.write(str(output_path), full_audio, self.SAMPLE_RATE)

                if show_progress:
                    logger.success(f"Generated: {output_path.name} ({duration:.1f}s, {segment_count} segments)")

                return output_path, duration

            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff
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
        """
        Generate audio for a single chapter.

        Args:
            chapter: Chapter dict with 'title' and 'text' keys
            output_dir: Directory for output files
            chapter_num: Chapter number for filename
            total_chapters: Total number of chapters (for progress display)

        Returns:
            Tuple of (path to generated audio, duration in seconds)
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        filename = f"chapter_{chapter_num:03d}.wav"
        output_path = output_dir / filename

        progress_str = f"[{chapter_num}/{total_chapters}] " if total_chapters else ""
        logger.step(f"{progress_str}Chapter: {chapter['title'][:60]}")

        return self.generate_audio(chapter["text"], output_path, show_progress=False)

    @classmethod
    def list_voices(cls) -> dict:
        """Return all available voices with their properties."""
        return cls.VOICES.copy()

    @classmethod
    def get_voice_info(cls, voice: str) -> Optional[dict]:
        """Get information about a specific voice."""
        return cls.VOICES.get(voice)


class ChunkedTTSGenerator:
    """
    Generate audio in chunks for very long texts.

    Memory-efficient processing for book-length content:
    - Splits text at sentence boundaries
    - Processes chunks sequentially
    - Provides progress updates
    - Handles concatenation automatically
    """

    def __init__(
        self,
        voice: Optional[str] = None,
        speed: Optional[float] = None,
        chunk_size: Optional[int] = None,
    ):
        """
        Initialize chunked generator.

        Args:
            voice: Voice to use
            speed: Speech speed multiplier
            chunk_size: Maximum characters per chunk (default from config)
        """
        self.tts = TTSGenerator(voice=voice, speed=speed)
        self.chunk_size = chunk_size or config.get(
            "processing", "chunk_size", default=5000
        )

    def _split_into_chunks(self, text: str) -> Generator[Tuple[int, str], None, None]:
        """
        Split text into chunks at sentence boundaries.

        Yields:
            Tuple of (chunk_number, chunk_text)
        """
        import re

        # Split into sentences (preserving the delimiter)
        sentences = re.split(r'(?<=[.!?])\s+', text)

        current_chunk = []
        current_length = 0
        chunk_num = 1

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            sentence_length = len(sentence)

            # If adding this sentence would exceed chunk size, yield current chunk
            if current_length + sentence_length > self.chunk_size and current_chunk:
                yield chunk_num, " ".join(current_chunk)
                chunk_num += 1
                current_chunk = []
                current_length = 0

            current_chunk.append(sentence)
            current_length += sentence_length + 1  # +1 for space

        # Yield remaining content
        if current_chunk:
            yield chunk_num, " ".join(current_chunk)

    def generate_long_audio(
        self,
        text: str,
        output_path: Path,
        progress_callback: Optional[callable] = None,
    ) -> Tuple[Path, float]:
        """
        Generate audio for long text using chunked processing.

        Args:
            text: Long text to convert
            output_path: Path for final output
            progress_callback: Optional callback(current, total, chunk_text)

        Returns:
            Tuple of (path to audio file, total duration)
        """
        output_path = Path(output_path).with_suffix(".wav")

        # Pre-calculate chunks for progress
        chunks = list(self._split_into_chunks(text))
        total_chunks = len(chunks)

        if total_chunks == 0:
            raise TTSGenerationError("No text chunks to process")

        logger.info(f"Processing {total_chunks} chunks ({len(text):,} characters)")

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            chunk_files = []
            total_duration = 0.0

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=logger.console,
            ) as progress:
                task = progress.add_task("Generating audio...", total=total_chunks)

                for chunk_num, chunk_text in chunks:
                    chunk_file = temp_path / f"chunk_{chunk_num:05d}.wav"

                    if progress_callback:
                        progress_callback(chunk_num, total_chunks, chunk_text[:50])

                    _, duration = self.tts.generate_audio(
                        chunk_text,
                        chunk_file,
                        show_progress=False,
                        add_trailing_silence=0.3,  # Small pause between chunks
                    )

                    chunk_files.append(chunk_file)
                    total_duration += duration

                    progress.update(task, advance=1, description=f"Chunk {chunk_num}/{total_chunks}")

            # Concatenate all chunks
            logger.info("Concatenating audio chunks...")
            final_path = self._concatenate_audio(chunk_files, output_path)

        logger.success(f"Generated: {output_path.name} ({total_duration:.1f}s)")
        return final_path, total_duration

    def _concatenate_audio(
        self,
        audio_files: List[Path],
        output_path: Path,
    ) -> Path:
        """Concatenate multiple audio files using FFmpeg."""
        output_path = Path(output_path).with_suffix(".wav")

        # Create concat file list
        concat_file = output_path.parent / "concat_list.txt"
        with open(concat_file, "w", encoding="utf-8") as f:
            for audio_file in audio_files:
                # FFmpeg requires forward slashes and escaped quotes
                safe_path = str(audio_file).replace("\\", "/").replace("'", "'\\''")
                f.write(f"file '{safe_path}'\n")

        try:
            cmd = [
                "ffmpeg",
                "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", str(concat_file),
                "-c", "copy",
                str(output_path),
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode != 0:
                raise TTSGenerationError(f"FFmpeg concat failed: {result.stderr}")

            return output_path

        finally:
            if concat_file.exists():
                concat_file.unlink()


def generate_from_text(
    text: str,
    output_path: Path,
    voice: Optional[str] = None,
    speed: Optional[float] = None,
    use_chunking: bool = True,
    chunk_threshold: int = 10000,
) -> Tuple[Path, float]:
    """
    Main function to generate audio from text.

    Automatically selects chunked processing for long texts.

    Args:
        text: Text to convert to audio
        output_path: Output file path
        voice: Voice to use (default from config)
        speed: Speech speed (default from config)
        use_chunking: Whether to use chunked processing for long texts
        chunk_threshold: Character count above which to use chunking

    Returns:
        Tuple of (path to audio file, duration in seconds)
    """
    text = text.strip()
    if not text:
        raise TTSGenerationError("Cannot generate audio from empty text")

    if use_chunking and len(text) > chunk_threshold:
        generator = ChunkedTTSGenerator(voice=voice, speed=speed)
        return generator.generate_long_audio(text, output_path)
    else:
        generator = TTSGenerator(voice=voice, speed=speed)
        return generator.generate_audio(text, output_path)


def generate_from_file(
    input_path: Path,
    output_path: Path,
    voice: Optional[str] = None,
    speed: Optional[float] = None,
) -> Tuple[Path, float]:
    """
    Generate audio from a text file.

    Args:
        input_path: Path to input text file
        output_path: Path for output audio file
        voice: Voice to use
        speed: Speech speed

    Returns:
        Tuple of (path to audio file, duration in seconds)
    """
    input_path = Path(input_path)

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    text = input_path.read_text(encoding="utf-8")
    return generate_from_text(text, output_path, voice=voice, speed=speed)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: python generate_audio.py <input_text_file> <output_audio_file> [voice]")
        print(f"\nAvailable voices: {', '.join(sorted(TTSGenerator.VOICES.keys()))}")
        sys.exit(1)

    input_file = Path(sys.argv[1])
    output_file = Path(sys.argv[2])
    voice = sys.argv[3] if len(sys.argv) > 3 else None

    path, duration = generate_from_file(input_file, output_file, voice=voice)
    print(f"Generated: {path} ({duration:.1f}s)")
