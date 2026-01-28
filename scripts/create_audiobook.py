"""
Audiobook Creation Module

Creates .m4b audiobook files with embedded chapters, metadata, and cover art.
Uses FFmpeg for audio encoding and chapter embedding.
"""

import json
import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from scripts.utils.config import config
from scripts.utils import logger


@dataclass
class Chapter:
    """Represents a chapter in an audiobook."""

    number: int
    title: str
    start_time: float  # In seconds
    end_time: float  # In seconds
    audio_file: Optional[Path] = None

    @property
    def duration(self) -> float:
        """Get chapter duration in seconds."""
        return self.end_time - self.start_time


@dataclass
class AudiobookMetadata:
    """Metadata for an audiobook."""

    title: str
    author: str
    narrator: str = ""
    year: str = ""
    genre: str = "Audiobook"
    description: str = ""
    copyright: str = ""
    cover_path: Optional[Path] = None

    def __post_init__(self):
        if not self.narrator:
            self.narrator = config.get("metadata", "narrator", default="AI Narrator")
        if not self.genre:
            self.genre = config.get("metadata", "genre", default="Audiobook")
        if not self.copyright:
            self.copyright = config.get("metadata", "copyright", default="Personal Use")


@dataclass
class Audiobook:
    """Represents a complete audiobook."""

    metadata: AudiobookMetadata
    chapters: List[Chapter] = field(default_factory=list)
    audio_files: List[Path] = field(default_factory=list)

    def add_chapter(
        self,
        title: str,
        audio_file: Path,
        duration: float,
    ) -> None:
        """Add a chapter to the audiobook."""
        start_time = 0.0 if not self.chapters else self.chapters[-1].end_time

        # Add pause between chapters
        pause = config.get("chapters", "pause_between", default=1.5)
        if self.chapters:
            start_time += pause

        chapter = Chapter(
            number=len(self.chapters) + 1,
            title=title,
            start_time=start_time,
            end_time=start_time + duration,
            audio_file=audio_file,
        )

        self.chapters.append(chapter)
        self.audio_files.append(audio_file)

    @property
    def total_duration(self) -> float:
        """Get total audiobook duration in seconds."""
        if not self.chapters:
            return 0.0
        return self.chapters[-1].end_time


