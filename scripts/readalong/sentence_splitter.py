"""
Sentence Splitter Module

Splits text into sentences for sentence-level TTS generation.
Handles complex punctuation, abbreviations, and dialogue.
"""

import re
from dataclasses import dataclass
from typing import List, Generator
import unicodedata


@dataclass
class Sentence:
    """Represents a single sentence with position information."""

    id: str  # Unique identifier (e.g., "ch01_s0042")
    text: str  # The sentence text
    start_char: int  # Character offset in original text
    end_char: int  # End character offset
    paragraph_id: int  # Which paragraph this belongs to

    def __post_init__(self):
        # Clean and normalize text
        self.text = self.text.strip()
        self.text = unicodedata.normalize("NFKC", self.text)


class SentenceSplitter:
    """
    Intelligent sentence splitter for TTS processing.

    Handles:
    - Standard punctuation (. ! ?)
    - Abbreviations (Mr., Dr., etc.)
    - Dialogue and quotations
    - Decimal numbers and URLs
    - Ellipsis (...)
    """

    # Common abbreviations that shouldn't end sentences
    ABBREVIATIONS = {
        "mr", "mrs", "ms", "dr", "prof", "sr", "jr", "st", "ltd", "inc",
        "vs", "etc", "al", "eg", "ie", "cf", "no", "vol", "pp", "ed",
        "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "oct", "nov", "dec",
        "fig", "figs", "eq", "eqs", "sec", "ch", "pt", "para",
    }

    def __init__(self, chapter_id: str = "ch01"):
        """
        Initialize the sentence splitter.

        Args:
            chapter_id: Identifier for the chapter (used in sentence IDs)
        """
        self.chapter_id = chapter_id
        self._sentence_counter = 0

    def split(self, text: str) -> List[Sentence]:
        """
        Split text into sentences.

        Args:
            text: Full text to split

        Returns:
            List of Sentence objects
        """
        sentences = []
        paragraphs = self._split_paragraphs(text)

        for para_id, paragraph in enumerate(paragraphs):
            if not paragraph.strip():
                continue

            para_sentences = self._split_paragraph(paragraph, para_id)

            # Calculate character offsets relative to full text
            para_start = text.find(paragraph)
            for sentence in para_sentences:
                sentence.start_char += para_start
                sentence.end_char += para_start

            sentences.extend(para_sentences)

        return sentences

    def split_iter(self, text: str) -> Generator[Sentence, None, None]:
        """
        Generator version of split for memory efficiency.

        Yields sentences one at a time.
        """
        for sentence in self.split(text):
            yield sentence

    def _split_paragraphs(self, text: str) -> List[str]:
        """Split text into paragraphs."""
        # Split on double newlines or multiple newlines
        paragraphs = re.split(r'\n\s*\n', text)
        return [p.strip() for p in paragraphs if p.strip()]

    def _split_paragraph(self, paragraph: str, para_id: int) -> List[Sentence]:
        """Split a single paragraph into sentences."""
        sentences = []

        # Normalize whitespace within paragraph
        paragraph = re.sub(r'\s+', ' ', paragraph).strip()

        if not paragraph:
            return sentences

        # Pre-process: protect abbreviations and special cases
        protected_text = self._protect_special_cases(paragraph)

        # Split on sentence-ending punctuation
        # Look for . ! ? followed by space and capital letter (or quote)
        pattern = r'([.!?]+)(?=\s+(?:[A-Z"\'\u201c\u201d]|$))'

        parts = re.split(pattern, protected_text)

        # Rejoin parts into sentences
        current_pos = 0
        i = 0
        while i < len(parts):
            text_part = parts[i]

            # Check if next part is punctuation
            if i + 1 < len(parts) and re.match(r'^[.!?]+$', parts[i + 1]):
                text_part += parts[i + 1]
                i += 2
            else:
                i += 1

            # Restore protected text
            text_part = self._restore_special_cases(text_part)
            text_part = text_part.strip()

            if text_part:
                sentence_id = f"{self.chapter_id}_s{self._sentence_counter:04d}"
                self._sentence_counter += 1

                # Find actual position in original paragraph
                start = paragraph.find(text_part, current_pos)
                if start == -1:
                    start = current_pos
                end = start + len(text_part)
                current_pos = end

                sentences.append(Sentence(
                    id=sentence_id,
                    text=text_part,
                    start_char=start,
                    end_char=end,
                    paragraph_id=para_id,
                ))

        return sentences

    def _protect_special_cases(self, text: str) -> str:
        """Replace special cases with placeholders to prevent incorrect splits."""
        protected = text

        # Protect abbreviations
        for abbr in self.ABBREVIATIONS:
            # Match abbreviation with period (case insensitive)
            pattern = rf'\b({abbr})\.'
            protected = re.sub(pattern, r'\1<PERIOD>', protected, flags=re.IGNORECASE)

        # Protect initials (single letters followed by period)
        protected = re.sub(r'\b([A-Z])\.\s*(?=[A-Z]\.)', r'\1<PERIOD> ', protected)

        # Protect decimal numbers
        protected = re.sub(r'(\d)\.(\d)', r'\1<DECIMAL>\2', protected)

        # Protect ellipsis
        protected = re.sub(r'\.{3,}', '<ELLIPSIS>', protected)

        # Protect time (3.30 pm)
        protected = re.sub(r'(\d{1,2})\.(\d{2})\s*(?=[ap]\.?m\.?)', r'\1<TIME>\2', protected, flags=re.IGNORECASE)

        return protected

    def _restore_special_cases(self, text: str) -> str:
        """Restore placeholders to original characters."""
        text = text.replace('<PERIOD>', '.')
        text = text.replace('<DECIMAL>', '.')
        text = text.replace('<ELLIPSIS>', '...')
        text = text.replace('<TIME>', '.')
        return text

    def reset_counter(self):
        """Reset the sentence counter (use when starting a new chapter)."""
        self._sentence_counter = 0


def split_into_sentences(
    text: str,
    chapter_id: str = "ch01"
) -> List[Sentence]:
    """
    Convenience function to split text into sentences.

    Args:
        text: Text to split
        chapter_id: Chapter identifier for sentence IDs

    Returns:
        List of Sentence objects
    """
    splitter = SentenceSplitter(chapter_id)
    return splitter.split(text)


if __name__ == "__main__":
    # Test the sentence splitter
    test_text = """
    The Intelligent Investor by Benjamin Graham is considered one of the
    most important investment books ever written. Mr. Graham was Warren
    Buffett's mentor at Columbia University.

    "Price is what you pay. Value is what you get." This famous quote
    captures the essence of value investing. Dr. Graham emphasized that
    investors should focus on a company's intrinsic value, not its
    current market price.

    The book was first published in 1949. Over 1.5 million copies have
    been sold worldwide!
    """

    sentences = split_into_sentences(test_text, "ch01")

    for s in sentences:
        print(f"[{s.id}] ({s.start_char}-{s.end_char}) P{s.paragraph_id}: {s.text[:60]}...")
