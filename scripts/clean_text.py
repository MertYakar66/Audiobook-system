"""
Text Cleaning Module

Cleans and prepares extracted text for TTS processing.
Handles common issues like hyphenation, special characters, and formatting.
"""

import re
from pathlib import Path
from typing import List, Optional

from scripts.utils.config import config
from scripts.utils import logger


class TextCleaner:
    """Clean and normalize text for TTS processing."""

    def __init__(self):
        self.config = config

    def clean(self, text: str) -> str:
        """
        Apply all cleaning operations to text.

        Args:
            text: Raw text to clean

        Returns:
            Cleaned text ready for TTS
        """
        # Apply cleaning steps in order
        text = self._fix_hyphenation(text)
        text = self._normalize_whitespace(text)
        text = self._fix_quotes(text)
        text = self._expand_abbreviations(text)
        text = self._clean_numbers(text)
        text = self._remove_artifacts(text)
        text = self._fix_punctuation(text)
        text = self._normalize_paragraphs(text)

        return text.strip()

    def _fix_hyphenation(self, text: str) -> str:
        """Fix words split across lines with hyphens."""
        # Join hyphenated words at line breaks
        text = re.sub(r"(\w+)-\s*\n\s*(\w+)", r"\1\2", text)
        return text

    def _normalize_whitespace(self, text: str) -> str:
        """Normalize various whitespace issues."""
        # Replace tabs with spaces
        text = text.replace("\t", " ")

        # Collapse multiple spaces
        text = re.sub(r" {2,}", " ", text)

        # Fix spaces before punctuation
        text = re.sub(r"\s+([,.!?;:])", r"\1", text)

        # Ensure space after punctuation
        text = re.sub(r"([,.!?;:])(\w)", r"\1 \2", text)

        return text

    def _fix_quotes(self, text: str) -> str:
        """Normalize quote characters."""
        # Smart quotes to straight quotes
        text = text.replace(""", '"')
        text = text.replace(""", '"')
        text = text.replace("'", "'")
        text = text.replace("'", "'")
        text = text.replace("«", '"')
        text = text.replace("»", '"')

        return text

    def _expand_abbreviations(self, text: str) -> str:
        """Expand common abbreviations for better TTS."""
        abbreviations = {
            r"\bMr\.": "Mister",
            r"\bMrs\.": "Missus",
            r"\bDr\.": "Doctor",
            r"\bProf\.": "Professor",
            r"\bSt\.": "Saint",
            r"\bvs\.": "versus",
            r"\betc\.": "etcetera",
            r"\be\.g\.": "for example",
            r"\bi\.e\.": "that is",
            r"\bno\.": "number",
            r"\bNo\.": "Number",
            r"\bvol\.": "volume",
            r"\bVol\.": "Volume",
            r"\bpp\.": "pages",
            r"\bp\.": "page",
        }

        for pattern, replacement in abbreviations.items():
            text = re.sub(pattern, replacement, text)

        return text

    def _clean_numbers(self, text: str) -> str:
        """Clean up number formatting for TTS."""
        # Remove commas from large numbers (TTS handles them better)
        text = re.sub(r"(\d),(\d{3})", r"\1\2", text)

        # Convert some number formats
        # $1.99 -> one dollar ninety-nine cents (leave as-is, TTS handles)

        return text

    def _remove_artifacts(self, text: str) -> str:
        """Remove PDF artifacts and unwanted content."""
        # Remove page numbers that slipped through
        text = re.sub(r"^\s*-?\s*\d+\s*-?\s*$", "", text, flags=re.MULTILINE)

        # Remove URLs (they sound terrible when read)
        text = re.sub(r"https?://\S+", "", text)

        # Remove email addresses
        text = re.sub(r"\S+@\S+\.\S+", "", text)

        # Remove footnote markers
        text = re.sub(r"\[\d+\]", "", text)
        text = re.sub(r"\*{1,3}", "", text)

        # Remove ISBN numbers
        text = re.sub(r"ISBN[:\s]*[\d-]+", "", text, flags=re.IGNORECASE)

        return text

    def _fix_punctuation(self, text: str) -> str:
        """Fix punctuation issues."""
        # Fix multiple punctuation marks
        text = re.sub(r"\.{2,}", "...", text)
        text = re.sub(r"\!{2,}", "!", text)
        text = re.sub(r"\?{2,}", "?", text)

        # Fix spacing around ellipsis
        text = re.sub(r"\s*\.\.\.\s*", "... ", text)

        # Remove orphaned punctuation
        text = re.sub(r"^\s*[,.;:]\s*", "", text, flags=re.MULTILINE)

        return text

    def _normalize_paragraphs(self, text: str) -> str:
        """Normalize paragraph breaks."""
        # Convert multiple newlines to double newline
        text = re.sub(r"\n{3,}", "\n\n", text)

        # Remove trailing whitespace from lines
        text = re.sub(r"[ \t]+$", "", text, flags=re.MULTILINE)

        # Remove leading whitespace from lines (except indentation for dialogue)
        text = re.sub(r"^[ \t]+", "", text, flags=re.MULTILINE)

        return text


