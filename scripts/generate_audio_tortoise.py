"""
TTS Audio Generation Module using Tortoise TTS

Generates audio from text using Tortoise TTS model with voice cloning capabilities.
Professional-grade implementation with:
- Voice cloning from reference audio samples
- Multiple built-in voices
- High-quality, natural-sounding speech
- Audio normalization for consistent volume
- Memory-efficient chunked processing
"""

# =============================================================================
# Thread constraints for stability (same as Kokoro version)
# =============================================================================
import os

os.environ["OMP_NUM_THREADS"] = "8"
os.environ["MKL_NUM_THREADS"] = "8"
os.environ["NUMEXPR_MAX_THREADS"] = "8"
os.environ["OMP_WAIT_POLICY"] = "PASSIVE"

import subprocess
import tempfile
import time
from pathlib import Path
from typing import List, Optional, Tuple, Generator

import numpy as np
import soundfile as sf
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

import torch
torch.set_num_threads(8)
torch.set_num_interop_threads(4)

from scripts.utils.config import config
from scripts.utils import logger


class VoiceNotFoundError(Exception):
    """Raised when a requested voice is not available."""
    pass


class TTSGenerationError(Exception):
    """Raised when TTS generation fails."""
    pass


class TortoiseTTSGenerator:
    """
    Generate audio from text using Tortoise TTS.

    Tortoise TTS provides high-quality, natural-sounding speech synthesis
    with voice cloning capabilities. It's slower than Kokoro but produces
    more expressive and natural results.

    Voice Cloning:
        Place 3-10 reference audio files (WAV, 6-10 seconds each) in:
        voices/<voice_name>/

    Built-in Voices:
        - angie, cond_latent_example, deniro, emma, freeman, geralt,
        - halle, jlaw, lj, mol, myself, pat, pat2, rainbow, snakes,
        - tim_reynolds, tom, train_atkins, train_daws, train_dotrice,
        - train_dreams, train_empire, train_grace, train_kennard, train_lescault,
        - train_mouse, weaver, william
    """

    # Built-in Tortoise voices
    BUILTIN_VOICES = [
        "angie", "cond_latent_example", "deniro", "emma", "freeman",
        "geralt", "halle", "jlaw", "lj", "mol", "myself", "pat", "pat2",
        "rainbow", "snakes", "tim_reynolds", "tom", "train_atkins",
        "train_daws", "train_dotrice", "train_dreams", "train_empire",
        "train_grace", "train_kennard", "train_lescault", "train_mouse",
        "weaver", "william"
    ]

    # Tortoise sample rate (different from Kokoro)
    SAMPLE_RATE = 24000

    # Voice presets for quality/speed tradeoff
    PRESETS = {
        "ultra_fast": {"num_autoregressive_samples": 1, "diffusion_iterations": 10},
        "fast": {"num_autoregressive_samples": 2, "diffusion_iterations": 30},
        "standard": {"num_autoregressive_samples": 4, "diffusion_iterations": 80},
        "high_quality": {"num_autoregressive_samples": 16, "diffusion_iterations": 200},
    }

    def __init__(
        self,
        voice: Optional[str] = None,
        speed: Optional[float] = None,
        preset: str = "fast",
        normalize_audio: bool = True,
        target_db: float = -20.0,
        voices_dir: Optional[Path] = None,
    ):
        """
        Initialize the Tortoise TTS generator.

        Args:
            voice: Voice to use (built-in name or custom voice folder name)
            speed: Speech speed multiplier (not directly supported, affects pacing)
            preset: Quality preset (ultra_fast, fast, standard, high_quality)
            normalize_audio: Whether to normalize audio levels
            target_db: Target dB level for normalization
            voices_dir: Directory containing custom voice samples
        """
        self.voice = voice or config.get("voice", "default", default="train_dotrice")
        self.speed = speed or config.voice_speed
        self.preset = preset
        self.normalize_audio = normalize_audio
        self.target_db = target_db

        # Set up voices directory
        self.voices_dir = voices_dir or config.project_root / "voices"
        self.voices_dir.mkdir(parents=True, exist_ok=True)

        # Lazy load the model
        self._tts = None

    def _get_tts(self):
        """Lazy load Tortoise TTS model."""
        if self._tts is None:
            try:
                from tortoise.api import TextToSpeech
                from tortoise.utils.audio import load_voices

                logger.info(f"Loading Tortoise TTS model...")
                self._tts = TextToSpeech()
                logger.success("Tortoise TTS model loaded")

            except ImportError as e:
                logger.error("Tortoise TTS not installed")
                raise TTSGenerationError(
                    "Tortoise TTS not found. Install with:\n"
                    "  pip install tortoise-tts\n"
                    "  # Or for CUDA support:\n"
                    "  pip install tortoise-tts[cuda]"
                ) from e

            except Exception as e:
                logger.error(f"Failed to load Tortoise TTS: {e}")
                raise TTSGenerationError(f"Failed to initialize TTS: {e}") from e

        return self._tts

    def _load_voice(self, voice_name: str):
        """
        Load voice samples for voice cloning.

        Args:
            voice_name: Name of voice (built-in or custom folder name)

        Returns:
            Tuple of (voice_samples, conditioning_latents) or (None, None) for built-in
        """
        from tortoise.utils.audio import load_voices

        # Check if custom voice exists
        custom_voice_dir = self.voices_dir / voice_name
        if custom_voice_dir.exists():
            voice_samples, conditioning_latents = load_voices(
                [voice_name],
                extra_voice_dirs=[str(self.voices_dir)]
            )
            return voice_samples, conditioning_latents

        # Use built-in voice
        if voice_name in self.BUILTIN_VOICES:
            voice_samples, conditioning_latents = load_voices([voice_name])
            return voice_samples, conditioning_latents

        raise VoiceNotFoundError(
            f"Voice '{voice_name}' not found. "
            f"Available built-in: {', '.join(self.BUILTIN_VOICES[:10])}... "
            f"Or create custom voice at: {custom_voice_dir}"
        )

    def _normalize(self, audio: np.ndarray) -> np.ndarray:
        """Normalize audio to target dB level."""
        if not self.normalize_audio:
            return audio

        rms = np.sqrt(np.mean(audio ** 2))
        if rms == 0:
            return audio

        current_db = 20 * np.log10(rms)
        gain_db = self.target_db - current_db
        gain = 10 ** (gain_db / 20)

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
        """
        output_path = Path(output_path).with_suffix(".wav")
        output_path.parent.mkdir(parents=True, exist_ok=True)

        text = text.strip()
        if not text:
            raise TTSGenerationError("Cannot generate audio from empty text")

        tts = self._get_tts()
        last_error = None

        for attempt in range(max_retries):
            try:
                if show_progress:
                    logger.info(f"Generating audio (voice: {self.voice}, preset: {self.preset})")

                # Load voice
                voice_samples, conditioning_latents = self._load_voice(self.voice)

                # Get preset parameters
                preset_params = self.PRESETS.get(self.preset, self.PRESETS["fast"])

                # Generate audio
                audio = tts.tts_with_preset(
                    text,
                    voice_samples=voice_samples,
                    conditioning_latents=conditioning_latents,
                    preset=self.preset,
                )

                # Convert to numpy if tensor
                if torch.is_tensor(audio):
                    audio = audio.squeeze().cpu().numpy()

                # Normalize audio levels
                audio = self._normalize(audio)

                # Add trailing silence
                if add_trailing_silence > 0:
                    audio = self._add_silence(audio, add_trailing_silence)

                # Calculate duration
                duration = len(audio) / self.SAMPLE_RATE

                # Save to file
                sf.write(str(output_path), audio, self.SAMPLE_RATE)

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
        """
        Generate audio for a single chapter.

        Args:
            chapter: Chapter dict with 'title' and 'text' keys
            output_dir: Directory for output files
            chapter_num: Chapter number for filename
            total_chapters: Total number of chapters

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

    def clone_voice(
        self,
        voice_name: str,
        reference_files: List[Path],
    ) -> Path:
        """
        Set up a custom voice for cloning.

        Args:
            voice_name: Name for the new voice
            reference_files: List of reference audio files (WAV, 6-10s each)

        Returns:
            Path to the voice directory
        """
        voice_dir = self.voices_dir / voice_name
        voice_dir.mkdir(parents=True, exist_ok=True)

        for i, ref_file in enumerate(reference_files):
            ref_path = Path(ref_file)
            if not ref_path.exists():
                raise FileNotFoundError(f"Reference file not found: {ref_file}")

            # Copy or link reference file
            dest = voice_dir / f"sample_{i+1}.wav"
            import shutil
            shutil.copy2(ref_path, dest)
            logger.info(f"Added voice sample: {dest.name}")

        logger.success(f"Voice '{voice_name}' created with {len(reference_files)} samples")
        return voice_dir

    @classmethod
    def list_voices(cls, voices_dir: Optional[Path] = None) -> dict:
        """Return all available voices."""
        voices = {}

        # Built-in voices
        for voice in cls.BUILTIN_VOICES:
            voices[voice] = {"type": "builtin", "description": "Tortoise built-in voice"}

        # Custom voices
        if voices_dir and voices_dir.exists():
            for voice_dir in voices_dir.iterdir():
                if voice_dir.is_dir():
                    sample_count = len(list(voice_dir.glob("*.wav")))
                    if sample_count > 0:
                        voices[voice_dir.name] = {
                            "type": "custom",
                            "description": f"Custom voice with {sample_count} samples"
                        }

        return voices


