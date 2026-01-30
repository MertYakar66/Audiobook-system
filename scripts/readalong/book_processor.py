"""
Book Processor Module

Orchestrates the complete Read-Along book processing pipeline.
Converts books to synchronized audio-text format with timing maps.
"""

import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Dict, Any

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


class BookProcessor:
    """
    Complete Read-Along book processor.

    Handles the full pipeline:
    1. Extract text from PDF/DOCX/TXT
    2. Clean and prepare text
    3. Split into chapters and sentences
    4. Generate timed audio for each sentence
    5. Create timing maps
    6. Package for web reader
    """

    def __init__(
        self,
        voice: Optional[str] = None,
        speed: Optional[float] = None,
    ):
        """
        Initialize book processor.

        Args:
            voice: TTS voice to use
            speed: Speech speed multiplier
        """
        self.voice = voice or config.voice
        self.speed = speed or config.voice_speed
        self.tts = TimedTTSGenerator(voice=self.voice, speed=self.speed)
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
    ) -> ProcessedBook:
        """
        Process a complete book for Read-Along.

        Args:
            input_path: Path to PDF, DOCX, or TXT file
            output_dir: Output directory (auto-generated if not provided)
            title: Override book title
            author: Override author name
            skip_chapters: Chapter numbers to skip

        Returns:
            ProcessedBook with all data and paths
        """
        input_path = Path(input_path)
        skip_chapters = skip_chapters or []

        logger.header(f"Processing: {input_path.name}")

        # Step 1: Extract text
        logger.step("Extracting text", 1, 6)
        text = self._extract_text(input_path)
        logger.info(f"Extracted {len(text):,} characters")

        # Step 2: Get metadata
        logger.step("Processing metadata", 2, 6)
        metadata = self._get_metadata(input_path, text)
        book_title = title or metadata.get("title", input_path.stem)
        book_author = author or metadata.get("author", "Unknown Author")
        logger.info(f"Title: {book_title}")
        logger.info(f"Author: {book_author}")

        # Step 3: Clean text
        logger.step("Cleaning text", 3, 6)
        text = self.cleaner.clean(text)
        logger.info(f"Cleaned: {len(text):,} characters")

        # Step 4: Detect chapters
        logger.step("Detecting chapters", 4, 6)
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

            logger.info(f"Chapter {i}/{len(chapters)}: {chapter['title'][:50]}")

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
        )
        manifest_path = output_dir / "manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)

        # Save full text for reader
        text_path = output_dir / "text.json"
        self._save_text_data(processed_chapters, text_path)

        total_duration = sum(ch.duration for ch in processed_chapters)

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
            show_progress=False,
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
    ) -> Dict[str, Any]:
        """Create book manifest for web reader."""
        return {
            "version": "1.0",
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
            },
        }

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
    title: Optional[str] = None,
    author: Optional[str] = None,
) -> ProcessedBook:
    """
    Convenience function to process a book for Read-Along.

    Args:
        input_path: Path to input file (PDF, DOCX, TXT)
        output_dir: Output directory
        voice: TTS voice to use
        title: Override book title
        author: Override author name

    Returns:
        ProcessedBook result
    """
    processor = BookProcessor(voice=voice)
    return processor.process_book(
        input_path,
        output_dir=output_dir,
        title=title,
        author=author,
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
