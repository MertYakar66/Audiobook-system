"""
Timed TTS Generator using pyttsx3

Generates audio with timing information for each sentence.
Uses pyttsx3 (system TTS) as a fallback when Tortoise is not available.

Lower quality than Tortoise but works reliably across systems.
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


class TimedPyttsx3TTSGenerator:
    """
    Generate audio with per-sentence timing using pyttsx3.

    This is a fallback TTS that uses system voices.
    Lower quality than Tortoise but reliable and fast.
    """

    SAMPLE_RATE = 22050  # pyttsx3 typically uses 22050
    SENTENCE_PAUSE = 0.3
    PARAGRAPH_PAUSE = 0.8

    def __init__(
        self,
        voice: Optional[str] = None,
        speed: Optional[float] = None,
        preset: str = "fast",  # Ignored for pyttsx3
        normalize_audio: bool = True,
        target_db: float = -20.0,
        voices_dir: Optional[Path] = None,  # Ignored for pyttsx3
    ):
        """
        Initialize the timed pyttsx3 TTS generator.

        Args:
            voice: Voice ID to use (system voice)
            speed: Speech speed multiplier
            preset: Ignored (for Tortoise compatibility)
            normalize_audio: Whether to normalize audio levels
            target_db: Target dB level for normalization
            voices_dir: Ignored (for Tortoise compatibility)
        """
        self.voice = voice
        self.speed = speed or config.voice_speed
        self.preset = preset
        self.normalize_audio = normalize_audio
        self.target_db = target_db

        self._engine = None

    def _get_engine(self):
        """Lazy load pyttsx3 engine."""
        if self._engine is None:
            try:
                import pyttsx3

                logger.info("Loading pyttsx3 TTS engine...")
                self._engine = pyttsx3.init()

                # Set voice if specified
                if self.voice:
                    voices = self._engine.getProperty('voices')
                    for v in voices:
                        if self.voice.lower() in v.id.lower() or self.voice.lower() in v.name.lower():
                            self._engine.setProperty('voice', v.id)
                            break

                # Set speed (default is 200 words per minute)
                base_rate = 200
                self._engine.setProperty('rate', int(base_rate * self.speed))

                logger.success("pyttsx3 TTS loaded")

            except ImportError as e:
                logger.error("pyttsx3 not installed")
                raise RuntimeError(
                    "pyttsx3 not found. Install with: pip install pyttsx3"
                ) from e

        return self._engine

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

        logger.info(f"Processing {len(sentences)} sentences with pyttsx3 TTS...")

        # Generate audio for each sentence
        timed_segments = []
        all_audio = []
        current_time = 0.0
        last_paragraph = -1

        engine = self._get_engine()

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
                audio_data = self._generate_sentence_audio(sentence.text, engine)
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

    def _generate_sentence_audio(self, text: str, engine) -> np.ndarray:
        """Generate audio for a single sentence using pyttsx3."""
        import tempfile
        import os

        # Create temp file for audio output
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            # Generate audio to file
            engine.save_to_file(text, tmp_path)
            engine.runAndWait()

            # Load the audio
            if os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 0:
                audio_data, sr = sf.read(tmp_path)

                # Resample if necessary
                if sr != self.SAMPLE_RATE:
                    from scipy import signal
                    samples = int(len(audio_data) * self.SAMPLE_RATE / sr)
                    audio_data = signal.resample(audio_data, samples)

                # Convert to mono if stereo
                if len(audio_data.shape) > 1:
                    audio_data = audio_data.mean(axis=1)

                return audio_data.astype(np.float32)
            else:
                # Return silence if generation failed
                return np.zeros(int(0.5 * self.SAMPLE_RATE), dtype=np.float32)

        finally:
            # Clean up temp file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

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


# Alias for compatibility
TimedTTSGenerator = TimedPyttsx3TTSGenerator


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
        preset: Ignored (for compatibility)
        chapter_id: Chapter identifier

    Returns:
        Tuple of (audio path, timed segments)
    """
    generator = TimedPyttsx3TTSGenerator(voice=voice)
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

    output_path = Path("test_pyttsx3_timed.wav")
    path, segments = generate_with_timing(test_text, output_path)

    print(f"\nGenerated: {path}")
    print(f"Segments: {len(segments)}")
    for seg in segments:
        print(f"  [{seg.start_time:.2f}-{seg.end_time:.2f}] {seg.text[:50]}...")
