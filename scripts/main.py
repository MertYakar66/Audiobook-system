#!/usr/bin/env python3
"""
Audiobook Generation System - Main CLI

Professional-grade pipeline for converting PDF/text files to M4B audiobooks.
Uses Kokoro-82M TTS for high-quality, natural-sounding narration.

Features:
- PDF text extraction with intelligent cleaning
- Automatic chapter detection
- Multiple voice options (American/British, Male/Female)
- Embedded chapter markers for easy navigation
- Cover art and metadata support
- Audiobookshelf integration for playback
"""

import shutil
import sys
import tempfile
from pathlib import Path
from typing import Optional

import click

from scripts.clean_text import ChapterDetector, TextCleaner
from scripts.create_audiobook import (
    Audiobook,
    AudiobookMetadata,
    M4BCreator,
    get_audio_duration,
)
from scripts.extract_text import PDFExtractor
from scripts.generate_audio import TTSGenerator
from scripts.metadata import CoverArtHandler, MetadataExtractor, get_cover
from scripts.readalong.book_processor import BookProcessor
from scripts.utils import logger
from scripts.utils.config import config


@click.group()
@click.version_option(version="3.0.0")
def cli():
    """
    Audiobook Generation System

    Convert PDF or text files to M4B audiobooks with chapters,
    metadata, and cover art.
    """
    pass


@cli.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.option(
    "-o", "--output",
    type=click.Path(),
    help="Output M4B file path (default: output/<title>.m4b)",
)
@click.option(
    "-v", "--voice",
    default=None,
    help=f"Voice to use (default: {config.voice})",
)
@click.option(
    "-t", "--title",
    default=None,
    help="Book title (default: extracted from file)",
)
@click.option(
    "-a", "--author",
    default=None,
    help="Author name (default: extracted from file)",
)
@click.option(
    "-c", "--cover",
    type=click.Path(exists=True),
    help="Cover image path",
)
@click.option(
    "--narrator",
    default=None,
    help="Narrator name for metadata",
)
@click.option(
    "--skip-pages",
    default="",
    help="Comma-separated page numbers to skip (0-indexed)",
)
@click.option(
    "--no-chapters",
    is_flag=True,
    help="Don't detect chapters, treat as single chapter",
)
@click.option(
    "--keep-intermediate",
    is_flag=True,
    help="Keep intermediate audio files",
)
def convert(
    input_file: str,
    output: Optional[str],
    voice: Optional[str],
    title: Optional[str],
    author: Optional[str],
    cover: Optional[str],
    narrator: Optional[str],
    skip_pages: str,
    no_chapters: bool,
    keep_intermediate: bool,
):
    """
    Convert a PDF or text file to an M4B audiobook.

    This is the main command that runs the complete pipeline:
    1. Extract text from PDF (if PDF)
    2. Clean and normalize text
    3. Detect chapters
    4. Generate audio for each chapter
    5. Create M4B with chapters and metadata
    """
    input_path = Path(input_file)
    logger.header(f"Converting: {input_path.name}")

    # Parse skip pages
    pages_to_skip = []
    if skip_pages:
        pages_to_skip = [int(p.strip()) for p in skip_pages.split(",")]

    # Create temporary directory for processing
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Step 1: Extract text if PDF
        logger.step("Extracting text", 1, 6)
        if input_path.suffix.lower() == ".pdf":
            with PDFExtractor(input_path) as extractor:
                text = extractor.extract_all(skip_pages=pages_to_skip)
        else:
            text = input_path.read_text(encoding="utf-8")

        logger.info(f"Extracted {len(text):,} characters")

        # Step 2: Clean text
        logger.step("Cleaning text", 2, 6)
        cleaner = TextCleaner()
        text = cleaner.clean(text)
        logger.info(f"Cleaned text: {len(text):,} characters")

        # Step 3: Extract metadata
        logger.step("Processing metadata", 3, 6)
        meta_extractor = MetadataExtractor()

        if input_path.suffix.lower() == ".pdf":
            extracted_meta = meta_extractor.extract_from_pdf(input_path)
        else:
            extracted_meta = meta_extractor.extract_from_text(text, str(input_path))

        # Use provided values or fall back to extracted
        book_title = title or extracted_meta.get("title", input_path.stem)
        book_author = author or extracted_meta.get("author", "Unknown Author")

        logger.info(f"Title: {book_title}")
        logger.info(f"Author: {book_author}")

        # Get cover art
        cover_path = None
        if cover:
            cover_path = Path(cover)
        elif input_path.suffix.lower() == ".pdf":
            cover_path = get_cover(
                input_path,
                temp_path / "cover.jpg",
                book_title,
                book_author,
            )
        else:
            # Create placeholder
            handler = CoverArtHandler()
            cover_path = handler.create_placeholder_cover(
                book_title,
                book_author,
                temp_path / "cover.jpg",
            )

        # Step 4: Detect chapters
        logger.step("Detecting chapters", 4, 6)
        if no_chapters:
            chapters = [{"number": 1, "title": book_title, "text": text}]
        else:
            detector = ChapterDetector()
            chapters = detector.split_into_chapters(text)

        logger.info(f"Found {len(chapters)} chapters")

        # Step 5: Generate audio for each chapter
        logger.step("Generating audio", 5, 6)
        tts = TTSGenerator(voice=voice or config.voice)

        chapter_audio_files = []
        chapter_titles = []
        audio_dir = temp_path / "audio"
        audio_dir.mkdir()

        for i, chapter in enumerate(chapters, 1):
            logger.info(f"Chapter {i}/{len(chapters)}: {chapter['title']}")

            audio_file = audio_dir / f"chapter_{i:03d}.wav"
            generated_path, _ = tts.generate_audio(chapter["text"], audio_file)

            chapter_audio_files.append(generated_path)
            chapter_titles.append(chapter["title"])

        # Step 6: Create M4B
        logger.step("Creating M4B audiobook", 6, 6)

        # Determine output path
        if output:
            output_path = Path(output)
        else:
            output_path = config.get_path("output") / f"{book_title}.m4b"

        # Create audiobook object
        metadata = AudiobookMetadata(
            title=book_title,
            author=book_author,
            narrator=narrator or config.get("metadata", "narrator", default="AI Narrator"),
            cover_path=cover_path,
        )

        audiobook = Audiobook(metadata=metadata)

        for audio_file, chapter_title in zip(chapter_audio_files, chapter_titles):
            duration = get_audio_duration(audio_file)
            audiobook.add_chapter(chapter_title, audio_file, duration)

        # Create the M4B file
        creator = M4BCreator()
        final_path = creator.create_m4b(audiobook, output_path)

        # Copy intermediate files if requested
        if keep_intermediate:
            intermediate_dir = output_path.parent / f"{output_path.stem}_chapters"
            intermediate_dir.mkdir(exist_ok=True)
            for audio_file in chapter_audio_files:
                shutil.copy2(audio_file, intermediate_dir)
            logger.info(f"Saved chapter audio files to: {intermediate_dir}")

    logger.header("Conversion Complete!")
    logger.success(f"Audiobook saved to: {final_path}")

    # Show summary
    duration_str = f"{audiobook.total_duration / 3600:.1f} hours"
    logger.info(f"Duration: {duration_str}")
    logger.info(f"Chapters: {len(chapters)}")


