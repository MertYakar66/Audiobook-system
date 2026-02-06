"""
Timed TTS Generator using Tortoise TTS

Generates audio with precise timing information for each sentence.
Captures start/end timestamps for Read-Along synchronization.
Uses Tortoise TTS for high-quality, natural speech synthesis.
"""

import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
import soundfile as sf

from scripts.readalong.sentence_splitter import Sentence, SentenceSplitter
from scripts.utils.config import config
from scripts.utils import logger


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


class TimedTortoiseTTSGenerator:
    """
    Generate audio with per-sentence timing using Tortoise TTS.

    Processes text sentence by sentence, capturing precise timestamps
    for Read-Along synchronization.
    """

    SAMPLE_RATE = 24000
    SENTENCE_PAUSE = 0.3
    PARAGRAPH_PAUSE = 0.8

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
        Initialize the timed Tortoise TTS generator.

        Args:
            voice: Voice to use (built-in or custom)
            speed: Speech speed multiplier
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
        self.voices_dir = voices_dir or config.project_root / "voices"

        self._tts = None
        self._voice_samples = None
        self._conditioning_latents = None

    def _get_tts(self):
        """Lazy load Tortoise TTS model."""
        if self._tts is None:
            try:
                from tortoise.api import TextToSpeech
                from tortoise.utils.audio import load_voices

                logger.info(f"Loading Tortoise TTS (voice: {self.voice})...")
                self._tts = TextToSpeech()

                # Load voice
                extra_dirs = [str(self.voices_dir)] if self.voices_dir.exists() else []
                self._voice_samples, self._conditioning_latents = load_voices(
                    [self.voice],
                    extra_voice_dirs=extra_dirs
                )

                logger.success("Tortoise TTS loaded")

            except ImportError as e:
                logger.error("Tortoise TTS not installed")
                raise RuntimeError(
                    "Tortoise TTS not found. Install with: pip install tortoise-tts"
                ) from e

        return self._tts

    def generate_timed_audio(
        self,
        text: str,
        output_path: Path,
        chapter_id: str = "ch01",
        show_progress: bool = True,
    ) -> Tuple[Path, List[TimedSegment]]:
        """
        Generate audio with timing information for each sentence.

        Args:
            text: Full text to convert
            output_path: Path for output audio file
            chapter_id: Chapter identifier for sentence IDs
            show_progress: Whether to show progress

        Returns:
            Tuple of (audio file path, list of timed segments)
        """
        import torch

        output_path = Path(output_path).with_suffix(".wav")
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Split text into sentences
        splitter = SentenceSplitter(chapter_id)
        sentences = splitter.split(text)

        if not sentences:
            raise ValueError("No sentences found in text")

        logger.info(f"Processing {len(sentences)} sentences with Tortoise TTS...")

        # Generate audio for each sentence
        timed_segments = []
        all_audio = []
        current_time = 0.0
        last_paragraph = -1

        tts = self._get_tts()

        for i, sentence in enumerate(sentences):
            if show_progress and (i + 1) % 5 == 0:
                logger.info(f"  Sentence {i + 1}/{len(sentences)}...")

            # Add paragraph pause if new paragraph
            if sentence.paragraph_id != last_paragraph and last_paragraph != -1:
                pause_samples = int(self.PARAGRAPH_PAUSE * self.SAMPLE_RATE)
                all_audio.append(np.zeros(pause_samples, dtype=np.float32))
                current_time += self.PARAGRAPH_PAUSE

            last_paragraph = sentence.paragraph_id

            # Generate audio for this sentence
            try:
                audio_data = self._generate_sentence_audio(sentence.text, tts)
            except Exception as e:
                logger.warning(f"Failed to generate audio for sentence {i}: {e}")
                audio_data = np.zeros(int(0.5 * self.SAMPLE_RATE), dtype=np.float32)

            # Calculate timing
            duration = len(audio_data) / self.SAMPLE_RATE
            start_time = current_time
            end_time = current_time + duration

            # Create timed segment
            segment = TimedSegment(
                sentence_id=sentence.id,
                text=sentence.text,
                start_time=start_time,
                end_time=end_time,
            )
            timed_segments.append(segment)

            # Append audio
            all_audio.append(audio_data)
            current_time = end_time

            # Add pause between sentences
            pause_samples = int(self.SENTENCE_PAUSE * self.SAMPLE_RATE)
            all_audio.append(np.zeros(pause_samples, dtype=np.float32))
            current_time += self.SENTENCE_PAUSE

        # Concatenate all audio
        full_audio = np.concatenate(all_audio)

        # Normalize
        if self.normalize_audio:
            full_audio = self._normalize(full_audio)

        # Save audio file
        sf.write(str(output_path), full_audio, self.SAMPLE_RATE)

        total_duration = len(full_audio) / self.SAMPLE_RATE
        logger.success(f"Generated: {output_path.name} ({total_duration:.1f}s, {len(timed_segments)} segments)")

        return output_path, timed_segments

    # Maximum characters per TTS call to prevent OOM errors
    MAX_CHARS_PER_CHUNK = 200

    def _generate_sentence_audio(self, text: str, tts) -> np.ndarray:
        """Generate audio for a single sentence with chunking for long text."""
        import torch
        import gc

        # Split very long sentences into chunks to prevent OOM
        if len(text) > self.MAX_CHARS_PER_CHUNK:
            return self._generate_chunked_audio(text, tts)

        # Generate with Tortoise
        audio = tts.tts_with_preset(
            text,
            voice_samples=self._voice_samples,
            conditioning_latents=self._conditioning_latents,
            preset=self.preset,
        )

        # Convert tensor to numpy
        if torch.is_tensor(audio):
            audio = audio.squeeze().cpu().numpy()

        # Clean up GPU memory after each sentence
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        gc.collect()

        return audio.astype(np.float32)

    def _generate_chunked_audio(self, text: str, tts) -> np.ndarray:
        """Split long text into chunks and generate audio for each."""
        import torch
        import gc

        # Split on punctuation or at max length
        chunks = self._split_text_into_chunks(text)
        audio_parts = []

        for chunk in chunks:
            if not chunk.strip():
                continue

            audio = tts.tts_with_preset(
                chunk,
                voice_samples=self._voice_samples,
                conditioning_latents=self._conditioning_latents,
                preset=self.preset,
            )

            if torch.is_tensor(audio):
                audio = audio.squeeze().cpu().numpy()

            audio_parts.append(audio.astype(np.float32))

            # Clean up memory after each chunk
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            gc.collect()

        if not audio_parts:
            return np.zeros(int(0.5 * self.SAMPLE_RATE), dtype=np.float32)

        # Add small pause between chunks
        pause = np.zeros(int(0.1 * self.SAMPLE_RATE), dtype=np.float32)
        result = []
        for i, part in enumerate(audio_parts):
            result.append(part)
            if i < len(audio_parts) - 1:
                result.append(pause)

        return np.concatenate(result)

    def _split_text_into_chunks(self, text: str) -> list:
        """Split text into smaller chunks at natural break points."""
        import re

        # First try to split on sentence-ending punctuation
        chunks = []
        current = ""

        # Split on commas, semicolons, colons, or natural phrase breaks
        parts = re.split(r'([,;:\-\u2014])\s*', text)

        for i, part in enumerate(parts):
            if not part:
                continue

            # If it's a delimiter, add it to current
            if re.match(r'^[,;:\-\u2014]$', part):
                current += part
                continue

            if len(current) + len(part) <= self.MAX_CHARS_PER_CHUNK:
                current += " " + part if current else part
            else:
                if current:
                    chunks.append(current.strip())
                current = part

        if current:
            chunks.append(current.strip())

        # If we still have chunks that are too long, force-split them
        final_chunks = []
        for chunk in chunks:
            if len(chunk) <= self.MAX_CHARS_PER_CHUNK:
                final_chunks.append(chunk)
            else:
                # Force split at word boundaries
                words = chunk.split()
                current = ""
                for word in words:
                    if len(current) + len(word) + 1 <= self.MAX_CHARS_PER_CHUNK:
                        current += " " + word if current else word
                    else:
                        if current:
                            final_chunks.append(current)
                        current = word
                if current:
                    final_chunks.append(current)

        return final_chunks

    def _normalize(self, audio: np.ndarray) -> np.ndarray:
        """Normalize audio to target dB level."""
        rms = np.sqrt(np.mean(audio ** 2))
        if rms == 0:
            return audio

        current_db = 20 * np.log10(rms)
        gain_db = self.target_db - current_db
        gain = 10 ** (gain_db / 20)

        normalized = audio * gain
        normalized = np.clip(normalized, -1.0, 1.0)

        return normalized

    def generate_chapter_timed(
        self,
        chapter: dict,
        output_dir: Path,
        chapter_num: int,
    ) -> Tuple[Path, List[TimedSegment]]:
        """
        Generate timed audio for a chapter.

        Args:
            chapter: Chapter dict with 'title' and 'text'
            output_dir: Output directory
            chapter_num: Chapter number

        Returns:
            Tuple of (audio path, timed segments)
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        chapter_id = f"ch{chapter_num:02d}"
        output_path = output_dir / f"{chapter_id}.wav"

        logger.step(f"Chapter {chapter_num}: {chapter['title'][:50]}")

        return self.generate_timed_audio(
            chapter["text"],
            output_path,
            chapter_id=chapter_id,
        )


# Alias for drop-in replacement
TimedTTSGenerator = TimedTortoiseTTSGenerator


def generate_with_timing(
    text: str,
    output_path: Path,
    voice: Optional[str] = None,
    preset: str = "fast",
    chapter_id: str = "ch01",
) -> Tuple[Path, List[TimedSegment]]:
    """
    Convenience function to generate audio with timing.

    Args:
        text: Text to convert
        output_path: Output audio path
        voice: Voice to use
        preset: Quality preset
        chapter_id: Chapter identifier

    Returns:
        Tuple of (audio path, timed segments)
    """
    generator = TimedTortoiseTTSGenerator(voice=voice, preset=preset)
    return generator.generate_timed_audio(text, output_path, chapter_id)


if __name__ == "__main__":
    test_text = """
    The Intelligent Investor teaches that successful investing requires
    patience and discipline. Mr. Market is an emotional character who
    offers you prices every day.

    Sometimes Mr. Market is euphoric and offers high prices. Other times
    he is depressed and offers bargains. The intelligent investor takes
    advantage of Mr. Market's mood swings!
    """

    output_path = Path("test_tortoise_timed.wav")
    path, segments = generate_with_timing(test_text, output_path)

    print(f"\nGenerated: {path}")
    print(f"Segments: {len(segments)}")
    for seg in segments:
        print(f"  [{seg.start_time:.2f}-{seg.end_time:.2f}] {seg.text[:50]}...")
