"""
Timing Map Module

Generates and manages timing maps that link audio timestamps to text.
Supports JSON export for web reader synchronization.
"""

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Optional, Dict, Any

from scripts.readalong.sentence_splitter import Sentence
from scripts.readalong.timed_tts import TimedSegment
from scripts.utils import logger


@dataclass
class TimingEntry:
    """Single timing entry linking audio time to text."""

    id: str  # Sentence/segment ID
    start: float  # Start time in seconds
    end: float  # End time in seconds
    text: str  # The text content
    paragraph: int = 0  # Paragraph index

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON export."""
        return {
            "id": self.id,
            "start": round(self.start, 3),
            "end": round(self.end, 3),
            "text": self.text,
            "paragraph": self.paragraph,
        }


@dataclass
class ChapterTiming:
    """Timing data for a single chapter."""

    chapter_id: str
    title: str
    audio_file: str  # Relative path to audio
    duration: float  # Total duration in seconds
    entries: List[TimingEntry] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON export."""
        return {
            "chapterId": self.chapter_id,
            "title": self.title,
            "audioFile": self.audio_file,
            "duration": round(self.duration, 3),
            "entries": [e.to_dict() for e in self.entries],
        }


@dataclass
class BookTimingMap:
    """Complete timing map for an entire book."""

    book_id: str
    title: str
    author: str
    chapters: List[ChapterTiming] = field(default_factory=list)
    total_duration: float = 0.0
    version: str = "1.0"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON export."""
        return {
            "version": self.version,
            "bookId": self.book_id,
            "title": self.title,
            "author": self.author,
            "totalDuration": round(self.total_duration, 3),
            "chapterCount": len(self.chapters),
            "chapters": [ch.to_dict() for ch in self.chapters],
        }

    def save(self, output_path: Path) -> Path:
        """Save timing map to JSON file."""
        output_path = Path(output_path).with_suffix(".json")
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

        logger.success(f"Saved timing map: {output_path}")
        return output_path

    @classmethod
    def load(cls, path: Path) -> "BookTimingMap":
        """Load timing map from JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        chapters = []
        for ch_data in data.get("chapters", []):
            entries = [
                TimingEntry(
                    id=e["id"],
                    start=e["start"],
                    end=e["end"],
                    text=e["text"],
                    paragraph=e.get("paragraph", 0),
                )
                for e in ch_data.get("entries", [])
            ]
            chapters.append(ChapterTiming(
                chapter_id=ch_data["chapterId"],
                title=ch_data["title"],
                audio_file=ch_data["audioFile"],
                duration=ch_data["duration"],
                entries=entries,
            ))

        return cls(
            book_id=data["bookId"],
            title=data["title"],
            author=data["author"],
            chapters=chapters,
            total_duration=data.get("totalDuration", 0),
            version=data.get("version", "1.0"),
        )