@cli.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.option("-o", "--output", type=click.Path(), help="Output text file path")
def extract(input_file: str, output: Optional[str]):
    """
    Extract text from a PDF file.

    Useful for reviewing/editing text before audiobook conversion.
    """
    input_path = Path(input_file)

    if input_path.suffix.lower() != ".pdf":
        logger.error("Input must be a PDF file")
        sys.exit(1)

    logger.header(f"Extracting: {input_path.name}")

    with PDFExtractor(input_path) as extractor:
        text = extractor.extract_all()

    if output:
        output_path = Path(output)
    else:
        output_path = config.get_path("input") / f"{input_path.stem}.txt"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8")

    logger.success(f"Extracted {len(text):,} characters to: {output_path}")


@cli.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.option("-o", "--output", type=click.Path(), help="Output text file path")
def clean(input_file: str, output: Optional[str]):
    """
    Clean text for TTS processing.

    Removes artifacts, fixes encoding, normalizes whitespace.
    """
    input_path = Path(input_file)

    logger.header(f"Cleaning: {input_path.name}")

    text = input_path.read_text(encoding="utf-8")
    cleaner = TextCleaner()
    cleaned = cleaner.clean(text)

    if output:
        output_path = Path(output)
    else:
        output_path = input_path.with_stem(f"{input_path.stem}_cleaned")

    output_path.write_text(cleaned, encoding="utf-8")

    logger.success(f"Cleaned text saved to: {output_path}")
    logger.info(f"Original: {len(text):,} chars -> Cleaned: {len(cleaned):,} chars")


@cli.command()
@click.argument("input_file", type=click.Path(exists=True))
def chapters(input_file: str):
    """
    Detect and list chapters in a text file.

    Helps verify chapter detection before full conversion.
    """
    input_path = Path(input_file)

    logger.header(f"Detecting chapters: {input_path.name}")

    text = input_path.read_text(encoding="utf-8")
    detector = ChapterDetector()
    found_chapters = detector.split_into_chapters(text)

    logger.info(f"Found {len(found_chapters)} chapters:\n")

    for chapter in found_chapters:
        char_count = len(chapter["text"])
        word_count = len(chapter["text"].split())
        logger.console.print(
            f"  {chapter['number']:3}. {chapter['title'][:50]:<50} "
            f"({word_count:,} words, {char_count:,} chars)"
        )


