"""
Book Processor Module - Enhanced Edition

Orchestrates the complete Read-Along book processing pipeline.
Converts books to synchronized audio-text format with timing maps.

Now uses Tortoise TTS for high-quality, natural speech with voice cloning.

Features:
- Resume interrupted processing from last completed chapter
- Progress state persistence
- Memory-optimized batch processing
- GPU acceleration support
- Voice cloning from custom audio samples
- Quality presets (ultra_fast, fast, standard, high_quality)
"""

import gc
import json
import os
import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple

from scripts.clean_text import TextCleaner, ChapterDetector
from scripts.extract_text import PDFExtractor
from scripts.metadata import MetadataExtractor, CoverArtHandler
from scripts.readalong.sentence_splitter import SentenceSplitter, Sentence
from scripts.readalong.timed_tts import TimedTTSGenerator, TimedSegment
from scripts.readalong.timing_map import TimingMap, BookTimingMap, ChapterTiming
from scripts.utils.config import config
from scripts.utils import logger


@dataclass
class ProcessedChapter:
    """Result of processing a single chapter."""

    chapter_id: str
    title: str
    audio_path: Path
    duration: float
    sentences: List[Sentence]
    segments: List[TimedSegment]
    text: str


@dataclass
class ProcessedBook:
    """Result of processing a complete book."""

    book_id: str
    title: str
    author: str
    cover_path: Optional[Path]
    chapters: List[ProcessedChapter]
    timing_map: BookTimingMap
    output_dir: Path
    total_duration: float
    source_file: Optional[Path] = None


@dataclass
class ProcessingState:
    """Tracks processing progress for resume capability."""

    book_id: str
    title: str
    author: str
    source_file: str
    total_chapters: int
    completed_chapters: List[int] = field(default_factory=list)
    chapter_data: Dict[str, Any] = field(default_factory=dict)
    started_at: str = ""
    last_updated: str = ""
    voice: str = "train_dotrice"
    speed: float = 1.0
    preset: str = "fast"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "book_id": self.book_id,
            "title": self.title,
            "author": self.author,
            "source_file": self.source_file,
            "total_chapters": self.total_chapters,
            "completed_chapters": self.completed_chapters,
            "chapter_data": self.chapter_data,
            "started_at": self.started_at,
            "last_updated": self.last_updated,
            "voice": self.voice,
            "speed": self.speed,
            "preset": self.preset,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProcessingState":
        return cls(
            book_id=data["book_id"],
            title=data["title"],
            author=data["author"],
            source_file=data["source_file"],
            total_chapters=data["total_chapters"],
            completed_chapters=data.get("completed_chapters", []),
            chapter_data=data.get("chapter_data", {}),
            started_at=data.get("started_at", ""),
            last_updated=data.get("last_updated", ""),
            voice=data.get("voice", "train_dotrice"),
            speed=data.get("speed", 1.0),
            preset=data.get("preset", "fast"),
        )

    def save(self, path: Path) -> None:
        self.last_updated = datetime.now().isoformat()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, path: Path) -> Optional["ProcessingState"]:
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return cls.from_dict(json.load(f))
        except Exception:
            return None


