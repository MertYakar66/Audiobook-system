"""
PDF Text Extraction Module

Extracts text from PDF files with intelligent formatting preservation.
Handles multi-column layouts, headers/footers, and encoding issues.
"""

import re
from pathlib import Path
from typing import List, Optional, Tuple

import fitz  # PyMuPDF
from rich.progress import track

from scripts.utils.config import config
from scripts.utils import logger


class PDFExtractor:
    """Extract and process text from PDF files."""

    def __init__(self, pdf_path: Path):
        self.pdf_path = Path(pdf_path)
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        self.doc = fitz.open(self.pdf_path)
        self.total_pages = len(self.doc)

    def extract_all(self, skip_pages: Optional[List[int]] = None) -> str:
        """
        Extract all text from the PDF.

        Args:
            skip_pages: List of page numbers to skip (0-indexed)

        Returns:
            Extracted text as a single string
        """
        skip_pages = skip_pages or []
        text_parts = []

        logger.info(f"Extracting text from {self.total_pages} pages...")

        for page_num in track(range(self.total_pages), description="Extracting"):
            if page_num in skip_pages:
                continue

            page = self.doc[page_num]
            text = page.get_text("text")

            # Clean up the extracted text
            text = self._clean_page_text(text, page_num)

            if text.strip():
                text_parts.append(text)

        return "\n\n".join(text_parts)

    def extract_with_layout(self) -> str:
        """
        Extract text preserving layout information.
        Better for complex documents with multiple columns.
        """
        text_parts = []

        for page_num in track(range(self.total_pages), description="Extracting"):
            page = self.doc[page_num]
            # Use dict extraction for better structure
            blocks = page.get_text("dict")["blocks"]

            page_text = []
            for block in blocks:
                if block["type"] == 0:  # Text block
                    for line in block["lines"]:
                        line_text = " ".join(
                            span["text"] for span in line["spans"]
                        )
                        page_text.append(line_text)

            text = "\n".join(page_text)
            text = self._clean_page_text(text, page_num)

            if text.strip():
                text_parts.append(text)

        return "\n\n".join(text_parts)

    def _clean_page_text(self, text: str, page_num: int) -> str:
        """Clean extracted text from a single page."""
        # Fix common encoding issues
        text = self._fix_encoding(text)

        # Remove form feeds and page breaks
        text = text.replace("\f", "\n")
        text = text.replace("\x0c", "\n")

        # Remove excessive whitespace
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)

        # Remove standalone page numbers (common in PDFs)
        text = re.sub(r"^\s*\d+\s*$", "", text, flags=re.MULTILINE)

        # Remove common headers/footers patterns
        # These are configurable in settings.yaml
        text = self._remove_headers_footers(text)

        return text.strip()

    def _fix_encoding(self, text: str) -> str:
        """Fix common encoding issues in PDF text."""
        # Common ligature replacements
        replacements = {
            "ﬁ": "fi",
            "ﬂ": "fl",
            "ﬀ": "ff",
            "ﬃ": "ffi",
            "ﬄ": "ffl",
            "\u2018": "'",  # Left single quote
            "\u2019": "'",  # Right single quote
            "\u201c": '"',  # Left double quote
            "\u201d": '"',  # Right double quote
            "\u2013": "-",  # En dash
            "\u2014": "-",  # Em dash
            "\u2026": "...",  # Ellipsis
            "\xa0": " ",  # Non-breaking space
        }

        for old, new in replacements.items():
            text = text.replace(old, new)

        return text

    def _remove_headers_footers(self, text: str) -> str:
        """Remove common header/footer patterns."""
        lines = text.split("\n")
        cleaned_lines = []

        for line in lines:
            stripped = line.strip()

            # Skip very short lines that look like page numbers
            if len(stripped) < 4 and stripped.isdigit():
                continue

            # Skip lines that are just the book title repeated (common header)
            # This is a heuristic - adjust based on your books
            if len(stripped) < 50 and stripped.isupper():
                # Might be a header, keep it but we could filter
                pass

            cleaned_lines.append(line)

        return "\n".join(cleaned_lines)

    def get_toc(self) -> List[Tuple[int, str, int]]:
        """
        Extract table of contents from PDF.

        Returns:
            List of (level, title, page_number) tuples
        """
        toc = self.doc.get_toc()
        return [(item[0], item[1], item[2]) for item in toc]

    def extract_page_range(self, start: int, end: int) -> str:
        """Extract text from a specific page range."""
        text_parts = []

        for page_num in range(start, min(end, self.total_pages)):
            page = self.doc[page_num]
            text = page.get_text("text")
            text = self._clean_page_text(text, page_num)

            if text.strip():
                text_parts.append(text)

        return "\n\n".join(text_parts)

    def close(self) -> None:
        """Close the PDF document."""
        self.doc.close()

    def __enter__(self) -> "PDFExtractor":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()


def extract_pdf(
    pdf_path: Path,
    output_path: Optional[Path] = None,
    skip_pages: Optional[List[int]] = None,
) -> str:
    """
    Main function to extract text from a PDF.

    Args:
        pdf_path: Path to the PDF file
        output_path: Optional path to save extracted text
        skip_pages: List of page numbers to skip

    Returns:
        Extracted text
    """
    pdf_path = Path(pdf_path)

    with PDFExtractor(pdf_path) as extractor:
        # Try to get TOC first for chapter information
        toc = extractor.get_toc()
        if toc:
            logger.info(f"Found {len(toc)} entries in table of contents")

        # Extract all text
        text = extractor.extract_all(skip_pages=skip_pages)

    logger.success(f"Extracted {len(text):,} characters from {pdf_path.name}")

    # Save to file if output path provided
    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text, encoding="utf-8")
        logger.success(f"Saved extracted text to {output_path}")

    return text


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python extract_text.py <pdf_path> [output_path]")
        sys.exit(1)

    pdf_file = Path(sys.argv[1])
    output_file = Path(sys.argv[2]) if len(sys.argv) > 2 else None

    extract_pdf(pdf_file, output_file)