class TimingMap:
    """
    Builder class for creating timing maps.

    Processes sentences and timed segments to create
    complete timing information for a book.
    """

    def __init__(
        self,
        book_id: str,
        title: str,
        author: str = "Unknown",
    ):
        """
        Initialize timing map builder.

        Args:
            book_id: Unique book identifier
            title: Book title
            author: Author name
        """
        self.book_map = BookTimingMap(
            book_id=book_id,
            title=title,
            author=author,
        )
        self._current_chapter: Optional[ChapterTiming] = None

    def add_chapter(
        self,
        chapter_id: str,
        title: str,
        audio_file: str,
        duration: float,
    ) -> "TimingMap":
        """
        Start a new chapter.

        Args:
            chapter_id: Chapter identifier
            title: Chapter title
            audio_file: Relative path to audio file
            duration: Total chapter duration

        Returns:
            self for method chaining
        """
        # Save previous chapter if exists
        if self._current_chapter:
            self.book_map.chapters.append(self._current_chapter)
            self.book_map.total_duration += self._current_chapter.duration

        self._current_chapter = ChapterTiming(
            chapter_id=chapter_id,
            title=title,
            audio_file=audio_file,
            duration=duration,
        )
        return self

    def add_entries_from_segments(
        self,
        segments: List[TimedSegment],
        sentences: Optional[List[Sentence]] = None,
    ) -> "TimingMap":
        """
        Add timing entries from timed segments.

        Args:
            segments: List of TimedSegment from TTS
            sentences: Optional list of Sentence for paragraph info

        Returns:
            self for method chaining
        """
        if not self._current_chapter:
            raise ValueError("Must call add_chapter first")

        # Create lookup for sentences
        sentence_lookup = {}
        if sentences:
            sentence_lookup = {s.id: s for s in sentences}

        for segment in segments:
            # Get paragraph from sentence if available
            paragraph = 0
            if segment.sentence_id in sentence_lookup:
                paragraph = sentence_lookup[segment.sentence_id].paragraph_id

            entry = TimingEntry(
                id=segment.sentence_id,
                start=segment.start_time,
                end=segment.end_time,
                text=segment.text,
                paragraph=paragraph,
            )
            self._current_chapter.entries.append(entry)

        return self

    def add_entry(
        self,
        id: str,
        start: float,
        end: float,
        text: str,
        paragraph: int = 0,
    ) -> "TimingMap":
        """
        Add a single timing entry.

        Args:
            id: Entry identifier
            start: Start time in seconds
            end: End time in seconds
            text: The text content
            paragraph: Paragraph index

        Returns:
            self for method chaining
        """
        if not self._current_chapter:
            raise ValueError("Must call add_chapter first")

        entry = TimingEntry(
            id=id,
            start=start,
            end=end,
            text=text,
            paragraph=paragraph,
        )
        self._current_chapter.entries.append(entry)
        return self

    def build(self) -> BookTimingMap:
        """
        Finalize and return the book timing map.

        Returns:
            Complete BookTimingMap
        """
        # Add final chapter
        if self._current_chapter:
            self.book_map.chapters.append(self._current_chapter)
            self.book_map.total_duration += self._current_chapter.duration
            self._current_chapter = None

        return self.book_map

    def save(self, output_path: Path) -> Path:
        """
        Build and save the timing map.

        Args:
            output_path: Output file path

        Returns:
            Path to saved file
        """
        book_map = self.build()
        return book_map.save(output_path)


def create_timing_from_segments(
    segments: List[TimedSegment],
    chapter_id: str,
    chapter_title: str,
    audio_file: str,
) -> ChapterTiming:
    """
    Create chapter timing from timed segments.

    Args:
        segments: List of TimedSegment
        chapter_id: Chapter identifier
        chapter_title: Chapter title
        audio_file: Audio file path

    Returns:
        ChapterTiming object
    """
    entries = []
    duration = 0.0

    for segment in segments:
        entries.append(TimingEntry(
            id=segment.sentence_id,
            start=segment.start_time,
            end=segment.end_time,
            text=segment.text,
        ))
        duration = max(duration, segment.end_time)

    return ChapterTiming(
        chapter_id=chapter_id,
        title=chapter_title,
        audio_file=audio_file,
        duration=duration,
        entries=entries,
    )


if __name__ == "__main__":
    # Test timing map creation
    from scripts.readalong.timed_tts import TimedSegment

    # Create test segments
    segments = [
        TimedSegment("ch01_s0000", "This is the first sentence.", 0.0, 2.5),
        TimedSegment("ch01_s0001", "This is the second sentence.", 2.8, 5.0),
        TimedSegment("ch01_s0002", "And this is the third.", 5.3, 7.0),
    ]

    # Build timing map
    builder = TimingMap(
        book_id="intelligent-investor",
        title="The Intelligent Investor",
        author="Benjamin Graham",
    )

    timing = (
        builder
        .add_chapter("ch01", "Chapter 1: Investment vs. Speculation", "ch01.wav", 7.5)
        .add_entries_from_segments(segments)
        .build()
    )

    print(json.dumps(timing.to_dict(), indent=2))