class M4BCreator:
    """Creates M4B audiobook files with chapters and metadata."""

    def __init__(self):
        self.bitrate = config.m4b_bitrate
        self.channels = config.get("audio", "m4b", "channels", default=1)
        self.sample_rate = config.sample_rate

        # Verify ffmpeg is available
        self._verify_ffmpeg()

    def _verify_ffmpeg(self) -> None:
        """Verify FFmpeg is installed."""
        try:
            subprocess.run(
                ["ffmpeg", "-version"],
                capture_output=True,
                check=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.error(
                "FFmpeg not found. Please install FFmpeg: "
                "https://ffmpeg.org/download.html"
            )
            raise RuntimeError("FFmpeg is required but not installed")

    def create_m4b(
        self,
        audiobook: Audiobook,
        output_path: Path,
    ) -> Path:
        """
        Create an M4B file from an audiobook.

        Args:
            audiobook: Audiobook object with chapters and metadata
            output_path: Output path for the M4B file

        Returns:
            Path to the created M4B file
        """
        output_path = Path(output_path).with_suffix(".m4b")
        output_path.parent.mkdir(parents=True, exist_ok=True)

        logger.header("Creating M4B Audiobook")
        logger.info(f"Title: {audiobook.metadata.title}")
        logger.info(f"Author: {audiobook.metadata.author}")
        logger.info(f"Chapters: {len(audiobook.chapters)}")

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Step 1: Concatenate all audio files
            logger.step("Concatenating audio files", 1, 4)
            combined_audio = self._concatenate_audio(
                audiobook.audio_files,
                temp_path / "combined.wav",
            )

            # Step 2: Create chapters metadata file
            logger.step("Creating chapter metadata", 2, 4)
            chapters_file = self._create_chapters_file(
                audiobook.chapters,
                temp_path / "chapters.txt",
            )

            # Step 3: Create metadata file
            logger.step("Adding metadata", 3, 4)
            metadata_file = self._create_metadata_file(
                audiobook.metadata,
                temp_path / "metadata.txt",
            )

            # Step 4: Encode to M4B with chapters
            logger.step("Encoding M4B file", 4, 4)
            self._encode_m4b(
                combined_audio,
                chapters_file,
                metadata_file,
                audiobook.metadata.cover_path,
                output_path,
            )

        logger.success(f"Created audiobook: {output_path}")
        logger.info(f"Duration: {self._format_duration(audiobook.total_duration)}")

        return output_path

    def _concatenate_audio(
        self,
        audio_files: List[Path],
        output_path: Path,
    ) -> Path:
        """Concatenate multiple audio files."""
        # Create file list for ffmpeg concat
        list_file = output_path.parent / "files.txt"
        with open(list_file, "w") as f:
            for audio_file in audio_files:
                # Escape single quotes in path
                escaped_path = str(audio_file).replace("'", "'\\''")
                f.write(f"file '{escaped_path}'\n")

        # Add silence between chapters
        pause_duration = config.get("chapters", "pause_between", default=1.5)

        cmd = [
            "ffmpeg",
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(list_file),
            "-af", f"apad=pad_dur={pause_duration}",
            "-c:a", "pcm_s16le",
            str(output_path),
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"FFmpeg concat error: {result.stderr}")
            raise RuntimeError("Failed to concatenate audio files")

        return output_path

    def _create_chapters_file(
        self,
        chapters: List[Chapter],
        output_path: Path,
    ) -> Path:
        """Create FFmpeg chapters metadata file."""
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(";FFMETADATA1\n")

            for chapter in chapters:
                # FFmpeg uses milliseconds for chapter times
                start_ms = int(chapter.start_time * 1000)
                end_ms = int(chapter.end_time * 1000)

                f.write("\n[CHAPTER]\n")
                f.write("TIMEBASE=1/1000\n")
                f.write(f"START={start_ms}\n")
                f.write(f"END={end_ms}\n")
                f.write(f"title={chapter.title}\n")

        return output_path

    def _create_metadata_file(
        self,
        metadata: AudiobookMetadata,
        output_path: Path,
    ) -> Path:
        """Create FFmpeg metadata file."""
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(";FFMETADATA1\n")
            f.write(f"title={metadata.title}\n")
            f.write(f"artist={metadata.author}\n")
            f.write(f"album={metadata.title}\n")
            f.write(f"composer={metadata.narrator}\n")
            f.write(f"genre={metadata.genre}\n")

            if metadata.year:
                f.write(f"date={metadata.year}\n")

            if metadata.description:
                # Escape newlines in description
                desc = metadata.description.replace("\n", "\\n")
                f.write(f"comment={desc}\n")

            if metadata.copyright:
                f.write(f"copyright={metadata.copyright}\n")

        return output_path

    def _encode_m4b(
        self,
        audio_file: Path,
        chapters_file: Path,
        metadata_file: Path,
        cover_path: Optional[Path],
        output_path: Path,
    ) -> None:
        """Encode the final M4B file."""
        cmd = [
            "ffmpeg",
            "-y",
            "-i", str(audio_file),
            "-i", str(metadata_file),
            "-i", str(chapters_file),
        ]

        # Add cover art if available
        if cover_path and cover_path.exists():
            cmd.extend(["-i", str(cover_path)])
            cmd.extend([
                "-map", "0:a",
                "-map", "3:v",
                "-c:v", "copy",
                "-disposition:v:0", "attached_pic",
            ])
        else:
            cmd.extend(["-map", "0:a"])

        # Add metadata mapping
        cmd.extend([
            "-map_metadata", "1",
            "-map_chapters", "2",
        ])

        # Audio encoding settings
        cmd.extend([
            "-c:a", "aac",
            "-b:a", self.bitrate,
            "-ac", str(self.channels),
            "-ar", str(self.sample_rate),
            "-movflags", "+faststart",
            str(output_path),
        ])

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"FFmpeg encode error: {result.stderr}")
            raise RuntimeError("Failed to encode M4B file")

    def _format_duration(self, seconds: float) -> str:
        """Format duration in hours:minutes:seconds."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)

        if hours > 0:
            return f"{hours}h {minutes}m {secs}s"
        return f"{minutes}m {secs}s"


def get_audio_duration(audio_path: Path) -> float:
    """Get the duration of an audio file in seconds."""
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-show_entries", "format=duration",
        "-of", "json",
        str(audio_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Failed to get duration: {result.stderr}")

    data = json.loads(result.stdout)
    return float(data["format"]["duration"])


def create_audiobook_from_chapters(
    chapter_audio_files: List[Path],
    chapter_titles: List[str],
    metadata: AudiobookMetadata,
    output_path: Path,
) -> Path:
    """
    Create an M4B audiobook from chapter audio files.

    Args:
        chapter_audio_files: List of audio files, one per chapter
        chapter_titles: List of chapter titles
        metadata: Audiobook metadata
        output_path: Output path for M4B file

    Returns:
        Path to created M4B file
    """
    if len(chapter_audio_files) != len(chapter_titles):
        raise ValueError("Number of audio files must match number of titles")

    audiobook = Audiobook(metadata=metadata)

    for audio_file, title in zip(chapter_audio_files, chapter_titles):
        duration = get_audio_duration(audio_file)
        audiobook.add_chapter(title, audio_file, duration)

    creator = M4BCreator()
    return creator.create_m4b(audiobook, output_path)


if __name__ == "__main__":
    # Example usage
    print("This module is meant to be imported. See main.py for usage.")
