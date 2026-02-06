"""
Timed TTS Generator using edge-tts

Generates audio with timing information for each sentence.
Uses Microsoft Edge's neural TTS voices via edge-tts.

Fast and high-quality - best balance of speed and quality.
"""

import asyncio
import os
import tempfile
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


# Good English voices from Edge TTS
EDGE_VOICES = {
    "male": "en-US-GuyNeural",
    "female": "en-US-JennyNeural",
    "british_male": "en-GB-RyanNeural",
    "british_female": "en-GB-SoniaNeural",
    "narrator": "en-US-DavisNeural",  # Good for audiobooks
}

DEFAULT_VOICE = "en-US-DavisNeural"  # Natural male narrator voice


class TimedEdgeTTSGenerator:
    """
    Generate audio with per-sentence timing using edge-tts.

    This uses Microsoft's neural TTS voices via edge-tts.
    High quality and very fast.
    """

    SAMPLE_RATE = 24000  # Edge TTS uses 24kHz
    SENTENCE_PAUSE = 0.3
    PARAGRAPH_PAUSE = 0.8

    def __init__(
        self,
        voice: Optional[str] = None,
        speed: Optional[float] = None,
        preset: str = "fast",  # Ignored for edge-tts
        normalize_audio: bool = True,
        target_db: float = -20.0,
        voices_dir: Optional[Path] = None,  # Ignored for edge-tts
    ):
        """
        Initialize the timed edge TTS generator.

        Args:
            voice: Voice ID to use (e.g., "en-US-GuyNeural")
            speed: Speech speed multiplier (0.5 to 2.0)
            preset: Ignored (for Tortoise compatibility)
            normalize_audio: Whether to normalize audio levels
            target_db: Target dB level for normalization
            voices_dir: Ignored (for Tortoise compatibility)
        """
        # Handle voice name mapping
        if voice and voice.lower() in EDGE_VOICES:
            self.voice = EDGE_VOICES[voice.lower()]
        else:
            self.voice = voice or DEFAULT_VOICE

        self.speed = speed or config.voice_speed
        self.preset = preset
        self.normalize_audio = normalize_audio
        self.target_db = target_db

        self._edge_tts = None

    def _get_rate_string(self) -> str:
        """Convert speed multiplier to edge-tts rate string."""
        # Speed 1.0 = +0%, 0.5 = -50%, 2.0 = +100%
        percentage = int((self.speed - 1.0) * 100)
        if percentage >= 0:
            return f"+{percentage}%"
        else:
            return f"{percentage}%"

    async def _generate_audio_async(self, text: str, output_path: str) -> bool:
        """Generate audio for text using edge-tts asynchronously."""
        try:
            import edge_tts

            rate = self._get_rate_string()
            communicate = edge_tts.Communicate(text, self.voice, rate=rate)
            await communicate.save(output_path)
            return True
        except Exception as e:
            logger.warning(f"Edge TTS generation failed: {e}")
            return False

    def _generate_audio_sync(self, text: str, output_path: str) -> bool:
        """Synchronous wrapper for audio generation."""
        try:
            # Try to get existing event loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're in an async context, create a new thread
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        self._generate_audio_async(text, output_path)
                    )
                    return future.result()
            else:
                return loop.run_until_complete(
                    self._generate_audio_async(text, output_path)
                )
        except RuntimeError:
            # No event loop, create one
            return asyncio.run(self._generate_audio_async(text, output_path))

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

        logger.info(f"Processing {len(sentences)} sentences with Edge TTS...")

        # Generate audio for each sentence
        timed_segments = []
        all_audio = []
        current_time = 0.0
        last_paragraph = -1

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
                audio_data = self._generate_sentence_audio(sentence.text)
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

    def _generate_sentence_audio(self, text: str) -> np.ndarray:
        """Generate audio for a single sentence using edge-tts."""
        # Create temp file for audio output
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            # Generate audio to file
            success = self._generate_audio_sync(text, tmp_path)

            if success and os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 0:
                # Load the audio (edge-tts outputs MP3)
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
TimedTTSGenerator = TimedEdgeTTSGenerator


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
    generator = TimedEdgeTTSGenerator(voice=voice)
    return generator.generate_timed_audio(text, output_path, chapter_id)


def list_voices():
    """List available edge-tts voices."""
    print("\nBuilt-in voice shortcuts:")
    for name, voice_id in EDGE_VOICES.items():
        print(f"  {name}: {voice_id}")
    print(f"\nDefault: {DEFAULT_VOICE}")
    print("\nFor full list, run: edge-tts --list-voices")


if __name__ == "__main__":
    test_text = """
    The Intelligent Investor teaches that successful investing requires
    patience and discipline. Mr. Market is an emotional character who
    offers you prices every day.

    Sometimes Mr. Market is euphoric and offers high prices. Other times
    he is depressed and offers bargains. The intelligent investor takes
    advantage of Mr. Market's mood swings!
    """

    print("Edge TTS Test")
    print("=" * 50)
    list_voices()

    output_path = Path("test_edge_timed.wav")
    path, segments = generate_with_timing(test_text, output_path)

    print(f"\nGenerated: {path}")
    print(f"Segments: {len(segments)}")
    for seg in segments:
        print(f"  [{seg.start_time:.2f}-{seg.end_time:.2f}] {seg.text[:50]}...")
