"""
Timed TTS Generator

Generates audio with precise timing information for each sentence.
Captures start/end timestamps for Read-Along synchronization.
"""

import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple, Generator

import numpy as np
import soundfile as sf

from scripts.readalong.sentence_splitter import Sentence, SentenceSplitter
from scripts.utils.config import config
from scripts.utils import logger


@dataclass
class TimedSegment:
    """Audio segment with timing information."""

    sentence_id: str  # Links to Sentence.id
    text: str  # The sentence text
    start_time: float  # Start time in seconds
    end_time: float  # End time in seconds
    audio_data: Optional[np.ndarray] = None  # Raw audio (optional)

    @property
    def duration(self) -> float:
        """Get segment duration."""
        return self.end_time - self.start_time


class TimedTTSGenerator:
    """
    Generate audio with per-sentence timing information.

    Processes text sentence by sentence, capturing precise timestamps
    for Read-Along synchronization.
    """

    SAMPLE_RATE = 24000  # Kokoro's native sample rate
    SENTENCE_PAUSE = 0.3  # Pause between sentences (seconds)
    PARAGRAPH_PAUSE = 0.8  # Extra pause between paragraphs (seconds)

    def __init__(
        self,
        voice: Optional[str] = None,
        speed: Optional[float] = None,
        normalize_audio: bool = True,
        target_db: float = -20.0,
    ):
        """
        Initialize the timed TTS generator.

        Args:
            voice: Voice to use (default from config)
            speed: Speech speed multiplier
            normalize_audio: Whether to normalize audio levels
            target_db: Target dB level for normalization
        """
        self.voice = voice or config.voice
        self.speed = speed or config.voice_speed
        self.normalize_audio = normalize_audio
        self.target_db = target_db

        # Lazy load pipeline
        self._pipeline = None

    def _get_pipeline(self):
        """Lazy load Kokoro pipeline."""
        if self._pipeline is None:
            try:
                from kokoro import KPipeline

                # Determine language from voice prefix
                lang_code = "a" if self.voice.startswith("a") else "b"

                logger.info(f"Loading Kokoro TTS (voice: {self.voice})...")
                self._pipeline = KPipeline(lang_code=lang_code)
                logger.success("Kokoro TTS loaded")

            except ImportError as e:
                logger.error("Kokoro not installed")
                raise RuntimeError(
                    "Kokoro not found. Install with: pip install kokoro>=0.3.0"
                ) from e

        return self._pipeline

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
        output_path = Path(output_path).with_suffix(".wav")
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Split text into sentences
        splitter = SentenceSplitter(chapter_id)
        sentences = splitter.split(text)

        if not sentences:
            raise ValueError("No sentences found in text")

        logger.info(f"Processing {len(sentences)} sentences...")

        # Generate audio for each sentence
        timed_segments = []
        all_audio = []
        current_time = 0.0
        last_paragraph = -1

        pipeline = self._get_pipeline()

        for i, sentence in enumerate(sentences):
            if show_progress and (i + 1) % 10 == 0:
                logger.info(f"  Sentence {i + 1}/{len(sentences)}...")

            # Add paragraph pause if new paragraph
            if sentence.paragraph_id != last_paragraph and last_paragraph != -1:
                pause_samples = int(self.PARAGRAPH_PAUSE * self.SAMPLE_RATE)
                all_audio.append(np.zeros(pause_samples, dtype=np.float32))
                current_time += self.PARAGRAPH_PAUSE

            last_paragraph = sentence.paragraph_id

            # Generate audio for this sentence
            try:
                audio_data = self._generate_sentence_audio(
                    sentence.text, pipeline
                )
            except Exception as e:
                logger.warning(f"Failed to generate audio for sentence {i}: {e}")
                # Use silence as fallback
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

    def _generate_sentence_audio(
        self,
        text: str,
        pipeline,
    ) -> np.ndarray:
        """Generate audio for a single sentence."""
        audio_segments = []

        for gs, ps, audio in pipeline(text, voice=self.voice, speed=self.speed):
            if audio is not None and len(audio) > 0:
                audio_segments.append(audio)

        if not audio_segments:
            # Return minimal silence if generation failed
            return np.zeros(int(0.1 * self.SAMPLE_RATE), dtype=np.float32)

        return np.concatenate(audio_segments)

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


def generate_with_timing(
    text: str,
    output_path: Path,
    voice: Optional[str] = None,
    chapter_id: str = "ch01",
) -> Tuple[Path, List[TimedSegment]]:
    """
    Convenience function to generate audio with timing.

    Args:
        text: Text to convert
        output_path: Output audio path
        voice: Voice to use
        chapter_id: Chapter identifier

    Returns:
        Tuple of (audio path, timed segments)
    """
    generator = TimedTTSGenerator(voice=voice)
    return generator.generate_timed_audio(text, output_path, chapter_id)


if __name__ == "__main__":
    # Test the timed TTS generator
    test_text = """
    The Intelligent Investor teaches that successful investing requires
    patience and discipline. Mr. Market is an emotional character who
    offers you prices every day.

    Sometimes Mr. Market is euphoric and offers high prices. Other times
    he is depressed and offers bargains. The intelligent investor takes
    advantage of Mr. Market's mood swings!
    """

    from pathlib import Path
    output_path = Path("test_timed.wav")

    path, segments = generate_with_timing(test_text, output_path)

    print(f"\nGenerated: {path}")
    print(f"Segments: {len(segments)}")
    for seg in segments:
        print(f"  [{seg.start_time:.2f}-{seg.end_time:.2f}] {seg.text[:50]}...")
