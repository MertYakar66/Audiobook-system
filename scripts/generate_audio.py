"""
TTS Audio Generation Module

Generates audio from text using Audiblez with Kokoro-82M model.
Supports chunked processing for long texts and progress tracking.
"""

import os
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional, Generator
import shutil

from scripts.utils.config import config
from scripts.utils import logger


class TTSGenerator:
    """
    Generate audio from text using Audiblez + Kokoro.

    Audiblez is a CLI tool that uses the Kokoro-82M model for high-quality TTS.
    This class wraps audiblez to provide programmatic access.
    """

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
            speed: Speech speed multiplier
            lang: Language code
        """
        self.voice = voice or config.voice
        self.speed = speed or config.voice_speed
        self.lang = lang or config.get("voice", "lang", default="en-us")
        self.sample_rate = config.sample_rate

        # Verify audiblez is available
        self._verify_audiblez()

    def _verify_audiblez(self) -> None:
        """Verify that audiblez is installed and accessible."""
        if shutil.which("audiblez") is None:
            # Try to find it in common locations
            possible_paths = [
                Path.home() / ".local" / "bin" / "audiblez",
                Path("/usr/local/bin/audiblez"),
            ]
            for path in possible_paths:
                if path.exists():
                    return

            logger.warning(
                "audiblez not found in PATH. "
                "Install with: pip install audiblez"
            )

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
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Create temporary text file for audiblez
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".txt",
            delete=False,
            encoding="utf-8",
        ) as f:
            f.write(text)
            text_file = f.name

        try:
            # Build audiblez command
            cmd = [
                "audiblez",
                text_file,
                "-v", self.voice,
                "-s", str(self.speed),
                "-l", self.lang,
                "-f", "wav",  # Output WAV for further processing
                "-o", str(output_path.with_suffix(".wav")),
            ]

            if config.use_gpu:
                # Audiblez uses GPU by default if available
                pass

            logger.info(f"Generating audio with voice: {self.voice}")

            # Run audiblez
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode != 0:
                logger.error(f"Audiblez error: {result.stderr}")
                raise RuntimeError(f"TTS generation failed: {result.stderr}")

            output_wav = output_path.with_suffix(".wav")
            if output_wav.exists():
                logger.success(f"Generated audio: {output_wav}")
                return output_wav
            else:
                raise FileNotFoundError(f"Expected output not found: {output_wav}")

        finally:
            # Clean up temp file
            os.unlink(text_file)

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
