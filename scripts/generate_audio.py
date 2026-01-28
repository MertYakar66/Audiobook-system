"""
TTS Audio Generation Module

Generates audio from text using Kokoro-82M TTS model directly.
Supports chunked processing for long texts and progress tracking.
"""

import os
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional, Generator

import soundfile as sf
import numpy as np

from scripts.utils.config import config
from scripts.utils import logger


class TTSGenerator:
    """
    Generate audio from text using Kokoro TTS.

    Uses the Kokoro-82M model directly via Python API for high-quality TTS.
    """

    # Kokoro voice mapping
    VOICE_MAP = {
        # American Female voices
        "af_sky": "af_sky",
        "af_bella": "af_bella",
        "af_nicole": "af_nicole",
        "af_sarah": "af_sarah",
        "af_heart": "af_heart",
        # American Male voices
        "am_michael": "am_michael",
        "am_adam": "am_adam",
        "am_fenrir": "am_fenrir",
        # British voices
        "bf_emma": "bf_emma",
        "bf_isabella": "bf_isabella",
        "bm_george": "bm_george",
        "bm_lewis": "bm_lewis",
    }

    def __init__(
        self,
        voice: Optional[str] = None,
        speed: Optional[float] = None,
        lang: Optional[str] = None,
    ):
        """
        Initialize the TTS generator.

        Args:
            voice: Voice to use (e.g., 'af_sky', 'am_michael')
            speed: Speech speed multiplier (default 1.0)
            lang: Language code ('a' for American, 'b' for British)
        """
        self.voice = voice or config.voice
        self.speed = speed or config.voice_speed
        self.sample_rate = config.sample_rate

        # Determine language from voice prefix
        if lang:
            self.lang = lang
        elif self.voice.startswith("b"):
            self.lang = "b"  # British
        else:
            self.lang = "a"  # American (default)

        # Lazy load the pipeline
        self._pipeline = None

    def _get_pipeline(self):
        """Lazy load Kokoro pipeline."""
        if self._pipeline is None:
            try:
                from kokoro import KPipeline
                logger.info(f"Loading Kokoro TTS (lang={self.lang})...")
                self._pipeline = KPipeline(lang_code=self.lang)
                logger.success("Kokoro TTS loaded successfully")
            except ImportError:
                logger.error(
                    "Kokoro not found. Install with: pip install kokoro-onnx"
                )
                raise
            except Exception as e:
                logger.error(f"Failed to load Kokoro: {e}")
                raise
        return self._pipeline

    def generate_audio(
        self,
        text: str,
        output_path: Path,
        show_progress: bool = True,
    ) -> Path:
        """
        Generate audio for a text string.

        Args:
            text: Text to convert to speech
            output_path: Path for output audio file
            show_progress: Whether to show progress

        Returns:
            Path to generated audio file
        """
        output_path = Path(output_path).with_suffix(".wav")
        output_path.parent.mkdir(parents=True, exist_ok=True)

        pipeline = self._get_pipeline()

        if show_progress:
            logger.info(f"Generating audio with voice: {self.voice}")

        try:
            # Generate audio using Kokoro pipeline
            # The pipeline returns a generator of (graphemes, phonemes, audio) tuples
            audio_segments = []

            for i, (gs, ps, audio) in enumerate(pipeline(text, voice=self.voice, speed=self.speed)):
                audio_segments.append(audio)
                if show_progress and i % 10 == 0:
                    logger.info(f"  Processing segment {i+1}...")

            if not audio_segments:
                raise RuntimeError("No audio generated from text")

            # Concatenate all audio segments
            full_audio = np.concatenate(audio_segments)

            # Save to WAV file
            sf.write(str(output_path), full_audio, self.sample_rate)

            if show_progress:
                duration = len(full_audio) / self.sample_rate
                logger.success(f"Generated audio: {output_path} ({duration:.1f}s)")

            return output_path

        except Exception as e:
            logger.error(f"TTS generation failed: {e}")
            raise RuntimeError(f"TTS generation failed: {e}")

    def generate_chapter_audio(
        self,
        chapter: dict,
        output_dir: Path,
        chapter_num: int,
    ) -> Path:
        """
        Generate audio for a single chapter.

        Args:
            chapter: Chapter dict with 'title' and 'text' keys
            output_dir: Directory for output files
            chapter_num: Chapter number for filename

        Returns:
            Path to generated audio file
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Create filename from chapter number
        filename = f"chapter_{chapter_num:03d}.wav"
        output_path = output_dir / filename

        logger.step(f"Generating Chapter {chapter_num}: {chapter['title']}")

        return self.generate_audio(chapter["text"], output_path)


class ChunkedTTSGenerator:
    """
    Generate audio in chunks for very long texts.

    Splits text into manageable chunks, generates audio for each,
    then concatenates them. This is more memory-efficient for long books.
    """

    def __init__(
        self,
        voice: Optional[str] = None,
        chunk_size: Optional[int] = None,
    ):
        self.tts = TTSGenerator(voice=voice)
        self.chunk_size = chunk_size or config.get(
            "processing", "chunk_size", default=5000
        )

    def _split_into_chunks(self, text: str) -> Generator[str, None, None]:
        """
        Split text into chunks at sentence boundaries.

        Yields:
            Text chunks of approximately chunk_size characters
        """
        import re

        # Split into sentences
        sentences = re.split(r"(?<=[.!?])\s+", text)

        current_chunk = []
        current_length = 0

        for sentence in sentences:
            sentence_length = len(sentence)

            if current_length + sentence_length > self.chunk_size and current_chunk:
                yield " ".join(current_chunk)
                current_chunk = [sentence]
                current_length = sentence_length
            else:
                current_chunk.append(sentence)
                current_length += sentence_length

        if current_chunk:
            yield " ".join(current_chunk)

    def generate_long_audio(
        self,
        text: str,
        output_path: Path,
        progress_callback: Optional[callable] = None,
    ) -> Path:
        """
        Generate audio for long text using chunked processing.

        Args:
            text: Long text to convert
            output_path: Path for final output
            progress_callback: Optional callback(current, total)

        Returns:
            Path to concatenated audio file
        """
        output_path = Path(output_path)
        chunks = list(self._split_into_chunks(text))
        total_chunks = len(chunks)

        logger.info(f"Processing {total_chunks} chunks...")

        # Create temp directory for chunk files
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            chunk_files = []

            for i, chunk in enumerate(chunks, 1):
                if progress_callback:
                    progress_callback(i, total_chunks)

                chunk_file = temp_path / f"chunk_{i:05d}.wav"
                self.tts.generate_audio(chunk, chunk_file, show_progress=False)
                chunk_files.append(chunk_file)

                logger.info(f"Processed chunk {i}/{total_chunks}")

            # Concatenate all chunks
            logger.info("Concatenating audio chunks...")
            final_path = self._concatenate_audio(chunk_files, output_path)

        return final_path

    def _concatenate_audio(
        self,
        audio_files: List[Path],
        output_path: Path,
    ) -> Path:
        """Concatenate multiple audio files using ffmpeg."""
        output_path = Path(output_path).with_suffix(".wav")

        # Create concat file list
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".txt",
            delete=False,
        ) as f:
            for audio_file in audio_files:
                f.write(f"file '{audio_file}'\n")
            concat_file = f.name

        try:
            cmd = [
                "ffmpeg",
                "-y",  # Overwrite output
                "-f", "concat",
                "-safe", "0",
                "-i", concat_file,
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
                raise RuntimeError(f"FFmpeg concat failed: {result.stderr}")

            return output_path

        finally:
            os.unlink(concat_file)


def generate_from_text(
    text: str,
    output_path: Path,
    voice: Optional[str] = None,
    chunked: bool = True,
) -> Path:
    """
    Main function to generate audio from text.

    Args:
        text: Text to convert to audio
        output_path: Output file path
        voice: Voice to use
        chunked: Whether to use chunked processing

    Returns:
        Path to generated audio
    """
    if chunked and len(text) > 10000:
        generator = ChunkedTTSGenerator(voice=voice)
        return generator.generate_long_audio(text, output_path)
    else:
        generator = TTSGenerator(voice=voice)
        return generator.generate_audio(text, output_path)


def generate_from_file(
    input_path: Path,
    output_path: Path,
    voice: Optional[str] = None,
) -> Path:
    """Generate audio from a text file."""
    input_path = Path(input_path)
    text = input_path.read_text(encoding="utf-8")
    return generate_from_text(text, output_path, voice=voice)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: python generate_audio.py <input_text_file> <output_audio_file>")
        sys.exit(1)

    input_file = Path(sys.argv[1])
    output_file = Path(sys.argv[2])

    generate_from_file(input_file, output_file)