class ChunkedTortoiseTTSGenerator:
    """
    Generate audio in chunks for very long texts.

    Memory-efficient processing for book-length content.
    """

    def __init__(
        self,
        voice: Optional[str] = None,
        speed: Optional[float] = None,
        preset: str = "fast",
        chunk_size: Optional[int] = None,
    ):
        self.tts = TortoiseTTSGenerator(voice=voice, speed=speed, preset=preset)
        self.chunk_size = chunk_size or config.get("processing", "chunk_size", default=500)

    def _split_into_chunks(self, text: str) -> Generator[Tuple[int, str], None, None]:
        """Split text into chunks at sentence boundaries."""
        import re

        # Tortoise works better with shorter chunks
        sentences = re.split(r'(?<=[.!?])\s+', text)

        current_chunk = []
        current_length = 0
        chunk_num = 1

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            sentence_length = len(sentence)

            if current_length + sentence_length > self.chunk_size and current_chunk:
                yield chunk_num, " ".join(current_chunk)
                chunk_num += 1
                current_chunk = []
                current_length = 0

            current_chunk.append(sentence)
            current_length += sentence_length + 1

        if current_chunk:
            yield chunk_num, " ".join(current_chunk)

    def generate_long_audio(
        self,
        text: str,
        output_path: Path,
        progress_callback: Optional[callable] = None,
    ) -> Tuple[Path, float]:
        """Generate audio for long text using chunked processing."""
        output_path = Path(output_path).with_suffix(".wav")

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
                        add_trailing_silence=0.3,
                    )

                    chunk_files.append(chunk_file)
                    total_duration += duration

                    progress.update(task, advance=1, description=f"Chunk {chunk_num}/{total_chunks}")

            logger.info("Concatenating audio chunks...")
            final_path = self._concatenate_audio(chunk_files, output_path)

        logger.success(f"Generated: {output_path.name} ({total_duration:.1f}s)")
        return final_path, total_duration

    def _concatenate_audio(self, audio_files: List[Path], output_path: Path) -> Path:
        """Concatenate multiple audio files using FFmpeg."""
        output_path = Path(output_path).with_suffix(".wav")

        concat_file = output_path.parent / "concat_list.txt"
        with open(concat_file, "w", encoding="utf-8") as f:
            for audio_file in audio_files:
                safe_path = str(audio_file).replace("\\", "/").replace("'", "'\\''")
                f.write(f"file '{safe_path}'\n")

        try:
            cmd = [
                "ffmpeg", "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", str(concat_file),
                "-c", "copy",
                str(output_path),
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, check=False)

            if result.returncode != 0:
                raise TTSGenerationError(f"FFmpeg concat failed: {result.stderr}")

            return output_path

        finally:
            if concat_file.exists():
                concat_file.unlink()