@cli.command()
@click.option("-v", "--voice", default=None, help="Voice to test")
@click.option("-t", "--text", default="Hello! This is a test of the audiobook generation system.", help="Text to speak")
@click.option("-o", "--output", type=click.Path(), default="test_output.wav", help="Output file")
def test_voice(voice: Optional[str], text: str, output: str):
    """
    Test TTS voice generation.

    Quick way to preview a voice before full conversion.
    """
    voice = voice or config.voice
    logger.header(f"Testing voice: {voice}")

    tts = TTSGenerator(voice=voice)
    output_path = Path(output)

    generated_path, duration = tts.generate_audio(text, output_path)

    logger.success(f"Test audio saved to: {generated_path}")
    logger.info(f"Duration: {duration:.1f} seconds")
    logger.info("Play this file to hear the voice sample.")


@cli.command()
def list_voices():
    """
    List available Kokoro voices.
    """
    logger.header("Available Kokoro Voices")

    voices = {
        "Female": [
            ("af_sky", "Calm, neutral (recommended)"),
            ("af_bella", "Warm, expressive"),
            ("af_nicole", "Professional"),
            ("af_sarah", "Friendly"),
        ],
        "Male": [
            ("am_michael", "Calm, neutral (recommended)"),
            ("am_adam", "Deep, authoritative"),
            ("am_fenrir", "Casual"),
        ],
    }

    for category, voice_list in voices.items():
        logger.console.print(f"\n[bold]{category}[/bold]")
        for voice_id, description in voice_list:
            marker = "*" if voice_id in ("af_sky", "am_michael") else " "
            logger.console.print(f"  {marker} {voice_id:<15} - {description}")

    logger.console.print("\n* Recommended for audiobooks")
    logger.console.print(f"\nCurrent default: {config.voice}")


@cli.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.option(
    "-o", "--output",
    type=click.Path(),
    help="Output directory (default: output/readalong/<book-id>)",
)
@click.option(
    "-v", "--voice",
    default=None,
    help=f"Voice to use (default: {config.voice})",
)
@click.option(
    "-t", "--title",
    default=None,
    help="Book title (default: extracted from file)",
)
@click.option(
    "-a", "--author",
    default=None,
    help="Author name (default: extracted from file)",
)
def readalong(
    input_file: str,
    output: Optional[str],
    voice: Optional[str],
    title: Optional[str],
    author: Optional[str],
):
    """
    Create a Read-Along book with synchronized audio and text.

    This produces a web-ready package with:
    - Sentence-level audio files
    - Timing maps linking audio to text
    - Text data for the web reader
    - Cover image

    Open the web/index.html file and load the output folder
    to experience synchronized reading.
    """
    input_path = Path(input_file)

    processor = BookProcessor(voice=voice)
    result = processor.process_book(
        input_path,
        output_dir=Path(output) if output else None,
        title=title,
        author=author,
    )

    logger.console.print("\n[bold]To use Read-Along:[/bold]")
    logger.console.print(f"  1. Open web/index.html in your browser")
    logger.console.print(f"  2. Click 'Select Book Folder'")
    logger.console.print(f"  3. Select: {result.output_dir}")
    logger.console.print(f"\n  Or serve with: python -m http.server 8000 --directory web")


@cli.command()
def info():
    """
    Show system information and configuration.
    """
    logger.header("Audiobook Generation System")

    logger.console.print("[bold]Paths:[/bold]")
    logger.console.print(f"  Project root: {config.project_root}")
    logger.console.print(f"  Input:        {config.get_path('input')}")
    logger.console.print(f"  Output:       {config.get_path('output')}")

    logger.console.print("\n[bold]Voice Settings:[/bold]")
    logger.console.print(f"  Default voice: {config.voice}")
    logger.console.print(f"  Speed:         {config.voice_speed}")
    logger.console.print(f"  Language:      {config.get('voice', 'lang')}")

    logger.console.print("\n[bold]Audio Settings:[/bold]")
    logger.console.print(f"  Sample rate:   {config.sample_rate} Hz")
    logger.console.print(f"  M4B bitrate:   {config.m4b_bitrate}")

    logger.console.print("\n[bold]Dependencies:[/bold]")

    # Check for required CLI tools
    tools = {
        "ffmpeg": shutil.which("ffmpeg"),
        "ffprobe": shutil.which("ffprobe"),
    }

    for tool, path in tools.items():
        status = "[green]OK[/green]" if path else "[red]NOT FOUND[/red]"
        logger.console.print(f"  {tool:<12} {status}")

    # Check for Kokoro TTS
    try:
        import kokoro
        logger.console.print(f"  {'kokoro':<12} [green]OK[/green]")
    except ImportError:
        logger.console.print(f"  {'kokoro':<12} [red]NOT FOUND[/red]")


def main():
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()