class ChapterDetector:
    """Detect and split text into chapters."""

    def __init__(self):
        self.config = config
        self.patterns = self._compile_patterns()

    def _compile_patterns(self) -> List[re.Pattern]:
        """Compile chapter detection patterns from config."""
        pattern_strings = config.get(
            "chapters",
            "patterns",
            default=[
                r"^Chapter\s+\d+",
                r"^CHAPTER\s+\d+",
                r"^Part\s+\d+",
            ],
        )

        return [
            re.compile(pattern, re.MULTILINE | re.IGNORECASE)
            for pattern in pattern_strings
        ]

    def detect_chapters(self, text: str) -> List[dict]:
        """
        Detect chapters in text.

        Returns:
            List of dicts with 'title', 'start', 'end' keys
        """
        chapters = []
        min_length = config.get("chapters", "min_length", default=500)

        # Find all chapter markers
        markers = []
        for pattern in self.patterns:
            for match in pattern.finditer(text):
                markers.append({
                    "title": match.group().strip(),
                    "start": match.start(),
                })

        # Sort by position
        markers.sort(key=lambda x: x["start"])

        # Remove duplicates (markers at same position)
        seen_positions = set()
        unique_markers = []
        for marker in markers:
            if marker["start"] not in seen_positions:
                seen_positions.add(marker["start"])
                unique_markers.append(marker)
        markers = unique_markers

        # Create chapters with end positions
        for i, marker in enumerate(markers):
            end = markers[i + 1]["start"] if i + 1 < len(markers) else len(text)

            # Only include if chapter is long enough
            if end - marker["start"] >= min_length:
                chapters.append({
                    "title": marker["title"],
                    "start": marker["start"],
                    "end": end,
                    "text": text[marker["start"]:end].strip(),
                })

        # If no chapters detected, treat entire text as one chapter
        if not chapters:
            chapters = [{
                "title": "Full Text",
                "start": 0,
                "end": len(text),
                "text": text.strip(),
            }]

        return chapters

    def split_into_chapters(self, text: str) -> List[dict]:
        """
        Split text into chapters with metadata.

        Returns:
            List of chapter dicts with 'number', 'title', 'text' keys
        """
        chapters = self.detect_chapters(text)

        result = []
        for i, chapter in enumerate(chapters, 1):
            result.append({
                "number": i,
                "title": chapter["title"],
                "text": chapter["text"],
            })

        logger.info(f"Detected {len(result)} chapters")
        return result


def clean_text(
    text: str,
    output_path: Optional[Path] = None,
    detect_chapters: bool = False,
) -> str:
    """
    Main function to clean text for TTS.

    Args:
        text: Raw text to clean
        output_path: Optional path to save cleaned text
        detect_chapters: Whether to detect and mark chapters

    Returns:
        Cleaned text
    """
    cleaner = TextCleaner()
    cleaned = cleaner.clean(text)

    logger.success(f"Cleaned text: {len(text):,} -> {len(cleaned):,} characters")

    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(cleaned, encoding="utf-8")
        logger.success(f"Saved cleaned text to {output_path}")

    return cleaned


def clean_file(input_path: Path, output_path: Optional[Path] = None) -> str:
    """Clean text from a file."""
    input_path = Path(input_path)
    text = input_path.read_text(encoding="utf-8")
    return clean_text(text, output_path)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python clean_text.py <input_file> [output_file]")
        sys.exit(1)

    input_file = Path(sys.argv[1])
    output_file = Path(sys.argv[2]) if len(sys.argv) > 2 else None

    clean_file(input_file, output_file)