# Convenience aliases for drop-in replacement
TTSGenerator = TortoiseTTSGenerator
ChunkedTTSGenerator = ChunkedTortoiseTTSGenerator


def generate_from_text(
    text: str,
    output_path: Path,
    voice: Optional[str] = None,
    speed: Optional[float] = None,
    preset: str = "fast",
    use_chunking: bool = True,
    chunk_threshold: int = 1000,  # Lower threshold for Tortoise
) -> Tuple[Path, float]:
    """
    Main function to generate audio from text.

    Args:
        text: Text to convert to audio
        output_path: Output file path
        voice: Voice to use
        speed: Speech speed (affects pacing)
        preset: Quality preset (ultra_fast, fast, standard, high_quality)
        use_chunking: Whether to use chunked processing
        chunk_threshold: Character count above which to use chunking

    Returns:
        Tuple of (path to audio file, duration in seconds)
    """
    text = text.strip()
    if not text:
        raise TTSGenerationError("Cannot generate audio from empty text")

    if use_chunking and len(text) > chunk_threshold:
        generator = ChunkedTortoiseTTSGenerator(voice=voice, speed=speed, preset=preset)
        return generator.generate_long_audio(text, output_path)
    else:
        generator = TortoiseTTSGenerator(voice=voice, speed=speed, preset=preset)
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
    import sys

    print("Tortoise TTS Generator")
    print("=" * 50)
    print()
    print("Available built-in voices:")
    for voice in TortoiseTTSGenerator.BUILTIN_VOICES:
        print(f"  - {voice}")
    print()
    print("Quality presets:")
    for preset, params in TortoiseTTSGenerator.PRESETS.items():
        print(f"  - {preset}: {params}")
    print()
    print("Usage:")
    print("  python generate_audio_tortoise.py <input.txt> <output.wav> [voice] [preset]")
    print()
    print("Voice Cloning:")
    print("  1. Create folder: voices/my_voice/")
    print("  2. Add 3-10 WAV files (6-10 seconds each) of the target voice")
    print("  3. Use voice name: --voice my_voice")