class BookProcessor:
    """
    Complete Read-Along book processor with enhanced features.

    Handles the full pipeline:
    1. Extract text from PDF/DOCX/TXT
    2. Clean and prepare text
    3. Split into chapters and sentences
    4. Generate timed audio for each sentence
    5. Create timing maps
    6. Package for web reader

    Enhanced features:
    - Resume from interrupted processing
    - Progress persistence
    - Memory optimization
    """

    STATE_FILE = "processing_state.json"

    def __init__(
        self,
        voice: Optional[str] = None,
        speed: Optional[float] = None,
        preset: Optional[str] = None,
    ):
        """
        Initialize book processor.

        Args:
            voice: TTS voice to use (built-in or custom)
            speed: Speech speed multiplier
            preset: TTS quality preset (ultra_fast, fast, standard, high_quality)
        """
        self.voice = voice or config.voice
        self.speed = speed or config.voice_speed
        self.preset = preset or config.voice_preset
        self.tts = TimedTTSGenerator(
            voice=self.voice,
            speed=self.speed,
            preset=self.preset,
        )
        self.cleaner = TextCleaner()
        self.chapter_detector = ChapterDetector()
        self.metadata_extractor = MetadataExtractor()
        self.cover_handler = CoverArtHandler()

    def process_book(
        self,
        input_path: Path,
        output_dir: Optional[Path] = None,
        title: Optional[str] = None,
        author: Optional[str] = None,
        skip_chapters: Optional[List[int]] = None,
        resume: bool = True,
    ) -> ProcessedBook:
        """
        Process a complete book for Read-Along.

        Args:
            input_path: Path to PDF, DOCX, or TXT file
            output_dir: Output directory (auto-generated if not provided)
            title: Override book title
            author: Override author name
            skip_chapters: Chapter numbers to skip
            resume: Resume from previous progress if available

        Returns:
            ProcessedBook with all data and paths
        """
        input_path = Path(input_path)
        skip_chapters = skip_chapters or []

        logger.header(f"Processing: {input_path.name}")

        # Step 1: Extract text
        logger.step("Extracting text", 1, 7)
        text = self._extract_text(input_path)
        logger.info(f"Extracted {len(text):,} characters")

        # Step 2: Get metadata
        logger.step("Processing metadata", 2, 7)
        metadata = self._get_metadata(input_path, text)
        book_title = title or metadata.get("title", input_path.stem)
        book_author = author or metadata.get("author", "Unknown Author")
        logger.info(f"Title: {book_title}")
        logger.info(f"Author: {book_author}")

        # Step 3: Clean text
        logger.step("Cleaning text", 3, 7)
        text = self.cleaner.clean(text)
        logger.info(f"Cleaned: {len(text):,} characters")

        # Step 4: Detect chapters
        logger.step("Detecting chapters", 4, 7)
        chapters = self.chapter_detector.split_into_chapters(text)
        logger.info(f"Found {len(chapters)} chapters")

        # Setup output directory
        book_id = self._create_book_id(book_title)
        if output_dir is None:
            output_dir = config.get_path("output") / "readalong" / book_id
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        audio_dir = output_dir / "audio"
        audio_dir.mkdir(exist_ok=True)

        # Check for existing progress (resume capability)
        state_path = output_dir / self.STATE_FILE
        state = None
        completed_chapters = []

        if resume:
            state = ProcessingState.load(state_path)
            if state and state.source_file == str(input_path):
                completed_chapters = state.completed_chapters
                if completed_chapters:
                    logger.info(f"Resuming: {len(completed_chapters)} chapters already complete")
            else:
                state = None

        # Create new state if needed
        if state is None:
            state = ProcessingState(
                book_id=book_id,
                title=book_title,
                author=book_author,
                source_file=str(input_path),
                total_chapters=len(chapters),
                started_at=datetime.now().isoformat(),
                voice=self.voice,
                speed=self.speed,
                preset=self.preset,
            )
            state.save(state_path)

        # Step 5: Process each chapter
        logger.step("Generating audio with timing", 5, 6)
        processed_chapters = []
        timing_builder = TimingMap(
            book_id=book_id,
            title=book_title,
            author=book_author,
        )

        for i, chapter in enumerate(chapters, 1):
            if i in skip_chapters:
                logger.info(f"Skipping chapter {i}")
                continue

            # Check if already processed (resume)
            if i in completed_chapters:
                logger.info(f"Chapter {i}/{len(chapters)}: {chapter['title'][:40]}... [CACHED]")
                # Load from state
                if str(i) in state.chapter_data:
                    ch_data = state.chapter_data[str(i)]
                    audio_path = Path(ch_data["audio_path"])

                    # Reconstruct processed chapter from state
                    splitter = SentenceSplitter(f"ch{i:02d}")
                    sentences = splitter.split(chapter["text"])

                    # Create minimal segments from stored timing
                    segments = []
                    for entry in ch_data.get("timing_entries", []):
                        segments.append(TimedSegment(
                            sentence_id=entry["id"],
                            text=entry["text"],
                            start_time=entry["start"],
                            end_time=entry["end"],
                        ))

                    processed = ProcessedChapter(
                        chapter_id=f"ch{i:02d}",
                        title=chapter["title"],
                        audio_path=audio_path,
                        duration=ch_data["duration"],
                        sentences=sentences,
                        segments=segments,
                        text=chapter["text"],
                    )
                    processed_chapters.append(processed)

                    # Add to timing map
                    audio_relative = f"audio/{audio_path.name}"
                    timing_builder.add_chapter(
                        chapter_id=processed.chapter_id,
                        title=processed.title,
                        audio_file=audio_relative,
                        duration=processed.duration,
                    )
                    timing_builder.add_entries_from_segments(
                        processed.segments,
                        processed.sentences,
                    )
                continue

            logger.info(f"Chapter {i}/{len(chapters)}: {chapter['title'][:40]}...")

            try:
                processed = self._process_chapter(
                    chapter=chapter,
                    chapter_num=i,
                    audio_dir=audio_dir,
                )
                processed_chapters.append(processed)

                # Add to timing map
                audio_relative = f"audio/{processed.audio_path.name}"
                timing_builder.add_chapter(
                    chapter_id=processed.chapter_id,
                    title=processed.title,
                    audio_file=audio_relative,
                    duration=processed.duration,
                )
                timing_builder.add_entries_from_segments(
                    processed.segments,
                    processed.sentences,
                )

                # Save progress
                state.completed_chapters.append(i)
                state.chapter_data[str(i)] = {
                    "audio_path": str(processed.audio_path),
                    "duration": processed.duration,
                    "timing_entries": [
                        {"id": s.sentence_id, "text": s.text, "start": s.start_time, "end": s.end_time}
                        for s in processed.segments
                    ],
                }
                state.save(state_path)

                # Memory cleanup after each chapter
                gc.collect()

            except Exception as e:
                logger.error(f"Failed to process chapter {i}: {e}")
                # Save progress before failing
                state.save(state_path)
                raise

        # Build timing map
        timing_map = timing_builder.build()

        # Step 6: Package output
        logger.step("Packaging output", 6, 6)

        # Save timing map
        timing_path = output_dir / "timing.json"
        timing_map.save(timing_path)

        # Extract/create cover
        cover_path = self._get_cover(input_path, output_dir, book_title, book_author)

        # Create book manifest
        manifest = self._create_manifest(
            book_id=book_id,
            title=book_title,
            author=book_author,
            chapters=processed_chapters,
            timing_map=timing_map,
            cover_path=cover_path,
            output_dir=output_dir,
            source_file=input_path,
        )
        manifest_path = output_dir / "manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)

        # Save full text for reader
        text_path = output_dir / "text.json"
        self._save_text_data(processed_chapters, text_path)

        # Copy source file for reference
        source_copy = output_dir / f"source{input_path.suffix}"
        if not source_copy.exists():
            try:
                shutil.copy2(input_path, source_copy)
            except Exception:
                pass  # Non-critical

        total_duration = sum(ch.duration for ch in processed_chapters)

        # Clean up state file on successful completion
        if len(processed_chapters) == len(chapters):
            state_path.unlink(missing_ok=True)

        logger.header("Processing Complete!")
        logger.success(f"Output: {output_dir}")
        logger.info(f"Duration: {self._format_duration(total_duration)}")
        logger.info(f"Chapters: {len(processed_chapters)}")

        return ProcessedBook(
            book_id=book_id,
            title=book_title,
            author=book_author,
            cover_path=cover_path,
            chapters=processed_chapters,
            timing_map=timing_map,
            output_dir=output_dir,
            total_duration=total_duration,
            source_file=input_path,
        )

    def _extract_text(self, path: Path) -> str:
        """Extract text from input file."""
        suffix = path.suffix.lower()

        if suffix == ".pdf":
            with PDFExtractor(path) as extractor:
                return extractor.extract_all()

        elif suffix == ".docx":
            try:
                import docx
                doc = docx.Document(path)
                return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())
            except ImportError:
                raise RuntimeError("python-docx required for DOCX files")

        elif suffix == ".txt":
            return path.read_text(encoding="utf-8")

        else:
            raise ValueError(f"Unsupported file type: {suffix}")

    def _get_metadata(self, path: Path, text: str) -> Dict[str, str]:
        """Extract metadata from source."""
        if path.suffix.lower() == ".pdf":
            return self.metadata_extractor.extract_from_pdf(path)
        return self.metadata_extractor.extract_from_text(text, str(path))

    def _process_chapter(
        self,
        chapter: dict,
        chapter_num: int,
        audio_dir: Path,
    ) -> ProcessedChapter:
        """Process a single chapter."""
        chapter_id = f"ch{chapter_num:02d}"

        # Split into sentences
        splitter = SentenceSplitter(chapter_id)
        sentences = splitter.split(chapter["text"])

        # Generate timed audio
        audio_path = audio_dir / f"{chapter_id}.wav"
        _, segments = self.tts.generate_timed_audio(
            chapter["text"],
            audio_path,
            chapter_id=chapter_id,
            show_progress=True,
        )

        # Calculate duration
        duration = segments[-1].end_time if segments else 0.0

        return ProcessedChapter(
            chapter_id=chapter_id,
            title=chapter["title"],
            audio_path=audio_path,
            duration=duration,
            sentences=sentences,
            segments=segments,
            text=chapter["text"],
        )

    def _get_cover(
        self,
        input_path: Path,
        output_dir: Path,
        title: str,
        author: str,
    ) -> Optional[Path]:
        """Extract or create cover image."""
        cover_path = output_dir / "cover.jpg"

        if input_path.suffix.lower() == ".pdf":
            try:
                extracted = self.cover_handler.extract_from_pdf(input_path, cover_path)
                if extracted:
                    return self.cover_handler.process_cover(extracted, cover_path)
            except Exception as e:
                logger.warning(f"Could not extract cover: {e}")

        # Create placeholder
        return self.cover_handler.create_placeholder_cover(
            title, author, cover_path
        )

    def _create_manifest(
        self,
        book_id: str,
        title: str,
        author: str,
        chapters: List[ProcessedChapter],
        timing_map: BookTimingMap,
        cover_path: Optional[Path],
        output_dir: Path,
        source_file: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """Create book manifest for web reader."""
        manifest = {
            "version": "2.0",
            "bookId": book_id,
            "title": title,
            "author": author,
            "cover": "cover.jpg" if cover_path else None,
            "timing": "timing.json",
            "text": "text.json",
            "totalDuration": timing_map.total_duration,
            "chapterCount": len(chapters),
            "chapters": [
                {
                    "id": ch.chapter_id,
                    "title": ch.title,
                    "duration": ch.duration,
                    "sentenceCount": len(ch.sentences),
                }
                for ch in chapters
            ],
            "generated": {
                "voice": self.voice,
                "speed": self.speed,
                "preset": self.preset,
                "tts_engine": "tortoise",
                "timestamp": datetime.now().isoformat(),
            },
        }

        # Add source file info
        if source_file:
            manifest["sourceFile"] = f"source{source_file.suffix}"
            manifest["sourceFormat"] = source_file.suffix.lower().lstrip(".")

        return manifest

    def _save_text_data(
        self,
        chapters: List[ProcessedChapter],
        output_path: Path,
    ) -> None:
        """Save text data for web reader."""
        text_data = {
            "chapters": []
        }

        for chapter in chapters:
            chapter_data = {
                "id": chapter.chapter_id,
                "title": chapter.title,
                "paragraphs": [],
            }

            # Group sentences by paragraph
            current_para = -1
            current_sentences = []

            for sentence in chapter.sentences:
                if sentence.paragraph_id != current_para:
                    if current_sentences:
                        chapter_data["paragraphs"].append({
                            "id": f"{chapter.chapter_id}_p{current_para:03d}",
                            "sentences": current_sentences,
                        })
                    current_para = sentence.paragraph_id
                    current_sentences = []

                current_sentences.append({
                    "id": sentence.id,
                    "text": sentence.text,
                })

            # Add final paragraph
            if current_sentences:
                chapter_data["paragraphs"].append({
                    "id": f"{chapter.chapter_id}_p{current_para:03d}",
                    "sentences": current_sentences,
                })

            text_data["chapters"].append(chapter_data)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(text_data, f, indent=2, ensure_ascii=False)

    def _create_book_id(self, title: str) -> str:
        """Create URL-safe book ID from title."""
        # Remove special characters, lowercase, replace spaces with hyphens
        book_id = re.sub(r"[^\w\s-]", "", title.lower())
        book_id = re.sub(r"\s+", "-", book_id)
        book_id = re.sub(r"-+", "-", book_id)
        return book_id[:50].strip("-")

    def _format_duration(self, seconds: float) -> str:
        """Format duration as human-readable string."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)

        if hours > 0:
            return f"{hours}h {minutes}m {secs}s"
        return f"{minutes}m {secs}s"


def process_readalong(
    input_path: Path,
    output_dir: Optional[Path] = None,
    voice: Optional[str] = None,
    preset: Optional[str] = None,
    title: Optional[str] = None,
    author: Optional[str] = None,
    resume: bool = True,
) -> ProcessedBook:
    """
    Convenience function to process a book for Read-Along.

    Args:
        input_path: Path to input file (PDF, DOCX, TXT)
        output_dir: Output directory
        voice: TTS voice to use
        preset: TTS quality preset (ultra_fast, fast, standard, high_quality)
        title: Override book title
        author: Override author name
        resume: Resume from previous progress if available

    Returns:
        ProcessedBook result
    """
    processor = BookProcessor(voice=voice, preset=preset)
    return processor.process_book(
        input_path,
        output_dir=output_dir,
        title=title,
        author=author,
        resume=resume,
    )


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python book_processor.py <input_file> [output_dir]")
        sys.exit(1)

    input_file = Path(sys.argv[1])
    output = Path(sys.argv[2]) if len(sys.argv) > 2 else None

    result = process_readalong(input_file, output)
    print(f"\nProcessed: {result.title}")
    print(f"Output: {result.output_dir}")
    print(f"Duration: {result.total_duration:.1f}s")
